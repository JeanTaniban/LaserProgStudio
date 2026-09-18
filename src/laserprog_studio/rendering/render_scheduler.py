# -*- coding: utf-8 -*-
"""Application-wide render scheduling for the main viewport.

The old application code historically called ``plotter.render()`` directly from
many controllers.  That is safe for small scenes but becomes catastrophic when a
single UI gesture produces several hover, gizmo, scene-sync and overlay refresh
requests in the same Qt event burst.

This scheduler is intentionally conservative: it does not change how actors are
created or styled.  It only turns many immediate render requests into one
coalesced render, while still exposing ``render_now`` for the rare paths that
really need a synchronous draw.
"""
from __future__ import annotations

import time
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Callable

from laserprog_studio.application.camera_motion_diagnostics import capture_camera_state, classify_camera_motion

try:  # pragma: no cover - diagnostics must never break rendering.
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None

try:  # pragma: no cover - imported lazily in headless tests.
    from PySide6.QtCore import QObject, QTimer
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover
    QObject = object  # type: ignore[assignment]
    QTimer = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]


@dataclass(slots=True)
class CentralRenderStats:
    requests: int = 0
    immediate_requests: int = 0
    performed: int = 0
    coalesced: int = 0
    throttled: int = 0
    skipped_reentrant: int = 0
    last_reason: str = ""
    recent_reasons: deque[str] = field(default_factory=lambda: deque(maxlen=64))


class CentralRenderScheduler(QObject):
    """Coalesce render requests for one PyVista/Qt viewport.

    ``plotter.render`` is patched to call :meth:`request` so legacy code is
    automatically routed through the same central path.  The original renderer
    remains available through :meth:`render_now` and is used internally by the
    timer flush.
    """

    def __init__(
        self,
        owner: Any,
        plotter: Any,
        *,
        min_interval_ms: float = 33.0,
        coalesce_delay_ms: int = 0,
        interactive_min_interval_ms: float = 16.0,
    ) -> None:
        try:
            super().__init__(owner if _is_qobject(owner) else None)  # type: ignore[misc]
        except Exception:  # pragma: no cover - QObject may be absent in tests.
            try:
                super().__init__()  # type: ignore[misc]
            except Exception:
                pass
        self.owner = owner
        self.plotter = plotter
        self.min_interval_ms = max(0.0, float(min_interval_ms))
        self.interactive_min_interval_ms = max(0.0, float(interactive_min_interval_ms))
        self.coalesce_delay_ms = max(0, int(coalesce_delay_ms))
        self.stats = CentralRenderStats()
        self._last_render_at_ms = 0.0
        self._pending = False
        self._pending_reasons: Counter[str] = Counter()
        self._in_render = False
        self._patched = False
        self._original_render: Callable[..., Any] | None = None
        self._last_camera_state = None
        self._timer = None
        if QTimer is not None:
            try:
                self._timer = QTimer(self)  # type: ignore[operator]
                self._timer.setSingleShot(True)
                self._timer.timeout.connect(self.flush)  # type: ignore[union-attr]
            except Exception:
                self._timer = None

    # ------------------------------------------------------------------
    # Installation / patching
    # ------------------------------------------------------------------
    def install_plotter_patch(self) -> None:
        if self._patched or self.plotter is None:
            return
        original = getattr(self.plotter, "render", None)
        if not callable(original):
            return
        self._original_render = original
        scheduler = self

        def _scheduled_render(*_args: Any, **_kwargs: Any) -> bool:
            reason = str(_kwargs.pop("reason", "plotter.render")) if _kwargs else "plotter.render"
            immediate = bool(_kwargs.pop("immediate", False)) if _kwargs else False
            force = bool(_kwargs.pop("force", False)) if _kwargs else False
            return scheduler.request(reason=reason, immediate=immediate, force=force)

        try:
            setattr(self.plotter, "_lps_original_render", original)
            setattr(self.plotter, "_lps_render_scheduler", self)
            setattr(self.plotter, "render", _scheduled_render)
            self._patched = True
            _audit_increment("render.scheduler.patch_installed")
        except Exception:
            self._patched = False

    def uninstall_plotter_patch(self) -> None:
        if not self._patched:
            return
        try:
            if self._original_render is not None:
                setattr(self.plotter, "render", self._original_render)
        except Exception:
            pass
        self._patched = False

    # ------------------------------------------------------------------
    # Request API
    # ------------------------------------------------------------------
    def request(self, *, reason: str = "unknown", immediate: bool = False, force: bool = False) -> bool:
        """Request a viewport render.

        Returns ``True`` when a real render has already been performed and
        ``False`` when the render was queued/coalesced.
        """
        reason = str(reason or "unknown")
        self.stats.requests += 1
        self.stats.last_reason = reason
        self.stats.recent_reasons.append(reason)
        self._pending_reasons[reason] += 1
        _audit_increment("render.central.request")
        _audit_increment(f"render.central.reason.{_safe_counter_name(reason)}")

        if immediate or force:
            self.stats.immediate_requests += 1
            _audit_increment("render.central.immediate_request")
            return self.render_now(reason=reason, force=True)

        # In pure headless tests without a Qt event loop, a queued QTimer would
        # never fire.  Fall back to a synchronous render so behavior stays
        # deterministic outside the real UI runtime.
        if not _qt_event_loop_available():
            return self.render_now(reason=f"{reason}.headless", force=True)

        now_ms = _now_ms()
        elapsed = now_ms - self._last_render_at_ms
        effective_min_interval = self._effective_min_interval_ms(reason)
        delay_ms = self.coalesce_delay_ms
        if effective_min_interval > 0 and elapsed < effective_min_interval:
            self.stats.throttled += 1
            delay_ms = max(delay_ms, int(round(effective_min_interval - elapsed)))
            _audit_increment("render.central.throttled")
            if effective_min_interval < self.min_interval_ms:
                _audit_increment("render.central.interactive_fast_path")
        else:
            _audit_increment("render.central.queued")
        self._queue(delay_ms=delay_ms)
        return False

    def _queue(self, *, delay_ms: int) -> None:
        self._pending = True
        timer = self._timer
        if timer is None:
            self.render_now(reason="timer_missing", force=True)
            return
        try:
            if timer.isActive():
                self.stats.coalesced += 1
                _audit_increment("render.central.coalesced")
                return
            timer.start(max(0, int(delay_ms)))
        except Exception:
            self.render_now(reason="timer_failed", force=True)


    def _effective_min_interval_ms(self, reason: str) -> float:
        """Use a faster cadence while a mouse button is driving camera/viewport interaction.

        The first centralisation pass applied the same 30 FPS budget to every
        anonymous ``plotter.render()`` call.  That is good for geometry refreshes
        but too sluggish for VTK camera drags, where the interactor updates the
        camera every raw mouse event and expects the next visible frame quickly.
        We keep coalescing, but allow a 60 FPS budget only while Qt reports a
        mouse button down.
        """

        zoom_active = False
        try:
            zoom_active = time.monotonic() < float(getattr(self.owner, "_camera_zoom_burst_until", 0.0) or 0.0)
        except Exception:
            zoom_active = False
        if _qt_mouse_buttons_down() or zoom_active:
            try:
                plan_trace_camera = bool(
                    str(getattr(self.owner, "active_tool", "")) == "plan_trace"
                    and (
                        bool(getattr(self.owner, "_creator_camera_navigation_active", False))
                        or zoom_active
                    )
                )
            except Exception:
                plan_trace_camera = False
            if zoom_active:
                _audit_increment("render.central.camera_zoom_budget")
            else:
                _audit_increment("render.central.mouse_drag_budget")
            if plan_trace_camera:
                # Plan Tracer's projected overlay now uses an affine camera
                # transform, so the CPU side no longer needs a 16 ms safety
                # budget. Allow up to ~120 Hz when the GPU/viewport can keep up.
                _audit_increment("render.central.plan_trace_camera_budget")
                return min(float(self.min_interval_ms), 8.0)
            return min(float(self.min_interval_ms), float(self.interactive_min_interval_ms))
        return float(self.min_interval_ms)

    def flush(self) -> bool:
        if not self._pending and not self._pending_reasons:
            return False
        return self.render_now(reason="flush", force=True)

    def render_now(self, *, reason: str = "immediate", force: bool = False) -> bool:
        if self._in_render:
            self.stats.skipped_reentrant += 1
            _audit_increment("render.central.reentrant_skipped")
            return False
        original = self._original_render or getattr(self.plotter, "_lps_original_render", None)
        if not callable(original):
            original = getattr(self.plotter, "render", None)
        if not callable(original):
            return False
        now_ms = _now_ms()
        effective_min_interval = self._effective_min_interval_ms(reason)
        if not force and effective_min_interval > 0 and now_ms - self._last_render_at_ms < effective_min_interval:
            self._queue(delay_ms=int(round(effective_min_interval - (now_ms - self._last_render_at_ms))))
            return False

        pending_count = sum(self._pending_reasons.values())
        top_reasons = dict(self._pending_reasons.most_common(8))
        self._pending_reasons.clear()
        self._pending = False
        self._in_render = True
        try:
            renderer = getattr(self.plotter, "renderer", None)
            camera_state_before = capture_camera_state(renderer)
            camera_mode = classify_camera_motion(self._last_camera_state, camera_state_before)
        except Exception:
            camera_state_before = None
            camera_mode = "unknown"
        start = time.perf_counter()
        try:
            original()
            return True
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            try:
                renderer = getattr(self.plotter, "renderer", None)
                camera_state_after = capture_camera_state(renderer) or camera_state_before
                if camera_state_after is not None:
                    self._last_camera_state = camera_state_after
            except Exception:
                pass
            self._last_render_at_ms = _now_ms()
            self.stats.performed += 1
            self._in_render = False
            _audit_increment("render.central.performed")
            _audit_timing("render.central.perform", elapsed_ms, details={"reason": reason, "pending": pending_count, "top_reasons": top_reasons})
            _audit_timing(
                f"render.central.perform.camera.{camera_mode}",
                elapsed_ms,
                details={"reason": reason, "pending": pending_count},
            )
            _audit_increment(f"render.central.camera_mode.{camera_mode}")
            _audit_value("render.central.camera.last_mode", camera_mode)
            _audit_value("render.central.last_ms", round(elapsed_ms, 4))
            _audit_value("render.central.pending_count", int(pending_count))


def install_central_render_scheduler(
    owner: Any,
    plotter: Any,
    *,
    min_interval_ms: float | None = None,
    coalesce_delay_ms: int = 0,
) -> CentralRenderScheduler | None:
    """Install the scheduler on ``owner.plotter`` and expose owner helpers."""
    if plotter is None:
        return None
    existing = getattr(owner, "render_scheduler", None)
    if isinstance(existing, CentralRenderScheduler):
        return existing
    if min_interval_ms is None:
        perf_mode = str(getattr(owner, "_performance_mode", "optimized") or "optimized")
        min_interval_ms = 33.0 if perf_mode == "optimized" else 16.0
    scheduler = CentralRenderScheduler(owner, plotter, min_interval_ms=float(min_interval_ms), coalesce_delay_ms=int(coalesce_delay_ms))
    scheduler.install_plotter_patch()
    try:
        owner.render_scheduler = scheduler
    except Exception:
        pass
    _install_owner_helpers(owner, scheduler)
    return scheduler


def _install_owner_helpers(owner: Any, scheduler: CentralRenderScheduler) -> None:
    def request_render(*, reason: str = "owner.request_render", immediate: bool = False, force: bool = False) -> bool:
        return scheduler.request(reason=reason, immediate=immediate, force=force)

    def render_now(*, reason: str = "owner.render_now") -> bool:
        return scheduler.render_now(reason=reason, force=True)

    def flush_render(*, reason: str = "owner.flush_render") -> bool:
        return scheduler.render_now(reason=reason, force=True)

    for name, fn in {
        "request_render": request_render,
        "render_now": render_now,
        "flush_render": flush_render,
    }.items():
        try:
            setattr(owner, name, fn)
        except Exception:
            pass


def request_render_for(owner: Any, *, reason: str = "request_render_for", immediate: bool = False, force: bool = False) -> bool:
    scheduler = getattr(owner, "render_scheduler", None)
    if isinstance(scheduler, CentralRenderScheduler):
        return scheduler.request(reason=reason, immediate=immediate, force=force)
    plotter = getattr(owner, "plotter", None)
    render = getattr(plotter, "render", None)
    if callable(render):
        try:
            render()
            return True
        except Exception:
            return False
    return False


def render_now_for(owner: Any, *, reason: str = "render_now_for") -> bool:
    scheduler = getattr(owner, "render_scheduler", None)
    if isinstance(scheduler, CentralRenderScheduler):
        return scheduler.render_now(reason=reason, force=True)
    plotter = getattr(owner, "plotter", None)
    original = getattr(plotter, "_lps_original_render", None)
    render = original if callable(original) else getattr(plotter, "render", None)
    if callable(render):
        try:
            render()
            return True
        except Exception:
            return False
    return False


def _is_qobject(value: Any) -> bool:
    try:
        return isinstance(value, QObject)  # type: ignore[arg-type]
    except Exception:
        return False


def _qt_mouse_buttons_down() -> bool:
    if QApplication is None:
        return False
    try:
        from PySide6.QtCore import Qt as _Qt
        buttons = QApplication.mouseButtons()
        return bool(buttons != _Qt.NoButton)
    except Exception:
        return False

def _qt_event_loop_available() -> bool:
    if QApplication is None:
        return False
    try:
        app = QApplication.instance()
        if app is None:
            return False
        # closingDown is False while the app can still process a queued timer.
        return not bool(app.closingDown())
    except Exception:
        return False


def _now_ms() -> float:
    return time.perf_counter() * 1000.0


def _safe_counter_name(reason: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in reason)[:90]


def _audit_increment(name: str, value: int = 1) -> None:
    if _APP_AUDIT is None:
        return
    try:
        _APP_AUDIT.increment(name, value)
    except Exception:
        pass


def _audit_value(name: str, value: Any) -> None:
    if _APP_AUDIT is None:
        return
    try:
        _APP_AUDIT.set_value(name, value)
    except Exception:
        pass


def _audit_timing(name: str, elapsed_ms: float, *, details: dict[str, Any] | None = None) -> None:
    if _APP_AUDIT is None:
        return
    try:
        _APP_AUDIT.record_timing(name, elapsed_ms, details=details)
    except Exception:
        pass

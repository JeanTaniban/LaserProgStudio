# -*- coding: utf-8 -*-
"""Structured diagnostics for the application Transform gizmo.

The Transform gizmo crosses several systems (selection, ToolContext, VTK
renderers, the central render scheduler and the screen-space picker).  A plain
exception log is not enough when the gizmo is declared correctly but is not
visible.  This module records compact JSONL snapshots of that whole chain.

The file is only enabled in global Debug Mode.  High-frequency picking misses
are also sampled so diagnostics never become the new performance problem.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any
import time

_DIAG_FILE = "transform_gizmo_debug.jsonl"


def _debug_enabled(owner: Any | None = None) -> bool:
    try:
        from laserprog_studio.services.debug_mode import should_record_diagnostics
        return bool(should_record_diagnostics(owner))
    except Exception:
        return False


def transform_gizmo_diagnostics_path() -> Path:
    path = Path.cwd() / "diagnostics"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path / _DIAG_FILE


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def _prop_count(renderer: Any) -> int | None:
    if renderer is None:
        return None
    try:
        return int(renderer.GetViewProps().GetNumberOfItems())
    except Exception:
        return None


def _renderer_snapshot(renderer: Any) -> dict[str, Any]:
    if renderer is None:
        return {"present": False}
    result: dict[str, Any] = {"present": True, "props": _prop_count(renderer)}
    for key, getter in (
        ("layer", "GetLayer"),
        ("interactive", "GetInteractive"),
        ("preserve_depth", "GetPreserveDepthBuffer"),
        ("erase", "GetErase"),
    ):
        try:
            result[key] = _safe(getattr(renderer, getter)())
        except Exception:
            pass
    try:
        result["viewport"] = [round(float(v), 5) for v in renderer.GetViewport()]
    except Exception:
        pass
    try:
        camera = renderer.GetActiveCamera()
        result["camera_present"] = camera is not None
        if camera is not None:
            result["camera_clipping"] = [round(float(v), 8) for v in camera.GetClippingRange()]
            result["camera_position"] = [round(float(v), 8) for v in camera.GetPosition()]
            result["camera_focal_point"] = [round(float(v), 8) for v in camera.GetFocalPoint()]
    except Exception:
        pass
    return result


def _snapshot_summary(snapshot: Any) -> dict[str, Any]:
    if snapshot is None:
        return {"present": False}
    try:
        positions = dict(getattr(snapshot, "positions", {}) or {})
        lines = dict(getattr(snapshot, "lines", {}) or {})
        rings = dict(getattr(snapshot, "rings", {}) or {})
        return {
            "present": True,
            "mode": str(getattr(snapshot, "mode", "") or ""),
            "center": _safe(tuple(getattr(snapshot, "center", ()) or ())),
            "length": _safe(getattr(snapshot, "length", None)),
            "axes": _safe(tuple(getattr(snapshot, "axes", ()) or ())),
            "positions": len(positions),
            "lines": len(lines),
            "rings": {str(k): len(tuple(v or ())) for k, v in rings.items()},
        }
    except Exception:
        return {"present": True, "summary_error": True}


def _backend_snapshot(owner: Any) -> dict[str, Any]:
    backend = getattr(owner, "_transform_gizmo_renderer", None)
    if backend is None:
        return {"present": False}
    result: dict[str, Any] = {
        "present": True,
        "mode": str(getattr(backend, "_mode", "") or ""),
        "groups": len(getattr(backend, "groups", {}) or {}),
        "actors": len(getattr(backend, "_all_actors", []) or []),
        "overlay_assembly": getattr(backend, "overlay_assembly", None) is not None,
        "main_assembly": getattr(backend, "main_assembly", None) is not None,
        "signature": getattr(backend, "_signature", None) is not None,
    }
    for name in ("overlay_assembly", "main_assembly"):
        assembly = getattr(backend, name, None)
        if assembly is None:
            continue
        try:
            result[f"{name}_visible"] = bool(assembly.GetVisibility())
        except Exception:
            pass
        try:
            result[f"{name}_parts"] = int(assembly.GetParts().GetNumberOfItems())
        except Exception:
            pass
        try:
            result[f"{name}_bounds"] = [round(float(v), 8) for v in assembly.GetBounds()]
        except Exception:
            pass
    return result


def _should_write(owner: Any, event: str, extra: dict[str, Any]) -> bool:
    """Rate-limit hot events while preserving failures and state changes."""

    hot_sampled = {"pick.miss", "pick.probe", "renderer.follow"}
    if event in hot_sampled:
        try:
            attr = "_transform_gizmo_diag_" + event.replace(".", "_")
            count = int(getattr(owner, attr, 0) or 0) + 1
            setattr(owner, attr, count)
            # First few events are useful, then periodic samples only.
            return count <= 5 or count % (30 if event == "renderer.follow" else 50) == 0 or bool(extra.get("force"))
        except Exception:
            return False

    coalesced = {
        "view.update_begin",
        "renderer.sync_begin",
        "renderer.sync_reused",
        "renderer.overlay_ready",
        "renderer.legacy_guides_cleared",
        "renderer.render_requested",
        "renderer.interaction_changed",
        "api.render_snapshot_begin",
        "api.render_snapshot_end",
        "api.sync_requested",
        "api.sync_success",
    }
    if event not in coalesced:
        return True
    try:
        now = time.monotonic()
        compact = tuple(sorted((str(k), repr(v)) for k, v in extra.items() if k not in {"qx", "qy"}))
        signature = (str(event), compact)
        last_sig = getattr(owner, "_transform_gizmo_diag_last_coalesced_signature", None)
        last_time = float(getattr(owner, "_transform_gizmo_diag_last_coalesced_time", 0.0) or 0.0)
        if signature == last_sig and now - last_time < 1.0:
            return False
        setattr(owner, "_transform_gizmo_diag_last_coalesced_signature", signature)
        setattr(owner, "_transform_gizmo_diag_last_coalesced_time", now)
        return True
    except Exception:
        return True


def record_transform_gizmo_event(
    owner: Any,
    event: str,
    *,
    snapshot: Any | None = None,
    extra: dict[str, Any] | None = None,
    error: BaseException | str | None = None,
    ui_log: bool = False,
) -> None:
    if not _debug_enabled(owner):
        return
    payload = dict(extra or {})
    if not _should_write(owner, str(event), payload):
        return
    try:
        seq = int(getattr(owner, "_transform_gizmo_diag_sequence", 0) or 0) + 1
        setattr(owner, "_transform_gizmo_diag_sequence", seq)
    except Exception:
        seq = 0

    plotter = getattr(owner, "plotter", None)
    main_renderer = getattr(plotter, "renderer", None)
    overlay_renderer = getattr(owner, "gizmo_overlay_renderer", None)
    ren_win = getattr(plotter, "ren_win", None) or getattr(plotter, "render_window", None)
    if callable(ren_win):
        try:
            ren_win = ren_win()
        except Exception:
            ren_win = None

    entry: dict[str, Any] = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "seq": seq,
        "event": str(event),
        "transform_mode": str(getattr(owner, "transform_mode", "") or ""),
        "active_tool": str(getattr(owner, "active_tool", "") or ""),
        "selected_indices": _safe(list(getattr(owner, "selected_indices", []) or [])),
        "active_index": _safe(getattr(owner, "active_index", None)),
        "native_active": bool(getattr(owner, "_native_transform_gizmo_active", False)),
        "snapshot": _snapshot_summary(snapshot if snapshot is not None else getattr(owner, "_native_transform_gizmo_snapshot", None)),
        "backend": _backend_snapshot(owner),
        "main_renderer": _renderer_snapshot(main_renderer),
        "overlay_renderer": _renderer_snapshot(overlay_renderer),
        "extra": _safe(payload),
    }
    try:
        entry["render_window_layers"] = int(ren_win.GetNumberOfLayers()) if ren_win is not None else None
    except Exception:
        entry["render_window_layers"] = None
    if error is not None:
        entry["error"] = repr(error) if isinstance(error, BaseException) else str(error)

    try:
        transform_gizmo_diagnostics_path().open("a", encoding="utf-8").write(
            json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        )
    except Exception:
        pass

    try:
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        audit.increment(f"transform.gizmo.diag.{event}")
        audit.set_value("transform.gizmo.diag.last_event", str(event))
    except Exception:
        pass

    if ui_log:
        try:
            logger = getattr(owner, "ui_log", None)
            if callable(logger):
                logger(f"[TRANSFORM_GIZMO_DIAG] #{seq} {event} -> {transform_gizmo_diagnostics_path()}")
        except Exception:
            pass


__all__ = ["record_transform_gizmo_event", "transform_gizmo_diagnostics_path"]

# -*- coding: utf-8 -*-
from __future__ import annotations

from ._window_deps import *
from .controllers import StudioControllers
from .runtime_state import initialize_runtime_state
from .tooling.ids import (
    TOOL_BOX,
    TOOL_ENGRAVING,
    TOOL_MATERIAL,
    TOOL_TEXTURE_PROJECTION,
    TOOL_JOINT,
    TOOL_LAYFLAT,
    TOOL_MOD_SPLIT,
    TOOL_MOD_SIMPLIFY,
    TOOL_MOD_RELIEF,
    TOOL_MOD_EXTRUDE_DOWN,
    TOOL_MOD_HOLLOW,
    TOOL_MOD_REPAIR,
    TOOL_NONE,
    TOOL_PRIMITIVE,
    TOOL_PLAN_TRACE,
    TOOL_VENT_GENERATOR,
    TOOL_VOLUME_MEASURE,
    TOOL_ACOUSTIC_DIFFUSER,
    TRANSFORM_NONE,
    TRANSFORM_ROTATE,
    TRANSFORM_SCALE,
    TRANSFORM_TRANSLATE,
)
from .ui.panels import UIPanelsLayer
from .assets import load_studio_icon
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None
import time


class LaserProgStudioV18(QMainWindow, UIPanelsLayer, StudioControllers):
    # Public constants mirror the tool ids used by the concrete Qt window.
    # Extension code should import ids from laserprog_studio.tooling.ids.
    TOOL_NONE = TOOL_NONE
    TOOL_BOX = TOOL_BOX
    TOOL_LAYFLAT = TOOL_LAYFLAT
    TOOL_JOINT = TOOL_JOINT
    TOOL_PRIMITIVE = TOOL_PRIMITIVE
    TOOL_ENGRAVING = TOOL_ENGRAVING
    TOOL_MATERIAL = TOOL_MATERIAL
    TOOL_TEXTURE_PROJECTION = TOOL_TEXTURE_PROJECTION
    TOOL_MOD_SPLIT = TOOL_MOD_SPLIT
    TOOL_MOD_SIMPLIFY = TOOL_MOD_SIMPLIFY
    TOOL_MOD_RELIEF = TOOL_MOD_RELIEF
    TOOL_MOD_EXTRUDE_DOWN = TOOL_MOD_EXTRUDE_DOWN
    TOOL_MOD_HOLLOW = TOOL_MOD_HOLLOW
    TOOL_MOD_REPAIR = TOOL_MOD_REPAIR
    TOOL_PLAN_TRACE = TOOL_PLAN_TRACE
    TOOL_VENT_GENERATOR = TOOL_VENT_GENERATOR
    TOOL_VOLUME_MEASURE = TOOL_VOLUME_MEASURE
    TOOL_ACOUSTIC_DIFFUSER = TOOL_ACOUSTIC_DIFFUSER


    TRANSFORM_NONE = TRANSFORM_NONE
    TRANSFORM_TRANSLATE = TRANSFORM_TRANSLATE
    TRANSFORM_ROTATE = TRANSFORM_ROTATE
    TRANSFORM_SCALE = TRANSFORM_SCALE


    def __init__(self):
        _startup_start = time.perf_counter() if (_APP_AUDIT is not None and getattr(_APP_AUDIT, "enabled", False)) else 0.0
        super().__init__()
        log_section("CREATE LASERPROG STUDIO V18")
        apply_pyvista_safe_theme()
        self.setWindowTitle("LaserProg Studio V18 - Unified Laser Workshop")
        try:
            self.setWindowIcon(load_studio_icon())
        except Exception:
            pass
        self.resize(1500, 900)
        self.setMinimumSize(1180, 760)

        initialize_runtime_state(self)

        self._apply_stylesheet()
        self._build_actions()
        self._build_menus()
        self._build_main_ui()
        try:
            if getattr(self, "ui_orchestration", None) is not None:
                self.ui_orchestration.install()
        except Exception:
            pass
        self._build_status_bar()
        self._install_value_field_select_all_globally()
        try:
            self.sync_scene_tabs()
            self.update_project_title()
        except Exception:
            pass
        try:
            self._autosave_timer = QTimer(self)
            prefs = getattr(self, "project_preferences", None)
            interval_s = int(getattr(prefs, "autosave_interval_s", 10) or 10)
            self._autosave_timer.setInterval(max(interval_s, 3) * 1000)
            self._autosave_timer.timeout.connect(lambda: self.action_controller.project.autosave_tick())
            if bool(getattr(prefs, "autosave_enabled", True)):
                self._autosave_timer.start()
        except Exception:
            self._autosave_timer = None
        QTimer.singleShot(250, self._post_start)
        if _APP_AUDIT is not None and getattr(_APP_AUDIT, "enabled", False):
            try:
                _APP_AUDIT.record_timing("app.window_init", (time.perf_counter() - _startup_start) * 1000.0)
                _APP_AUDIT.set_value("app.window_size", f"{self.width()}x{self.height()}")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Qt virtual-event bridges
    # ------------------------------------------------------------------
    # QMainWindow must stay first in the inheritance list for PySide/VTK.
    # However, PySide's QMainWindow/QObject already exposes eventFilter and
    # event handlers, so methods living only in later controller layers are shadowed by
    # the Qt base class. These small bridges restore the behavior that existed
    # when everything lived directly in window.py. Without them, the installed
    # event filter never reaches InteractionLayer, which breaks viewport
    # selection and gizmo press/hover/drag handling.
    def eventFilter(self, obj, event):
        if _APP_AUDIT is None or not getattr(_APP_AUDIT, "enabled", False):
            return StudioControllers.eventFilter(self, obj, event)
        start = time.perf_counter()
        try:
            return StudioControllers.eventFilter(self, obj, event)
        finally:
            try:
                event_type = str(event.type()) if event is not None else "unknown"
                _APP_AUDIT.record_timing(f"qt.event_filter.{event_type}", (time.perf_counter() - start) * 1000.0)
                _APP_AUDIT.increment(f"qt.event_filter_count.{event_type}")
            except Exception:
                pass

    def keyPressEvent(self, event):
        if _APP_AUDIT is None or not getattr(_APP_AUDIT, "enabled", False):
            return StudioControllers.keyPressEvent(self, event)
        start = time.perf_counter()
        try:
            return StudioControllers.keyPressEvent(self, event)
        finally:
            _APP_AUDIT.record_timing("qt.key_press", (time.perf_counter() - start) * 1000.0)

    def keyReleaseEvent(self, event):
        if _APP_AUDIT is None or not getattr(_APP_AUDIT, "enabled", False):
            return StudioControllers.keyReleaseEvent(self, event)
        start = time.perf_counter()
        try:
            return StudioControllers.keyReleaseEvent(self, event)
        finally:
            _APP_AUDIT.record_timing("qt.key_release", (time.perf_counter() - start) * 1000.0)

    def closeEvent(self, event):
        if _APP_AUDIT is None or not getattr(_APP_AUDIT, "enabled", False):
            return StudioControllers.closeEvent(self, event)
        start = time.perf_counter()
        try:
            return StudioControllers.closeEvent(self, event)
        finally:
            try:
                _APP_AUDIT.record_timing("app.close_event", (time.perf_counter() - start) * 1000.0)
                _APP_AUDIT.export_markdown(reason="window_close")
            except Exception:
                pass

    # Direct Python bridges for the two high-traffic transform entry points.
    # They keep the concrete Qt class as the public owner of the workflow while
    # the implementation stays in the extracted UI/controller modules.
    def set_transform_mode(self, mode: str) -> None:
        return UIPanelsLayer.set_transform_mode(self, mode)

    def update_gizmo(self, render: bool = True) -> None:
        return StudioControllers.update_gizmo(self, render=render)

    def request_render(self, *, reason: str = "window.request_render", immediate: bool = False, force: bool = False) -> bool:
        try:
            from laserprog_studio.rendering.render_scheduler import request_render_for
            return bool(request_render_for(self, reason=reason, immediate=immediate, force=force))
        except Exception:
            try:
                plotter = getattr(self, "plotter", None)
                render = getattr(plotter, "render", None)
                if callable(render):
                    render()
                    return True
            except Exception:
                pass
            return False

    def render_now(self, *, reason: str = "window.render_now") -> bool:
        try:
            from laserprog_studio.rendering.render_scheduler import render_now_for
            return bool(render_now_for(self, reason=reason))
        except Exception:
            return self.request_render(reason=reason, immediate=True, force=True)

    def flush_render(self, *, reason: str = "window.flush_render") -> bool:
        return self.render_now(reason=reason)


# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from ..studio_log import log_exception
from .owner_delegating_controller import OwnerDelegatingController
from .texture_gizmo_qt import qapplication as _qapplication, qevent as _qevent, qt as _qt, qtimer as _qtimer


class TextureGizmoEventService(OwnerDelegatingController):
    """Migrated TEX gizmo responsibility extracted from TextureGizmoController."""

    def _texture_rotation_event_qpos(self, obj, event) -> tuple[float, float] | None:
        """Return event position in plotter Qt coordinates for diagnostics/drag.

        Mouse events may arrive either on the QVTK widget itself or on one of its
        native children.  This helper maps global coordinates back to the plotter
        when needed.  It keeps all TEX rotation math in the same coordinate system
        as the transform gizmos.
        """
        try:
            plotter = getattr(self, "plotter", None)
            if plotter is None:
                return None
            if obj is plotter:
                try:
                    pos_obj = event.position()
                except Exception:
                    pos_obj = event.pos()
                return (float(pos_obj.x()), float(pos_obj.y()))
            try:
                gp = event.globalPosition().toPoint()
            except Exception:
                try:
                    gp = event.globalPos()
                except Exception:
                    gp = None
            if gp is not None and hasattr(plotter, "mapFromGlobal"):
                lp = plotter.mapFromGlobal(gp)
                return (float(lp.x()), float(lp.y()))
            try:
                pos_obj = event.position()
            except Exception:
                try:
                    pos_obj = event.pos()
                except Exception:
                    return None
            return (float(pos_obj.x()), float(pos_obj.y()))
        except Exception:
            return None

    def _texture_rotation_buttons_diag(self, event) -> str:
        try:
            button = getattr(event, "button", lambda: None)()
        except Exception:
            button = None
        try:
            buttons = getattr(event, "buttons", lambda: None)()
        except Exception:
            buttons = None
        return f"button={button} buttons={buttons}"

    def _handle_texture_rotation_global_mouse_event(self, obj, event) -> bool:
        """Capture TEX rotation ring drag events from any Qt receiver.

        The previous implementation proved that events were received, but some
        PySide/QWindow event types did not reliably take the same branch as the
        normal plotter event path.  This version uses the integer QEvent type as
        the source of truth, logs before and after the rotation update, and then
        consumes the event exactly like the transform gizmo drag code does.
        """
        try:
            etype = event.type()
            try:
                etype_i = int(etype)
            except Exception:
                etype_i = -1
            mouse_move_i = int(_qevent().MouseMove)
            mouse_release_i = int(_qevent().MouseButtonRelease)
            if etype_i not in {mouse_move_i, mouse_release_i}:
                return False

            pressed = bool(getattr(self, "_texture_rotation_gizmo_pressed", False))
            active = bool(getattr(self, "_texture_rotation_gizmo_drag_active", False))
            if not (pressed or active):
                return False

            qpos = self._texture_rotation_event_qpos(obj, event)
            if qpos is None:
                self.ui_log(f"[TEXTURE_GIZMO_EVT] global no-qpos etype={etype_i} obj={type(obj).__name__} pressed={pressed} active={active}")
                return False
            qx, qy = qpos

            if bool(getattr(self, "_diagnostic_verbose", False)):
                try:
                    self._texture_rotation_gizmo_event_seq = int(getattr(self, "_texture_rotation_gizmo_event_seq", 0)) + 1
                    self.ui_log(
                        f"[TEXTURE_GIZMO_EVT] global#{self._texture_rotation_gizmo_event_seq} "
                        f"etype={etype_i} obj={type(obj).__name__} q=({qx:.1f},{qy:.1f}) "
                        f"{self._texture_rotation_buttons_diag(event)} pressed={pressed} active={active}"
                    )
                except Exception:
                    pass

            if etype_i == mouse_move_i:
                before = int(getattr(self, "_texture_rotation_gizmo_update_count", 0) or 0)
                self._update_texture_rotation_gizmo_drag(qx, qy, source="global-move")
                after = int(getattr(self, "_texture_rotation_gizmo_update_count", 0) or 0)
                if after == before:
                    self.ui_log(
                        f"[TEXTURE_GIZMO_EVT] global move consumed but no update "
                        f"q=({qx:.1f},{qy:.1f}) before={before} after={after}"
                    )
                try:
                    event.accept()
                except Exception:
                    pass
                return True

            if etype_i == mouse_release_i:
                try:
                    before = int(getattr(self, "_texture_rotation_gizmo_update_count", 0) or 0)
                    self._update_texture_rotation_gizmo_drag(qx, qy, source="global-release")
                    after = int(getattr(self, "_texture_rotation_gizmo_update_count", 0) or 0)
                    if after == before:
                        self.ui_log(
                            f"[TEXTURE_GIZMO_EVT] global release consumed but no update "
                            f"q=({qx:.1f},{qy:.1f}) before={before} after={after}"
                        )
                finally:
                    self._finish_texture_rotation_gizmo_drag()
                try:
                    event.accept()
                except Exception:
                    pass
                return True

            return False
        except Exception:
            log_exception("handle_texture_rotation_global_mouse_event")
            return False

    def _texture_rotation_qt_from_vtk_event(self) -> tuple[float, float] | None:
        try:
            interactor = getattr(getattr(self, "plotter", None), "iren", None)
            interactor = getattr(interactor, "interactor", interactor)
            if interactor is None:
                return None
            x, y = interactor.GetEventPosition()
            h = float(self.plotter.height())
            return (float(x), h - float(y))
        except Exception:
            return None

    def _install_texture_rotation_global_event_filter(self) -> None:
        try:
            app = _qapplication().instance()
            if app is not None and not bool(getattr(self, "_global_event_filter_installed", False)):
                # The main window may already be installed as a permanent
                # application event filter for Tab / Shift+number shortcuts.  In
                # that case TEX can reuse it during drag, but must not remove it
                # when the drag ends.
                permanent_shortcut_filter = bool(getattr(self.owner, "_shortcut_event_filter_installed", False))
                self._texture_rotation_global_filter_owned = not permanent_shortcut_filter
                if not permanent_shortcut_filter:
                    app.installEventFilter(self.owner)
                self._global_event_filter_installed = True
                self.ui_log("[TEXTURE_GIZMO_EVT] global filter ready for active TEX drag")
        except Exception:
            log_exception("install_texture_rotation_global_event_filter")

    def _remove_texture_rotation_global_event_filter(self) -> None:
        try:
            app = _qapplication().instance()
            if app is not None and bool(getattr(self, "_global_event_filter_installed", False)):
                if bool(getattr(self, "_texture_rotation_global_filter_owned", True)):
                    app.removeEventFilter(self.owner)
                self._global_event_filter_installed = False
                self._texture_rotation_global_filter_owned = False
                self.ui_log("[TEXTURE_GIZMO_EVT] global filter released after TEX drag")
        except Exception:
            log_exception("remove_texture_rotation_global_event_filter")

    def _install_texture_rotation_vtk_observers(self) -> None:
        """Install temporary VTK observers for TEX rotation drag.

        The normal transform gizmo usually gets Qt MouseMove events.  TEX has an
        additional VTK observer fallback because QVTK can swallow Qt move events
        while the camera interactor owns the left button.
        """
        try:
            self._remove_texture_rotation_vtk_observers()
            iren = getattr(getattr(self, "plotter", None), "iren", None)
            interactor = getattr(iren, "interactor", iren)
            if interactor is None or not hasattr(interactor, "AddObserver"):
                self.ui_log("[TEXTURE_GIZMO_EVT] vtk observers unavailable")
                return

            def on_move(_obj, _evt):
                try:
                    if not bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                        return
                    qpos = self._texture_rotation_qt_from_vtk_event()
                    if qpos is None:
                        self.ui_log("[TEXTURE_GIZMO_EVT] vtk-move no-qpos")
                        return
                    qx, qy = qpos
                    if bool(getattr(self, "_diagnostic_verbose", False)):
                        self.ui_log(f"[TEXTURE_GIZMO_EVT] vtk-move q=({qx:.1f},{qy:.1f})")
                    self._update_texture_rotation_gizmo_drag(qx, qy)
                except Exception:
                    log_exception("texture_rotation_vtk_move")

            def on_release(_obj, _evt):
                try:
                    if not (bool(getattr(self, "_texture_rotation_gizmo_pressed", False)) or bool(getattr(self, "_texture_rotation_gizmo_drag_active", False))):
                        return
                    qpos = self._texture_rotation_qt_from_vtk_event()
                    if qpos is not None:
                        qx, qy = qpos
                        if bool(getattr(self, "_diagnostic_verbose", False)):
                            self.ui_log(f"[TEXTURE_GIZMO_EVT] vtk-release q=({qx:.1f},{qy:.1f})")
                        if bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                            self._update_texture_rotation_gizmo_drag(qx, qy)
                    self._finish_texture_rotation_gizmo_drag()
                except Exception:
                    log_exception("texture_rotation_vtk_release")

            ids = []
            ids.append(int(interactor.AddObserver("MouseMoveEvent", on_move, 1.0)))
            ids.append(int(interactor.AddObserver("LeftButtonReleaseEvent", on_release, 1.0)))
            self._texture_rotation_gizmo_vtk_observer_ids = ids
            self.ui_log(f"[TEXTURE_GIZMO_EVT] vtk observers installed ids={ids}")
        except Exception:
            log_exception("install_texture_rotation_vtk_observers")

    def _remove_texture_rotation_vtk_observers(self) -> None:
        try:
            ids = list(getattr(self, "_texture_rotation_gizmo_vtk_observer_ids", []) or [])
            if not ids:
                return
            iren = getattr(getattr(self, "plotter", None), "iren", None)
            interactor = getattr(iren, "interactor", iren)
            if interactor is not None and hasattr(interactor, "RemoveObserver"):
                for oid in ids:
                    try:
                        interactor.RemoveObserver(int(oid))
                    except Exception:
                        pass
            self.ui_log(f"[TEXTURE_GIZMO_EVT] vtk observers removed ids={ids}")
        except Exception:
            log_exception("remove_texture_rotation_vtk_observers")
        finally:
            self._texture_rotation_gizmo_vtk_observer_ids = []

    def _ensure_texture_rotation_poll_timer(self) -> None:
        """Create a small polling timer used while dragging the TEX rotation ring.

        Some QVTK builds swallow MouseMove events after we consume the press event.
        The normal transform gizmos receive moves reliably, but the TEX tool owns a
        temporary preview/decal actor and has an active tool panel; polling the real
        cursor position during the drag makes the rotation independent from the
        exact Qt/VTK mouse routing.
        """
        try:
            timer = getattr(self, "_texture_rotation_gizmo_poll_timer", None)
            if timer is None:
                timer = _qtimer()(self.owner)
                timer.setInterval(int(getattr(self, "_texture_poll_interval_ms", 50)))
                timer.timeout.connect(self._poll_texture_rotation_gizmo_drag)
                self._texture_rotation_gizmo_poll_timer = timer
                self.ui_log(f"[TEXTURE_GIZMO_EVT] poll timer created interval={int(getattr(self, '_texture_poll_interval_ms', 50))}ms")
        except Exception:
            log_exception("ensure_texture_rotation_poll_timer")

    def _start_texture_rotation_poll_timer(self) -> None:
        try:
            self._ensure_texture_rotation_poll_timer()
            timer = getattr(self, "_texture_rotation_gizmo_poll_timer", None)
            if timer is not None and not timer.isActive():
                timer.start()
                self.ui_log("[TEXTURE_GIZMO_EVT] poll timer started")
        except Exception:
            log_exception("start_texture_rotation_poll_timer")

    def _stop_texture_rotation_poll_timer(self) -> None:
        try:
            timer = getattr(self, "_texture_rotation_gizmo_poll_timer", None)
            if timer is not None and timer.isActive():
                timer.stop()
                self.ui_log("[TEXTURE_GIZMO_EVT] poll timer stopped")
        except Exception:
            log_exception("stop_texture_rotation_poll_timer")

    def _texture_rotation_current_cursor_qpos(self) -> tuple[float, float] | None:
        """Return current global cursor position mapped to the plotter widget."""
        try:
            from PySide6.QtGui import QCursor

            plotter = getattr(self, "plotter", None)
            if plotter is None:
                return None
            local = plotter.mapFromGlobal(QCursor.pos())
            return (float(local.x()), float(local.y()))
        except Exception:
            return None

    def _poll_texture_rotation_gizmo_drag(self) -> None:
        """Timer fallback that updates rotation while the left button is held."""
        try:
            pressed = bool(getattr(self, "_texture_rotation_gizmo_pressed", False))
            active = bool(getattr(self, "_texture_rotation_gizmo_drag_active", False))
            if not (pressed or active):
                self._stop_texture_rotation_poll_timer()
                return
            try:
                buttons = _qapplication().mouseButtons()
            except Exception:
                buttons = _qt().NoButton
            if not (buttons & _qt().LeftButton):
                qpos = self._texture_rotation_current_cursor_qpos()
                if qpos is not None and active:
                    self.ui_log(
                        f"[TEXTURE_GIZMO_EVT] poll-release q=({qpos[0]:.1f},{qpos[1]:.1f}) "
                        f"pressed={pressed} active={active}"
                    )
                    self._update_texture_rotation_gizmo_drag(qpos[0], qpos[1])
                self._finish_texture_rotation_gizmo_drag()
                return
            qpos = self._texture_rotation_current_cursor_qpos()
            if qpos is None:
                self.ui_log(f"[TEXTURE_GIZMO_EVT] poll no-qpos pressed={pressed} active={active}")
                return
            qx, qy = qpos
            last = getattr(self, "_texture_rotation_gizmo_last_poll_qpos", None)
            self._texture_rotation_gizmo_poll_count = int(getattr(self, "_texture_rotation_gizmo_poll_count", 0) or 0) + 1
            if last is None:
                moved = None
            else:
                moved = max(abs(float(qx) - float(last[0])), abs(float(qy) - float(last[1])))
            self._texture_rotation_gizmo_last_poll_qpos = (float(qx), float(qy))
            # Do not spam identical timer samples, but log enough to diagnose routing.
            if bool(getattr(self, "_diagnostic_verbose", False)) and (moved is None or moved >= 1.0 or (int(getattr(self, "_texture_rotation_gizmo_poll_count", 0) or 0) % 30 == 0)):
                try:
                    self.ui_log(
                        f"[TEXTURE_GIZMO_EVT] poll#{int(getattr(self, '_texture_rotation_gizmo_poll_count', 0) or 0)} "
                        f"q=({qx:.1f},{qy:.1f}) moved={moved} buttons={int(buttons)} pressed={pressed} active={active}"
                    )
                except Exception:
                    pass
            self._update_texture_rotation_gizmo_drag(qx, qy)
        except Exception:
            log_exception("poll_texture_rotation_gizmo_drag")


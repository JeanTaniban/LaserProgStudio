# -*- coding: utf-8 -*-
from __future__ import annotations
import time
from .._window_deps import *
from ..application.creator_pointer_interaction import (
    active_creator_tool_for_pointer,
    begin_creator_camera_navigation as begin_creator_camera_navigation_state,
    creator_camera_navigation_active,
    finish_creator_camera_navigation as finish_creator_camera_navigation_state,
    handle_creator_tool_pointer_event,
)
from .interaction_gizmo_refresh import InteractionGizmoRefreshLayer
from .interaction_picking import InteractionPickingLayer
from .interaction_pointer_recovery import InteractionPointerRecoveryLayer
from .interaction_value_fields import InteractionValueFieldsLayer
from .selection_box import SelectionBoxLayer
class InteractionLayer(
    SelectionBoxLayer,
    InteractionValueFieldsLayer,
    InteractionGizmoRefreshLayer,
    InteractionPickingLayer,
    InteractionPointerRecoveryLayer,
):
    def _setup_vtk_interaction(self) -> None:
        """Install the VTK Terrain camera style and a non-intrusive Qt selection layer.
        We rely on VTK/PyVista for navigation. We only observe Qt mouse events to detect a short click.
        """
        try:
            import vtk
            self._picker = vtk.vtkPropPicker()
            try:
                self.plotter.enable_terrain_style(mouse_wheel_zooms=1.05, shift_pans=False)
                self._camera_style_name = "terrain"
                self.ui_log("[VTK] Terrain camera enabled: stable orbit, right-pan projects screen->world")
            except TypeError:
                self.plotter.enable_terrain_style()
                self._camera_style_name = "terrain_classic"
                self.ui_log("[VTK] Terrain camera enabled (terrain mode)")
            except Exception:
                log_exception("enable_terrain_style")
                self.plotter.enable_trackball_style()
                self._camera_style_name = "trackball_fallback"
                self.ui_log("[VTK] Camera fallback: Trackball style enabled")
            self.plotter.setMouseTracking(True)
            try:
                self.plotter.setFocusPolicy(Qt.StrongFocus)
            except Exception:
                pass
            try:
                self.plotter.add_key_event("v", lambda: self.ui_log("[KEY] V ignored"))
                self.plotter.add_key_event("V", lambda: self.ui_log("[KEY] V ignored"))
            except Exception:
                pass
            self.plotter.installEventFilter(self)
            self._global_event_filter_installed = False
            self._shortcut_event_filter_installed = False
            try:
                app = QApplication.instance()
                if app is not None:
                    app.installEventFilter(self)
                    self._shortcut_event_filter_installed = True
                    self.ui_log("[SHORTCUT] Application shortcut filter installed")
            except Exception:
                log_exception("install_shortcut_event_filter")
            self._viewport_pointer_buttons_down = False
            self._creator_camera_navigation_candidate_mode = ""
            self._qt_click_pos = None
            self._qt_click_time = 0.0
            try:
                self._clear_right_selection_context_state()
            except Exception:
                self._right_context_press_pos = None
                self._right_context_press_time = 0.0
                self._right_context_candidate = False
            self.ui_log("[PICKING] Qt selection installed: short click only, navigation stays in VTK")
        except Exception:
            log_exception("setup_vtk_interaction")

    def _begin_creator_camera_navigation(self, *, mode: str, screen_pos=None, renew: bool = False):
        tool = active_creator_tool_for_pointer(self)
        if tool is None:
            return None
        try:
            return begin_creator_camera_navigation_state(
                self,
                tool,
                mode=str(mode),
                screen_pos=screen_pos,
                renew=bool(renew),
            )
        except Exception:
            return None

    def _finish_creator_camera_navigation(self, *, screen_pos=None, generation=None) -> bool:
        tool = active_creator_tool_for_pointer(self)
        try:
            return bool(
                finish_creator_camera_navigation_state(
                    self,
                    tool,
                    screen_pos=screen_pos,
                    generation=generation,
                )
            )
        except Exception:
            return False

    def eventFilter(self, obj, event):  # noqa: N802
        """Non-intrusive interactions around the Terrain camera.
        - short left click: select/deselect
        - double left click: select + focus camera on part
        - drag X/Y/Z arrow gizmo: translate along axis
        - drag X/Y/Z ring gizmo: rotate around world axis
        - drag X/Y/Z cube handle: scale around the bounds center
        - drag an XY bounds-frame edge: scale from the opposite edge
        - right drag: camera pan
        - middle click: ignored
        """
        try:
            if self._handle_global_high_frequency_shortcut_event(obj, event):
                return True
            if self._handle_value_field_select_all_event(obj, event):
                return False
            if obj is getattr(self, "light_transform_overlay", None):
                etype = event.type()
                if etype == QEvent.Enter:
                    self._set_light_transform_overlay_hover(True)
                elif etype == QEvent.Leave:
                    self._set_light_transform_overlay_hover(False)
                elif etype == QEvent.Resize:
                    self._schedule_light_overlay_position()
                return False
            if obj in (getattr(self, "plotter_area", None), self):
                etype = event.type()
                reposition_events = {QEvent.Move, QEvent.Resize, QEvent.Show, QEvent.Hide}
                for name in ("WindowStateChange", "ScreenChangeInternal"):
                    value = getattr(QEvent, name, None)
                    if value is not None:
                        reposition_events.add(value)
                if etype in reposition_events:
                    self._schedule_light_overlay_position(force=True)
                return False
            try:
                if self._handle_texture_rotation_global_mouse_event(obj, event):
                    return True
            except Exception:
                log_exception("texture_rotation_global_mouse_event")
            plotter = getattr(self, "plotter", None)
            if plotter is not None and obj is plotter:
                etype = event.type()
                if etype in {QEvent.KeyPress, QEvent.KeyRelease, QEvent.ShortcutOverride}:
                    try:
                        mods = event.modifiers()
                        key = event.key()
                        ctrl = bool(mods & Qt.ControlModifier)
                        alt = bool(mods & Qt.AltModifier)
                        if key == Qt.Key_V and not alt:
                            self.ui_log(f"[KEY_DIAG] eventFilter key=V ctrl={ctrl} alt={alt} etype={int(etype)} accepted path=paste")
                            event.accept()
                            if etype == QEvent.KeyPress and ctrl:
                                self.paste_selection()
                            return True
                        if ctrl and not alt and key in {Qt.Key_A, Qt.Key_C, Qt.Key_D}:
                            path = {Qt.Key_A: "select_all", Qt.Key_C: "copy", Qt.Key_D: "duplicate"}.get(key, "shortcut")
                            self.ui_log(f"[KEY_DIAG] eventFilter key={key} ctrl={ctrl} alt={alt} etype={int(etype)} accepted path={path}")
                            event.accept()
                            if etype == QEvent.KeyPress:
                                if key == Qt.Key_A:
                                    self.select_all_parts()
                                elif key == Qt.Key_C:
                                    self.copy_selected()
                                elif key == Qt.Key_D:
                                    self.duplicate_selected()
                            return True
                    except Exception:
                        pass
                mouse_events = {
                    QEvent.MouseButtonPress,
                    QEvent.MouseButtonRelease,
                    QEvent.MouseButtonDblClick,
                    QEvent.MouseMove,
                }
                if etype == QEvent.Resize:
                    self._schedule_light_overlay_position()
                    return False
                cancel_events = {QEvent.Leave, QEvent.FocusOut, QEvent.Hide}
                for name in ("WindowDeactivate", "ApplicationDeactivate"):
                    value = getattr(QEvent, name, None)
                    if value is not None:
                        cancel_events.add(value)
                if etype in cancel_events:
                    if creator_camera_navigation_active(self):
                        QTimer.singleShot(0, lambda: self._finish_creator_camera_navigation())
                    self._reset_viewport_pointer_state(release_vtk=True)
                    return False
                if etype == QEvent.Wheel:
                    try:
                        wheel_pos = event.position()
                    except Exception:
                        try:
                            wheel_pos = event.pos()
                        except Exception:
                            wheel_pos = None
                    wheel_screen = None if wheel_pos is None else (float(wheel_pos.x()), float(wheel_pos.y()))
                    zoom_generation = self._begin_creator_camera_navigation(
                        mode="zoom",
                        screen_pos=wheel_screen,
                        renew=True,
                    )
                    if zoom_generation is not None:
                        # Trackpads emit many short pulses. Only the last timer may
                        # end camera-exclusive mode and run the one cursor/snap catch-up.
                        QTimer.singleShot(90, lambda g=zoom_generation, p=wheel_screen: self._finish_creator_camera_navigation(screen_pos=p, generation=g))
                    if self._is_fixed_camera_mode():
                        self._zoom_fixed_camera_from_wheel(event)
                        return True
                    # Let VTK update the perspective camera first, then resize
                    # lightweight gizmos on the next Qt turn. Every wheel/trackpad
                    # variation participates; the live refresh coalesces at 60 FPS.
                    self._request_zoom_gizmo_refresh(after_camera_event=True)
                    return False
                if etype not in mouse_events:
                    return False
                try:
                    pos_obj = event.position()
                except Exception:
                    try:
                        pos_obj = event.pos()
                    except Exception:
                        return False
                qx, qy = float(pos_obj.x()), float(pos_obj.y())
                planar_controller = getattr(self, "planar_tool_controller", None)
                try:
                    buttons = event.buttons()
                except Exception:
                    buttons = Qt.NoButton
                diag_controller = getattr(self, "tool_core_diag_controller", None)
                diag_active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none")) == getattr(self, "TOOL_CORE_DIAGNOSTIC", "tool_core_diagnostic")
                if diag_active and diag_controller is not None:
                    if etype == QEvent.MouseButtonPress and event.button() == Qt.MiddleButton:
                        if diag_controller.show_blender_style_popover(qx, qy):
                            event.accept()
                            return True
                    if etype == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                        try:
                            shift_down = bool(event.modifiers() & Qt.ShiftModifier)
                        except Exception:
                            shift_down = False
                        if diag_controller.handle_pointer_press(qx, qy, shift_down=shift_down):
                            event.accept()
                            return True
                    elif etype == QEvent.MouseMove:
                        left_down = bool(buttons & Qt.LeftButton)
                        if diag_controller.handle_pointer_move(qx, qy, buttons_down=left_down) and left_down:
                            event.accept()
                            return True
                        if buttons != Qt.NoButton and getattr(diag_controller, "camera_size_update_mode", "end") == "live":
                            self._request_live_gizmo_refresh(render=True)
                    elif etype == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                        if diag_controller.handle_pointer_release(qx, qy):
                            event.accept()
                            return True
                        QTimer.singleShot(0, diag_controller.refresh_camera_size_after_move)
                creator_tool = active_creator_tool_for_pointer(self)
                try:
                    if str(getattr(self, "active_tool", "")) == "plan_trace":
                        from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_controller_event

                        record_controller_event(
                            "controller.creator_dispatch.before",
                            self,
                            etype,
                            event,
                            qx,
                            qy,
                            buttons,
                            Qt=Qt,
                            QEvent=QEvent,
                            has_creator_tool=creator_tool is not None,
                            creator_tool_id=getattr(creator_tool, "id", None),
                        )
                except Exception:
                    pass
                if creator_tool is not None:
                    creator_handled = bool(handle_creator_tool_pointer_event(self, creator_tool, etype, event, qx, qy, buttons, Qt=Qt, QEvent=QEvent))
                    try:
                        if str(getattr(self, "active_tool", "")) == "plan_trace":
                            from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_controller_event

                            record_controller_event(
                                "controller.creator_dispatch.after",
                                self,
                                etype,
                                event,
                                qx,
                                qy,
                                buttons,
                                Qt=Qt,
                                QEvent=QEvent,
                                handled=creator_handled,
                            )
                    except Exception:
                        pass
                    if creator_handled:
                        event.accept()
                        return True
                # Texture Projection is a click-to-place tool, but a left drag in
                # empty viewport space must stay a normal VTK camera orbit/pan.
                # The Creator API already recorded the empty press above; if this
                # is not a TEX handle, do not let the legacy selection-box/click
                # path consume the press and starve the camera interactor.
                if (
                    etype == QEvent.MouseButtonPress
                    and event.button() == Qt.LeftButton
                    and getattr(self, "active_tool", self.TOOL_NONE) == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection")
                ):
                    try:
                        tex_hit = self._pick_texture_rotation_gizmo_from_qt_pos(qx, qy)
                    except Exception:
                        tex_hit = None
                    if tex_hit is None:
                        try:
                            self._viewport_pointer_buttons_down = True
                            self._creator_camera_navigation_candidate_mode = "orbit"
                        except Exception:
                            pass
                        return False
                if etype == QEvent.MouseButtonPress:
                    self._viewport_pointer_buttons_down = True
                    try:
                        if event.button() == Qt.LeftButton:
                            self._creator_camera_navigation_candidate_mode = "orbit"
                        elif event.button() in {Qt.MiddleButton, Qt.RightButton}:
                            self._creator_camera_navigation_candidate_mode = "pan"
                    except Exception:
                        self._creator_camera_navigation_candidate_mode = "mixed"
                    if (
                        event.button() == Qt.LeftButton
                        and planar_controller is not None
                        and callable(getattr(planar_controller, "is_active_planar_tool", None))
                        and planar_controller.is_active_planar_tool()
                    ):
                        event.accept()
                        return bool(planar_controller.handle_pointer_press(qx, qy, shift_down=bool(event.modifiers() & Qt.ShiftModifier)))
                    if event.button() == Qt.MiddleButton:
                        return True
                    if event.button() == Qt.RightButton:
                        import time
                        try:
                            context_candidate = bool(self._right_selection_context_press(qx, qy))
                        except Exception:
                            context_candidate = False
                            self._right_context_press_pos = (qx, qy)
                            self._right_context_press_time = time.monotonic()
                            self._right_context_candidate = False
                        # A short right click over an existing selection opens the
                        # selection context menu.  Do not start camera pan until the
                        # pointer really moves; otherwise a normal context-click would
                        # jitter the camera before the menu opens.
                        self._right_pan_active = not context_candidate
                        self._right_pan_last = (qx, qy)
                        self._qt_click_pos = None
                        return True
                    if event.button() == Qt.LeftButton:
                        if self._right_pan_active:
                            return True
                        if self.active_tool in {self.TOOL_MOD_SPLIT, getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down")}:
                            picked_split = self._pick_split_plane_handle_from_qt_pos(qx, qy)
                            if picked_split:
                                self._qt_click_pos = None
                                self._split_handle_pressed = True
                                self._split_handle_press_pos = (qx, qy)
                                return True
                        picked = self._pick_gizmo_from_qt_pos_fast(qx, qy)
                        try:
                            self.ui_log(f"[PICKING_DIAG] left_press q=({qx:.1f},{qy:.1f}) gizmo_pick={picked} gizmo_actors={len(getattr(self, 'gizmo_actors', {}))} mode={self.transform_mode} active={self.active_index}")
                        except Exception:
                            pass
                        if picked and picked[0] == "gizmo":
                            self._qt_click_pos = None
                            axis = str(picked[1]).lower()
                            if self.active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection") and axis in {"texrot", "texmove", "texscale", "texstretch_u", "texstretch_v"}:
                                self._texture_rotation_gizmo_pressed = True
                                self._texture_rotation_gizmo_press_pos = (qx, qy)
                                self._start_texture_rotation_gizmo_drag(qx, qy, kind=axis)
                                try:
                                    self.plotter.grabMouse()
                                    event.accept()
                                except Exception:
                                    pass
                                return True
                            if self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE} and self.active_index is not None and self._transform_tools_available():
                                self._gizmo_pressed_axis = axis
                                self._gizmo_press_pos = (qx, qy)
                                self._set_highlighted_transform_axis(axis)
                            return True
                        if self._selection_box_candidate_allowed(event):
                            additive = bool(event.modifiers() & Qt.ShiftModifier)
                            self._begin_selection_box_candidate(qx, qy, additive=additive)
                            return True
                        import time
                        self._qt_click_pos = (qx, qy)
                        self._qt_click_time = time.monotonic()
                        if self._is_fixed_camera_mode():
                            return True
                elif etype == QEvent.MouseMove:
                    camera_navigation = creator_camera_navigation_active(self)
                    # During a VTK-owned orbit/middle-pan, let the camera style
                    # consume the move immediately.  Do not run planar routing,
                    # pointer recovery, selection-box logic or gizmo hover.
                    # Right-pan is the only exception because LaserProg applies
                    # that camera movement itself below.
                    if camera_navigation and not bool(getattr(self, "_right_pan_active", False)):
                        try:
                            from ..diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                            audit.increment("creator.camera_navigation.controller_fast_path")
                        except Exception:
                            pass
                        return False
                    try:
                        if (
                            planar_controller is not None
                            and callable(getattr(planar_controller, "is_active_planar_tool", None))
                            and planar_controller.is_active_planar_tool()
                            and (buttons & Qt.LeftButton)
                        ):
                            event.accept()
                            return bool(planar_controller.handle_pointer_move(qx, qy, shift_down=bool(event.modifiers() & Qt.ShiftModifier)))
                    except Exception:
                        pass
                    try:
                        if buttons & Qt.MiddleButton:
                            return True
                    except Exception:
                        pass
                    if buttons == Qt.NoButton:
                        # QVTK can report ``NoButton`` on move events after a
                        # press handled by our foreground vtkActor2D overlay.
                        # The explicit press/release events remain reliable, so
                        # keep a pending/active Transform drag alive from the
                        # controller-owned pointer state instead of cancelling it
                        # before the movement threshold can be reached.
                        transform_drag_owned = bool(
                            (getattr(self, "_gizmo_pressed_axis", None) is not None
                             or getattr(self, "_drag_axis", None) is not None)
                            and getattr(self, "_viewport_pointer_buttons_down", False)
                        )
                        if not transform_drag_owned and not camera_navigation and (
                            bool(getattr(self, "_viewport_pointer_buttons_down", False))
                            or bool(getattr(self, "_right_pan_active", False))
                            or getattr(self, "_drag_axis", None) is not None
                        ):
                            self._reset_viewport_pointer_state(release_vtk=True)
                            return True
                    if buttons & Qt.RightButton:
                        try:
                            if self._right_selection_context_should_delay_pan(qx, qy):
                                return True
                            if bool(getattr(self, "_right_context_candidate", False)) and not bool(getattr(self, "_right_pan_active", False)):
                                self._right_selection_context_start_pan_from_press(qx, qy)
                                try:
                                    self._begin_creator_camera_navigation(mode="pan", screen_pos=(qx, qy))
                                except Exception:
                                    pass
                        except Exception:
                            pass
                    if self._right_pan_active and self._right_pan_last is not None:
                        right_drag_owned = bool(buttons & Qt.RightButton) or bool(
                            camera_navigation
                            and getattr(self, "_viewport_pointer_buttons_down", False)
                        )
                        if not right_drag_owned:
                            self._reset_viewport_pointer_state(release_vtk=True)
                            try:
                                self._clear_right_selection_context_state()
                            except Exception:
                                pass
                            return True
                        try:
                            from ..diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                            audit.increment("creator.camera_navigation.custom_right_pan_frame")
                        except Exception:
                            pass
                        lx, ly = self._right_pan_last
                        self._right_pan_last = (qx, qy)
                        self._pan_camera_from_qt(lx, ly, qx, qy)
                        try:
                            if diag_active and diag_controller is not None and getattr(diag_controller, "camera_size_update_mode", "end") == "live":
                                self._request_live_gizmo_refresh(render=True)
                        except Exception:
                            pass
                        return True
                    if self._split_handle_pressed and self._split_handle_press_pos is not None:
                        x0, y0 = self._split_handle_press_pos
                        moved = max(abs(qx - x0), abs(qy - y0))
                        if moved >= 4.0 and not self._split_drag_active:
                            self._start_extrude_down_handle_drag(x0, y0) if self.active_tool == getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down") else self._start_split_plane_handle_drag(x0, y0)
                        if self._split_drag_active:
                            self._update_extrude_down_handle_drag(qx, qy) if self.active_tool == getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down") else self._update_split_plane_handle_drag(qx, qy)
                        return True
                    if self._split_drag_active:
                        self._update_extrude_down_handle_drag(qx, qy) if self.active_tool == getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down") else self._update_split_plane_handle_drag(qx, qy)
                        return True
                    if bool(getattr(self, "_selection_box_candidate", False)):
                        if self._update_selection_box_drag(qx, qy):
                            return True
                    if bool(getattr(self, "_texture_rotation_gizmo_pressed", False)) and getattr(self, "_texture_rotation_gizmo_press_pos", None) is not None:
                        x0, y0 = self._texture_rotation_gizmo_press_pos
                        moved = max(abs(qx - x0), abs(qy - y0))
                        if moved >= 4.0 and not bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                            self._start_texture_rotation_gizmo_drag(x0, y0)
                        if bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                            self._update_texture_rotation_gizmo_drag(qx, qy)
                        return True
                    if bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                        self._update_texture_rotation_gizmo_drag(qx, qy)
                        return True
                    if self._gizmo_pressed_axis is not None and self._gizmo_press_pos is not None:
                        x0, y0 = self._gizmo_press_pos
                        moved = max(abs(qx - x0), abs(qy - y0))
                        if moved >= 4.0 and self._drag_axis is None:
                            self._start_gizmo_drag(self._gizmo_pressed_axis, x0, y0)
                        if self._drag_axis is not None:
                            self._update_gizmo_drag(qx, qy)
                        return True
                    if self._drag_axis is not None:
                        self._update_gizmo_drag(qx, qy)
                        return True
                    try:
                        if self._is_fixed_camera_mode() and (buttons & Qt.LeftButton):
                            return True
                    except Exception:
                        pass
                    try:
                        if buttons == Qt.NoButton:
                            self._update_gizmo_hover(qx, qy)
                    except Exception:
                        self._update_gizmo_hover(qx, qy)
                elif etype == QEvent.MouseButtonRelease:
                    if creator_camera_navigation_active(self):
                        QTimer.singleShot(
                            0,
                            lambda p=(qx, qy): self._finish_creator_camera_navigation(screen_pos=p),
                        )
                    try:
                        released_button = event.button()
                    except Exception:
                        released_button = Qt.NoButton
                    if buttons == Qt.NoButton or released_button in {Qt.LeftButton, Qt.MiddleButton, Qt.RightButton}:
                        # Qt/QVTK can still report the released button in
                        # event.buttons() on the release frame.  The controller
                        # latch must be cleared from event.button(), otherwise
                        # subsequent plain hover moves look like camera drags and
                        # Creator tools suppress their cursor updates.
                        self._viewport_pointer_buttons_down = False
                        self._creator_camera_navigation_candidate_mode = ""
                    if (
                        event.button() == Qt.LeftButton
                        and planar_controller is not None
                        and callable(getattr(planar_controller, "is_active_planar_tool", None))
                        and planar_controller.is_active_planar_tool()
                    ):
                        event.accept()
                        return bool(planar_controller.handle_pointer_release(qx, qy, shift_down=bool(event.modifiers() & Qt.ShiftModifier)))
                    if event.button() == Qt.MiddleButton:
                        return True
                    if event.button() == Qt.RightButton:
                        try:
                            open_context_menu = bool(self._right_selection_context_should_open(qx, qy))
                        except Exception:
                            open_context_menu = False
                        self._reset_viewport_pointer_state(release_vtk=True)
                        try:
                            self._clear_right_selection_context_state()
                        except Exception:
                            pass
                        if open_context_menu:
                            event.accept()
                            QTimer.singleShot(0, lambda x=qx, y=qy: self._show_selection_context_menu(x, y))
                            return True
                        try:
                            if diag_active and diag_controller is not None:
                                QTimer.singleShot(0, diag_controller.refresh_camera_size_after_move)
                            else:
                                QTimer.singleShot(0, lambda: self._refresh_camera_scaled_overlays(render=True))
                        except Exception:
                            pass
                        return True
                    if event.button() == Qt.LeftButton:
                        if bool(getattr(self, "_texture_rotation_gizmo_pressed", False)) or bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                            try:
                                if bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                                    self._update_texture_rotation_gizmo_drag(qx, qy)
                            except Exception:
                                pass
                            self._finish_texture_rotation_gizmo_drag()
                            try:
                                self.plotter.releaseMouse()
                                event.accept()
                            except Exception:
                                pass
                            return True
                        if self._split_handle_pressed or self._split_drag_active:
                            self._finish_extrude_down_handle_drag() if self.active_tool == getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down") else self._finish_split_plane_handle_drag()
                            return True
                        if self._gizmo_pressed_axis is not None:
                            if self._drag_axis is not None:
                                self._finish_gizmo_drag()
                            self._gizmo_pressed_axis = None
                            self._gizmo_press_pos = None
                            return True
                        if self._drag_axis is not None:
                            self._finish_gizmo_drag()
                            return True
                        if bool(getattr(self, "_selection_box_candidate", False)):
                            handled_box = self._finish_selection_box(qx, qy)
                            if handled_box:
                                return True
                        if self._suppress_next_left_release:
                            self._suppress_next_left_release = False
                            self._qt_click_pos = None
                            return False
                        import time
                        if self._qt_click_pos is not None:
                            x0, y0 = self._qt_click_pos
                            moved = max(abs(qx - x0), abs(qy - y0))
                            elapsed = time.monotonic() - self._qt_click_time
                            self._qt_click_pos = None
                            if moved <= 5.0 and elapsed <= 0.55:
                                additive = bool(event.modifiers() & Qt.ShiftModifier)
                                QTimer.singleShot(0, lambda x=qx, y=qy, add=additive: self._select_from_qt_click(x, y, additive=add))
                            elif (
                                (self.active_index is not None and self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE})
                                or getattr(self, "active_tool", self.TOOL_NONE) == self.TOOL_MOD_SPLIT
                                or (
                                    getattr(self, "active_tool", self.TOOL_NONE) == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection")
                                    and self.has_preview()
                                )
                                or active_creator_tool_for_pointer(self) is not None
                            ):
                                QTimer.singleShot(0, lambda: self._refresh_camera_scaled_overlays(render=True))
                            if self._is_fixed_camera_mode():
                                return True
                elif etype == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                    if (
                        planar_controller is not None
                        and callable(getattr(planar_controller, "is_active_planar_tool", None))
                        and planar_controller.is_active_planar_tool()
                    ):
                        self._suppress_next_left_release, self._qt_click_pos = True, None
                        event.accept(); return bool(planar_controller.handle_pointer_double_click(qx, qy))
                    self._suppress_next_left_release, self._qt_click_pos = True, None
                    creator_tool = active_creator_tool_for_pointer(self)
                    if creator_tool is not None:
                        event.accept(); return True
                    picked = self._pick_from_qt_pos(qx, qy)
                    if picked and picked[0] == "mesh":
                        idx = int(picked[1])
                        self.select_index(idx, toggle=False)
                        if not self._is_fixed_camera_mode():
                            self.focus_camera_on_index(idx)
                        return True
                elif etype == QEvent.Leave:
                    self._reset_viewport_pointer_state(release_vtk=True)
        except Exception:
            log_exception("event_filter_selection")
        return False
    # ------------------------------------------------------------------
    # Configurable high-frequency shortcuts
    # ------------------------------------------------------------------
    def _shortcut_preferences(self):
        try:
            prefs = getattr(self, "project_preferences", None)
            if prefs is None:
                from ..services.project_preferences import load_project_preferences
                prefs = load_project_preferences()
                self.project_preferences = prefs
            return getattr(prefs, "shortcuts", None)
        except Exception:
            return None

    def _shortcut_hold_threshold_s(self) -> float:
        shortcuts = self._shortcut_preferences()
        try:
            return max(0.2, min(float(getattr(shortcuts, "hold_threshold_s", 0.5)), 2.0))
        except Exception:
            return 0.5

    def _shortcut_multi_press_window_ms(self) -> int:
        shortcuts = self._shortcut_preferences()
        try:
            return int(max(0.1, min(float(getattr(shortcuts, "multi_press_window_s", 0.65)), 2.0)) * 1000.0)
        except Exception:
            return 650

    def _shortcut_key_matches(self, logical: str, key: int) -> bool:
        logical = str(logical or "").strip().lower()
        if logical == "tab":
            return key == Qt.Key_Tab
        if logical == "space":
            return key == Qt.Key_Space
        if logical == "left_alt":
            # Qt does not reliably expose left/right Alt on every backend.  The
            # default is named Left Alt in Preferences, and Key_Alt is accepted as
            # the portable implementation.
            return key == Qt.Key_Alt
        return False

    def _event_text(self, event: Any) -> str:
        try:
            return str(event.text())
        except Exception:
            return ""

    def _is_shortcut_filter_allowed(self, obj: Any) -> bool:
        """Keep global high-frequency shortcuts inside the main application UI.

        A modal dialog must keep its native keyboard behaviour.  The main
        window/inspector/viewport, however, all route Tab and Shift+number here
        so focus widgets cannot steal these production shortcuts.
        """
        try:
            modal = QApplication.activeModalWidget()
            if modal is not None and modal is not self:
                return False
        except Exception:
            pass
        return True

    def _is_high_frequency_shortcut_event(self, key: int, mods: Any, text: str | None = None) -> bool:
        try:
            if bool(mods & Qt.ShiftModifier) and self._toolbar_shortcut_index(key, text) is not None:
                return True
            shortcuts = self._shortcut_preferences()
            transform_key = str(getattr(shortcuts, "transform_cycle_key", "tab")) if shortcuts is not None else "tab"
            if self._shortcut_key_matches(transform_key, key) and not bool(mods & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier)):
                return True
            preview_key = str(getattr(shortcuts, "preview_apply_key", "left_alt")) if shortcuts is not None else "left_alt"
            if self._shortcut_key_matches(preview_key, key):
                return True
        except Exception:
            pass
        return False

    def _handle_global_high_frequency_shortcut_event(self, obj: Any, event: Any) -> bool:
        try:
            etype = event.type()
            if etype not in {QEvent.ShortcutOverride, QEvent.KeyPress, QEvent.KeyRelease}:
                return False
            if not self._is_shortcut_filter_allowed(obj):
                return False
            key = event.key()
            mods = event.modifiers()
            text = self._event_text(event)
            if etype == QEvent.ShortcutOverride:
                if self._is_high_frequency_shortcut_event(key, mods, text):
                    event.accept()
                    return True
                return False
            if etype == QEvent.KeyPress:
                if self._handle_toolbar_number_shortcut(key, mods, text):
                    event.accept()
                    return True
                if self._handle_transform_cycle_key_press(key, mods, event):
                    return True
                if self._handle_preview_apply_key_press(key, event):
                    return True
                return False
            if etype == QEvent.KeyRelease:
                if self._handle_transform_cycle_key_release(key, event):
                    return True
                if self._handle_preview_apply_key_release(key, event):
                    return True
                if bool(mods & Qt.ShiftModifier) and self._toolbar_shortcut_index(key, text) is not None:
                    event.accept()
                    return True
        except Exception:
            log_exception("global_high_frequency_shortcut_event")
        return False

    def _qt_key_attr(self, name: str):
        try:
            return getattr(Qt, name)
        except Exception:
            return None

    def _toolbar_shortcut_digit(self, key: int, text: str | None = None) -> int | None:
        """Return the user-facing digit pressed for toolbar shortcuts.

        The mapping is intentionally layout tolerant.  On AZERTY keyboards the
        physical number row can be reported as &, é, ", ', (, -, è, _, ç, à
        instead of 1, 2, 3, 4, 5, 6, 7, 8, 9, 0.  Users should not need to know
        which Qt symbol their keyboard emits.
        """
        try:
            text_value = str(text or "")
        except Exception:
            text_value = ""
        if text_value:
            for ch in text_value:
                if ch.isdigit():
                    return int(ch)
            azerty_text = {
                "&": 1,
                "é": 2,
                "É": 2,
                '"': 3,
                "'": 4,
                "(": 5,
                "-": 6,
                "è": 7,
                "È": 7,
                "_": 8,
                "ç": 9,
                "Ç": 9,
                "à": 0,
                "À": 0,
            }
            for ch in text_value:
                if ch in azerty_text:
                    return azerty_text[ch]
        key_to_digit = {
            Qt.Key_0: 0, Qt.Key_1: 1, Qt.Key_2: 2, Qt.Key_3: 3, Qt.Key_4: 4,
            Qt.Key_5: 5, Qt.Key_6: 6, Qt.Key_7: 7, Qt.Key_8: 8, Qt.Key_9: 9,
        }
        optional_key_names = {
            "Key_Ampersand": 1,
            "Key_Eacute": 2,
            "Key_QuoteDbl": 3,
            "Key_Apostrophe": 4,
            "Key_ParenLeft": 5,
            "Key_Minus": 6,
            "Key_Egrave": 7,
            "Key_Underscore": 8,
            "Key_Ccedilla": 9,
            "Key_Agrave": 0,
        }
        for key_name, digit in optional_key_names.items():
            value = self._qt_key_attr(key_name)
            if value is not None and key == value:
                return int(digit)
        return key_to_digit.get(key)

    def _toolbar_shortcut_index(self, key: int, text: str | None = None) -> int | None:
        digit = self._toolbar_shortcut_digit(key, text)
        if digit is None:
            return None
        # User-facing numbering: Shift+1 (or Shift+& on AZERTY) opens the first
        # visible toolbar item.  Shift+0 is kept useful as the tenth item.
        return 9 if int(digit) == 0 else int(digit) - 1

    def _handle_toolbar_number_shortcut(self, key: int, mods: Any, text: str | None = None) -> bool:
        try:
            if not bool(mods & Qt.ShiftModifier):
                return False
            index = self._toolbar_shortcut_index(key, text)
            if index is None:
                return False
            ids = list(getattr(self, "toolbar_item_ids", []) or [])
            if not (0 <= int(index) < len(ids)):
                try:
                    self.statusBar().showMessage(f"No toolbar item at position {int(index) + 1}", 1200)
                except Exception:
                    pass
                return True
            controller = getattr(self, "toolbar_controller", None)
            if controller is None and hasattr(self, "_toolbar_controller"):
                controller = self._toolbar_controller()
            if controller is not None:
                controller.activate_item(ids[int(index)])
                return True
        except Exception:
            log_exception("toolbar_number_shortcut")
        return False

    def _handle_transform_cycle_key_press(self, key: int, mods: Any, event: Any) -> bool:
        try:
            shortcuts = self._shortcut_preferences()
            logical_key = str(getattr(shortcuts, "transform_cycle_key", "tab")) if shortcuts is not None else "tab"
            if not self._shortcut_key_matches(logical_key, key):
                return False
            if bool(mods & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier)):
                return False
            if bool(getattr(event, "isAutoRepeat", lambda: False)()):
                return True
            now = time.perf_counter()
            self._transform_cycle_key_down_at = now
            self._transform_cycle_hold_fired = False
            self._transform_cycle_press_counted = False
            # If a multi-press sequence is already open, apply the next transform
            # as soon as the next physical press arrives.  The release will only
            # acknowledge the key, not wait for the timeout to select the mode.
            if int(getattr(self, "_transform_cycle_tap_count", 0)) > 0:
                self._transform_cycle_tap_count = int(getattr(self, "_transform_cycle_tap_count", 0)) + 1
                self._transform_cycle_press_counted = True
                self._apply_transform_cycle_taps_immediately()
                generation = int(getattr(self, "_transform_cycle_generation", 0)) + 1
                self._transform_cycle_generation = generation
                QTimer.singleShot(self._shortcut_multi_press_window_ms(), lambda g=generation: self._finish_transform_cycle_window(g))
            threshold_ms = int(self._shortcut_hold_threshold_s() * 1000.0)
            QTimer.singleShot(threshold_ms, lambda start=now: self._transform_cycle_hold_if_current(start))
            event.accept()
            return True
        except Exception:
            log_exception("transform_cycle_key_press")
            return False

    def _transform_cycle_hold_if_current(self, start_time: float) -> None:
        try:
            if getattr(self, "_transform_cycle_key_down_at", None) != start_time:
                return
            self._transform_cycle_hold_fired = True
            self._transform_cycle_press_counted = False
            self._transform_cycle_tap_count = 0
            self._transform_cycle_generation = int(getattr(self, "_transform_cycle_generation", 0)) + 1
            self.set_transform_mode(self.TRANSFORM_NONE)
        except Exception:
            log_exception("transform_cycle_hold")

    def _handle_transform_cycle_key_release(self, key: int, event: Any) -> bool:
        try:
            shortcuts = self._shortcut_preferences()
            logical_key = str(getattr(shortcuts, "transform_cycle_key", "tab")) if shortcuts is not None else "tab"
            if not self._shortcut_key_matches(logical_key, key):
                return False
            start = getattr(self, "_transform_cycle_key_down_at", None)
            self._transform_cycle_key_down_at = None
            if bool(getattr(self, "_transform_cycle_hold_fired", False)):
                event.accept()
                return True
            if start is None:
                event.accept()
                return True
            if (time.perf_counter() - float(start)) >= self._shortcut_hold_threshold_s():
                self.set_transform_mode(self.TRANSFORM_NONE)
                event.accept()
                return True
            if not bool(getattr(self, "_transform_cycle_press_counted", False)):
                self._transform_cycle_tap_count = int(getattr(self, "_transform_cycle_tap_count", 0)) + 1
                self._apply_transform_cycle_taps_immediately()
                generation = int(getattr(self, "_transform_cycle_generation", 0)) + 1
                self._transform_cycle_generation = generation
                QTimer.singleShot(self._shortcut_multi_press_window_ms(), lambda g=generation: self._finish_transform_cycle_window(g))
            self._transform_cycle_press_counted = False
            event.accept()
            return True
        except Exception:
            log_exception("transform_cycle_key_release")
            return False

    def _transform_cycle_mode_for_taps(self, taps: int) -> str:
        """Map the current quick-tap sequence to the transform mode shown now."""
        try:
            normalized = ((max(1, int(taps)) - 1) % 3) + 1
        except Exception:
            normalized = 1
        return {
            1: self.TRANSFORM_TRANSLATE,
            2: self.TRANSFORM_ROTATE,
            3: self.TRANSFORM_SCALE,
        }.get(normalized, self.TRANSFORM_TRANSLATE)

    def _apply_transform_cycle_taps_immediately(self) -> None:
        """Update the active transform tool on every tap, not after timeout."""
        try:
            taps = int(getattr(self, "_transform_cycle_tap_count", 0))
            if taps <= 0:
                return
            self.set_transform_mode(self._transform_cycle_mode_for_taps(taps))
        except Exception:
            log_exception("transform_cycle_live_apply")

    def _finish_transform_cycle_window(self, generation: int) -> None:
        try:
            if int(getattr(self, "_transform_cycle_generation", 0)) != int(generation):
                return
            # The transform mode was already applied live at each tap.  The timer
            # now only closes the multi-press sequence so the next tap starts
            # from Translate again instead of waiting to apply the chosen mode.
            self._transform_cycle_tap_count = 0
        except Exception:
            log_exception("transform_cycle_window_finish")

    def _commit_transform_cycle_taps(self, generation: int) -> None:
        """Backward-compatible alias for older tests/extensions."""
        self._finish_transform_cycle_window(generation)

    def _handle_preview_apply_key_press(self, key: int, event: Any) -> bool:
        try:
            shortcuts = self._shortcut_preferences()
            logical_key = str(getattr(shortcuts, "preview_apply_key", "left_alt")) if shortcuts is not None else "left_alt"
            if not self._shortcut_key_matches(logical_key, key):
                return False
            if bool(getattr(event, "isAutoRepeat", lambda: False)()):
                return True
            now = time.perf_counter()
            self._preview_apply_key_down_at = now
            self._preview_apply_hold_fired = False
            QTimer.singleShot(int(self._shortcut_hold_threshold_s() * 1000.0), lambda start=now: self._preview_apply_hold_if_current(start))
            event.accept()
            return True
        except Exception:
            log_exception("preview_apply_key_press")
            return False

    def _preview_apply_hold_if_current(self, start_time: float) -> None:
        try:
            if getattr(self, "_preview_apply_key_down_at", None) != start_time:
                return
            self._preview_apply_hold_fired = True
            self.apply_preview_and_close_tool()
        except Exception:
            log_exception("preview_apply_hold")

    def _handle_preview_apply_key_release(self, key: int, event: Any) -> bool:
        try:
            shortcuts = self._shortcut_preferences()
            logical_key = str(getattr(shortcuts, "preview_apply_key", "left_alt")) if shortcuts is not None else "left_alt"
            if not self._shortcut_key_matches(logical_key, key):
                return False
            start = getattr(self, "_preview_apply_key_down_at", None)
            self._preview_apply_key_down_at = None
            if bool(getattr(self, "_preview_apply_hold_fired", False)):
                event.accept()
                return True
            if start is not None and (time.perf_counter() - float(start)) < self._shortcut_hold_threshold_s():
                self._trigger_active_tool_preview_shortcut()
            event.accept()
            return True
        except Exception:
            log_exception("preview_apply_key_release")
            return False

    def _trigger_active_tool_preview_shortcut(self) -> bool:
        try:
            from ..tooling.registry import get_studio_tool

            active = getattr(self, "active_tool", getattr(self, "TOOL_NONE", "none"))
            if active == getattr(self, "TOOL_NONE", "none"):
                return False
            tool = get_studio_tool(active)
            ctx = None
            tool_context = getattr(tool, "tool_context", None)
            if callable(tool_context):
                ctx = tool_context(self.context)
            else:
                ctx = getattr(self.context, "tool_context", None)
            inspector = getattr(ctx, "inspector", None)
            panel = getattr(inspector, "panel", None)
            if inspector is not None and panel is not None:
                candidate_ids = (
                    "stage_preview",
                    "preview",
                    "add_preview",
                    "generate_preview",
                    "measure",
                    "assign_selected",
                )
                field_ids = {str(field.id) for field in panel.fields()}
                button_ids = set()
                for field in panel.fields():
                    if getattr(field, "kind", "") == "button_row":
                        for choice_id, _label in getattr(field, "choices", ()):
                            button_ids.add(str(choice_id))
                for action_id in candidate_ids:
                    if action_id in field_ids or action_id in button_ids:
                        try:
                            inspector.trigger(action_id)
                            return True
                        except Exception:
                            continue
            # Planar tools expose a controller-level preview generator.
            planar = getattr(self, "planar_tool_controller", None)
            if planar is not None and callable(getattr(planar, "refresh_generated_preview_if_ready", None)):
                return bool(planar.refresh_generated_preview_if_ready())
        except Exception:
            log_exception("preview_shortcut")
        return False

    def keyPressEvent(self, event):  # noqa: N802
        try:
            mods = event.modifiers()
            key = event.key()
            ctrl = bool(mods & Qt.ControlModifier)
            alt = bool(mods & Qt.AltModifier)
            if self._handle_toolbar_number_shortcut(key, mods, self._event_text(event)):
                event.accept()
                return
            if self._handle_transform_cycle_key_press(key, mods, event):
                return
            if self._handle_preview_apply_key_press(key, event):
                return
            if ctrl and not alt and key in {Qt.Key_Z, Qt.Key_Y}:
                try:
                    from ..application.creator_global_shortcuts import dispatch_creator_key_shortcut

                    key_name = "z" if key == Qt.Key_Z else "y"
                    modifiers = {"ctrl"}
                    if bool(mods & Qt.ShiftModifier):
                        modifiers.add("shift")
                    if dispatch_creator_key_shortcut(self, key_name, modifiers=frozenset(modifiers)):
                        event.accept()
                        return
                except Exception:
                    pass
            if key in {Qt.Key_Escape, Qt.Key_Delete, Qt.Key_Backspace} and not ctrl and not alt:
                try:
                    from ..application.creator_pointer_interaction import active_creator_tool_for_pointer
                    from ..tool_core.events import ToolEvent, ToolEventType

                    creator_tool = active_creator_tool_for_pointer(self)
                    if creator_tool is not None:
                        key_name = "escape" if key == Qt.Key_Escape else "delete"
                        handled = creator_tool.on_event(
                            ToolEvent(
                                ToolEventType.KEY_PRESS,
                                key=key_name,
                                modifiers=frozenset(),
                                raw=event,
                            ),
                            self.context,
                        )
                        if handled:
                            event.accept()
                            return
                except Exception:
                    pass
                if key == Qt.Key_Escape:
                    planar_controller = getattr(self, "planar_tool_controller", None)
                    if planar_controller is not None and callable(getattr(planar_controller, "exit_plan_trace_add_mode", None)):
                        if planar_controller.exit_plan_trace_add_mode():
                            event.accept()
                            return
            if not ctrl and not alt and key in {Qt.Key_N, Qt.Key_T, Qt.Key_R, Qt.Key_S}:
                self.ui_log(f"[KEY_DIAG] keyPress transform key={key} ctrl={ctrl} alt={alt} before_mode={self.transform_mode}")
                event.accept()
                mode = {
                    Qt.Key_N: self.TRANSFORM_NONE,
                    Qt.Key_T: self.TRANSFORM_TRANSLATE,
                    Qt.Key_R: self.TRANSFORM_ROTATE,
                    Qt.Key_S: self.TRANSFORM_SCALE,
                }.get(key, self.TRANSFORM_NONE)
                self.set_transform_mode(mode)
                return
            if key == Qt.Key_V and not alt:
                self.ui_log(f"[KEY_DIAG] keyPress key=V ctrl={ctrl} alt={alt} path={'paste' if ctrl else 'plain-V'}")
                event.accept()
                if ctrl:
                    self.paste_selection()
                return
            if ctrl and not alt and key in {Qt.Key_A, Qt.Key_C, Qt.Key_D}:
                path = {Qt.Key_A: "select_all", Qt.Key_C: "copy", Qt.Key_D: "duplicate"}.get(key, "shortcut")
                self.ui_log(f"[KEY_DIAG] keyPress key={key} ctrl={ctrl} alt={alt} path={path}")
                event.accept()
                if key == Qt.Key_A:
                    self.select_all_parts()
                elif key == Qt.Key_C:
                    self.copy_selected()
                elif key == Qt.Key_D:
                    self.duplicate_selected()
                return
        except Exception:
            pass
        QMainWindow.keyPressEvent(self, event)
    def keyReleaseEvent(self, event):  # noqa: N802
        try:
            mods = event.modifiers()
            key = event.key()
            ctrl = bool(mods & Qt.ControlModifier)
            alt = bool(mods & Qt.AltModifier)
            if self._handle_transform_cycle_key_release(key, event):
                return
            if self._handle_preview_apply_key_release(key, event):
                return
            if key == Qt.Key_V and not alt:
                event.accept()
                return
            if ctrl and not alt and key in {Qt.Key_A, Qt.Key_C, Qt.Key_D}:
                event.accept()
                return
        except Exception:
            pass
        QMainWindow.keyReleaseEvent(self, event)

# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class InteractionPointerRecoveryLayer:
    def _release_vtk_mouse_buttons(self) -> None:
        """Force the embedded VTK interactor out of any stuck mouse-button state."""
        try:
            plotter = getattr(self, "plotter", None)
            if plotter is None:
                return
            try:
                plotter.releaseMouse()
            except Exception:
                pass

            targets = []
            for candidate in (
                getattr(plotter, "iren", None),
                getattr(getattr(plotter, "iren", None), "interactor", None),
                getattr(plotter, "interactor", None),
            ):
                if candidate is not None and candidate not in targets:
                    targets.append(candidate)
                try:
                    style = candidate.GetInteractorStyle() if candidate is not None else None
                except Exception:
                    style = None
                if style is not None and style not in targets:
                    targets.append(style)

            for target in targets:
                for method_name in ("OnLeftButtonUp", "OnMiddleButtonUp", "OnRightButtonUp"):
                    method = getattr(target, method_name, None)
                    if callable(method):
                        try:
                            method()
                        except Exception:
                            pass
                invoke = getattr(target, "InvokeEvent", None)
                if callable(invoke):
                    for event_name in ("LeftButtonReleaseEvent", "MiddleButtonReleaseEvent", "RightButtonReleaseEvent"):
                        try:
                            invoke(event_name)
                        except Exception:
                            pass
        except Exception:
            log_exception("release_vtk_mouse_buttons")

    def _reset_viewport_pointer_state(self, *, release_vtk: bool = True) -> None:
        """Cancel active viewport gestures after a lost release/focus change."""
        try:
            self._viewport_pointer_buttons_down = False
            self._creator_camera_navigation_candidate_mode = ""
            self._qt_click_pos = None
            self._right_pan_active = False
            self._right_pan_last = None
            try:
                self._clear_right_selection_context_state()
            except Exception:
                self._right_context_press_pos = None
                self._right_context_press_time = 0.0
                self._right_context_candidate = False
            self._gizmo_pressed_axis = None
            self._gizmo_press_pos = None
            self._split_handle_pressed = False
            self._split_handle_press_pos = None
            try:
                self._clear_selection_box_state()
            except Exception:
                pass
            if bool(getattr(self, "_split_drag_active", False)):
                try:
                    if getattr(self, "active_tool", None) == getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down"):
                        self._finish_extrude_down_handle_drag()
                    else:
                        self._finish_split_plane_handle_drag()
                except Exception:
                    pass
            try:
                self._set_hovered_transform_axis(None, render=True)
            except Exception:
                pass
            if getattr(self, "_drag_axis", None) is not None:
                try:
                    self._finish_gizmo_drag()
                except Exception:
                    pass
            if bool(getattr(self, "_texture_rotation_gizmo_pressed", False)) or bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                try:
                    self._finish_texture_rotation_gizmo_drag()
                except Exception:
                    pass
            if release_vtk:
                self._release_vtk_mouse_buttons()
        except Exception:
            log_exception("reset_viewport_pointer_state")

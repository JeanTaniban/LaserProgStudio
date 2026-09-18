# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class GizmoHighlightLayer:
    def _highlight_transform_axis(self, axis: str | None) -> None:
        try:
            axis = self._logical_axis_from_handle(axis)
            rows = {
                self.TRANSFORM_TRANSLATE: {"x": self.pos_x, "y": self.pos_y, "z": self.pos_z},
                self.TRANSFORM_ROTATE: {"x": self.rot_x, "y": self.rot_y, "z": self.rot_z},
                self.TRANSFORM_SCALE: {"x": self.scale_x, "y": self.scale_y, "z": self.scale_z},
            }
            all_widgets = [self.pos_x, self.pos_y, self.pos_z, self.rot_x, self.rot_y, self.rot_z, self.scale_x, self.scale_y, self.scale_z]
            active_mode = self._drag_transform_mode or self.transform_mode
            active_row = rows.get(active_mode, {})
            for widget in all_widgets:
                widget.setStyleSheet("")
            # Compact Light UI overlay uses a single X/Y/Z row whose meaning is
            # determined by the current transform mode. Highlight it with the
            # same axis hover/drag state as the full inspector.
            try:
                for widget in (getattr(self, "light_x", None), getattr(self, "light_y", None), getattr(self, "light_z", None)):
                    if widget is not None:
                        widget.setStyleSheet("")
                light_widgets = {"x": getattr(self, "light_x", None), "y": getattr(self, "light_y", None), "z": getattr(self, "light_z", None)}
            except Exception:
                light_widgets = {}
            highlight_style = "background:#17324a; border:1px solid #66b9ef; border-radius:6px; padding:4px;"
            if axis in active_row:
                active_row[axis].setStyleSheet(highlight_style)
            try:
                lw = light_widgets.get(axis) if axis else None
                if lw is not None and bool(getattr(self, "light_transform_overlay", None) and self.light_transform_overlay.isVisible()):
                    lw.setStyleSheet(highlight_style)
            except Exception:
                pass
        except Exception:
            pass

    def _normalize_transform_axis(self, axis: str | None) -> str | None:
        return self._logical_axis_from_handle(axis)

    def _visible_transform_axis(self) -> str | None:
        # Drag and hover are temporary visual states. The clicked axis remains
        # as a softer persistent hint when the mouse is not over another axis.
        return self._normalize_transform_axis(self._drag_axis or self._hovered_transform_axis or self._highlighted_transform_axis)

    def _set_highlighted_transform_axis(self, axis: str | None) -> None:
        self._highlighted_transform_axis = (axis or "").lower().strip() or None
        self._apply_highlighted_transform_axis()

    def _set_hovered_transform_axis(self, axis: str | None, *, render: bool = False) -> None:
        axis = (axis or "").lower().strip() or None
        if axis == self._hovered_transform_axis:
            return
        self._hovered_transform_axis = axis
        self._apply_highlighted_transform_axis()
        if render:
            try:
                self.plotter.render()
            except Exception:
                pass

    def _mix_rgb(self, a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
        t = max(0.0, min(1.0, float(t)))
        return (
            float(a[0]) + (float(b[0]) - float(a[0])) * t,
            float(a[1]) + (float(b[1]) - float(a[1])) * t,
            float(a[2]) + (float(b[2]) - float(a[2])) * t,
        )

    def _apply_gizmo_actor_highlight(self) -> None:
        try:
            active_handle = (self._drag_axis or self._hovered_transform_axis or "").lower().strip()
            pinned_handle = (self._highlighted_transform_axis or "").lower().strip()
            active_axis = self._normalize_transform_axis(active_handle)
            pinned_axis = self._normalize_transform_axis(pinned_handle)
            for key, actor in self.gizmo_actors.items():
                if actor is None:
                    continue
                actor_axis = self.gizmo_actor_ids.get(id(actor))
                if actor_axis is None:
                    # Address fallback for actors recreated through VTK wrappers.
                    try:
                        actor_axis = self.gizmo_key_by_addr.get(actor.GetAddressAsString(""))
                    except Exception:
                        actor_axis = None
                actor_handle = (actor_axis or "").lower().strip()
                actor_axis = self._normalize_transform_axis(actor_handle)
                if actor_axis is None:
                    continue
                base = self._gizmo_actor_base_colors.get(id(actor))
                if base is None:
                    try:
                        base = tuple(float(v) for v in actor.GetProperty().GetColor())
                    except Exception:
                        base = parse_hex_color(self._gizmo_axis_definitions().get(actor_axis, ((0, 0, 0), "#ffffff"))[1])
                if actor_handle == active_handle or actor_axis == active_axis:
                    color = self._mix_rgb(base, (1.0, 1.0, 1.0), 0.72)
                    line_width = 5.0
                elif actor_handle == pinned_handle or actor_axis == pinned_axis:
                    color = self._mix_rgb(base, (1.0, 1.0, 1.0), 0.38)
                    line_width = 3.0
                else:
                    color = base
                    line_width = 1.0
                prop = actor.GetProperty()
                prop.SetColor(float(color[0]), float(color[1]), float(color[2]))
                try:
                    prop.SetLineWidth(line_width)
                except Exception:
                    pass
                try:
                    prop.SetSpecular(0.25 if actor_axis == active_axis else 0.0)
                except Exception:
                    pass
        except Exception:
            log_exception("apply_gizmo_actor_highlight")

    def _apply_highlighted_transform_axis(self) -> None:
        visible_axis = self._visible_transform_axis()
        self._highlight_transform_axis(visible_axis)
        self._apply_gizmo_actor_highlight()
        try:
            from laserprog_studio.application.transform_gizmo_api import sync_native_transform_interaction

            sync_native_transform_interaction(
                self,
                active_axis=visible_axis,
                pinned_axis=getattr(self, "_highlighted_transform_axis", None),
                render=False,
            )
        except Exception:
            pass

    def _update_gizmo_hover(self, qx: float, qy: float) -> None:
        try:
            if self._drag_axis is not None or self._gizmo_pressed_axis is not None:
                return
            if self.active_index is None or not self._transform_tools_available() or self.transform_mode not in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}:
                self._set_hovered_transform_axis(None, render=True)
                return
            import time
            now = time.monotonic()
            last = self._last_gizmo_hover_probe_pos
            if last is not None:
                moved = max(abs(float(qx) - last[0]), abs(float(qy) - last[1]))
            else:
                moved = 999.0
            interval_s = max(float(getattr(self, "_gizmo_hover_min_interval_ms", 24.0)), 1.0) / 1000.0
            if moved < 1.5 and (now - self._last_gizmo_hover_probe_time) < interval_s:
                return
            self._last_gizmo_hover_probe_time = now
            self._last_gizmo_hover_probe_pos = (float(qx), float(qy))
            if self.active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                tool = self._creator_texture_projection_tool() if hasattr(self, "_creator_texture_projection_tool") else None
                context = getattr(self, "app_context", None) or getattr(self, "context", None)
                if tool is not None and context is not None and hasattr(tool, "hover_projector_handle"):
                    tool.hover_projector_handle(context, qx, qy)
                    self._set_hovered_transform_axis(None, render=False)
                    return
            picked = self._pick_gizmo_from_qt_pos_fast(qx, qy)
            axis = str(picked[1]).lower() if picked and picked[0] == "gizmo" else None
            self._set_hovered_transform_axis(axis, render=True)
        except Exception:
            log_exception("update_gizmo_hover")

    def _clear_gizmo_interaction(self, *, clear_highlight: bool = False) -> None:
        # Cancel an in-progress gizmo interaction without changing selection.
        self._gizmo_pressed_axis = None
        self._gizmo_press_pos = None
        if self._drag_axis is not None:
            try:
                self._finish_gizmo_drag()
            except Exception:
                pass
        if clear_highlight:
            self._gizmo_delta_display_signature = None
            self._set_hovered_transform_axis(None, render=False)
            self._set_highlighted_transform_axis(None)

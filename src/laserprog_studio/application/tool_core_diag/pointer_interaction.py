# -*- coding: utf-8 -*-
from __future__ import annotations

from ...studio_log import log_exception
from ...tool_core.diagnostic import HandleDemoBuilder, SelectionDemoBuilder
from ..tool_core_diag_scene import ToolCoreDiagScenePainter


class ToolCoreDiagPointerLayer:
    """Extracted responsibilities for :class:`ToolCoreDiagController`."""

    def handle_pointer_press(self, qx: float, qy: float, *, shift_down: bool = False) -> bool:
        try:
            self._last_pointer_px = (int(qx), int(qy))
            if self._api_lab_active:
                return self._handle_api_lab_pointer_press(qx, qy, shift_down=shift_down)
            if self._selection_demo_active:
                return self._handle_selection_pointer_press(qx, qy, shift_down=shift_down)
            # A viewport click means “outside” for transient Qt overlay windows,
            # because clicks inside the widget are consumed by the widget itself.
            self.close_click_away_overlays()
            demo = HandleDemoBuilder(self.runner.ctx)
            if not self._has_handle_demo():
                demo.build_demo()
            handle_id = self._nearest_demo_handle(qx, qy)
            if not handle_id:
                return False
            self._handle_demo_grabbed_id = handle_id
            self._handle_demo_grab_depth = self._display_depth_for_handle(handle_id)
            demo.apply_grabbed(handle_id)
            self._render_demo_scene()
            self._write_report("Handle demo grabbed")
            return True
        except Exception:
            log_exception("tool_core_diag_handle_pointer_press")
            return False

    def handle_pointer_move(self, qx: float, qy: float, *, buttons_down: bool = False) -> bool:
        try:
            self._last_pointer_px = (int(qx), int(qy))
            if self._api_lab_active:
                return self._handle_api_lab_pointer_move(qx, qy, buttons_down=buttons_down)
            if self._selection_demo_active:
                return self._handle_selection_pointer_move(qx, qy, buttons_down=buttons_down)
            demo = HandleDemoBuilder(self.runner.ctx)
            if not self._has_handle_demo():
                return False
            grabbed_id = self._handle_demo_grabbed_id
            if grabbed_id:
                world = self._qt_to_world_at_demo_depth(qx, qy, self._handle_demo_grab_depth)
                if world is not None:
                    demo.move_handle(grabbed_id, world)
                    demo.apply_grabbed(grabbed_id)
                    self._render_demo_scene()
                    return True
            if buttons_down:
                return False
            hover_id = self._nearest_demo_handle(qx, qy)
            current_hover = next((h.id for h in self.runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.hover), None)
            if hover_id != current_hover:
                demo.apply_hover(hover_id)
                self._render_demo_scene()
                return bool(hover_id)
            return False
        except Exception:
            log_exception("tool_core_diag_handle_pointer_move")
            return False

    def handle_pointer_release(self, qx: float, qy: float) -> bool:
        try:
            self._last_pointer_px = (int(qx), int(qy))
            if self._api_lab_active:
                return self._handle_api_lab_pointer_release(qx, qy)
            if self._selection_demo_active:
                return self._handle_selection_pointer_release(qx, qy)
            demo = HandleDemoBuilder(self.runner.ctx)
            had_grab = bool(self._handle_demo_grabbed_id)
            self._handle_demo_grabbed_id = None
            hover_id = self._nearest_demo_handle(qx, qy)
            demo.apply_hover(hover_id)
            if had_grab:
                self._render_demo_scene()
                self._write_report("Handle demo released")
                return True
            return False
        except Exception:
            log_exception("tool_core_diag_handle_pointer_release")
            return False

    def _handle_api_lab_pointer_press(self, qx: float, qy: float, *, shift_down: bool = False) -> bool:
        try:
            self.close_click_away_overlays()
            if not self.runner.ctx.selection.actors(owner_tool="tool_core_diag"):
                self.runner.run_api_lab_setup()
            # Do a read-only hit-test first.  Empty presses are usually camera
            # drags, so they must not clear selection or refresh guide geometry at
            # the beginning of the camera interaction.  The camera-size refresh is
            # handled on release by refresh_camera_size_after_move().
            hit = self.runner.ctx.selection.hit_test((float(qx), float(qy)), self._world_to_qt_screen, owner_tool="tool_core_diag", selectable_only=True)
            actor_id = None if hit is None else hit.actor_id
            if actor_id is None:
                # Empty click clears selection, but empty drag without Shift is
                # camera navigation.  Do not start the rectangle or repaint at
                # press time; decide on release whether it was a click or an
                # orbit drag.  Box selection is explicitly Shift + left drag.
                had_selection = bool(self.runner.ctx.selection.ids())
                self._api_lab_empty_press_cleared = had_selection
                self._api_lab_empty_press_had_selection = had_selection
                self._api_lab_empty_press_start = (float(qx), float(qy))
                if had_selection and not bool(shift_down):
                    self.runner.api_lab.clear_selection(render=False)
                self._selection_drag_last_world = None
                self._api_lab_box_active = False
                if bool(shift_down) and getattr(self.runner.ctx.selection_box.config, "enabled", False):
                    self.runner.ctx.selection_box.begin((float(qx), float(qy)), mode=None)
                    # The Shift-drag gesture is owned by the API lab; consuming
                    # the press prevents the camera from starting an orbit.
                    return True
                return False
            self._api_lab_empty_press_cleared = False
            actor_id = self.runner.api_lab.select_at((float(qx), float(qy)), self._world_to_qt_screen, additive=bool(shift_down))
            self._selection_drag_depth = self._display_depth_for_actor(actor_id)
            world = self._qt_to_world_at_demo_depth(qx, qy, self._selection_drag_depth)
            self._selection_drag_last_world = world
            grabbed = self.runner.api_lab.begin_grab_if_possible(actor_id, (float(qx), float(qy)), world)
            self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            self._write_report("API Lab picked" if not grabbed else "API Lab grabbed")
            return True
        except Exception:
            log_exception("tool_core_diag_api_lab_pointer_press")
            return False

    def _handle_api_lab_pointer_move(self, qx: float, qy: float, *, buttons_down: bool = False) -> bool:
        try:
            if not self.runner.ctx.selection.actors(owner_tool="tool_core_diag"):
                return False
            if buttons_down and self.runner.ctx.selection_box.pending and not self.runner.ctx.selection.state.grab_active:
                active = self.runner.ctx.selection_box.update((float(qx), float(qy)))
                if active:
                    self._api_lab_box_active = True
                    self._show_api_lab_box_overlay(qx, qy)
                    return True
                return False
            if buttons_down and self.runner.ctx.selection.state.grab_active:
                world = self._qt_to_world_at_demo_depth(qx, qy, self._selection_drag_depth)
                last = self._selection_drag_last_world
                if world is None or last is None:
                    return False
                delta = (float(world[0]) - float(last[0]), float(world[1]) - float(last[1]), float(world[2]) - float(last[2]))
                moved = self.runner.api_lab.move_selected(delta)
                self._selection_drag_last_world = world
                if moved:
                    self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
                    return True
                return False
            if buttons_down:
                return False
            previous_hover = self.runner.ctx.selection.state.hover_id
            actor_id = self.runner.api_lab.hit_actor((float(qx), float(qy)), self._world_to_qt_screen)
            if actor_id != previous_hover:
                self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            return bool(actor_id)
        except Exception:
            log_exception("tool_core_diag_api_lab_pointer_move")
            return False

    def _handle_api_lab_pointer_release(self, qx: float, qy: float) -> bool:
        try:
            had_grab = bool(self.runner.ctx.selection.state.grab_active)
            empty_cleared = bool(getattr(self, "_api_lab_empty_press_cleared", False))
            if self.runner.ctx.selection_box.pending:
                self._hide_api_lab_box_overlay()
                if self.runner.ctx.selection_box.active:
                    result = self.runner.ctx.selection_box.finish((float(qx), float(qy)), world_to_screen=self._world_to_qt_screen)
                    self.runner.api_lab.render_visuals()
                    self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
                    self._api_lab_empty_press_cleared = False
                    self._api_lab_empty_press_start = None
                    self._api_lab_empty_press_had_selection = False
                    self._api_lab_box_active = False
                    self._write_report(f"API Lab box selection: tool={len(result.tool_actor_ids)} scene={len(result.scene_object_ids)}")
                    return True
                self.runner.ctx.selection_box.cancel()
            self.runner.api_lab.end_grab()
            self._selection_drag_last_world = None
            self._api_lab_box_active = False
            start = self._api_lab_empty_press_start
            had_empty_selection = bool(self._api_lab_empty_press_had_selection)
            self._api_lab_empty_press_cleared = False
            self._api_lab_empty_press_start = None
            self._api_lab_empty_press_had_selection = False
            empty_click = False
            if start is not None:
                moved = max(abs(float(qx) - float(start[0])), abs(float(qy) - float(start[1])))
                empty_click = moved <= 5.0
            if had_grab or (empty_click and had_empty_selection):
                if empty_click and had_empty_selection:
                    self.runner.api_lab.clear_selection(render=True)
                self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
                self._write_report("API Lab selection cleared" if empty_click and had_empty_selection and not had_grab else "API Lab released")
                return True
            return False
        except Exception:
            log_exception("tool_core_diag_api_lab_pointer_release")
            return False

    def _handle_selection_pointer_press(self, qx: float, qy: float, *, shift_down: bool = False) -> bool:
        try:
            self.close_click_away_overlays()
            demo = SelectionDemoBuilder(self.runner.ctx)
            if not self.runner.ctx.selection.actors(owner_tool="tool_core_diag"):
                demo.build_demo()
            actor_id = demo.select_at((float(qx), float(qy)), self._world_to_qt_screen, additive=bool(shift_down))
            if actor_id is None:
                demo.render_visuals()
                self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
                self._write_report("Selection demo cleared")
                return False
            self._selection_drag_depth = self._display_depth_for_actor(actor_id)
            self._selection_drag_last_world = self._qt_to_world_at_demo_depth(qx, qy, self._selection_drag_depth)
            grabbed = demo.begin_grab_if_possible(actor_id, (float(qx), float(qy)))
            demo.render_visuals()
            self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            self._write_report("Selection demo picked" if not grabbed else "Selection demo grabbed")
            return True
        except Exception:
            log_exception("tool_core_diag_selection_pointer_press")
            return False

    def _handle_selection_pointer_move(self, qx: float, qy: float, *, buttons_down: bool = False) -> bool:
        try:
            demo = SelectionDemoBuilder(self.runner.ctx)
            if not self.runner.ctx.selection.actors(owner_tool="tool_core_diag"):
                return False
            if buttons_down and self.runner.ctx.selection_box.pending and not self.runner.ctx.selection.state.grab_active:
                active = self.runner.ctx.selection_box.update((float(qx), float(qy)))
                if active:
                    self._api_lab_box_active = True
                    self._show_api_lab_box_overlay(qx, qy)
                    return True
                return False
            if buttons_down and self.runner.ctx.selection.state.grab_active:
                world = self._qt_to_world_at_demo_depth(qx, qy, self._selection_drag_depth)
                last = self._selection_drag_last_world
                if world is None or last is None:
                    return False
                delta = (float(world[0]) - float(last[0]), float(world[1]) - float(last[1]), float(world[2]) - float(last[2]))
                moved = demo.move_selected(delta)
                self._selection_drag_last_world = world
                if moved:
                    demo.render_visuals()
                    self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
                    return True
                return False
            if buttons_down:
                return False
            previous_hover = self.runner.ctx.selection.state.hover_id
            actor_id = demo.hit_actor((float(qx), float(qy)), self._world_to_qt_screen)
            if actor_id != previous_hover:
                demo.render_visuals()
                self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            return bool(actor_id)
        except Exception:
            log_exception("tool_core_diag_selection_pointer_move")
            return False

    def _handle_selection_pointer_release(self, qx: float, qy: float) -> bool:
        try:
            had_grab = bool(self.runner.ctx.selection.state.grab_active)
            self.runner.ctx.selection.end_grab()
            self._selection_drag_last_world = None
            if had_grab:
                SelectionDemoBuilder(self.runner.ctx).render_visuals()
                self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
                self._write_report("Selection demo released")
                return True
            return False
        except Exception:
            log_exception("tool_core_diag_selection_pointer_release")
            return False

    def _ensure_api_lab_box_overlay(self):
        try:
            band = getattr(self, "_api_lab_box_band", None)
            if band is None:
                from ..ui.selection_box_overlay import SelectionBoxOverlay
                band = SelectionBoxOverlay(self.owner.plotter)
                self._api_lab_box_band = band
            return band
        except Exception:
            log_exception("tool_core_diag_api_lab_box_overlay")
            return None

    def _show_api_lab_box_overlay(self, qx: float, qy: float) -> None:
        try:
            from PySide6.QtCore import QPoint, QRect
            start = self.runner.ctx.selection_box.state.start_screen_pos
            if start is None:
                return
            rect = QRect(QPoint(int(round(start[0])), int(round(start[1]))), QPoint(int(round(qx)), int(round(qy)))).normalized()
            band = self._ensure_api_lab_box_overlay()
            if band is not None:
                try:
                    band.set_selection_rect(rect)
                except Exception:
                    band.setGeometry(rect)
                try:
                    band.raise_()
                except Exception:
                    pass
                if not band.isVisible():
                    band.show()
        except Exception:
            log_exception("tool_core_diag_api_lab_box_show")

    def _hide_api_lab_box_overlay(self) -> None:
        try:
            band = getattr(self, "_api_lab_box_band", None)
            if band is not None:
                try:
                    band.clear_selection_rect()
                except Exception:
                    pass
                band.hide()
        except Exception:
            pass

    def _display_depth_for_actor(self, actor_id: str) -> float:
        try:
            actor = self.runner.ctx.selection.actor(actor_id)
            if actor is not None and actor.primary_position is not None:
                _x, _y, z = self.owner._world_to_display(tuple(float(v) for v in actor.primary_position))
                return float(z)
        except Exception:
            pass
        return 0.5

    def _has_handle_demo(self) -> bool:
        return any(str(handle.kind).startswith("demo_") for handle in self.runner.ctx.gizmos.handles(owner_tool="tool_core_diag"))

    def _has_camera_sized_guides(self) -> bool:
        return any(
            str(handle.kind).startswith(("demo_", "style_", "api_lab_"))
            for handle in self.runner.ctx.gizmos.handles(owner_tool="tool_core_diag")
        )

    def _nearest_demo_handle(self, qx: float, qy: float) -> str | None:
        demo = HandleDemoBuilder(self.runner.ctx)
        return demo.nearest_grabbable((float(qx), float(qy)), self._world_to_qt_screen)

    def _world_to_qt_screen(self, world_pos) -> tuple[float, float]:
        try:
            x, y_vtk, _z = self.owner._world_to_display(tuple(float(v) for v in world_pos))
            h = float(self.owner.plotter.height())
            return (float(x), float(h) - float(y_vtk))
        except Exception:
            return (float(world_pos[0]), float(world_pos[1]))

    def _display_depth_for_handle(self, handle_id: str) -> float:
        try:
            for handle in self.runner.ctx.gizmos.handles(owner_tool="tool_core_diag"):
                if handle.id == handle_id:
                    _x, _y, z = self.owner._world_to_display(tuple(float(v) for v in handle.position))
                    return float(z)
        except Exception:
            pass
        return 0.5

    def _qt_to_world_at_demo_depth(self, qx: float, qy: float, depth: float):
        try:
            h = float(self.owner.plotter.height())
            return tuple(float(v) for v in self.owner._display_to_world_at_depth(float(qx), h - float(qy), float(depth)))
        except Exception:
            return None

    def _render_demo_scene(self) -> None:
        self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)



# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
class TextureProjectionToolLayer:
    """Projected texture tool: image selection, UV projection, metadata preview."""
    def _texture_projection_controller(self):
        controller = getattr(self, "texture_projection_controller", None)
        if controller is None:
            from ..application.texture_projection_controller import TextureProjectionController
            controller = TextureProjectionController.create(self.app_context)
            self.texture_projection_controller = controller
        return controller
    def _texture_projection_selected_indices(self) -> list[int]:
        return self._texture_projection_controller()._texture_projection_selected_indices()
    def _clear_texture_projection_tool_state(self) -> None:
        return self._texture_projection_controller()._clear_texture_projection_tool_state()
    def _initialize_texture_projection_tool(self, render: bool | None = None) -> None:
        return self._texture_projection_controller()._initialize_texture_projection_tool(render=render)
    def _choose_texture_projection_file(self) -> None:
        return self._texture_projection_controller()._choose_texture_projection_file()
    def _register_texture_asset(self, path: Path):
        return self._texture_projection_controller()._register_texture_asset(path)
    def _texture_projection_params_from_ui(self, **kwargs):
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "params_from_context"):
            return tool.params_from_context(context, **kwargs)
        return self._texture_projection_controller()._texture_projection_params_from_ui(**kwargs)
    def _update_texture_projection_report(self, *, preview_meshes=None, error: str | None = None) -> None:
        return self._texture_projection_controller()._update_texture_projection_report(preview_meshes=preview_meshes, error=error)
    def _texture_projection_anchor_from_pick(self, idx: int, point, normal, cell_id: int) -> dict[str, object]:
        return self._texture_projection_controller()._texture_projection_anchor_from_pick(idx, point, normal, cell_id)
    def _mesh_triangle_normal(self, mesh, cell_id: int) -> tuple[float, float, float] | None:
        return self._texture_projection_controller()._mesh_triangle_normal(mesh, cell_id)
    def _pick_texture_projection_anchor_at(self, x: int, y: int):
        return self._texture_projection_controller()._pick_texture_projection_anchor_at(x, y)
    def _pick_texture_projection_anchor_from_qt_pos(self, qx: float, qy: float):
        return self._texture_projection_controller()._pick_texture_projection_anchor_from_qt_pos(qx, qy)
    def generate_texture_projection_preview(self, **kwargs) -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None:
            target = kwargs.pop("target_index", None)
            if target is not None and hasattr(tool, "preview_index"):
                tool.preview_index(context, int(target), **kwargs)
                return None
            if hasattr(tool, "preview_selected"):
                tool.preview_selected(context, **kwargs)
                return None
        return self._texture_projection_controller().generate_texture_projection_preview(**kwargs)
    def _creator_texture_projection_tool(self):
        try:
            from ..tooling.ids import TOOL_TEXTURE_PROJECTION
            from ..tooling.registry import get_studio_tool
            active = getattr(self, "active_tool", None)
            if active != TOOL_TEXTURE_PROJECTION:
                return None
            tool = get_studio_tool(TOOL_TEXTURE_PROJECTION)
            return tool if hasattr(tool, "preview_index") else None
        except Exception:
            return None
    def apply_texture_projection_to_index(self, idx: int, **kwargs) -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None:
            tool.preview_index(context, int(idx), **kwargs)
            return None
        return self._texture_projection_controller().apply_texture_projection_to_index(idx, **kwargs)
    def apply_texture_projection_from_pick(self, idx: int, point, normal, cell_id: int) -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None:
            tool.preview_index(context, int(idx), seed_face_index=int(cell_id), projection_origin=point, projection_normal=normal)
            return None
        return self._texture_projection_controller().apply_texture_projection_from_pick(idx, point, normal, cell_id)
    def clear_texture_projection_selected(self) -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "clear_selected"):
            tool.clear_selected(context)
            return None
        return self._texture_projection_controller().clear_texture_projection_selected()
    def _texture_gizmo_controller(self):
        controller = getattr(self, "texture_gizmo_controller", None)
        if controller is None:
            from ..application.texture_gizmo_controller import TextureGizmoController
            controller = TextureGizmoController.create(self.app_context)
            self.texture_gizmo_controller = controller
        return controller
    def _texture_rotation_target(self):
        return self._texture_gizmo_controller()._texture_rotation_target()
    def _texture_rotation_ring_basis(self, normal):
        return self._texture_gizmo_controller()._texture_rotation_ring_basis(normal)
    def _texture_rotation_world_radius_for_screen(self, center, radius_px: float=72.0) -> float:
        return self._texture_gizmo_controller()._texture_rotation_world_radius_for_screen(center, radius_px)
    def _texture_rotation_project_qt(self, point) -> tuple[float, float] | None:
        return self._texture_gizmo_controller()._texture_rotation_project_qt(point)
    @staticmethod
    def _texture_rotation_point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        from ..application.texture_gizmo_controller import texture_rotation_point_segment_distance
        return texture_rotation_point_segment_distance(px, py, ax, ay, bx, by)
    def _pick_texture_rotation_gizmo_from_qt_pos(self, qx: float, qy: float):
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "pick_projector_handle"):
            picked = tool.pick_projector_handle(context, qx, qy)
            if picked is not None:
                return picked
        return self._texture_gizmo_controller()._pick_texture_rotation_gizmo_from_qt_pos(qx, qy)
    def _texture_move_source_index_for_target(self, target_idx: int, decal_mesh) -> int | None:
        return self._texture_gizmo_controller()._texture_move_source_index_for_target(target_idx, decal_mesh)
    @staticmethod
    def _texture_vec3_add(a, b):
        from ..application.texture_gizmo_controller import texture_vec3_add
        return texture_vec3_add(a, b)
    @staticmethod
    def _texture_vec3_scale(v, s: float):
        from ..application.texture_gizmo_controller import texture_vec3_scale
        return texture_vec3_scale(v, s)
    def _texture_move_basis_from_target(self, mesh, normal):
        return self._texture_gizmo_controller()._texture_move_basis_from_target(mesh, normal)
    def _texture_move_screen_matrix(self, center, u_axis, v_axis):
        return self._texture_gizmo_controller()._texture_move_screen_matrix(center, u_axis, v_axis)
    def _texture_move_delta_from_screen(self, dx: float, dy: float) -> tuple[float, float] | None:
        return self._texture_gizmo_controller()._texture_move_delta_from_screen(dx, dy)
    def _texture_move_apply_origin(self, origin, *, source: str='move') -> None:
        return self._texture_gizmo_controller()._texture_move_apply_origin(origin, source=source)
    def _texture_projection_set_mesh_projection_values(self, mesh, params, *, origin=None) -> None:
        return self._texture_gizmo_controller()._texture_projection_set_mesh_projection_values(mesh, params, origin=origin)
    def _texture_projection_set_actor_uvs_fast(self, idx: int, mesh) -> bool:
        return self._texture_gizmo_controller()._texture_projection_set_actor_uvs_fast(idx, mesh)
    def _texture_projection_update_decal_live(self, idx: int, mesh, params, *, origin=None) -> bool:
        return self._texture_gizmo_controller()._texture_projection_update_decal_live(idx, mesh, params, origin=origin)
    def _texture_projection_update_attached_mesh_live(self, idx: int, mesh, params, *, origin=None) -> bool:
        return self._texture_gizmo_controller()._texture_projection_update_attached_mesh_live(idx, mesh, params, origin=origin)
    def _texture_projection_live_update_current_target(self, *, origin=None, source: str='drag', refresh_gizmo: bool=False) -> bool:
        return self._texture_gizmo_controller()._texture_projection_live_update_current_target(origin=origin, source=source, refresh_gizmo=refresh_gizmo)
    def _texture_rotation_screen_angle(self, qx: float, qy: float, center_qt=None) -> float | None:
        return self._texture_gizmo_controller()._texture_rotation_screen_angle(qx, qy, center_qt)
    def _texture_rotation_event_qpos(self, obj, event) -> tuple[float, float] | None:
        return self._texture_gizmo_controller()._texture_rotation_event_qpos(obj, event)
    def _texture_rotation_buttons_diag(self, event) -> str:
        return self._texture_gizmo_controller()._texture_rotation_buttons_diag(event)
    def _handle_texture_rotation_global_mouse_event(self, obj, event) -> bool:
        return self._texture_gizmo_controller()._handle_texture_rotation_global_mouse_event(obj, event)
    def _texture_rotation_qt_from_vtk_event(self) -> tuple[float, float] | None:
        return self._texture_gizmo_controller()._texture_rotation_qt_from_vtk_event()
    def _install_texture_rotation_global_event_filter(self) -> None:
        return self._texture_gizmo_controller()._install_texture_rotation_global_event_filter()
    def _remove_texture_rotation_global_event_filter(self) -> None:
        return self._texture_gizmo_controller()._remove_texture_rotation_global_event_filter()
    def _install_texture_rotation_vtk_observers(self) -> None:
        return self._texture_gizmo_controller()._install_texture_rotation_vtk_observers()
    def _remove_texture_rotation_vtk_observers(self) -> None:
        return self._texture_gizmo_controller()._remove_texture_rotation_vtk_observers()
    def _ensure_texture_rotation_poll_timer(self) -> None:
        return self._texture_gizmo_controller()._ensure_texture_rotation_poll_timer()
    def _start_texture_rotation_poll_timer(self) -> None:
        return self._texture_gizmo_controller()._start_texture_rotation_poll_timer()
    def _stop_texture_rotation_poll_timer(self) -> None:
        return self._texture_gizmo_controller()._stop_texture_rotation_poll_timer()
    def _texture_rotation_current_cursor_qpos(self) -> tuple[float, float] | None:
        return self._texture_gizmo_controller()._texture_rotation_current_cursor_qpos()
    def _poll_texture_rotation_gizmo_drag(self) -> None:
        return self._texture_gizmo_controller()._poll_texture_rotation_gizmo_drag()
    def _make_texture_rotation_ring_mesh(self, center, normal, radius: float, tube_radius: float):
        return self._texture_gizmo_controller()._make_texture_rotation_ring_mesh(center, normal, radius, tube_radius)
    def _make_texture_move_center_mesh(self, center, radius: float):
        return self._texture_gizmo_controller()._make_texture_move_center_mesh(center, radius)
    def update_texture_rotation_gizmo(self, render: bool=True) -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "render_projector_ui"):
            return tool.render_projector_ui(context, render=render)
        return self._texture_gizmo_controller().update_texture_rotation_gizmo(render)
    def _start_texture_rotation_gizmo_drag(self, qx: float, qy: float, *, kind: str='texrot') -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "start_projector_drag"):
            if tool.start_projector_drag(context, qx, qy, kind=kind):
                return None
        return self._texture_gizmo_controller()._start_texture_rotation_gizmo_drag(qx, qy, kind=kind)
    def _update_texture_rotation_gizmo_drag(self, qx: float, qy: float, *, source: str='direct') -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "update_projector_drag"):
            if tool.update_projector_drag(context, qx, qy, source=source):
                return None
        return self._texture_gizmo_controller()._update_texture_rotation_gizmo_drag(qx, qy, source=source)
    def _update_texture_move_gizmo_drag(self, qx: float, qy: float, *, source: str='direct') -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "update_projector_drag"):
            if tool.update_projector_drag(context, qx, qy, source=source):
                return None
        return self._texture_gizmo_controller()._update_texture_move_gizmo_drag(qx, qy, source=source)
    def _finish_texture_rotation_gizmo_drag(self) -> None:
        tool = self._creator_texture_projection_tool()
        context = getattr(self, "app_context", None) or getattr(self, "context", None)
        if tool is not None and context is not None and hasattr(tool, "finish_projector_drag"):
            if tool.finish_projector_drag(context):
                return None
        return self._texture_gizmo_controller()._finish_texture_rotation_gizmo_drag()

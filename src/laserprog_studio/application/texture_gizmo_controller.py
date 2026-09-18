# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..app_context import AppContext
from .owner_delegating_controller import OwnerDelegatingController
from .texture_gizmo_drag_service import TextureGizmoDragService
from .texture_gizmo_event_service import TextureGizmoEventService
from .texture_gizmo_live_update_service import TextureGizmoLiveUpdateService
from .texture_gizmo_math import (
    texture_rotation_point_segment_distance,
    texture_vec3_add,
    texture_vec3_scale,
)
from .texture_gizmo_qt import qapplication, qevent, qt, qtimer
from .texture_gizmo_render_service import TextureGizmoRenderService
from .texture_gizmo_target_service import TextureGizmoTargetService


def _qevent() -> Any:
    return qevent()


def _qtimer() -> Any:
    return qtimer()


def _qt() -> Any:
    return qt()


def _qapplication() -> Any:
    return qapplication()


class TextureGizmoController(OwnerDelegatingController):
    """Facade for TEX rotation/move gizmo services.

    Pass 11 keeps the public method surface intact while splitting the
    former 1.5k-line controller into small, named services: target/picking,
    live UV updates, Qt/VTK events, rendering and drag orchestration.
    """

    def __init__(self, context: AppContext):
        super().__init__(context)
        object.__setattr__(self, "_local_target_service", TextureGizmoTargetService(context))
        object.__setattr__(self, "_local_live_update_service", TextureGizmoLiveUpdateService(context))
        object.__setattr__(self, "_local_event_service", TextureGizmoEventService(context))
        object.__setattr__(self, "_local_render_service", TextureGizmoRenderService(context))
        object.__setattr__(self, "_local_drag_service", TextureGizmoDragService(context))

    @classmethod
    def create(cls, context: AppContext) -> "TextureGizmoController":
        return cls(context)

    def _texture_rotation_target(self):
        return self._local_target_service._texture_rotation_target()

    def _texture_rotation_ring_basis(self, normal):
        return self._local_target_service._texture_rotation_ring_basis(normal)

    def _texture_rotation_world_radius_for_screen(self, center, radius_px: float = 72.0) -> float:
        return self._local_target_service._texture_rotation_world_radius_for_screen(center, radius_px)

    def _texture_rotation_project_qt(self, point) -> tuple[float, float] | None:
        return self._local_target_service._texture_rotation_project_qt(point)

    @staticmethod
    def _texture_rotation_point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        return texture_rotation_point_segment_distance(px, py, ax, ay, bx, by)

    def _pick_texture_rotation_gizmo_from_qt_pos(self, qx: float, qy: float):
        return self._local_target_service._pick_texture_rotation_gizmo_from_qt_pos(qx, qy)

    def _texture_move_source_index_for_target(self, target_idx: int, decal_mesh) -> int | None:
        return self._local_target_service._texture_move_source_index_for_target(target_idx, decal_mesh)

    @staticmethod
    def _texture_vec3_add(a, b):
        return texture_vec3_add(a, b)

    @staticmethod
    def _texture_vec3_scale(v, s: float):
        return texture_vec3_scale(v, s)

    def _texture_move_basis_from_target(self, mesh, normal):
        return self._local_target_service._texture_move_basis_from_target(mesh, normal)

    def _texture_move_screen_matrix(self, center, u_axis, v_axis):
        return self._local_target_service._texture_move_screen_matrix(center, u_axis, v_axis)

    def _texture_move_delta_from_screen(self, dx: float, dy: float) -> tuple[float, float] | None:
        return self._local_target_service._texture_move_delta_from_screen(dx, dy)

    def _texture_move_apply_origin(self, origin, *, source: str = "move") -> None:
        return self._local_target_service._texture_move_apply_origin(origin, source=source)

    def _texture_projection_set_mesh_projection_values(self, mesh, params, *, origin=None) -> None:
        return self._local_live_update_service._texture_projection_set_mesh_projection_values(mesh, params, origin=origin)

    def _texture_projection_set_actor_uvs_fast(self, idx: int, mesh) -> bool:
        return self._local_live_update_service._texture_projection_set_actor_uvs_fast(idx, mesh)

    def _texture_projection_update_decal_live(self, idx: int, mesh, params, *, origin=None) -> bool:
        return self._local_live_update_service._texture_projection_update_decal_live(idx, mesh, params, origin=origin)

    def _texture_projection_update_attached_mesh_live(self, idx: int, mesh, params, *, origin=None) -> bool:
        return self._local_live_update_service._texture_projection_update_attached_mesh_live(idx, mesh, params, origin=origin)

    def _texture_projection_live_update_current_target(self, *, origin=None, source: str = "drag", refresh_gizmo: bool = False) -> bool:
        return self._local_live_update_service._texture_projection_live_update_current_target(origin=origin, source=source, refresh_gizmo=refresh_gizmo)

    def _texture_rotation_screen_angle(self, qx: float, qy: float, center_qt=None) -> float | None:
        return self._local_drag_service._texture_rotation_screen_angle(qx, qy, center_qt)

    def _texture_rotation_event_qpos(self, obj, event) -> tuple[float, float] | None:
        return self._local_event_service._texture_rotation_event_qpos(obj, event)

    def _texture_rotation_buttons_diag(self, event) -> str:
        return self._local_event_service._texture_rotation_buttons_diag(event)

    def _handle_texture_rotation_global_mouse_event(self, obj, event) -> bool:
        return self._local_event_service._handle_texture_rotation_global_mouse_event(obj, event)

    def _texture_rotation_qt_from_vtk_event(self) -> tuple[float, float] | None:
        return self._local_event_service._texture_rotation_qt_from_vtk_event()

    def _install_texture_rotation_global_event_filter(self) -> None:
        return self._local_event_service._install_texture_rotation_global_event_filter()

    def _remove_texture_rotation_global_event_filter(self) -> None:
        return self._local_event_service._remove_texture_rotation_global_event_filter()

    def _install_texture_rotation_vtk_observers(self) -> None:
        return self._local_event_service._install_texture_rotation_vtk_observers()

    def _remove_texture_rotation_vtk_observers(self) -> None:
        return self._local_event_service._remove_texture_rotation_vtk_observers()

    def _ensure_texture_rotation_poll_timer(self) -> None:
        return self._local_event_service._ensure_texture_rotation_poll_timer()

    def _start_texture_rotation_poll_timer(self) -> None:
        return self._local_event_service._start_texture_rotation_poll_timer()

    def _stop_texture_rotation_poll_timer(self) -> None:
        return self._local_event_service._stop_texture_rotation_poll_timer()

    def _texture_rotation_current_cursor_qpos(self) -> tuple[float, float] | None:
        return self._local_event_service._texture_rotation_current_cursor_qpos()

    def _poll_texture_rotation_gizmo_drag(self) -> None:
        return self._local_event_service._poll_texture_rotation_gizmo_drag()

    def _make_texture_rotation_ring_mesh(self, center, normal, radius: float, tube_radius: float):
        return self._local_render_service._make_texture_rotation_ring_mesh(center, normal, radius, tube_radius)

    def _make_texture_move_center_mesh(self, center, radius: float):
        return self._local_render_service._make_texture_move_center_mesh(center, radius)

    def update_texture_rotation_gizmo(self, render: bool = True) -> None:
        return self._local_render_service.update_texture_rotation_gizmo(render)

    def _start_texture_rotation_gizmo_drag(self, qx: float, qy: float, *, kind: str = "texrot") -> None:
        return self._local_drag_service._start_texture_rotation_gizmo_drag(qx, qy, kind=kind)

    def _update_texture_rotation_gizmo_drag(self, qx: float, qy: float, *, source: str = "direct") -> None:
        return self._local_drag_service._update_texture_rotation_gizmo_drag(qx, qy, source=source)

    def _update_texture_move_gizmo_drag(self, qx: float, qy: float, *, source: str = "direct") -> None:
        return self._local_drag_service._update_texture_move_gizmo_drag(qx, qy, source=source)

    def _finish_texture_rotation_gizmo_drag(self) -> None:
        return self._local_drag_service._finish_texture_rotation_gizmo_drag()


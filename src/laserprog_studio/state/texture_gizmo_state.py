# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextureGizmoState:
    """Runtime fields owned by the TEX rotation/move gizmo.

    Window bridge code still reads the underscored attributes on ``MainWindow``.
    ``apply_to_window`` keeps those window fields synchronized while centralising the default
    values in one documented state object for future controller-only access.
    """

    rotation_pressed: bool = False
    rotation_press_pos: tuple[float, float] | None = None
    drag_active: bool = False
    drag_kind: str | None = None
    start_qpos: tuple[float, float] | None = None
    start_vector: Any = None
    center: Any = None
    normal: Any = None
    center_qt: Any = None
    start_screen_angle: float | None = None
    start_value: float = 0.0
    move_start_origin: Any = None
    move_current_origin: Any = None
    move_source_index: int | None = None
    move_u_axis: Any = None
    move_v_axis: Any = None
    move_screen_matrix: Any = None
    current_value: Any = None
    last_qpos: Any = None
    last_applied: Any = None
    target_index: int | None = None
    screen_radius_px: float = 82.0
    pick_radius_px: float = 44.0
    world_radius: float = 0.0
    ring_center: Any = None
    ring_normal: Any = None
    vtk_observer_ids: list[int] = field(default_factory=list)
    event_seq: int = 0
    update_count: int = 0
    poll_timer: Any = None
    last_poll_qpos: Any = None
    poll_count: int = 0
    global_event_filter_installed: bool = False

    def apply_to_window(self, window: Any) -> None:
        window._texture_rotation_gizmo_pressed = self.rotation_pressed
        window._texture_rotation_gizmo_press_pos = self.rotation_press_pos
        window._texture_rotation_gizmo_drag_active = self.drag_active
        window._texture_rotation_gizmo_drag_kind = self.drag_kind
        window._texture_rotation_gizmo_start_qpos = self.start_qpos
        window._texture_rotation_gizmo_start_vector = self.start_vector
        window._texture_rotation_gizmo_center = self.center
        window._texture_rotation_gizmo_normal = self.normal
        window._texture_rotation_gizmo_center_qt = self.center_qt
        window._texture_rotation_gizmo_start_screen_angle = self.start_screen_angle
        window._texture_rotation_gizmo_start_value = self.start_value
        window._texture_move_gizmo_start_origin = self.move_start_origin
        window._texture_move_gizmo_current_origin = self.move_current_origin
        window._texture_move_gizmo_source_index = self.move_source_index
        window._texture_move_gizmo_u_axis = self.move_u_axis
        window._texture_move_gizmo_v_axis = self.move_v_axis
        window._texture_move_gizmo_screen_matrix = self.move_screen_matrix
        window._texture_rotation_gizmo_current_value = self.current_value
        window._texture_rotation_gizmo_last_qpos = self.last_qpos
        window._texture_rotation_gizmo_last_applied = self.last_applied
        window._texture_rotation_gizmo_target_index = self.target_index
        window._texture_rotation_gizmo_screen_radius_px = self.screen_radius_px
        window._texture_rotation_gizmo_pick_radius_px = self.pick_radius_px
        window._texture_rotation_gizmo_radius_world = self.world_radius
        window._texture_rotation_gizmo_ring_center = self.ring_center
        window._texture_rotation_gizmo_ring_normal = self.ring_normal
        window._texture_rotation_gizmo_vtk_observer_ids = list(self.vtk_observer_ids)
        window._texture_rotation_gizmo_event_seq = self.event_seq
        window._texture_rotation_gizmo_update_count = self.update_count
        window._texture_rotation_gizmo_poll_timer = self.poll_timer
        window._texture_rotation_gizmo_last_poll_qpos = self.last_poll_qpos
        window._texture_rotation_gizmo_poll_count = self.poll_count
        window._global_event_filter_installed = self.global_event_filter_installed

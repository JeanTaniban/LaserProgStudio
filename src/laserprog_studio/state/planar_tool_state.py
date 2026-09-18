# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..planar_tools import FixedPlanarView, LockedPlaneSpec


@dataclass(slots=True)
class PlanarToolState:
    """Runtime state shared by locked-plane drawing tools."""

    active: bool = False
    active_tool_id: str | None = None
    locked_view: FixedPlanarView | None = None
    locked_plane: LockedPlaneSpec | None = None
    previous_camera_view_mode: str = "free"
    previous_camera_snapshot: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], float] | None = None
    payload: Any | None = None
    pointer_drag_active: bool = False
    pointer_drag_mode: str | None = None
    pending_plane_point: tuple[float, float] | None = None
    first_point_depth_resolved: bool = False
    last_edit_warning: str = ""
    last_pointer_raw_plane: tuple[float, float] | None = None
    snap_preview_plane_point: tuple[float, float] | None = None
    snap_preview_raw_plane: tuple[float, float] | None = None
    snap_preview_label: str = ""
    scene_snap_anchor_cache: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    scene_snap_edge_cache: tuple[tuple[tuple[float, float], tuple[float, float]], ...] = field(default_factory=tuple)
    scene_snap_compiled_cache: Any | None = None
    payload_snap_signature: Any | None = None
    payload_snap_anchor_cache: tuple[tuple[float, float], ...] = field(default_factory=tuple)
    payload_snap_compiled_cache: Any | None = None
    drag_snap_anchor_cache: tuple[tuple[float, float], ...] | None = None
    drag_snap_edge_cache: tuple[tuple[tuple[float, float], tuple[float, float]], ...] | None = None
    drag_snap_compiled_cache: Any | None = None
    last_preview_draw_monotonic: float = 0.0

    def begin(self, *, tool_id: str, view: FixedPlanarView, plane: LockedPlaneSpec, previous_camera_view_mode: str, previous_camera_snapshot: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], float] | None = None) -> None:
        self.active = True
        self.active_tool_id = str(tool_id)
        self.locked_view = view
        self.locked_plane = plane
        self.previous_camera_view_mode = str(previous_camera_view_mode or "free")
        self.previous_camera_snapshot = previous_camera_snapshot
        self.previous_camera_snapshot = None
        self.payload = None
        self.pointer_drag_active = False
        self.pointer_drag_mode = None
        self.pending_plane_point = None
        self.first_point_depth_resolved = False
        self.last_edit_warning = ""
        self.last_pointer_raw_plane = None
        self.snap_preview_plane_point = None
        self.snap_preview_raw_plane = None
        self.snap_preview_label = ""
        self.scene_snap_anchor_cache = ()
        self.scene_snap_edge_cache = ()
        self.scene_snap_compiled_cache = None
        self.payload_snap_signature = None
        self.payload_snap_anchor_cache = ()
        self.payload_snap_compiled_cache = None
        self.drag_snap_anchor_cache = None
        self.drag_snap_edge_cache = None
        self.drag_snap_compiled_cache = None
        self.last_preview_draw_monotonic = 0.0

    def end(self) -> None:
        self.active = False
        self.active_tool_id = None
        self.locked_view = None
        self.locked_plane = None
        self.previous_camera_snapshot = None
        self.payload = None
        self.pointer_drag_active = False
        self.pointer_drag_mode = None
        self.pending_plane_point = None
        self.first_point_depth_resolved = False
        self.last_edit_warning = ""
        self.last_pointer_raw_plane = None
        self.snap_preview_plane_point = None
        self.snap_preview_raw_plane = None
        self.snap_preview_label = ""
        self.scene_snap_anchor_cache = ()
        self.scene_snap_edge_cache = ()
        self.scene_snap_compiled_cache = None
        self.payload_snap_signature = None
        self.payload_snap_anchor_cache = ()
        self.payload_snap_compiled_cache = None
        self.drag_snap_anchor_cache = None
        self.drag_snap_edge_cache = None
        self.drag_snap_compiled_cache = None
        self.last_preview_draw_monotonic = 0.0

"""Viewport interaction state for the free-space Cloth tracer.

The topology/workflow machine stays headless in :mod:`state_machine`.  This
module owns only user-facing stages and transient cursor/selection state.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

Point3 = tuple[float, float, float]


class ClothUxStage(str, Enum):
    OPENING = "opening"
    MAIN = "main"
    CLOSE = "close"
    DRAW = "draw"
    PROPERTIES = "properties"
    # Compatibility states retained for old sessions/tests.
    SELECT_FACE_LOOP = "select_face_loop"
    SELECT_SOURCE_GEOMETRY = "select_source_geometry"
    SELECT_JOIN_FACES = "select_join_faces"
    TEXTILE_PROPERTIES = "textile_properties"
    SELECT_FOLD_EDGE = "select_fold_edge"
    FLAT_PREVIEW = "flat_preview"
    # Kept as a serialized/backward-compatible enum member.  New Cloth sessions
    # never enter it: free-space drawing replaced mandatory workplanes.
    PICK_PLANE = "pick_plane"


@dataclass(slots=True)
class ClothInteractionState:
    stage: ClothUxStage = ClothUxStage.OPENING
    # ``active_plane`` is now only a transient editing/construction plane used by
    # point dragging. It is never a prerequisite for drawing.
    active_plane: Any | None = None
    active_plane_label: str = "Free 3D"
    reference_object_id: str | None = None
    reference_face_index: int | None = None
    hovered_object_id: str | None = None
    hovered_face_vertices: tuple[Point3, ...] = ()
    hovered_curve_id: str | None = None
    hovered_point_id: str | None = None
    hovered_patch_id: str | None = None
    hovered_patch_group_ids: tuple[str, ...] = ()
    cursor_world: Point3 | None = None
    cursor_snap_label: str = "Free 3D"
    cursor_source: str = "free"
    cursor_snap_kind: str = "free"
    cursor_snapped: bool = False
    cursor_source_id: str | None = None
    cursor_metadata: dict[str, Any] | None = None
    selected_curve_ids: tuple[str, ...] = ()
    selected_fold_id: str | None = None
    selected_pattern_curve_id: str | None = None
    pattern_operation: str = "fold"
    pattern_angle_degrees: float = 0.0
    pattern_radius_mm: float = 0.0
    flat_preview_mesh: Any | None = None
    join_proposals: tuple[Any, ...] = ()
    join_proposal_index: int = 0
    editing_output_kind: str = "folded"
    source_flat_scene_id: str | None = None
    message: str = "Draw directly in 3D or hover an existing Cloth to edit it."
    camera_interaction_active: bool = False

    def reset(self) -> None:
        fresh = ClothInteractionState()
        for name in self.__dataclass_fields__:
            setattr(self, name, getattr(fresh, name))

    def set_construction_plane(self, plane: Any | None, *, label: str = "Free 3D") -> None:
        self.active_plane = plane
        self.active_plane_label = str(label)

    # Compatibility helper for old saved/runtime call sites. It no longer gates
    # the state machine or locks drawing to the selected face.
    def set_plane(self, plane: Any, *, label: str, object_id: str | None = None, face_index: int | None = None) -> None:
        self.set_construction_plane(plane, label=label)
        self.reference_object_id = object_id
        self.reference_face_index = face_index
        self.stage = ClothUxStage.DRAW
        self.hovered_face_vertices = ()
        self.cursor_world = None

    def enter_plane_pick(self) -> None:
        # Old API calls now lead to free-space drawing instead of a dead step.
        self.enter_draw()
        self.message = "Free 3D drawing is active. Snap to scene edges or click empty space."

    def enter_main(self) -> None:
        self.stage = ClothUxStage.MAIN
        self.message = "Select mesh surface groups, textile groups or textile edges."

    def enter_close(self) -> None:
        self.stage = ClothUxStage.CLOSE
        self.message = "Review the proposed textile closure."

    def enter_properties(self) -> None:
        self.stage = ClothUxStage.PROPERTIES
        self.message = "Select textile faces only, then assign their role."

    def enter_draw(self) -> None:
        self.stage = ClothUxStage.DRAW
        self.message = "Choose a drawing tool, then place points directly in 3D."

    def enter_face_loop(self) -> None:
        self.stage = ClothUxStage.SELECT_FACE_LOOP
        self.selected_curve_ids = ()
        self.message = "Select connected boundary curves, then create the face."

    def enter_source_geometry(self) -> None:
        self.stage = ClothUxStage.SELECT_SOURCE_GEOMETRY
        self.message = "Select logical mesh surfaces. Shift adds more; Create textile faces copies them into Cloth."

    def enter_join_faces(self) -> None:
        self.stage = ClothUxStage.SELECT_JOIN_FACES
        self.join_proposals = ()
        self.join_proposal_index = 0
        self.message = "Select at least two existing textile faces. The assistant never joins raw mesh faces directly."

    def enter_textile_properties(self) -> None:
        self.stage = ClothUxStage.TEXTILE_PROPERTIES
        self.message = "Select persistent textile faces, then choose their function, layer and material."

    def enter_fold(self) -> None:
        self.stage = ClothUxStage.SELECT_FOLD_EDGE
        self.selected_fold_id = None
        self.selected_pattern_curve_id = None
        self.pattern_operation = "fold"
        self.pattern_angle_degrees = 0.0
        self.pattern_radius_mm = 0.0
        self.message = "Select a shared panel edge, then choose Fold or Cut and validate it."

    def enter_flat_preview(self, mesh: Any | None) -> None:
        self.flat_preview_mesh = mesh
        self.stage = ClothUxStage.FLAT_PREVIEW
        self.message = "Flat pattern preview. Return to editing or Apply."

    def toggle_curve_selection(self, curve_id: str) -> tuple[str, ...]:
        curve_id = str(curve_id)
        values = list(self.selected_curve_ids)
        if curve_id in values:
            values.remove(curve_id)
        else:
            values.append(curve_id)
        self.selected_curve_ids = tuple(values)
        return self.selected_curve_ids

    def clear_hover(self) -> None:
        self.hovered_object_id = None
        self.hovered_face_vertices = ()
        self.hovered_curve_id = None
        self.hovered_point_id = None
        self.hovered_patch_id = None
        self.hovered_patch_group_ids = ()
        self.cursor_world = None
        self.cursor_snap_label = "Free 3D"
        self.cursor_source = "free"
        self.cursor_snap_kind = "free"
        self.cursor_snapped = False
        self.cursor_source_id = None
        self.cursor_metadata = None


class ClothUxMachine:
    def __init__(self, state: ClothInteractionState | None = None) -> None:
        self.state = state or ClothInteractionState()

    def start_new(self, *, require_plane: bool = False) -> ClothInteractionState:  # noqa: ARG002 - compatibility
        self.state.enter_draw()
        self.state.message = "Polyline is ready. Place the first point directly in 3D."
        return self.state

    def edit_existing(self) -> ClothInteractionState:
        self.state.enter_draw()
        self.state.message = "Existing Cloth loaded. Choose a drawing or edit tool."
        return self.state

    def back(self) -> ClothInteractionState:
        stage = self.state.stage
        if stage is ClothUxStage.FLAT_PREVIEW:
            self.state.flat_preview_mesh = None
            self.state.enter_draw()
        elif stage in {ClothUxStage.CLOSE, ClothUxStage.DRAW, ClothUxStage.PROPERTIES, ClothUxStage.SELECT_FACE_LOOP, ClothUxStage.SELECT_SOURCE_GEOMETRY, ClothUxStage.SELECT_JOIN_FACES, ClothUxStage.TEXTILE_PROPERTIES, ClothUxStage.SELECT_FOLD_EDGE, ClothUxStage.PICK_PLANE}:
            self.state.selected_curve_ids = ()
            self.state.selected_fold_id = None
            self.state.selected_pattern_curve_id = None
            self.state.enter_main()
        return self.state


__all__ = ["ClothInteractionState", "ClothUxMachine", "ClothUxStage", "Point3"]

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


Point3 = tuple[float, float, float]


# Multi-turn folds are useful for tightly rolled living hinges.  Keep the
# finite range explicit so the inspector, geometry and persistence layers all
# agree instead of silently wrapping values at +/-180 degrees.
FOLDING_MIN_ANGLE_DEG = -720.0
FOLDING_MAX_ANGLE_DEG = 720.0


def clamp_folding_angle_deg(value: float) -> float:
    return float(max(FOLDING_MIN_ANGLE_DEG, min(FOLDING_MAX_ANGLE_DEG, float(value))))


class FoldingPhase(str, Enum):
    SELECT_MESH = "select_mesh"
    SELECT_FACE = "select_face"
    PLACE_START = "place_start"
    PLACE_END = "place_end"
    ADJUST_CURVE = "adjust_curve"


class FoldingMode(str, Enum):
    """Geometry strategy stored with a Folding result.

    ``FREE_CURVE`` is retained only to reopen projects created by v107-v113.
    New sessions use ``LIVING_HINGE``.
    """

    LIVING_HINGE = "living_hinge"
    FREE_CURVE = "free_curve"


class FoldingFixedSide(str, Enum):
    START = "start"
    END = "end"


class FoldingDeformationMode(str, Enum):
    """How geometry inside the flexible band is transported.

    ``PRESERVE_STRUCTURE`` adds a topology-aware local-rigidity solve after the
    smooth fold.  It is intended for meshes containing ribs, holes, bosses or
    other details whose local proportions should remain stable.

    ``UNIFORM`` applies the analytic sweep directly to every refined vertex.
    This intentionally stretches/compresses all internal details uniformly with
    the surrounding material.
    """

    PRESERVE_STRUCTURE = "preserve_structure"
    UNIFORM = "uniform"


@dataclass(slots=True)
class FoldingCurve:
    # The first four fields deliberately retain their original order so old
    # scripts/tests that construct FoldingCurve positionally remain compatible.
    start: Point3 | None = None
    end: Point3 | None = None
    control_1_offset_mm: float = 0.0
    control_2_offset_mm: float = 0.0
    mode: str = FoldingMode.FREE_CURVE.value
    fold_angle_deg: float = 0.0
    fixed_side: str = FoldingFixedSide.START.value
    # Local tangent-angle offsets, in degrees, at evenly spaced stations along
    # the neutral line.  Zero offsets reproduce the original circular profile.
    # A variable-size tuple keeps the model compact while allowing 1, 3, 5 or
    # 7 interactive shape handles.
    shape_angles_deg: tuple[float, ...] = (0.0, 0.0, 0.0)
    deformation_mode: str = FoldingDeformationMode.PRESERVE_STRUCTURE.value

    @property
    def complete(self) -> bool:
        return self.start is not None and self.end is not None

    @property
    def is_living_hinge(self) -> bool:
        return str(self.mode) == FoldingMode.LIVING_HINGE.value

    def normalized_fixed_side(self) -> str:
        return FoldingFixedSide.END.value if str(self.fixed_side) == FoldingFixedSide.END.value else FoldingFixedSide.START.value

    def normalized_deformation_mode(self) -> str:
        return (
            FoldingDeformationMode.UNIFORM.value
            if str(self.deformation_mode) == FoldingDeformationMode.UNIFORM.value
            else FoldingDeformationMode.PRESERVE_STRUCTURE.value
        )

    def normalized_shape_angles(self) -> tuple[float, ...]:
        values = tuple(float(max(-270.0, min(270.0, value))) for value in tuple(self.shape_angles_deg or ()))
        if not values:
            return (0.0,)
        if len(values) > 7:
            values = values[:7]
        return values

    @property
    def shape_control_count(self) -> int:
        return len(self.normalized_shape_angles())


def new_living_hinge_curve() -> FoldingCurve:
    return FoldingCurve(
        mode=FoldingMode.LIVING_HINGE.value,
        fold_angle_deg=90.0,
        fixed_side=FoldingFixedSide.START.value,
        shape_angles_deg=(0.0, 0.0, 0.0),
        deformation_mode=FoldingDeformationMode.PRESERVE_STRUCTURE.value,
    )


@dataclass(slots=True)
class FoldingSession:
    phase: FoldingPhase = FoldingPhase.SELECT_MESH
    # Folding can operate on a selection of independent scene meshes.  The
    # meshes share one deformation frame/curve during the session, but remain
    # separate document objects in preview and after Apply.
    target_object_ids: tuple[str, ...] = ()
    target_indices: tuple[int, ...] = ()
    target_names: tuple[str, ...] = ()
    source_meshes: tuple[Any, ...] = ()
    group_id: str = ""
    target_object_id: str | None = None
    target_index: int | None = None
    target_name: str = ""
    source_mesh: Any | None = None
    selected_face_object_id: str | None = None
    selected_face_object_index: int | None = None
    selected_face_index: int | None = None
    selected_face_vertices: tuple[Point3, ...] = ()
    hovered_face_index: int | None = None
    hovered_face_vertices: tuple[Point3, ...] = ()
    hovered_object_id: str | None = None
    hovered_object_name: str = ""
    hover_point: Point3 | None = None
    plane: Any | None = None
    plane_origin: Point3 | None = None
    curve: FoldingCurve = field(default_factory=new_living_hinge_curve)
    dirty: bool = False
    applied_since_open: bool = False
    editing_existing: bool = False
    last_preview_error: str = ""
    preview_pending: bool = False
    preview_ready: bool = False
    status_message: str = "Select a mesh."

    @property
    def target_count(self) -> int:
        return len(self.target_object_ids) if self.target_object_ids else (1 if self.target_object_id is not None else 0)

    def target_rows(self) -> tuple[tuple[str, int, str, Any], ...]:
        """Return normalized group members while retaining single-mesh compatibility."""

        if self.target_object_ids and self.source_meshes:
            return tuple(
                (str(object_id), int(index), str(name), mesh)
                for object_id, index, name, mesh in zip(
                    self.target_object_ids,
                    self.target_indices,
                    self.target_names,
                    self.source_meshes,
                )
            )
        if self.target_object_id is None or self.target_index is None or self.source_mesh is None:
            return ()
        return ((str(self.target_object_id), int(self.target_index), str(self.target_name), self.source_mesh),)

    def clear_transient_hover(self) -> None:
        self.hovered_face_index = None
        self.hovered_face_vertices = ()
        self.hovered_object_id = None
        self.hovered_object_name = ""
        self.hover_point = None

    def reset(self, *, keep_applied_state: bool = False) -> None:
        applied = self.applied_since_open if keep_applied_state else False
        self.phase = FoldingPhase.SELECT_MESH
        self.target_object_ids = ()
        self.target_indices = ()
        self.target_names = ()
        self.source_meshes = ()
        self.group_id = ""
        self.target_object_id = None
        self.target_index = None
        self.target_name = ""
        self.source_mesh = None
        self.selected_face_object_id = None
        self.selected_face_object_index = None
        self.selected_face_index = None
        self.selected_face_vertices = ()
        self.clear_transient_hover()
        self.plane = None
        self.plane_origin = None
        self.curve = new_living_hinge_curve()
        self.dirty = False
        self.applied_since_open = applied
        self.editing_existing = False
        self.last_preview_error = ""
        self.preview_pending = False
        self.preview_ready = False
        self.status_message = "Select a mesh."


__all__ = [
    "FOLDING_MAX_ANGLE_DEG",
    "FOLDING_MIN_ANGLE_DEG",
    "FoldingCurve",
    "FoldingDeformationMode",
    "FoldingFixedSide",
    "FoldingMode",
    "FoldingPhase",
    "FoldingSession",
    "Point3",
    "clamp_folding_angle_deg",
    "new_living_hinge_curve",
]

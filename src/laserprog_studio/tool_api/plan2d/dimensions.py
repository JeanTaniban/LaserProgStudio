"""Public Plan 2D Dimension API for sketch-like Creator tools.

Tool authors should use this small facade instead of importing measurement
internals directly.  The implementation remains split across
``tool_core.dimensions`` modules to keep the API from growing into a monolith.
"""
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.tool_core.dimensions import (
    DEFAULT_UNIT_SYSTEM,
    DimensionKind,
    DimensionLayout,
    DimensionMeasurement,
    DimensionReference,
    DimensionReferenceType,
    DimensionStyle,
    UnitSystem,
    layout_dimension,
    measure_dimension,
    find_dimension_reference_hit,
)


@dataclass(frozen=True, slots=True)
class DimensionSpec:
    kind: DimensionKind | str
    references: tuple[DimensionReference, ...]
    offset: float = 10.0
    driving: bool = False

    @staticmethod
    def aligned_distance(point_a_id: str, point_b_id: str, *, offset: float = 10.0) -> "DimensionSpec":
        return DimensionSpec(
            DimensionKind.ALIGNED_DISTANCE,
            (
                DimensionReference(DimensionReferenceType.POINT, str(point_a_id), "a"),
                DimensionReference(DimensionReferenceType.POINT, str(point_b_id), "b"),
            ),
            offset=float(offset),
        )

    @staticmethod
    def edge_length(line_id: str, *, offset: float = 10.0) -> "DimensionSpec":
        return DimensionSpec(
            DimensionKind.EDGE_LENGTH,
            (DimensionReference(DimensionReferenceType.LINE, str(line_id), "edge"),),
            offset=float(offset),
        )

    @staticmethod
    def angle(line_a_id: str, line_b_id: str, *, offset: float = 12.0) -> "DimensionSpec":
        return DimensionSpec(
            DimensionKind.ANGLE,
            (
                DimensionReference(DimensionReferenceType.LINE, str(line_a_id), "a"),
                DimensionReference(DimensionReferenceType.LINE, str(line_b_id), "b"),
            ),
            offset=float(offset),
        )

    @staticmethod
    def circle_radius(circle_id: str) -> "DimensionSpec":
        return DimensionSpec(DimensionKind.RADIUS, (DimensionReference(DimensionReferenceType.CIRCLE, str(circle_id), "circle"),), offset=0.0)

    @staticmethod
    def circle_diameter(circle_id: str) -> "DimensionSpec":
        return DimensionSpec(DimensionKind.DIAMETER, (DimensionReference(DimensionReferenceType.CIRCLE, str(circle_id), "circle"),), offset=0.0)


def add_dimension(sketch, spec: DimensionSpec, *, dimension_id: str | None = None):
    """Add a passive dimension to a sketch document."""

    return sketch.add_dimension(
        spec.kind,
        tuple(spec.references),
        dimension_id=dimension_id,
        offset=float(spec.offset),
        driving=bool(spec.driving),
    )


__all__ = [
    "DEFAULT_UNIT_SYSTEM",
    "DimensionKind",
    "DimensionLayout",
    "DimensionMeasurement",
    "DimensionReference",
    "DimensionReferenceType",
    "DimensionSpec",
    "DimensionStyle",
    "UnitSystem",
    "add_dimension",
    "find_dimension_reference_hit",
    "layout_dimension",
    "measure_dimension",
]

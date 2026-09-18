"""Dimension datatypes shared by sketch tools.

This module deliberately contains only small, serializable declarations.  The
measurement math, unit formatting and viewport registration live in sibling
modules/API facades so the dimensions feature does not become another monolith.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

Point2 = tuple[float, float]


class DimensionKind(str, Enum):
    """Supported passive dimension categories.

    Driving constraints will reuse these ids later, but this first foundation
    keeps them passive: they display measurements and follow referenced geometry.
    """

    ALIGNED_DISTANCE = "aligned_distance"
    HORIZONTAL_DISTANCE = "horizontal_distance"
    VERTICAL_DISTANCE = "vertical_distance"
    EDGE_LENGTH = "edge_length"
    RADIUS = "radius"
    DIAMETER = "diameter"
    ANGLE = "angle"


class DimensionReferenceType(str, Enum):
    POINT = "point"
    LINE = "line"
    ARC = "arc"
    CIRCLE = "circle"


@dataclass(frozen=True, slots=True)
class DimensionReference:
    """Reference from a dimension to sketch topology.

    ``role`` lets one dimension store multiple references of the same type
    without requiring callers to know field names.  For example an aligned
    distance uses two point references with roles ``a`` and ``b``.
    """

    type: DimensionReferenceType | str
    id: str
    role: str = ""

    def normalized_type(self) -> str:
        return self.type.value if isinstance(self.type, DimensionReferenceType) else str(self.type)


@dataclass(slots=True)
class DimensionStyle:
    """Visual style hint for an API-owned dimension actor."""

    color_role: str = "dimension"
    passive: bool = True
    text_size_px: int = 13
    show_witness_lines: bool = True
    show_arrow_ticks: bool = True


@dataclass(slots=True)
class DimensionLayout:
    """Computed 2D layout for displaying one dimension."""

    dimension_line: tuple[Point2, Point2]
    witness_lines: tuple[tuple[Point2, Point2], ...] = ()
    label_position: Point2 = (0.0, 0.0)
    label: str = ""
    value: float | None = None
    valid: bool = True
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

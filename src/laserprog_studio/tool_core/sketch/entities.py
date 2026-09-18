"""Canonical 2D sketch entities shared by drawing tools."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from laserprog_studio.tool_core.dimensions import DimensionKind, DimensionReference, DimensionStyle

Point2 = tuple[float, float]


class SketchEntityType(str, Enum):
    POINT = "point"
    LINE = "line"
    ARC = "arc"
    BEZIER = "bezier"
    CIRCLE = "circle"
    POLYLINE = "polyline"
    FACE = "face"
    DIMENSION = "dimension"


@dataclass(slots=True)
class SketchPoint:
    id: str
    position: Point2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SketchLine:
    id: str
    start_point_id: str
    end_point_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SketchArc:
    id: str
    start_point_id: str
    end_point_id: str
    control_point_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SketchBezier:
    id: str
    start_point_id: str
    end_point_id: str
    control_1_point_id: str
    control_2_point_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SketchCircle:
    id: str
    center_point_id: str
    radius_point_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SketchPolyline:
    id: str
    edge_ids: tuple[str, ...]
    point_ids: tuple[str, ...]
    closed: bool = False
    recognized_shape: str = "free"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SketchFace:
    id: str
    boundary_entity_ids: tuple[str, ...]
    polygon_points: tuple[Point2, ...]
    hole_polygons: tuple[tuple[Point2, ...], ...] = ()
    hole_boundary_entity_ids: tuple[tuple[str, ...], ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SketchDimension:
    """Passive or future-driving dimension attached to sketch topology.

    The entity stores only semantic references and display intent.  Measurement
    computation, unit formatting and viewport layout live in
    ``tool_core.dimensions`` so the sketch module stays small.
    """

    id: str
    kind: DimensionKind | str
    references: tuple[DimensionReference, ...]
    offset: float = 10.0
    label_position: Point2 | None = None
    driving: bool = False
    value_override: float | None = None
    style: DimensionStyle = field(default_factory=DimensionStyle)
    metadata: dict[str, Any] = field(default_factory=dict)

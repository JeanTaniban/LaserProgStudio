"""Shared snap contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


class SnapSource(str, Enum):
    NONE = "none"
    GRID = "grid"
    SKETCH_POINT = "sketch_point"
    SKETCH_EDGE = "sketch_edge"
    MESH_VERTEX = "mesh_vertex"
    MESH_EDGE = "mesh_edge"
    SCENE_POINT = "scene_point"
    SCENE_EDGE = "scene_edge"
    TOOL_ACTOR_POINT = "tool_actor_point"
    TOOL_ACTOR_EDGE = "tool_actor_edge"
    TOOL_TEMP_POINT = "tool_temp_point"
    TOOL_TEMP_EDGE = "tool_temp_edge"
    UI_POINT = "ui_point"
    UI_EDGE = "ui_edge"
    CUSTOM_POINT = "custom_point"
    CUSTOM_EDGE = "custom_edge"
    SKETCH_CURVE = "sketch_curve"
    SCENE_CURVE = "scene_curve"
    TOOL_ACTOR_CURVE = "tool_actor_curve"
    TOOL_TEMP_CURVE = "tool_temp_curve"
    CUSTOM_CURVE = "custom_curve"
    CENTER = "center"
    INTERSECTION = "intersection"


class SnapKind(str, Enum):
    """Semantic type of a snap result.

    ``SnapSource`` tells where the target came from (scene mesh, tool temp
    target, grid, ...). ``SnapKind`` tells what the target means geometrically
    for UI and priority profiles.  Tool authors should normally only consume
    ``SnapResult.position``; the API uses ``kind`` to style cursors and labels.
    """

    FREE = "free"
    VERTEX = "vertex"
    EDGE = "edge"
    MIDPOINT = "midpoint"
    INTERSECTION = "intersection"
    CENTER = "center"
    QUADRANT = "quadrant"
    ANGLE = "angle"
    GRID = "grid"
    PERPENDICULAR = "perpendicular"
    TANGENT = "tangent"


@dataclass(frozen=True, slots=True)
class SnapResult:
    snapped: bool
    position: Point3
    source: SnapSource = SnapSource.NONE
    source_id: str | None = None
    distance_px: float = float("inf")
    priority: int = 1000
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: SnapKind = SnapKind.FREE
    label: str | None = None

    def __post_init__(self) -> None:
        source = _coerce_source(self.source)
        kind = _coerce_kind(self.kind)
        if self.snapped and kind is SnapKind.FREE:
            kind = snap_kind_for_source(source, metadata=self.metadata)
        label = self.label if self.label is not None else snap_label_for_kind(kind)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "position", _point3(self.position))
        object.__setattr__(self, "distance_px", float(self.distance_px))
        object.__setattr__(self, "priority", int(self.priority))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def is_snapped(self) -> bool:
        return bool(self.snapped)

    @classmethod
    def none(cls, position: Point3) -> "SnapResult":
        return cls(False, position, kind=SnapKind.FREE, label="Free")


@dataclass(frozen=True, slots=True)
class SnapTarget:
    """A point or segment that can be supplied to ``SnapManager.smart``.

    ``world_pos`` is used for geometry snap. ``screen_pos`` is optional and lets
    UI handles/guides participate in snapping even when they are rendered in a
    screen-space overlay.  A UI-only point may omit ``world_pos``; the snap result
    then keeps the queried world position while reporting the UI source id.

    ``kind`` is optional.  When omitted, the API derives it from ``source``:
    point-like sources become :class:`SnapKind.VERTEX`, segment-like sources
    become :class:`SnapKind.EDGE`, ``CENTER`` becomes ``CENTER``, etc.
    """

    id: str
    source: SnapSource = SnapSource.CUSTOM_POINT
    world_pos: Point3 | None = None
    screen_pos: Point2 | None = None
    start: Point3 | None = None
    end: Point3 | None = None
    control: Point3 | None = None
    center: Point3 | None = None
    radius: float | None = None
    basis_u: Point3 | None = None
    basis_v: Point3 | None = None
    radius_px: float = 14.0
    priority: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: SnapKind | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "source", _coerce_source(self.source))
        if self.kind is not None:
            object.__setattr__(self, "kind", _coerce_kind(self.kind))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    @property
    def is_segment(self) -> bool:
        return self.start is not None and self.end is not None and self.control is None

    @property
    def is_arc(self) -> bool:
        return self.start is not None and self.end is not None and self.control is not None

    @property
    def is_circle(self) -> bool:
        return self.center is not None and self.radius is not None and float(self.radius) > 0.0

    @classmethod
    def point(
        cls,
        id: str,
        position: Point3,
        *,
        screen_pos: Point2 | None = None,
        source: SnapSource = SnapSource.CUSTOM_POINT,
        radius_px: float = 14.0,
        priority: int = 50,
        metadata: dict[str, Any] | None = None,
        kind: SnapKind | str | None = None,
    ) -> "SnapTarget":
        return cls(
            id=str(id),
            source=source,
            world_pos=_point3(position),
            screen_pos=_point2(screen_pos) if screen_pos is not None else None,
            radius_px=float(radius_px),
            priority=int(priority),
            metadata=dict(metadata or {}),
            kind=_coerce_kind(kind) if kind is not None else None,
        )

    @classmethod
    def ui_point(
        cls,
        id: str,
        screen_pos: Point2,
        *,
        world_pos: Point3 | None = None,
        radius_px: float = 14.0,
        priority: int = 15,
        metadata: dict[str, Any] | None = None,
        kind: SnapKind | str | None = None,
    ) -> "SnapTarget":
        return cls(
            id=str(id),
            source=SnapSource.UI_POINT,
            world_pos=_point3(world_pos) if world_pos is not None else None,
            screen_pos=_point2(screen_pos),
            radius_px=float(radius_px),
            priority=int(priority),
            metadata=dict(metadata or {}),
            kind=_coerce_kind(kind) if kind is not None else None,
        )


    @classmethod
    def arc(
        cls,
        id: str,
        start: Point3,
        end: Point3,
        control: Point3,
        *,
        source: SnapSource = SnapSource.CUSTOM_CURVE,
        radius_px: float = 14.0,
        priority: int = 65,
        metadata: dict[str, Any] | None = None,
        kind: SnapKind | str | None = None,
    ) -> "SnapTarget":
        """Create a circular-arc snap target.

        Tools declare three points; the API expands that to curve snap and exact
        line/circle/arc intersection candidates.
        """

        return cls(
            id=str(id),
            source=source,
            start=_point3(start),
            end=_point3(end),
            control=_point3(control),
            radius_px=float(radius_px),
            priority=int(priority),
            metadata=dict(metadata or {}),
            kind=_coerce_kind(kind) if kind is not None else None,
        )


    @classmethod
    def circle(
        cls,
        id: str,
        center: Point3,
        radius: float,
        *,
        source: SnapSource = SnapSource.CUSTOM_CURVE,
        radius_px: float = 14.0,
        priority: int = 65,
        metadata: dict[str, Any] | None = None,
        kind: SnapKind | str | None = None,
        basis_u: Point3 | None = None,
        basis_v: Point3 | None = None,
    ) -> "SnapTarget":
        """Create a circular curve snap target.

        The API expands a circle target into center, quadrant/angle landmarks and
        a closest point on the circumference.  Tools only declare the curve; snap
        semantics and cursor styles stay API-owned.
        """

        return cls(
            id=str(id),
            source=source,
            center=_point3(center),
            radius=float(radius),
            radius_px=float(radius_px),
            priority=int(priority),
            metadata=dict(metadata or {}),
            kind=_coerce_kind(kind) if kind is not None else None,
            basis_u=_point3(basis_u) if basis_u is not None else None,
            basis_v=_point3(basis_v) if basis_v is not None else None,
        )

    @classmethod
    def segment(
        cls,
        id: str,
        start: Point3,
        end: Point3,
        *,
        source: SnapSource = SnapSource.CUSTOM_EDGE,
        radius_px: float = 14.0,
        priority: int = 70,
        metadata: dict[str, Any] | None = None,
        kind: SnapKind | str | None = None,
    ) -> "SnapTarget":
        return cls(
            id=str(id),
            source=source,
            start=_point3(start),
            end=_point3(end),
            radius_px=float(radius_px),
            priority=int(priority),
            metadata=dict(metadata or {}),
            kind=_coerce_kind(kind) if kind is not None else None,
        )


class SnapProvider(Protocol):
    id: str
    priority: int
    enabled: bool

    def build_cache(self, ctx: Any) -> None: ...

    def query(self, world_pos: Point3, screen_pos: Point2, ctx: Any) -> list[SnapResult]: ...


_POINT_SOURCES = {
    SnapSource.SKETCH_POINT,
    SnapSource.MESH_VERTEX,
    SnapSource.SCENE_POINT,
    SnapSource.TOOL_ACTOR_POINT,
    SnapSource.TOOL_TEMP_POINT,
    SnapSource.UI_POINT,
    SnapSource.CUSTOM_POINT,
}

_EDGE_SOURCES = {
    SnapSource.SKETCH_EDGE,
    SnapSource.MESH_EDGE,
    SnapSource.SCENE_EDGE,
    SnapSource.TOOL_ACTOR_EDGE,
    SnapSource.TOOL_TEMP_EDGE,
    SnapSource.UI_EDGE,
    SnapSource.CUSTOM_EDGE,
    SnapSource.SKETCH_CURVE,
    SnapSource.SCENE_CURVE,
    SnapSource.TOOL_ACTOR_CURVE,
    SnapSource.TOOL_TEMP_CURVE,
    SnapSource.CUSTOM_CURVE,
}


def snap_kind_for_source(source: SnapSource | str, *, metadata: dict[str, Any] | None = None) -> SnapKind:
    data = dict(metadata or {})
    explicit = data.get("snap_kind") or data.get("kind")
    if explicit is not None:
        return _coerce_kind(explicit)
    source_value = _coerce_source(source)
    if source_value is SnapSource.GRID:
        return SnapKind.GRID
    if source_value is SnapSource.CENTER:
        return SnapKind.CENTER
    if source_value is SnapSource.INTERSECTION:
        return SnapKind.INTERSECTION
    if source_value in _POINT_SOURCES:
        return SnapKind.VERTEX
    if source_value in _EDGE_SOURCES:
        return SnapKind.EDGE
    return SnapKind.FREE


def snap_label_for_kind(kind: SnapKind | str) -> str:
    value = _coerce_kind(kind)
    return {
        SnapKind.FREE: "Free",
        SnapKind.VERTEX: "Vertex",
        SnapKind.EDGE: "Edge",
        SnapKind.MIDPOINT: "Midpoint",
        SnapKind.INTERSECTION: "Intersection",
        SnapKind.CENTER: "Center",
        SnapKind.QUADRANT: "Quadrant",
        SnapKind.ANGLE: "Angle",
        SnapKind.GRID: "Grid",
        SnapKind.PERPENDICULAR: "Perpendicular",
        SnapKind.TANGENT: "Tangent",
    }[value]


def _coerce_source(value: SnapSource | str) -> SnapSource:
    if isinstance(value, SnapSource):
        return value
    text = str(value or SnapSource.NONE.value)
    return SnapSource(text) if text in SnapSource._value2member_map_ else SnapSource.NONE


def _coerce_kind(value: SnapKind | str | None) -> SnapKind:
    if isinstance(value, SnapKind):
        return value
    text = str(value or SnapKind.FREE.value).strip().lower().replace("-", "_")
    aliases = {"none": "free", "point": "vertex", "segment": "edge", "middle": "midpoint", "mid": "midpoint", "angle_point": "angle", "circle_angle": "angle"}
    text = aliases.get(text, text)
    return SnapKind(text) if text in SnapKind._value2member_map_ else SnapKind.FREE


def _point3(value: Point3) -> Point3:
    return (float(value[0]), float(value[1]), float(value[2]))


def _point2(value: Point2) -> Point2:
    return (float(value[0]), float(value[1]))


__all__ = [
    "Point2",
    "Point3",
    "SnapKind",
    "SnapProvider",
    "SnapResult",
    "SnapSource",
    "SnapTarget",
    "snap_kind_for_source",
    "snap_label_for_kind",
]

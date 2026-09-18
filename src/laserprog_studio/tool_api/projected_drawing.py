"""Public API for world geometry and handles drawn in screen space.

The API is declarative and backend-free: tools create immutable primitives,
submit them to ``ctx.projected_drawing.for_tool(tool_id)``, and the application
projects them into persistent ``vtkActor2D`` content. Point/line/face actors and
screen-locked handles may optionally be fixed, selectable or grabbable without
exposing VTK, PyVista or Qt objects to tool authors.
"""
from __future__ import annotations

import math
from typing import Iterable

from laserprog_studio.tool_core.projected_drawing import (
    Point3,
    ProjectedActorKind,
    ProjectedDragConstraint,
    ProjectedDrawingManager,
    ProjectedDrawingRegistry,
    ProjectedDrawingSnapshot,
    ProjectedFace,
    ProjectedFaceBatch,
    ProjectedFaceStyle,
    ProjectedHandle,
    ProjectedHandleShape,
    ProjectedHandleStyle,
    ProjectedInteraction,
    ProjectedLine,
    ProjectedLineStyle,
    ProjectedManipulator,
    ProjectedPointCloud,
    ProjectedSegmentBatch,
    ProjectedPoint,
    ProjectedPointStyle,
    ProjectedPrimitive,
    ProjectedText,
    ProjectedTextStyle,
    ProjectedTriangleMesh,
    ProjectedPrimitiveKind,
    ProjectedVisualState,
)

from .errors import ToolApiValidationError


def _id(value: str) -> str:
    result = str(value).strip()
    if not result:
        raise ToolApiValidationError("Projected primitive id must be non-empty.")
    return result


def _point3(value: Iterable[float], *, field: str = "position") -> Point3:
    # Dense tools generally already hold canonical ``(float, float, float)``
    # tuples. Reusing those immutable tuples avoids allocating and converting
    # tens of thousands of coordinates during a cold scene replacement.
    if isinstance(value, tuple) and len(value) == 3:
        x, y, z = value
        if type(x) is float and type(y) is float and type(z) is float and math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
            return value
    try:
        values = tuple(float(component) for component in value)
    except Exception as exc:
        raise ToolApiValidationError(f"{field} must be an iterable of three finite numbers.") from exc
    if len(values) != 3 or not all(math.isfinite(component) for component in values):
        raise ToolApiValidationError(f"{field} must contain exactly three finite numbers.")
    return (values[0], values[1], values[2])


def _points3(values: Iterable[Iterable[float]], *, field: str, minimum: int) -> tuple[Point3, ...]:
    result = tuple(_point3(value, field=f"{field}[{index}]") for index, value in enumerate(values))
    if len(result) < minimum:
        raise ToolApiValidationError(f"{field} must contain at least {minimum} world points.")
    return result


def _color(value: str | None, *, field: str, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    text = str(value or "").strip()
    if len(text) == 7 and text.startswith("#"):
        try:
            int(text[1:], 16)
        except ValueError:
            pass
        else:
            return text.upper()
    raise ToolApiValidationError(f"{field} must be a '#RRGGBB' colour string" + (" or None." if allow_none else "."))


def _positive(value: float, *, field: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ToolApiValidationError(f"{field} must be a finite number greater than zero.")
    return result


def _opacity(value: float, *, field: str) -> float:
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise ToolApiValidationError(f"{field} must be between 0 and 1.")
    return result




def _enum(value, enum_type, *, field: str):
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(str(value))
    except Exception as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ToolApiValidationError(f"{field} must be one of: {allowed}.") from exc


def _metadata(value: dict[str, object] | Iterable[tuple[str, object]] | None) -> tuple[tuple[str, object], ...]:
    if value is None:
        return ()
    try:
        items = value.items() if isinstance(value, dict) else value
        return tuple((str(key), item) for key, item in items)
    except Exception as exc:
        raise ToolApiValidationError("metadata must be a mapping or iterable of key/value pairs.") from exc


def point(
    id: str,
    position: Iterable[float],
    *,
    color: str = "#DCE7F2",
    size_px: float = 7.0,
    opacity: float = 1.0,
    layer: int = 20,
    visible: bool = True,
    interaction: ProjectedInteraction | str = ProjectedInteraction.FIXED,
    hit_radius_px: float = 10.0,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedPoint:
    """Declare one fixed-size screen point anchored to a world position."""

    return ProjectedPoint(
        id=_id(id),
        position=_point3(position),
        style=ProjectedPointStyle(
            color=str(_color(color, field="color")),
            size_px=_positive(size_px, field="size_px"),
            opacity=_opacity(opacity, field="opacity"),
        ),
        layer=int(layer),
        visible=bool(visible),
        interaction=_enum(interaction, ProjectedInteraction, field="interaction"),
        hit_radius_px=_positive(hit_radius_px, field="hit_radius_px"),
        actor_kind=ProjectedActorKind.POINT,
        metadata=_metadata(metadata),
    )

def line(
    id: str,
    start: Iterable[float],
    end: Iterable[float],
    *,
    color: str = "#7FC8FF",
    width_px: float = 2.0,
    opacity: float = 1.0,
    layer: int = 10,
    visible: bool = True,
    interaction: ProjectedInteraction | str = ProjectedInteraction.FIXED,
    hit_radius_px: float = 10.0,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedLine:
    """Declare one screen-space line segment between two world positions."""

    return polyline(
        id,
        (start, end),
        color=color,
        width_px=width_px,
        opacity=opacity,
        layer=layer,
        closed=False,
        visible=visible,
        interaction=interaction,
        hit_radius_px=hit_radius_px,
        actor_kind=ProjectedActorKind.LINE,
        metadata=metadata,
    )

def polyline(
    id: str,
    points: Iterable[Iterable[float]],
    *,
    color: str = "#7FC8FF",
    width_px: float = 2.0,
    opacity: float = 1.0,
    layer: int = 10,
    closed: bool = False,
    visible: bool = True,
    interaction: ProjectedInteraction | str = ProjectedInteraction.FIXED,
    hit_radius_px: float = 10.0,
    actor_kind: ProjectedActorKind | str = ProjectedActorKind.POLYLINE,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedLine:
    """Declare a connected chain of world points rendered as a 2D polyline."""

    return ProjectedLine(
        id=_id(id),
        points=_points3(points, field="points", minimum=2),
        style=ProjectedLineStyle(
            color=str(_color(color, field="color")),
            width_px=_positive(width_px, field="width_px"),
            opacity=_opacity(opacity, field="opacity"),
        ),
        layer=int(layer),
        closed=bool(closed),
        visible=bool(visible),
        interaction=_enum(interaction, ProjectedInteraction, field="interaction"),
        hit_radius_px=_positive(hit_radius_px, field="hit_radius_px"),
        actor_kind=_enum(actor_kind, ProjectedActorKind, field="actor_kind"),
        metadata=_metadata(metadata),
    )

def face(
    id: str,
    vertices: Iterable[Iterable[float]],
    *,
    holes: Iterable[Iterable[Iterable[float]]] = (),
    fill_color: str = "#4C8EB8",
    fill_opacity: float = 0.24,
    outline_color: str | None = "#8FD4FF",
    outline_width_px: float = 1.5,
    outline_opacity: float = 0.9,
    layer: int = 0,
    visible: bool = True,
    interaction: ProjectedInteraction | str = ProjectedInteraction.FIXED,
    hit_radius_px: float = 8.0,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedFace:
    """Declare one filled polygon in world space."""

    face_vertices = _points3(vertices, field="vertices", minimum=3)
    if len(set(face_vertices)) < 3:
        raise ToolApiValidationError("vertices must contain at least three distinct world points.")
    hole_values = tuple(_points3(ring, field=f"holes[{index}]", minimum=3) for index, ring in enumerate(holes))
    for index, ring in enumerate(hole_values):
        if len(set(ring)) < 3:
            raise ToolApiValidationError(f"holes[{index}] must contain at least three distinct world points.")
    return ProjectedFace(
        id=_id(id),
        vertices=face_vertices,
        holes=hole_values,
        style=ProjectedFaceStyle(
            fill_color=str(_color(fill_color, field="fill_color")),
            fill_opacity=_opacity(fill_opacity, field="fill_opacity"),
            outline_color=_color(outline_color, field="outline_color", allow_none=True),
            outline_width_px=_positive(outline_width_px, field="outline_width_px"),
            outline_opacity=_opacity(outline_opacity, field="outline_opacity"),
        ),
        layer=int(layer),
        visible=bool(visible),
        interaction=_enum(interaction, ProjectedInteraction, field="interaction"),
        hit_radius_px=_positive(hit_radius_px, field="hit_radius_px"),
        actor_kind=ProjectedActorKind.FACE,
        metadata=_metadata(metadata),
    )


def circle(
    id: str,
    center: Iterable[float],
    radius_point: Iterable[float],
    *,
    segments: int = 72,
    color: str = "#7FC8FF",
    width_px: float = 2.0,
    opacity: float = 1.0,
    layer: int = 10,
    visible: bool = True,
    interaction: ProjectedInteraction | str = ProjectedInteraction.FIXED,
    hit_radius_px: float = 10.0,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedLine:
    """Declare a circle on the world XY plane from a centre and radius point."""

    c = _point3(center, field="center")
    r = _point3(radius_point, field="radius_point")
    radius = math.hypot(r[0] - c[0], r[1] - c[1])
    if radius <= 1.0e-12:
        raise ToolApiValidationError("radius_point must differ from center in XY.")
    count = max(12, int(segments))
    points = tuple(
        (c[0] + math.cos(2.0 * math.pi * i / count) * radius,
         c[1] + math.sin(2.0 * math.pi * i / count) * radius,
         c[2])
        for i in range(count)
    )
    metadata_items = dict(_metadata(metadata))
    metadata_items["circle_hit_points"] = (c, r)
    return polyline(
        id, points, color=color, width_px=width_px, opacity=opacity, layer=layer,
        closed=True, visible=visible, interaction=interaction,
        hit_radius_px=hit_radius_px, actor_kind=ProjectedActorKind.CIRCLE,
        metadata=metadata_items,
    )


def arc(
    id: str,
    points: Iterable[Iterable[float]],
    *,
    color: str = "#7FC8FF",
    width_px: float = 2.0,
    opacity: float = 1.0,
    layer: int = 10,
    visible: bool = True,
    interaction: ProjectedInteraction | str = ProjectedInteraction.FIXED,
    hit_radius_px: float = 10.0,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedLine:
    """Declare a sampled arc actor. The point chain must contain at least three points."""

    values = _points3(points, field="points", minimum=3)
    return polyline(
        id, values, color=color, width_px=width_px, opacity=opacity, layer=layer,
        closed=False, visible=visible, interaction=interaction,
        hit_radius_px=hit_radius_px, actor_kind=ProjectedActorKind.ARC,
        metadata=metadata,
    )


def text(
    id: str,
    value: str,
    position: Iterable[float],
    *,
    color: str = "#E8F1F8",
    size_px: int = 14,
    opacity: float = 1.0,
    anchor: str = "center",
    offset_px: Iterable[float] = (0.0, 0.0),
    bold: bool = False,
    italic: bool = False,
    layer: int = 40,
    visible: bool = True,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedText:
    """Declare a persistent text label anchored to a world position."""

    label = str(value)
    if not label:
        raise ToolApiValidationError("text value must be non-empty.")
    anchor_value = str(anchor).strip().lower().replace("-", "_")
    allowed_anchors = {
        "center", "left", "right", "top", "bottom",
        "top_left", "top_right", "bottom_left", "bottom_right",
    }
    if anchor_value not in allowed_anchors:
        raise ToolApiValidationError(f"anchor must be one of: {', '.join(sorted(allowed_anchors))}.")
    try:
        offset = tuple(float(component) for component in offset_px)
    except Exception as exc:
        raise ToolApiValidationError("offset_px must contain two finite numbers.") from exc
    if len(offset) != 2 or not all(math.isfinite(component) for component in offset):
        raise ToolApiValidationError("offset_px must contain exactly two finite numbers.")
    size = int(size_px)
    if size <= 0:
        raise ToolApiValidationError("size_px must be greater than zero.")
    return ProjectedText(
        id=_id(id),
        text=label,
        position=_point3(position),
        style=ProjectedTextStyle(
            color=str(_color(color, field="color")),
            size_px=size,
            opacity=_opacity(opacity, field="opacity"),
            bold=bool(bold),
            italic=bool(italic),
        ),
        anchor=anchor_value,
        offset_px=(offset[0], offset[1]),
        layer=int(layer),
        visible=bool(visible),
        metadata=_metadata(metadata),
    )


def triangle_mesh(
    id: str,
    vertices: Iterable[Iterable[float]],
    triangles: Iterable[Iterable[int]],
    *,
    fill_color: str = "#4C8EB8",
    fill_opacity: float = 0.24,
    outline_color: str | None = "#8FD4FF",
    outline_width_px: float = 1.0,
    outline_opacity: float = 0.75,
    layer: int = 0,
    visible: bool = True,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedTriangleMesh:
    """Declare an indexed triangle mesh without exposing VTK/PyVista objects."""

    points = _points3(vertices, field="vertices", minimum=3)
    cells: list[tuple[int, int, int]] = []
    for index, triangle in enumerate(triangles):
        try:
            cell = tuple(int(value) for value in triangle)
        except Exception as exc:
            raise ToolApiValidationError(f"triangles[{index}] must contain three integer indices.") from exc
        if len(cell) != 3 or len(set(cell)) != 3:
            raise ToolApiValidationError(f"triangles[{index}] must contain three distinct indices.")
        if any(value < 0 or value >= len(points) for value in cell):
            raise ToolApiValidationError(f"triangles[{index}] contains an out-of-range vertex index.")
        cells.append((cell[0], cell[1], cell[2]))
    if not cells:
        raise ToolApiValidationError("triangles must contain at least one triangle.")
    return ProjectedTriangleMesh(
        id=_id(id),
        vertices=points,
        triangles=tuple(cells),
        style=ProjectedFaceStyle(
            fill_color=str(_color(fill_color, field="fill_color")),
            fill_opacity=_opacity(fill_opacity, field="fill_opacity"),
            outline_color=_color(outline_color, field="outline_color", allow_none=True),
            outline_width_px=_positive(outline_width_px, field="outline_width_px"),
            outline_opacity=_opacity(outline_opacity, field="outline_opacity"),
        ),
        layer=int(layer),
        visible=bool(visible),
        metadata=_metadata(metadata),
    )


def handle(
    id: str,
    position: Iterable[float],
    *,
    shape: ProjectedHandleShape | str = ProjectedHandleShape.SOLID,
    direction: Iterable[float] = (1.0, 0.0, 0.0),
    size_px: float = 18.0,
    line_width_px: float = 2.0,
    color: str = "#4AA7FF",
    hover_color: str = "#7AD8FF",
    selected_color: str = "#FFD36B",
    grabbed_color: str = "#FF6E32",
    disabled_color: str = "#697386",
    opacity: float = 1.0,
    layer: int = 30,
    visible: bool = True,
    interaction: ProjectedInteraction | str = ProjectedInteraction.GRABBABLE,
    constraint: ProjectedDragConstraint | str = ProjectedDragConstraint.PLANE_XY,
    hit_radius_px: float | None = None,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedHandle:
    """Declare a screen-locked point handle with native hover/select/drag state."""

    size = _positive(size_px, field="size_px")
    return ProjectedHandle(
        id=_id(id),
        position=_point3(position),
        shape=_enum(shape, ProjectedHandleShape, field="shape"),
        style=ProjectedHandleStyle(
            size_px=size,
            line_width_px=_positive(line_width_px, field="line_width_px"),
            normal_color=str(_color(color, field="color")),
            hover_color=str(_color(hover_color, field="hover_color")),
            selected_color=str(_color(selected_color, field="selected_color")),
            grabbed_color=str(_color(grabbed_color, field="grabbed_color")),
            disabled_color=str(_color(disabled_color, field="disabled_color")),
            opacity=_opacity(opacity, field="opacity"),
        ),
        direction=_point3(direction, field="direction"),
        layer=int(layer),
        visible=bool(visible),
        interaction=_enum(interaction, ProjectedInteraction, field="interaction"),
        constraint=_enum(constraint, ProjectedDragConstraint, field="constraint"),
        hit_radius_px=_positive(hit_radius_px if hit_radius_px is not None else max(8.0, size * 0.65), field="hit_radius_px"),
        metadata=_metadata(metadata),
    )


def drag_arrow(
    id: str,
    position: Iterable[float],
    direction: Iterable[float],
    *,
    constraint: ProjectedDragConstraint | str,
    color: str = "#4AA7FF",
    size_px: float = 30.0,
    layer: int = 35,
    metadata: dict[str, object] | Iterable[tuple[str, object]] | None = None,
) -> ProjectedHandle:
    """Convenience factory for a grabbable directional translation arrow."""

    return handle(
        id, position, shape=ProjectedHandleShape.TRANSLATE_ARROW,
        direction=direction, constraint=constraint, interaction=ProjectedInteraction.GRABBABLE,
        color=color, size_px=size_px, layer=layer, metadata=metadata,
    )



_AXIS_VECTORS: dict[str, Point3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}
_AXIS_COLORS: dict[str, str] = {
    "x": "#F26D6D",
    "y": "#67C587",
    "z": "#5C8FF7",
}
_AXIS_CONSTRAINTS: dict[str, ProjectedDragConstraint] = {
    "x": ProjectedDragConstraint.AXIS_X,
    "y": ProjectedDragConstraint.AXIS_Y,
    "z": ProjectedDragConstraint.AXIS_Z,
}


def _manipulator_axes(axes: Iterable[str]) -> tuple[str, ...]:
    result = tuple(str(axis).strip().lower() for axis in axes)
    if not result or any(axis not in _AXIS_VECTORS for axis in result):
        raise ToolApiValidationError("axes must contain one or more of: x, y, z.")
    if len(set(result)) != len(result):
        raise ToolApiValidationError("axes must not contain duplicates.")
    return result


def _offset(origin: Point3, direction: Point3, distance: float) -> Point3:
    return (
        origin[0] + direction[0] * distance,
        origin[1] + direction[1] * distance,
        origin[2] + direction[2] * distance,
    )


def translate_gizmo(
    id: str,
    origin: Iterable[float] = (0.0, 0.0, 0.0),
    *,
    axes: Iterable[str] = ("x", "y", "z"),
    axis_length: float = 1.0,
    size_px: float = 30.0,
    include_center: bool = True,
    center_constraint: ProjectedDragConstraint | str = ProjectedDragConstraint.PLANE_XY,
    layer: int = 35,
) -> ProjectedManipulator:
    """Build a standard translation gizmo from constrained projected handles."""

    manipulator_id = _id(id)
    center = _point3(origin)
    distance = _positive(axis_length, field="axis_length")
    axis_values = _manipulator_axes(axes)
    primitives: list[ProjectedPrimitive] = []
    handle_ids: list[str] = []
    for axis in axis_values:
        direction = _AXIS_VECTORS[axis]
        handle_id = f"{manipulator_id}:{axis}"
        primitives.append(drag_arrow(
            handle_id,
            _offset(center, direction, distance),
            direction,
            constraint=_AXIS_CONSTRAINTS[axis],
            color=_AXIS_COLORS[axis],
            size_px=size_px,
            layer=layer,
            metadata={"manipulator_id": manipulator_id, "manipulator_kind": "translate", "axis": axis},
        ))
        handle_ids.append(handle_id)
    if include_center:
        center_id = f"{manipulator_id}:center"
        primitives.append(handle(
            center_id,
            center,
            shape=ProjectedHandleShape.SOLID,
            constraint=center_constraint,
            interaction=ProjectedInteraction.GRABBABLE,
            color="#F0A805",
            size_px=max(10.0, float(size_px) * 0.62),
            layer=layer + 1,
            metadata={"manipulator_id": manipulator_id, "manipulator_kind": "translate", "axis": "center"},
        ))
        handle_ids.append(center_id)
    return ProjectedManipulator(manipulator_id, "translate", center, tuple(primitives), tuple(handle_ids))


def rotate_gizmo(
    id: str,
    origin: Iterable[float] = (0.0, 0.0, 0.0),
    *,
    axes: Iterable[str] = ("x", "y", "z"),
    axis_length: float = 1.0,
    size_px: float = 24.0,
    layer: int = 35,
) -> ProjectedManipulator:
    """Build the historical ring-handle rotation manipulator."""

    manipulator_id = _id(id)
    center = _point3(origin)
    distance = _positive(axis_length, field="axis_length")
    primitives: list[ProjectedPrimitive] = []
    handle_ids: list[str] = []
    for axis in _manipulator_axes(axes):
        direction = _AXIS_VECTORS[axis]
        handle_id = f"{manipulator_id}:rotate:{axis}"
        primitives.append(handle(
            handle_id,
            _offset(center, direction, distance),
            shape=ProjectedHandleShape.RING,
            direction=direction,
            constraint=_AXIS_CONSTRAINTS[axis],
            interaction=ProjectedInteraction.GRABBABLE,
            color=_AXIS_COLORS[axis],
            size_px=size_px,
            layer=layer,
            metadata={"manipulator_id": manipulator_id, "manipulator_kind": "rotate", "axis": axis},
        ))
        handle_ids.append(handle_id)
    return ProjectedManipulator(manipulator_id, "rotate", center, tuple(primitives), tuple(handle_ids))


def scale_gizmo(
    id: str,
    origin: Iterable[float] = (0.0, 0.0, 0.0),
    *,
    axes: Iterable[str] = ("x", "y", "z"),
    axis_length: float = 1.0,
    size_px: float = 22.0,
    include_uniform: bool = True,
    layer: int = 35,
) -> ProjectedManipulator:
    """Build axis and uniform scale handles."""

    manipulator_id = _id(id)
    center = _point3(origin)
    distance = _positive(axis_length, field="axis_length")
    primitives: list[ProjectedPrimitive] = []
    handle_ids: list[str] = []
    for axis in _manipulator_axes(axes):
        direction = _AXIS_VECTORS[axis]
        handle_id = f"{manipulator_id}:scale:{axis}"
        primitives.append(handle(
            handle_id,
            _offset(center, direction, distance),
            shape=ProjectedHandleShape.SQUARE,
            direction=direction,
            constraint=_AXIS_CONSTRAINTS[axis],
            interaction=ProjectedInteraction.GRABBABLE,
            color=_AXIS_COLORS[axis],
            size_px=size_px,
            layer=layer,
            metadata={"manipulator_id": manipulator_id, "manipulator_kind": "scale", "axis": axis},
        ))
        handle_ids.append(handle_id)
    if include_uniform:
        uniform_id = f"{manipulator_id}:scale:uniform"
        primitives.append(handle(
            uniform_id,
            _offset(center, (1.0, 1.0, 1.0), distance * 0.62),
            shape=ProjectedHandleShape.SQUARE,
            constraint=ProjectedDragConstraint.FREE,
            interaction=ProjectedInteraction.GRABBABLE,
            color="#F0A805",
            size_px=size_px,
            layer=layer + 1,
            metadata={"manipulator_id": manipulator_id, "manipulator_kind": "scale", "axis": "uniform"},
        ))
        handle_ids.append(uniform_id)
    return ProjectedManipulator(manipulator_id, "scale", center, tuple(primitives), tuple(handle_ids))


def plane_gizmo(
    id: str,
    origin: Iterable[float] = (0.0, 0.0, 0.0),
    *,
    normal: Iterable[float] = (0.0, 0.0, 1.0),
    axis_length: float = 1.0,
    size_px: float = 24.0,
    layer: int = 35,
) -> ProjectedManipulator:
    """Build origin and normal handles for a plane manipulator."""

    manipulator_id = _id(id)
    center = _point3(origin)
    direction = _point3(normal, field="normal")
    norm = math.sqrt(sum(component * component for component in direction))
    if norm <= 1.0e-12:
        raise ToolApiValidationError("normal must be non-zero.")
    unit = tuple(component / norm for component in direction)
    distance = _positive(axis_length, field="axis_length")
    origin_id = f"{manipulator_id}:origin"
    normal_id = f"{manipulator_id}:normal"
    primitives = (
        handle(origin_id, center, shape=ProjectedHandleShape.TARGET, constraint=ProjectedDragConstraint.PLANE_XY, color="#F0A805", size_px=size_px, layer=layer, metadata={"manipulator_id": manipulator_id, "manipulator_kind": "plane", "role": "origin"}),
        handle(normal_id, _offset(center, unit, distance), shape=ProjectedHandleShape.AXIS, direction=unit, constraint=ProjectedDragConstraint.FREE, color="#5C8FF7", size_px=size_px, layer=layer, metadata={"manipulator_id": manipulator_id, "manipulator_kind": "plane", "role": "normal"}),
    )
    return ProjectedManipulator(manipulator_id, "plane", center, primitives, (origin_id, normal_id), (("normal", unit),))


def triad_gizmo(
    id: str,
    origin: Iterable[float] = (0.0, 0.0, 0.0),
    *,
    axis_length: float = 1.0,
    size_px: float = 26.0,
    layer: int = 35,
) -> ProjectedManipulator:
    """Build a three-axis translation triad."""

    base = translate_gizmo(id, origin, axes=("x", "y", "z"), axis_length=axis_length, size_px=size_px, include_center=False, layer=layer)
    return ProjectedManipulator(base.id, "triad", base.origin, base.primitives, base.handle_ids, base.metadata)


def box_bounds_gizmo(
    id: str,
    bounds: Iterable[float],
    *,
    size_px: float = 20.0,
    layer: int = 35,
    include_edges: bool = True,
) -> ProjectedManipulator:
    """Build eight grabbable corner handles and optional box edges."""

    manipulator_id = _id(id)
    try:
        values = tuple(float(value) for value in bounds)
    except Exception as exc:
        raise ToolApiValidationError("bounds must contain six finite numbers.") from exc
    if len(values) != 6 or not all(math.isfinite(value) for value in values):
        raise ToolApiValidationError("bounds must contain exactly six finite numbers.")
    xmin, xmax, ymin, ymax, zmin, zmax = values
    if xmin > xmax or ymin > ymax or zmin > zmax:
        raise ToolApiValidationError("bounds minimum values must not exceed maximum values.")
    corners: tuple[Point3, ...] = (
        (xmin, ymin, zmin), (xmax, ymin, zmin), (xmin, ymax, zmin), (xmax, ymax, zmin),
        (xmin, ymin, zmax), (xmax, ymin, zmax), (xmin, ymax, zmax), (xmax, ymax, zmax),
    )
    primitives: list[ProjectedPrimitive] = []
    handle_ids: list[str] = []
    for index, position in enumerate(corners):
        handle_id = f"{manipulator_id}:corner:{index}"
        primitives.append(handle(handle_id, position, shape=ProjectedHandleShape.DIAMOND, constraint=ProjectedDragConstraint.FREE, color="#F0A805", size_px=size_px, layer=layer, metadata={"manipulator_id": manipulator_id, "manipulator_kind": "box_bounds", "corner": index}))
        handle_ids.append(handle_id)
    if include_edges:
        edge_pairs = ((0,1),(0,2),(1,3),(2,3),(4,5),(4,6),(5,7),(6,7),(0,4),(1,5),(2,6),(3,7))
        primitives.append(segment_batch(
            f"{manipulator_id}:edges",
            tuple((corners[a], corners[b]) for a, b in edge_pairs),
            color="#8FD4FF",
            width_px=1.5,
            opacity=0.8,
            layer=layer - 1,
        ))
    center = ((xmin + xmax) * 0.5, (ymin + ymax) * 0.5, (zmin + zmax) * 0.5)
    return ProjectedManipulator(manipulator_id, "box_bounds", center, tuple(primitives), tuple(handle_ids), (("bounds", values),))


def _optional_item_ids(values: Iterable[str] | None, count: int, *, field: str = "item_ids") -> tuple[str, ...]:
    if values is None:
        return ()
    result = tuple(_id(value) for value in values)
    if len(result) != count:
        raise ToolApiValidationError(f"{field} must contain exactly {count} entries.")
    if len(set(result)) != len(result):
        raise ToolApiValidationError(f"{field} must be unique.")
    return result


def point_cloud(
    id: str,
    positions: Iterable[Iterable[float]],
    *,
    item_ids: Iterable[str] | None = None,
    color: str = "#DCE7F2",
    size_px: float = 7.0,
    opacity: float = 1.0,
    layer: int = 20,
    visible: bool = True,
) -> ProjectedPointCloud:
    """Declare one packed point cloud for high-volume scenes."""

    if isinstance(positions, tuple) and all(
        isinstance(value, tuple)
        and len(value) == 3
        and all(type(component) is float and math.isfinite(component) for component in value)
        for value in positions
    ):
        values = positions
    else:
        values = tuple(_point3(value, field=f"positions[{index}]") for index, value in enumerate(positions))
    return ProjectedPointCloud(
        id=_id(id),
        positions=values,
        item_ids=_optional_item_ids(item_ids, len(values)),
        style=ProjectedPointStyle(
            color=str(_color(color, field="color")),
            size_px=_positive(size_px, field="size_px"),
            opacity=_opacity(opacity, field="opacity"),
        ),
        layer=int(layer),
        visible=bool(visible),
    )


def segment_batch(
    id: str,
    segments: Iterable[Iterable[Iterable[float]]],
    *,
    item_ids: Iterable[str] | None = None,
    color: str = "#7FC8FF",
    width_px: float = 2.0,
    opacity: float = 1.0,
    layer: int = 10,
    visible: bool = True,
) -> ProjectedSegmentBatch:
    """Declare one packed collection of independent line segments."""

    values: list[tuple[Point3, Point3]] = []
    for index, segment in enumerate(segments):
        pair = tuple(segment)
        if len(pair) != 2:
            raise ToolApiValidationError(f"segments[{index}] must contain exactly two world points.")
        values.append((_point3(pair[0], field=f"segments[{index}][0]"), _point3(pair[1], field=f"segments[{index}][1]")))
    return ProjectedSegmentBatch(
        id=_id(id),
        segments=tuple(values),
        item_ids=_optional_item_ids(item_ids, len(values)),
        style=ProjectedLineStyle(
            color=str(_color(color, field="color")),
            width_px=_positive(width_px, field="width_px"),
            opacity=_opacity(opacity, field="opacity"),
        ),
        layer=int(layer),
        visible=bool(visible),
    )


def face_batch(
    id: str,
    polygons: Iterable[Iterable[Iterable[float]]],
    *,
    item_ids: Iterable[str] | None = None,
    fill_color: str = "#4C8EB8",
    fill_opacity: float = 0.24,
    outline_color: str | None = "#8FD4FF",
    outline_width_px: float = 1.5,
    outline_opacity: float = 0.9,
    layer: int = 0,
    visible: bool = True,
) -> ProjectedFaceBatch:
    """Declare one packed same-style polygon collection."""

    values = tuple(_points3(polygon, field=f"polygons[{index}]", minimum=3) for index, polygon in enumerate(polygons))
    for index, vertices in enumerate(values):
        if len(set(vertices)) < 3:
            raise ToolApiValidationError(f"polygons[{index}] must contain at least three distinct world points.")
    return ProjectedFaceBatch(
        id=_id(id),
        polygons=values,
        item_ids=_optional_item_ids(item_ids, len(values)),
        style=ProjectedFaceStyle(
            fill_color=str(_color(fill_color, field="fill_color")),
            fill_opacity=_opacity(fill_opacity, field="fill_opacity"),
            outline_color=_color(outline_color, field="outline_color", allow_none=True),
            outline_width_px=_positive(outline_width_px, field="outline_width_px"),
            outline_opacity=_opacity(outline_opacity, field="outline_opacity"),
        ),
        layer=int(layer),
        visible=bool(visible),
    )

def _ids(prefix: str, count: int, ids: Iterable[str] | None) -> tuple[str, ...]:
    if ids is None:
        base = _id(prefix)
        return tuple(f"{base}:{index}" for index in range(count))
    result = tuple(_id(value) for value in ids)
    if len(result) != count:
        raise ToolApiValidationError(f"ids must contain exactly {count} entries.")
    if len(set(result)) != len(result):
        raise ToolApiValidationError("ids must be unique.")
    return result


def points(
    id_prefix: str,
    positions: Iterable[Iterable[float]],
    *,
    ids: Iterable[str] | None = None,
    color: str = "#DCE7F2",
    size_px: float = 7.0,
    opacity: float = 1.0,
    layer: int = 20,
    visible: bool = True,
) -> tuple[ProjectedPoint, ...]:
    """Create many same-style points with one validation pass.

    ``ids`` may provide stable element identifiers.  Otherwise identifiers are
    generated as ``<id_prefix>:0``, ``<id_prefix>:1``…
    """

    values = tuple(_point3(value, field=f"positions[{index}]") for index, value in enumerate(positions))
    item_ids = _ids(id_prefix, len(values), ids)
    style = ProjectedPointStyle(
        color=str(_color(color, field="color")),
        size_px=_positive(size_px, field="size_px"),
        opacity=_opacity(opacity, field="opacity"),
    )
    return tuple(
        ProjectedPoint(id=item_id, position=position, style=style, layer=int(layer), visible=bool(visible))
        for item_id, position in zip(item_ids, values)
    )


def line_segments(
    id_prefix: str,
    segments: Iterable[Iterable[Iterable[float]]],
    *,
    ids: Iterable[str] | None = None,
    color: str = "#7FC8FF",
    width_px: float = 2.0,
    opacity: float = 1.0,
    layer: int = 10,
    visible: bool = True,
) -> tuple[ProjectedLine, ...]:
    """Create many independent same-style two-point lines efficiently."""

    values: list[tuple[Point3, Point3]] = []
    for index, segment in enumerate(segments):
        pair = tuple(segment)
        if len(pair) != 2:
            raise ToolApiValidationError(f"segments[{index}] must contain exactly two world points.")
        values.append((_point3(pair[0], field=f"segments[{index}][0]"), _point3(pair[1], field=f"segments[{index}][1]")))
    item_ids = _ids(id_prefix, len(values), ids)
    style = ProjectedLineStyle(
        color=str(_color(color, field="color")),
        width_px=_positive(width_px, field="width_px"),
        opacity=_opacity(opacity, field="opacity"),
    )
    return tuple(
        ProjectedLine(id=item_id, points=segment, style=style, layer=int(layer), visible=bool(visible))
        for item_id, segment in zip(item_ids, values)
    )


def faces(
    id_prefix: str,
    polygons: Iterable[Iterable[Iterable[float]]],
    *,
    ids: Iterable[str] | None = None,
    fill_color: str = "#4C8EB8",
    fill_opacity: float = 0.24,
    outline_color: str | None = "#8FD4FF",
    outline_width_px: float = 1.5,
    outline_opacity: float = 0.9,
    layer: int = 0,
    visible: bool = True,
) -> tuple[ProjectedFace, ...]:
    """Create many same-style faces while validating the style only once."""

    values = tuple(_points3(polygon, field=f"polygons[{index}]", minimum=3) for index, polygon in enumerate(polygons))
    for index, vertices in enumerate(values):
        if len(set(vertices)) < 3:
            raise ToolApiValidationError(f"polygons[{index}] must contain at least three distinct world points.")
    item_ids = _ids(id_prefix, len(values), ids)
    style = ProjectedFaceStyle(
        fill_color=str(_color(fill_color, field="fill_color")),
        fill_opacity=_opacity(fill_opacity, field="fill_opacity"),
        outline_color=_color(outline_color, field="outline_color", allow_none=True),
        outline_width_px=_positive(outline_width_px, field="outline_width_px"),
        outline_opacity=_opacity(outline_opacity, field="outline_opacity"),
    )
    return tuple(
        ProjectedFace(id=item_id, vertices=vertices, style=style, layer=int(layer), visible=bool(visible))
        for item_id, vertices in zip(item_ids, values)
    )

def registry(ctx, owner_tool: str) -> ProjectedDrawingRegistry:
    """Return the owner-scoped projected drawing registry from a ToolContext."""

    manager = getattr(ctx, "projected_drawing", None)
    if not isinstance(manager, ProjectedDrawingManager):
        raise ToolApiValidationError("This ToolContext does not expose ctx.projected_drawing.")
    return manager.for_tool(owner_tool)


def world_radius_for_screen_pixels(
    plotter,
    world_position: Iterable[float],
    pixel_radius: float,
    *,
    fallback_world_per_px: float = 0.05,
) -> float:
    """Return a world-space radius that appears as ``pixel_radius`` on screen.

    Tools use this for projected 2D controls whose anchor points live in the
    scene, but whose manipulation affordance should remain camera-sized.  The
    public API intentionally returns a plain float so Creator tools do not need
    to import the historical gizmo camera-scale result type.
    """

    try:
        from laserprog_studio.tool_core.gizmos.camera_scale import plotter_pixel_radius_to_world

        result = plotter_pixel_radius_to_world(
            plotter,
            _point3(world_position, field="world_position"),
            _positive(pixel_radius, field="pixel_radius"),
            fallback_world_per_px=float(fallback_world_per_px),
        )
        return float(result.world_radius)
    except Exception:
        return max(_positive(pixel_radius, field="pixel_radius") * float(fallback_world_per_px), 1.0e-9)


__all__ = [
    "Point3",
    "ProjectedActorKind",
    "ProjectedDragConstraint",
    "ProjectedHandle",
    "ProjectedHandleShape",
    "ProjectedHandleStyle",
    "ProjectedInteraction",
    "ProjectedVisualState",
    "ProjectedDrawingManager",
    "ProjectedDrawingRegistry",
    "ProjectedDrawingSnapshot",
    "ProjectedFace",
    "ProjectedFaceBatch",
    "ProjectedFaceStyle",
    "ProjectedLine",
    "ProjectedLineStyle",
    "ProjectedManipulator",
    "ProjectedPointCloud",
    "ProjectedSegmentBatch",
    "ProjectedPoint",
    "ProjectedPointStyle",
    "ProjectedPrimitive",
    "ProjectedText",
    "ProjectedTextStyle",
    "ProjectedTriangleMesh",
    "ProjectedPrimitiveKind",
    "arc",
    "box_bounds_gizmo",
    "circle",
    "drag_arrow",
    "face",
    "handle",
    "face_batch",
    "faces",
    "line",
    "segment_batch",
    "line_segments",
    "point",
    "plane_gizmo",
    "point_cloud",
    "points",
    "polyline",
    "registry",
    "rotate_gizmo",
    "scale_gizmo",
    "text",
    "translate_gizmo",
    "triad_gizmo",
    "triangle_mesh",
    "world_radius_for_screen_pixels",
]

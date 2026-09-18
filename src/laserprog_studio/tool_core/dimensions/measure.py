"""Pure measurement and layout helpers for sketch dimensions."""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, pi, sin

from .types import DimensionKind, DimensionLayout, DimensionReference, DimensionReferenceType
from .units import DEFAULT_UNIT_SYSTEM, UnitSystem

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class DimensionMeasurement:
    value: float | None
    label: str
    valid: bool = True
    reason: str = ""


def measure_dimension(sketch, dimension, *, units: UnitSystem | None = None) -> DimensionMeasurement:
    """Measure a sketch dimension without touching UI state."""

    units = units or DEFAULT_UNIT_SYSTEM
    kind = _kind_value(dimension.kind)
    try:
        if kind in {DimensionKind.ALIGNED_DISTANCE.value, DimensionKind.HORIZONTAL_DISTANCE.value, DimensionKind.VERTICAL_DISTANCE.value}:
            a, b = _dimension_points(sketch, dimension.references)
            if a is None or b is None:
                return DimensionMeasurement(None, "invalid", False, "missing_point_reference")
            dx = float(b[0]) - float(a[0])
            dy = float(b[1]) - float(a[1])
            if kind == DimensionKind.HORIZONTAL_DISTANCE.value:
                value = abs(dx)
            elif kind == DimensionKind.VERTICAL_DISTANCE.value:
                value = abs(dy)
            else:
                value = hypot(dx, dy)
            return DimensionMeasurement(value, units.format_length(value))
        if kind == DimensionKind.EDGE_LENGTH.value:
            line = _first_referenced_line(sketch, dimension.references)
            if line is None:
                return DimensionMeasurement(None, "invalid", False, "missing_line_reference")
            a = sketch.points.get(line.start_point_id)
            b = sketch.points.get(line.end_point_id)
            if a is None or b is None:
                return DimensionMeasurement(None, "invalid", False, "missing_line_endpoint")
            value = _distance(a.position, b.position)
            return DimensionMeasurement(value, units.format_length(value))
        if kind in {DimensionKind.RADIUS.value, DimensionKind.DIAMETER.value}:
            circle = _first_referenced_circle(sketch, dimension.references)
            if circle is None:
                return DimensionMeasurement(None, "invalid", False, "missing_circle_reference")
            center = sketch.points.get(circle.center_point_id)
            radius_point = sketch.points.get(circle.radius_point_id)
            if center is None or radius_point is None:
                return DimensionMeasurement(None, "invalid", False, "missing_circle_point")
            radius = _distance(center.position, radius_point.position)
            value = radius * (2.0 if kind == DimensionKind.DIAMETER.value else 1.0)
            prefix = "Ø " if kind == DimensionKind.DIAMETER.value else "R "
            return DimensionMeasurement(value, prefix + units.format_length(value))
        if kind == DimensionKind.ANGLE.value:
            lines = _referenced_lines(sketch, dimension.references)
            if len(lines) < 2:
                return DimensionMeasurement(None, "invalid", False, "missing_angle_lines")
            angle = _angle_between_lines(sketch, lines[0], lines[1])
            if angle is None:
                return DimensionMeasurement(None, "invalid", False, "invalid_angle_lines")
            return DimensionMeasurement(angle, f"{angle:.1f}°")
    except Exception as exc:  # pragma: no cover - defensive for future tools
        return DimensionMeasurement(None, "invalid", False, f"measure_failed:{type(exc).__name__}")
    return DimensionMeasurement(None, "invalid", False, f"unsupported_dimension_kind:{kind}")


def layout_dimension(sketch, dimension, *, units: UnitSystem | None = None) -> DimensionLayout:
    """Build a simple stable 2D layout for passive dimension display."""

    measurement = measure_dimension(sketch, dimension, units=units)
    kind = _kind_value(dimension.kind)
    if kind in {DimensionKind.ALIGNED_DISTANCE.value, DimensionKind.HORIZONTAL_DISTANCE.value, DimensionKind.VERTICAL_DISTANCE.value}:
        a, b = _dimension_points(sketch, dimension.references)
        if a is None or b is None:
            return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, valid=False, reason=measurement.reason)
        return _layout_aligned(a, b, float(getattr(dimension, "offset", 10.0)), measurement)
    if kind == DimensionKind.EDGE_LENGTH.value:
        line = _first_referenced_line(sketch, dimension.references)
        if line is None:
            return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, valid=False, reason=measurement.reason)
        a = sketch.points.get(line.start_point_id)
        b = sketch.points.get(line.end_point_id)
        if a is None or b is None:
            return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, valid=False, reason=measurement.reason)
        return _layout_aligned(a.position, b.position, float(getattr(dimension, "offset", 10.0)), measurement)
    if kind in {DimensionKind.RADIUS.value, DimensionKind.DIAMETER.value}:
        circle = _first_referenced_circle(sketch, dimension.references)
        if circle is None:
            return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, valid=False, reason=measurement.reason)
        center = sketch.points.get(circle.center_point_id)
        radius_point = sketch.points.get(circle.radius_point_id)
        if center is None or radius_point is None:
            return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, valid=False, reason=measurement.reason)
        return _layout_radius(center.position, radius_point.position, measurement, diameter=(kind == DimensionKind.DIAMETER.value))
    if kind == DimensionKind.ANGLE.value:
        lines = _referenced_lines(sketch, dimension.references)
        if len(lines) < 2:
            return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, valid=False, reason=measurement.reason)
        return _layout_angle(sketch, lines[0], lines[1], float(getattr(dimension, "offset", 12.0)), measurement)
    return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, value=measurement.value, valid=measurement.valid, reason=measurement.reason)


def _layout_aligned(a: Point2, b: Point2, offset: float, measurement: DimensionMeasurement) -> DimensionLayout:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    length = hypot(dx, dy)
    if length <= 1.0e-12:
        label_pos = ((ax + bx) * 0.5, (ay + by) * 0.5)
        return DimensionLayout(((ax, ay), (bx, by)), label_position=label_pos, label=measurement.label, value=measurement.value, valid=False, reason="zero_length")
    nx, ny = -dy / length, dx / length
    off = float(offset)
    da = (ax + nx * off, ay + ny * off)
    db = (bx + nx * off, by + ny * off)
    label_pos = ((da[0] + db[0]) * 0.5, (da[1] + db[1]) * 0.5)
    return DimensionLayout(
        dimension_line=(da, db),
        witness_lines=((a, da), (b, db)),
        label_position=label_pos,
        label=measurement.label,
        value=measurement.value,
        valid=measurement.valid,
        reason=measurement.reason,
    )


def _layout_radius(center: Point2, radius_point: Point2, measurement: DimensionMeasurement, *, diameter: bool) -> DimensionLayout:
    cx, cy = float(center[0]), float(center[1])
    rx, ry = float(radius_point[0]), float(radius_point[1])
    dx, dy = rx - cx, ry - cy
    radius = hypot(dx, dy)
    if radius <= 1.0e-12:
        return DimensionLayout(((center), (radius_point)), label=measurement.label, label_position=center, value=measurement.value, valid=False, reason="zero_radius")
    ux, uy = dx / radius, dy / radius
    if diameter:
        a = (cx - ux * radius, cy - uy * radius)
        b = (cx + ux * radius, cy + uy * radius)
        label_pos = (cx, cy)
        return DimensionLayout((a, b), label_position=label_pos, label=measurement.label, value=measurement.value, valid=measurement.valid, reason=measurement.reason)
    label_pos = (cx + ux * radius * 0.58, cy + uy * radius * 0.58)
    return DimensionLayout((center, radius_point), label_position=label_pos, label=measurement.label, value=measurement.value, valid=measurement.valid, reason=measurement.reason)


def _layout_angle(sketch, first, second, offset: float, measurement: DimensionMeasurement) -> DimensionLayout:
    line_a = _line_points(sketch, first)
    line_b = _line_points(sketch, second)
    if line_a is None or line_b is None:
        return DimensionLayout(((0.0, 0.0), (0.0, 0.0)), label=measurement.label, value=measurement.value, valid=False, reason="missing_angle_endpoint")
    a0, a1 = line_a
    b0, b1 = line_b
    vertex = _common_point(a0, a1, b0, b1)
    if vertex is None:
        vertex = _infinite_line_intersection(a0, a1, b0, b1)
    if vertex is None:
        # Parallel lines have no stable angle vertex.  Still expose a valid label
        # near the midpoint so passive measurements do not silently disappear.
        mx = (a0[0] + a1[0] + b0[0] + b1[0]) * 0.25
        my = (a0[1] + a1[1] + b0[1] + b1[1]) * 0.25
        return DimensionLayout(((a0), (b0)), label_position=(mx, my), label=measurement.label, value=measurement.value, valid=measurement.valid, reason=measurement.reason, metadata={"layout_kind": "angle_parallel"})
    v1 = _direction_away_from(vertex, a0, a1)
    v2 = _direction_away_from(vertex, b0, b1)
    if v1 is None or v2 is None:
        return DimensionLayout(((vertex), (vertex)), label_position=vertex, label=measurement.label, value=measurement.value, valid=False, reason="zero_length_angle_line")
    radius = max(float(offset), 10.0)
    p1 = (vertex[0] + v1[0] * radius, vertex[1] + v1[1] * radius)
    p2 = (vertex[0] + v2[0] * radius, vertex[1] + v2[1] * radius)
    angle1 = atan2(v1[1], v1[0])
    angle2 = atan2(v2[1], v2[0])
    sweep = angle2 - angle1
    while sweep <= -pi:
        sweep += 2.0 * pi
    while sweep > pi:
        sweep -= 2.0 * pi
    mid = angle1 + sweep * 0.5
    label_pos = (vertex[0] + cos(mid) * radius * 1.22, vertex[1] + sin(mid) * radius * 1.22)
    return DimensionLayout(
        dimension_line=(p1, p2),
        witness_lines=((vertex, p1), (vertex, p2)),
        label_position=label_pos,
        label=measurement.label,
        value=measurement.value,
        valid=measurement.valid,
        reason=measurement.reason,
        metadata={"layout_kind": "angle", "vertex": vertex},
    )


def _line_points(sketch, line) -> tuple[Point2, Point2] | None:
    start = sketch.points.get(line.start_point_id)
    end = sketch.points.get(line.end_point_id)
    if start is None or end is None:
        return None
    return start.position, end.position


def _common_point(a0: Point2, a1: Point2, b0: Point2, b1: Point2, *, eps: float = 1.0e-9) -> Point2 | None:
    for first in (a0, a1):
        for second in (b0, b1):
            if _distance(first, second) <= eps:
                return ((float(first[0]) + float(second[0])) * 0.5, (float(first[1]) + float(second[1])) * 0.5)
    return None


def _infinite_line_intersection(a0: Point2, a1: Point2, b0: Point2, b1: Point2, *, eps: float = 1.0e-12) -> Point2 | None:
    x1, y1 = float(a0[0]), float(a0[1])
    x2, y2 = float(a1[0]), float(a1[1])
    x3, y3 = float(b0[0]), float(b0[1])
    x4, y4 = float(b1[0]), float(b1[1])
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) <= eps:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
    return (float(px), float(py))


def _direction_away_from(vertex: Point2, a: Point2, b: Point2) -> Point2 | None:
    da = _distance(vertex, a)
    db = _distance(vertex, b)
    target = a if da >= db else b
    dx = float(target[0]) - float(vertex[0])
    dy = float(target[1]) - float(vertex[1])
    length = hypot(dx, dy)
    if length <= 1.0e-12:
        return None
    return (dx / length, dy / length)


def _dimension_points(sketch, references: tuple[DimensionReference, ...]) -> tuple[Point2 | None, Point2 | None]:
    points = []
    for ref in references:
        if _ref_type(ref) == DimensionReferenceType.POINT.value and ref.id in sketch.points:
            points.append(sketch.points[ref.id].position)
    if len(points) < 2:
        return None, None
    return points[0], points[1]


def _first_referenced_line(sketch, references: tuple[DimensionReference, ...]):
    lines = _referenced_lines(sketch, references)
    return lines[0] if lines else None


def _referenced_lines(sketch, references: tuple[DimensionReference, ...]) -> list:
    out = []
    for ref in references:
        if _ref_type(ref) == DimensionReferenceType.LINE.value and ref.id in sketch.lines:
            out.append(sketch.lines[ref.id])
    return out


def _first_referenced_circle(sketch, references: tuple[DimensionReference, ...]):
    for ref in references:
        if _ref_type(ref) == DimensionReferenceType.CIRCLE.value and ref.id in sketch.circles:
            return sketch.circles[ref.id]
    return None


def _angle_between_lines(sketch, first, second) -> float | None:
    a0 = sketch.points.get(first.start_point_id)
    a1 = sketch.points.get(first.end_point_id)
    b0 = sketch.points.get(second.start_point_id)
    b1 = sketch.points.get(second.end_point_id)
    if a0 is None or a1 is None or b0 is None or b1 is None:
        return None
    v1 = (a1.position[0] - a0.position[0], a1.position[1] - a0.position[1])
    v2 = (b1.position[0] - b0.position[0], b1.position[1] - b0.position[1])
    if hypot(*v1) <= 1.0e-12 or hypot(*v2) <= 1.0e-12:
        return None
    angle = abs((atan2(v2[1], v2[0]) - atan2(v1[1], v1[0])) * 180.0 / pi)
    if angle > 180.0:
        angle = 360.0 - angle
    return angle


def _kind_value(value) -> str:
    return value.value if isinstance(value, DimensionKind) else str(value)


def _ref_type(ref: DimensionReference) -> str:
    return ref.normalized_type() if hasattr(ref, "normalized_type") else str(ref.type)


def _distance(a: Point2, b: Point2) -> float:
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))

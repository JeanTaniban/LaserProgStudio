# -*- coding: utf-8 -*-
"""Pure geometry kernel for Plan Tracer's additive Mirror tool.

The module deliberately knows nothing about Qt, overlays, selection actors or
history.  It receives semantic sketch primitives, splits every open curve at an
infinite mirror axis, reflects each side onto the opposite side and returns an
add-only plan.  Existing geometry is never removed or rewired.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Iterable, Sequence

import numpy as np

from laserprog_studio.tool_api.plan2d.curves import sample_cubic_bezier
from laserprog_studio.tool_api.plan2d.plane import sample_plan_arc_xy

Point2 = tuple[float, float]
_EPS = 1.0e-9


@dataclass(frozen=True, slots=True)
class MirrorAxis:
    start: Point2
    end: Point2

    def __post_init__(self) -> None:
        if math.dist(self.start, self.end) <= _EPS:
            raise ValueError("Mirror axis requires two distinct points")

    @property
    def direction(self) -> Point2:
        dx = float(self.end[0]) - float(self.start[0])
        dy = float(self.end[1]) - float(self.start[1])
        length = math.hypot(dx, dy)
        return (dx / length, dy / length)

    @property
    def normal(self) -> Point2:
        dx, dy = self.direction
        return (-dy, dx)

    def signed_distance(self, point: Point2) -> float:
        nx, ny = self.normal
        return (float(point[0]) - float(self.start[0])) * nx + (float(point[1]) - float(self.start[1])) * ny

    def reflect(self, point: Point2) -> Point2:
        distance = self.signed_distance(point)
        nx, ny = self.normal
        return (float(point[0]) - 2.0 * distance * nx, float(point[1]) - 2.0 * distance * ny)


@dataclass(frozen=True, slots=True)
class PointPrimitive:
    source_id: str
    point: Point2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LinePrimitive:
    source_id: str
    start: Point2
    end: Point2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArcPrimitive:
    source_id: str
    start: Point2
    end: Point2
    control: Point2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BezierPrimitive:
    source_id: str
    start: Point2
    control_1: Point2
    control_2: Point2
    end: Point2
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CirclePrimitive:
    source_id: str
    center: Point2
    radius_point: Point2
    metadata: dict[str, Any] = field(default_factory=dict)


MirrorPrimitive = PointPrimitive | LinePrimitive | ArcPrimitive | BezierPrimitive | CirclePrimitive


@dataclass(frozen=True, slots=True)
class MirrorPlan:
    axis: MirrorAxis
    additions: tuple[MirrorPrimitive, ...]
    source_count: int
    split_source_count: int
    skipped_on_axis_count: int
    skipped_duplicate_count: int

    @property
    def addition_count(self) -> int:
        return len(self.additions)


@dataclass(frozen=True, slots=True)
class _CircularArcParameterization:
    center: Point2
    radius: float
    start_angle: float
    sweep: float

    def point_at(self, t: float) -> Point2:
        angle = self.start_angle + self.sweep * float(t)
        return (
            self.center[0] + math.cos(angle) * self.radius,
            self.center[1] + math.sin(angle) * self.radius,
        )


def _circle_arc_parameterization(start: Point2, end: Point2, control: Point2) -> _CircularArcParameterization | None:
    sx, sy = map(float, start)
    ex, ey = map(float, end)
    cx, cy = map(float, control)
    det = 2.0 * (sx * (cy - ey) + cx * (ey - sy) + ex * (sy - cy))
    if abs(det) <= 1.0e-12:
        return None
    s2 = sx * sx + sy * sy
    c2 = cx * cx + cy * cy
    e2 = ex * ex + ey * ey
    ox = (s2 * (cy - ey) + c2 * (ey - sy) + e2 * (sy - cy)) / det
    oy = (s2 * (ex - cx) + c2 * (sx - ex) + e2 * (cx - sx)) / det
    radius = math.hypot(sx - ox, sy - oy)
    if radius <= 1.0e-12 or not math.isfinite(radius):
        return None
    a0 = math.atan2(sy - oy, sx - ox)
    a1 = math.atan2(ey - oy, ex - ox)
    ac = math.atan2(cy - oy, cx - ox)

    def ccw_delta(a: float, b: float) -> float:
        return (b - a) % math.tau

    ccw_sweep = ccw_delta(a0, a1)
    contains_control = ccw_delta(a0, ac) <= ccw_sweep + 1.0e-9
    sweep = ccw_sweep if contains_control else -ccw_delta(a1, a0)
    return _CircularArcParameterization((ox, oy), radius, a0, sweep)


def _arc_parameter_for_point(parameterization: _CircularArcParameterization, point: Point2) -> float | None:
    angle = math.atan2(point[1] - parameterization.center[1], point[0] - parameterization.center[0])
    if parameterization.sweep > 0.0:
        delta = (angle - parameterization.start_angle) % math.tau
        t = delta / parameterization.sweep
    else:
        delta = (parameterization.start_angle - angle) % math.tau
        t = delta / (-parameterization.sweep)
    if -1.0e-8 <= t <= 1.0 + 1.0e-8:
        return max(0.0, min(1.0, t))
    return None


def _arc_axis_roots(arc: ArcPrimitive, axis: MirrorAxis) -> list[float]:
    parameterization = _circle_arc_parameterization(arc.start, arc.end, arc.control)
    if parameterization is None:
        return _quadratic_axis_roots(arc.start, arc.control, arc.end, axis)
    nx, ny = axis.normal
    cx = parameterization.center[0] - axis.start[0]
    cy = parameterization.center[1] - axis.start[1]
    signed_center = cx * nx + cy * ny
    distance = abs(signed_center)
    radius = parameterization.radius
    if distance > radius + 1.0e-9:
        return []
    foot = (
        parameterization.center[0] - signed_center * nx,
        parameterization.center[1] - signed_center * ny,
    )
    tangent_x, tangent_y = axis.direction
    offset = math.sqrt(max(0.0, radius * radius - signed_center * signed_center))
    candidates = [
        (foot[0] + tangent_x * offset, foot[1] + tangent_y * offset),
        (foot[0] - tangent_x * offset, foot[1] - tangent_y * offset),
    ]
    roots: list[float] = []
    for candidate in candidates:
        t = _arc_parameter_for_point(parameterization, candidate)
        if t is not None and 1.0e-8 < t < 1.0 - 1.0e-8:
            roots.append(t)
    return _dedupe_parameters(roots)


def _quadratic_axis_roots(start: Point2, control: Point2, end: Point2, axis: MirrorAxis) -> list[float]:
    values = [axis.signed_distance(point) for point in (start, control, end)]
    # Bernstein quadratic -> power basis.
    a = values[0] - 2.0 * values[1] + values[2]
    b = -2.0 * values[0] + 2.0 * values[1]
    c = values[0]
    roots = np.roots([a, b, c] if abs(a) > 1.0e-14 else [b, c]) if abs(a) > 1.0e-14 or abs(b) > 1.0e-14 else []
    return _real_unit_roots(roots)


def _bezier_axis_roots(bezier: BezierPrimitive, axis: MirrorAxis) -> list[float]:
    values = [axis.signed_distance(point) for point in (bezier.start, bezier.control_1, bezier.control_2, bezier.end)]
    if max(abs(value) for value in values) <= 1.0e-10:
        return []
    a = -values[0] + 3.0 * values[1] - 3.0 * values[2] + values[3]
    b = 3.0 * values[0] - 6.0 * values[1] + 3.0 * values[2]
    c = -3.0 * values[0] + 3.0 * values[1]
    d = values[0]
    coefficients = [a, b, c, d]
    while len(coefficients) > 1 and abs(coefficients[0]) <= 1.0e-14:
        coefficients.pop(0)
    return _real_unit_roots(np.roots(coefficients) if len(coefficients) > 1 else [])


def _real_unit_roots(roots: Iterable[complex]) -> list[float]:
    values: list[float] = []
    for root in roots:
        if abs(float(np.imag(root))) > 1.0e-8:
            continue
        value = float(np.real(root))
        if 1.0e-8 < value < 1.0 - 1.0e-8:
            values.append(value)
    return _dedupe_parameters(values)


def _dedupe_parameters(values: Iterable[float]) -> list[float]:
    result: list[float] = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > 1.0e-7:
            result.append(value)
    return result


def _lerp(a: Point2, b: Point2, t: float) -> Point2:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def _split_cubic(points: tuple[Point2, Point2, Point2, Point2], t: float) -> tuple[tuple[Point2, Point2, Point2, Point2], tuple[Point2, Point2, Point2, Point2]]:
    p0, p1, p2, p3 = points
    p01 = _lerp(p0, p1, t)
    p12 = _lerp(p1, p2, t)
    p23 = _lerp(p2, p3, t)
    p012 = _lerp(p01, p12, t)
    p123 = _lerp(p12, p23, t)
    p0123 = _lerp(p012, p123, t)
    return (p0, p01, p012, p0123), (p0123, p123, p23, p3)


def _cubic_subcurve(points: tuple[Point2, Point2, Point2, Point2], t0: float, t1: float) -> tuple[Point2, Point2, Point2, Point2]:
    if t0 <= 0.0 and t1 >= 1.0:
        return points
    left, _right = _split_cubic(points, t1)
    if t0 <= 0.0:
        return left
    relative = t0 / max(t1, 1.0e-15)
    _discard, segment = _split_cubic(left, relative)
    return segment


def _quadratic_to_cubic(start: Point2, control: Point2, end: Point2) -> tuple[Point2, Point2, Point2, Point2]:
    return (
        start,
        (start[0] + (control[0] - start[0]) * 2.0 / 3.0, start[1] + (control[1] - start[1]) * 2.0 / 3.0),
        (end[0] + (control[0] - end[0]) * 2.0 / 3.0, end[1] + (control[1] - end[1]) * 2.0 / 3.0),
        end,
    )


def _reflect_metadata(metadata: dict[str, Any], *, source_id: str) -> dict[str, Any]:
    result = dict(metadata or {})
    for key in tuple(result):
        text = str(key)
        if text.startswith("generated_for_") or text.endswith("_id") or text.endswith("_arc_id"):
            result.pop(key, None)
    # Side intent is orientation-dependent and cannot safely survive an
    # arbitrary-axis reflection. Geometry remains exact through control points.
    for key in ("curve_side", "arc_side", "side"):
        result.pop(key, None)
    result.update({"generated_by": "mirror", "mirror_source_id": str(source_id)})
    return result


def _reflect_primitive(primitive: MirrorPrimitive, axis: MirrorAxis) -> MirrorPrimitive:
    metadata = _reflect_metadata(primitive.metadata, source_id=primitive.source_id)
    source_id = primitive.source_id
    if isinstance(primitive, PointPrimitive):
        return PointPrimitive(source_id, axis.reflect(primitive.point), metadata)
    if isinstance(primitive, LinePrimitive):
        return LinePrimitive(source_id, axis.reflect(primitive.start), axis.reflect(primitive.end), metadata)
    if isinstance(primitive, ArcPrimitive):
        return ArcPrimitive(source_id, axis.reflect(primitive.start), axis.reflect(primitive.end), axis.reflect(primitive.control), metadata)
    if isinstance(primitive, BezierPrimitive):
        return BezierPrimitive(
            source_id,
            axis.reflect(primitive.start),
            axis.reflect(primitive.control_1),
            axis.reflect(primitive.control_2),
            axis.reflect(primitive.end),
            metadata,
        )
    if isinstance(primitive, CirclePrimitive):
        return CirclePrimitive(source_id, axis.reflect(primitive.center), axis.reflect(primitive.radius_point), metadata)
    raise TypeError(type(primitive))


def _split_open_primitive(primitive: LinePrimitive | ArcPrimitive | BezierPrimitive, axis: MirrorAxis) -> tuple[list[MirrorPrimitive], bool, bool]:
    """Return side-contained pieces, whether a split occurred, and on-axis flag."""

    if isinstance(primitive, LinePrimitive):
        d0, d1 = axis.signed_distance(primitive.start), axis.signed_distance(primitive.end)
        if abs(d0) <= 1.0e-9 and abs(d1) <= 1.0e-9:
            return [], False, True
        if d0 * d1 < -1.0e-18:
            t = d0 / (d0 - d1)
            cut = _lerp(primitive.start, primitive.end, t)
            return [
                LinePrimitive(primitive.source_id, primitive.start, cut, primitive.metadata),
                LinePrimitive(primitive.source_id, cut, primitive.end, primitive.metadata),
            ], True, False
        return [primitive], False, False

    if isinstance(primitive, ArcPrimitive):
        parameterization = _circle_arc_parameterization(primitive.start, primitive.end, primitive.control)
        if parameterization is None:
            cubic = _quadratic_to_cubic(primitive.start, primitive.control, primitive.end)
            fallback = BezierPrimitive(primitive.source_id, cubic[0], cubic[1], cubic[2], cubic[3], primitive.metadata)
            return _split_open_primitive(fallback, axis)
        roots = _arc_axis_roots(primitive, axis)
        if not roots:
            samples = [parameterization.point_at(value) for value in (0.0, 0.25, 0.5, 0.75, 1.0)]
            if max(abs(axis.signed_distance(point)) for point in samples) <= 1.0e-9:
                return [], False, True
            return [primitive], False, False
        bounds = [0.0, *roots, 1.0]
        pieces: list[MirrorPrimitive] = []
        for t0, t1 in zip(bounds, bounds[1:]):
            if t1 - t0 <= 1.0e-9:
                continue
            pieces.append(ArcPrimitive(
                primitive.source_id,
                parameterization.point_at(t0),
                parameterization.point_at(t1),
                parameterization.point_at((t0 + t1) * 0.5),
                primitive.metadata,
            ))
        return pieces, True, False

    roots = _bezier_axis_roots(primitive, axis)
    samples = sample_cubic_bezier(primitive.start, primitive.control_1, primitive.control_2, primitive.end, segments=12)
    if max(abs(axis.signed_distance(point)) for point in samples) <= 1.0e-9:
        return [], False, True
    if not roots:
        return [primitive], False, False
    control = (primitive.start, primitive.control_1, primitive.control_2, primitive.end)
    bounds = [0.0, *roots, 1.0]
    pieces = []
    for t0, t1 in zip(bounds, bounds[1:]):
        if t1 - t0 <= 1.0e-9:
            continue
        p0, p1, p2, p3 = _cubic_subcurve(control, t0, t1)
        pieces.append(BezierPrimitive(primitive.source_id, p0, p1, p2, p3, primitive.metadata))
    return pieces, True, False


def sample_primitive(primitive: MirrorPrimitive, *, segments: int = 32) -> list[Point2]:
    if isinstance(primitive, PointPrimitive):
        return [primitive.point]
    if isinstance(primitive, LinePrimitive):
        return [_lerp(primitive.start, primitive.end, index / 8.0) for index in range(9)]
    if isinstance(primitive, ArcPrimitive):
        return list(sample_plan_arc_xy(primitive.start, primitive.end, primitive.control, segments=max(8, segments)))
    if isinstance(primitive, BezierPrimitive):
        return sample_cubic_bezier(primitive.start, primitive.control_1, primitive.control_2, primitive.end, segments=max(12, segments))
    if isinstance(primitive, CirclePrimitive):
        radius = math.dist(primitive.center, primitive.radius_point)
        count = max(24, int(segments) * 2)
        points = [
            (
                primitive.center[0] + math.cos(math.tau * index / count) * radius,
                primitive.center[1] + math.sin(math.tau * index / count) * radius,
            )
            for index in range(count)
        ]
        return points + points[:1] if points else []
    return []


def _point_segment_distance(point: Point2, start: Point2, end: Point2) -> float:
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1.0e-24:
        return math.dist(point, start)
    t = max(0.0, min(1.0, ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq))
    projection = (start[0] + t * dx, start[1] + t * dy)
    return math.dist(point, projection)


def _point_on_line_segment(point: Point2, line: LinePrimitive, tolerance: float) -> bool:
    return _point_segment_distance(point, line.start, line.end) <= tolerance


def _same_point(a: Point2, b: Point2, tolerance: float) -> bool:
    return math.dist(a, b) <= tolerance


def _arc_contains_point(arc: ArcPrimitive, point: Point2, tolerance: float) -> bool:
    parameterization = _circle_arc_parameterization(arc.start, arc.end, arc.control)
    if parameterization is None:
        return False
    radial_error = abs(math.dist(parameterization.center, point) - parameterization.radius)
    if radial_error > tolerance:
        return False
    return _arc_parameter_for_point(parameterization, point) is not None


def _bezier_is_same_or_reversed(existing: BezierPrimitive, candidate: BezierPrimitive, tolerance: float) -> bool:
    direct = (
        _same_point(existing.start, candidate.start, tolerance)
        and _same_point(existing.control_1, candidate.control_1, tolerance)
        and _same_point(existing.control_2, candidate.control_2, tolerance)
        and _same_point(existing.end, candidate.end, tolerance)
    )
    reverse = (
        _same_point(existing.start, candidate.end, tolerance)
        and _same_point(existing.control_1, candidate.control_2, tolerance)
        and _same_point(existing.control_2, candidate.control_1, tolerance)
        and _same_point(existing.end, candidate.start, tolerance)
    )
    return direct or reverse


def _polyline_covers(candidate: Sequence[Point2], existing: Sequence[Point2], tolerance: float) -> bool:
    if not candidate or not existing:
        return False
    if len(candidate) == 1:
        return min(math.dist(candidate[0], point) for point in existing) <= tolerance
    segments = list(zip(existing, existing[1:]))
    if not segments:
        return False
    return all(min(_point_segment_distance(point, a, b) for a, b in segments) <= tolerance for point in candidate)


def _primitive_covers(existing: MirrorPrimitive, candidate: MirrorPrimitive, tolerance: float) -> bool:
    """Return whether ``existing`` already contains the candidate geometry.

    Coverage is deliberately type-aware.  A chord whose endpoints lie on a
    circle is not a duplicate of the circle, and a point lying on an edge remains
    a distinct point entity.  Exact kernels are used for lines/circles/arcs;
    Bézier subcurve coverage uses a dense deterministic fallback after checking
    exact control-point equality/reversal.
    """

    if type(existing) is not type(candidate):
        return False
    if isinstance(candidate, PointPrimitive) and isinstance(existing, PointPrimitive):
        return _same_point(existing.point, candidate.point, tolerance)
    if isinstance(candidate, LinePrimitive) and isinstance(existing, LinePrimitive):
        return (
            _point_on_line_segment(candidate.start, existing, tolerance)
            and _point_on_line_segment(candidate.end, existing, tolerance)
            and _point_on_line_segment(_lerp(candidate.start, candidate.end, 0.5), existing, tolerance)
        )
    if isinstance(candidate, CirclePrimitive) and isinstance(existing, CirclePrimitive):
        existing_radius = math.dist(existing.center, existing.radius_point)
        candidate_radius = math.dist(candidate.center, candidate.radius_point)
        return _same_point(existing.center, candidate.center, tolerance) and abs(existing_radius - candidate_radius) <= tolerance
    if isinstance(candidate, ArcPrimitive) and isinstance(existing, ArcPrimitive):
        existing_parameterization = _circle_arc_parameterization(existing.start, existing.end, existing.control)
        candidate_parameterization = _circle_arc_parameterization(candidate.start, candidate.end, candidate.control)
        if existing_parameterization is None or candidate_parameterization is None:
            return False
        if math.dist(existing_parameterization.center, candidate_parameterization.center) > tolerance:
            return False
        if abs(existing_parameterization.radius - candidate_parameterization.radius) > tolerance:
            return False
        return all(
            _arc_contains_point(existing, candidate_parameterization.point_at(index / 12.0), tolerance)
            for index in range(13)
        )
    if isinstance(candidate, BezierPrimitive) and isinstance(existing, BezierPrimitive):
        if _bezier_is_same_or_reversed(existing, candidate, tolerance):
            return True
        candidate_points = sample_cubic_bezier(
            candidate.start,
            candidate.control_1,
            candidate.control_2,
            candidate.end,
            segments=40,
        )
        existing_points = sample_cubic_bezier(
            existing.start,
            existing.control_1,
            existing.control_2,
            existing.end,
            segments=512,
        )
        scale = max(
            math.dist(existing.start, existing.end),
            math.dist(existing.start, existing.control_1),
            math.dist(existing.end, existing.control_2),
            1.0,
        )
        return _polyline_covers(candidate_points, existing_points, max(tolerance, scale * 1.0e-7))
    return False


def _quantized(value: float, step: float) -> int:
    return int(round(float(value) / max(abs(float(step)), 1.0e-12)))


def _point_key(point: Point2, tolerance: float) -> tuple[int, int]:
    return (_quantized(point[0], tolerance), _quantized(point[1], tolerance))


def _near_point_keys(point: Point2, tolerance: float) -> tuple[tuple[int, int], ...]:
    x, y = _point_key(point, tolerance)
    return tuple((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def _line_support_key(line: LinePrimitive, tolerance: float) -> tuple[int, int, int] | None:
    dx = float(line.end[0]) - float(line.start[0])
    dy = float(line.end[1]) - float(line.start[1])
    length = math.hypot(dx, dy)
    if length <= 1.0e-12:
        return None
    dx, dy = dx / length, dy / length
    if dx < -1.0e-12 or (abs(dx) <= 1.0e-12 and dy < 0.0):
        dx, dy = -dx, -dy
    nx, ny = -dy, dx
    offset = nx * float(line.start[0]) + ny * float(line.start[1])
    angular_step = 1.0e-8
    return (_quantized(dx, angular_step), _quantized(dy, angular_step), _quantized(offset, tolerance))


def _near_line_keys(line: LinePrimitive, tolerance: float) -> tuple[tuple[int, int, int], ...]:
    key = _line_support_key(line, tolerance)
    if key is None:
        return ()
    x, y, offset = key
    return tuple(
        (x + dx, y + dy, offset + doffset)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for doffset in (-1, 0, 1)
    )


def _circle_key(center: Point2, radius: float, tolerance: float) -> tuple[int, int, int]:
    return (
        _quantized(center[0], tolerance),
        _quantized(center[1], tolerance),
        _quantized(radius, tolerance),
    )


def _near_circle_keys(center: Point2, radius: float, tolerance: float) -> tuple[tuple[int, int, int], ...]:
    x, y, r = _circle_key(center, radius, tolerance)
    return tuple(
        (x + dx, y + dy, r + dr)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dr in (-1, 0, 1)
    )


def _primitive_bounds(primitive: MirrorPrimitive) -> tuple[float, float, float, float]:
    sampled = sample_primitive(primitive, segments=24)
    if not sampled:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [point[0] for point in sampled]
    ys = [point[1] for point in sampled]
    return (min(xs), min(ys), max(xs), max(ys))


def _bounds_can_cover(outer: tuple[float, float, float, float], inner: tuple[float, float, float, float], tolerance: float) -> bool:
    return (
        outer[0] <= inner[0] + tolerance
        and outer[1] <= inner[1] + tolerance
        and outer[2] >= inner[2] - tolerance
        and outer[3] >= inner[3] - tolerance
    )


class _PrimitiveCoverageIndex:
    """Type-aware spatial index for add-only duplicate suppression.

    The first implementation scanned every existing primitive for every mirror
    candidate, making whole-sketch Mirror quadratic.  Most sketch entities have
    a compact analytic signature, so they can be queried in near-constant time.
    Bézier containment retains the exact/dense fallback, but only after cheap
    endpoint and bounding-box filtering.
    """

    def __init__(self, primitives: Iterable[MirrorPrimitive], tolerance: float) -> None:
        self.tolerance = max(float(tolerance), 1.0e-9)
        self.points: dict[tuple[int, int], list[PointPrimitive]] = {}
        self.lines: dict[tuple[int, int, int], list[LinePrimitive]] = {}
        self.circles: dict[tuple[int, int, int], list[CirclePrimitive]] = {}
        self.arcs: dict[tuple[int, int, int], list[ArcPrimitive]] = {}
        self.beziers_by_endpoints: dict[tuple[tuple[int, int], tuple[int, int]], list[BezierPrimitive]] = {}
        self.beziers: list[tuple[BezierPrimitive, tuple[float, float, float, float]]] = []
        self.fallback: dict[type[Any], list[MirrorPrimitive]] = {}
        for primitive in primitives:
            self.add(primitive)

    def add(self, primitive: MirrorPrimitive) -> None:
        tolerance = self.tolerance
        if isinstance(primitive, PointPrimitive):
            self.points.setdefault(_point_key(primitive.point, tolerance), []).append(primitive)
            return
        if isinstance(primitive, LinePrimitive):
            key = _line_support_key(primitive, tolerance)
            if key is not None:
                self.lines.setdefault(key, []).append(primitive)
                return
        elif isinstance(primitive, CirclePrimitive):
            radius = math.dist(primitive.center, primitive.radius_point)
            self.circles.setdefault(_circle_key(primitive.center, radius, tolerance), []).append(primitive)
            return
        elif isinstance(primitive, ArcPrimitive):
            parameterization = _circle_arc_parameterization(primitive.start, primitive.end, primitive.control)
            if parameterization is not None:
                key = _circle_key(parameterization.center, parameterization.radius, tolerance)
                self.arcs.setdefault(key, []).append(primitive)
                return
        elif isinstance(primitive, BezierPrimitive):
            start = _point_key(primitive.start, tolerance)
            end = _point_key(primitive.end, tolerance)
            self.beziers_by_endpoints.setdefault((start, end), []).append(primitive)
            self.beziers_by_endpoints.setdefault((end, start), []).append(primitive)
            self.beziers.append((primitive, _primitive_bounds(primitive)))
            return
        self.fallback.setdefault(type(primitive), []).append(primitive)

    def _candidates(self, candidate: MirrorPrimitive) -> Iterable[MirrorPrimitive]:
        tolerance = self.tolerance
        if isinstance(candidate, PointPrimitive):
            for key in _near_point_keys(candidate.point, tolerance):
                yield from self.points.get(key, ())
            return
        if isinstance(candidate, LinePrimitive):
            for key in _near_line_keys(candidate, tolerance):
                yield from self.lines.get(key, ())
            yield from self.fallback.get(LinePrimitive, ())
            return
        if isinstance(candidate, CirclePrimitive):
            radius = math.dist(candidate.center, candidate.radius_point)
            for key in _near_circle_keys(candidate.center, radius, tolerance):
                yield from self.circles.get(key, ())
            return
        if isinstance(candidate, ArcPrimitive):
            parameterization = _circle_arc_parameterization(candidate.start, candidate.end, candidate.control)
            if parameterization is not None:
                for key in _near_circle_keys(parameterization.center, parameterization.radius, tolerance):
                    yield from self.arcs.get(key, ())
            yield from self.fallback.get(ArcPrimitive, ())
            return
        if isinstance(candidate, BezierPrimitive):
            start = _point_key(candidate.start, tolerance)
            end = _point_key(candidate.end, tolerance)
            yielded: set[int] = set()
            for item in self.beziers_by_endpoints.get((start, end), ()):
                yielded.add(id(item))
                yield item
            candidate_bounds = _primitive_bounds(candidate)
            for item, bounds in self.beziers:
                if id(item) in yielded or not _bounds_can_cover(bounds, candidate_bounds, tolerance):
                    continue
                yield item
            return
        yield from self.fallback.get(type(candidate), ())

    def covers(self, candidate: MirrorPrimitive) -> bool:
        return any(_primitive_covers(item, candidate, self.tolerance) for item in self._candidates(candidate))


def build_mirror_plan(
    sources: Iterable[MirrorPrimitive],
    axis: MirrorAxis,
    *,
    existing: Iterable[MirrorPrimitive] = (),
    tolerance: float = 1.0e-6,
) -> MirrorPlan:
    source_values = tuple(sources)
    existing_values = tuple(existing)
    existing_index = _PrimitiveCoverageIndex(existing_values, tolerance)
    additions_index = _PrimitiveCoverageIndex((), tolerance)
    additions: list[MirrorPrimitive] = []
    split_count = 0
    on_axis_count = 0
    duplicate_count = 0

    for primitive in source_values:
        pieces: list[MirrorPrimitive]
        split = False
        on_axis = False
        if isinstance(primitive, (LinePrimitive, ArcPrimitive, BezierPrimitive)):
            pieces, split, on_axis = _split_open_primitive(primitive, axis)
        elif isinstance(primitive, PointPrimitive):
            if abs(axis.signed_distance(primitive.point)) <= tolerance:
                pieces, on_axis = [], True
            else:
                pieces = [primitive]
        elif isinstance(primitive, CirclePrimitive):
            # A circle whose center lies on the axis is already globally
            # symmetric. An off-axis circle is mirrored as a whole, even when it
            # geometrically crosses the axis.
            if abs(axis.signed_distance(primitive.center)) <= tolerance:
                pieces, on_axis = [], True
            else:
                pieces = [primitive]
        else:
            pieces = []
        if split:
            split_count += 1
        if on_axis:
            on_axis_count += 1
        for piece in pieces:
            mirrored = _reflect_primitive(piece, axis)
            if existing_index.covers(mirrored):
                duplicate_count += 1
                continue
            if additions_index.covers(mirrored):
                duplicate_count += 1
                continue
            additions.append(mirrored)
            additions_index.add(mirrored)

    return MirrorPlan(
        axis=axis,
        additions=tuple(additions),
        source_count=len(source_values),
        split_source_count=split_count,
        skipped_on_axis_count=on_axis_count,
        skipped_duplicate_count=duplicate_count,
    )


__all__ = [
    "ArcPrimitive",
    "BezierPrimitive",
    "CirclePrimitive",
    "LinePrimitive",
    "MirrorAxis",
    "MirrorPlan",
    "MirrorPrimitive",
    "PointPrimitive",
    "build_mirror_plan",
    "sample_primitive",
]

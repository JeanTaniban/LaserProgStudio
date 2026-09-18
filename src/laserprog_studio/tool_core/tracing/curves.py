"""Dimension-neutral curve helpers for tracing tools."""
from __future__ import annotations

import math
from typing import Iterable, Sequence

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
_EPS = 1.0e-12


def distance3(first: Point3, second: Point3) -> float:
    return math.sqrt(sum((float(second[i]) - float(first[i])) ** 2 for i in range(3)))


def polyline_length(points: Sequence[Point3]) -> float:
    return sum(distance3(points[index - 1], points[index]) for index in range(1, len(points)))


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a: Point3, b: Point3) -> Point3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _scale(v: Point3, factor: float) -> Point3:
    return (v[0] * factor, v[1] * factor, v[2] * factor)


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v: Point3) -> float:
    return math.sqrt(_dot(v, v))


def _normalize(v: Point3) -> Point3 | None:
    length = _norm(v)
    if length <= _EPS:
        return None
    return _scale(v, 1.0 / length)


def sample_circular_arc_3d(start: Point3, end: Point3, control: Point3, *, segments: int = 24) -> tuple[Point3, ...]:
    """Sample the circular arc through three coplanar 3D points.

    Degenerate triples fall back to a quadratic curve.  This keeps preview code
    deterministic while the topology validator can still report the invalid arc.
    """

    segments = max(4, int(segments))
    s = tuple(float(v) for v in start)
    e = tuple(float(v) for v in end)
    c = tuple(float(v) for v in control)
    chord = _sub(e, s)
    to_control = _sub(c, s)
    axis_u = _normalize(chord)
    normal = _normalize(_cross(chord, to_control))
    if axis_u is None or normal is None:
        return tuple(
            _add(_add(_scale(s, (1.0 - t) ** 2), _scale(c, 2.0 * (1.0 - t) * t)), _scale(e, t * t))
            for t in (index / segments for index in range(segments + 1))
        )
    axis_v = _normalize(_cross(normal, axis_u))
    if axis_v is None:
        return (s, e)

    ex = _dot(_sub(e, s), axis_u)
    ey = _dot(_sub(e, s), axis_v)
    cx = _dot(_sub(c, s), axis_u)
    cy = _dot(_sub(c, s), axis_v)
    det = 2.0 * (0.0 * (cy - ey) + cx * (ey - 0.0) + ex * (0.0 - cy))
    if abs(det) <= _EPS:
        return tuple(
            _add(_add(_scale(s, (1.0 - t) ** 2), _scale(c, 2.0 * (1.0 - t) * t)), _scale(e, t * t))
            for t in (index / segments for index in range(segments + 1))
        )
    c2 = cx * cx + cy * cy
    e2 = ex * ex + ey * ey
    ox = (c2 * ey - e2 * cy) / det
    oy = (e2 * cx - c2 * ex) / det
    radius = math.hypot(ox, oy)
    if radius <= _EPS or not math.isfinite(radius):
        return (s, e)

    def angle(x: float, y: float) -> float:
        return math.atan2(y - oy, x - ox)

    a0 = angle(0.0, 0.0)
    a1 = angle(ex, ey)
    ac = angle(cx, cy)
    ccw = (a1 - a0) % math.tau
    control_on_ccw = (ac - a0) % math.tau <= ccw + 1.0e-9
    sweep = ccw if control_on_ccw else -((a0 - a1) % math.tau)
    result: list[Point3] = []
    for index in range(segments + 1):
        theta = a0 + sweep * (index / segments)
        local = _add(_scale(axis_u, ox + math.cos(theta) * radius), _scale(axis_v, oy + math.sin(theta) * radius))
        result.append(_add(s, local))
    return tuple(result)


def max_plane_deviation(points: Iterable[Point3], *, origin: Point3, normal: Point3) -> float:
    unit = _normalize(normal)
    if unit is None:
        return math.inf
    return max((abs(_dot(_sub(tuple(float(v) for v in point), origin), unit)) for point in points), default=0.0)


__all__ = ["Point2", "Point3", "distance3", "max_plane_deviation", "polyline_length", "sample_circular_arc_3d"]

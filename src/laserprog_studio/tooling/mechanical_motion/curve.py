# -*- coding: utf-8 -*-
from __future__ import annotations

from bisect import bisect_left
from math import dist
from typing import Iterable

from .models import Point3, point3


def cubic_bezier(p0: Point3, p1: Point3, p2: Point3, p3: Point3, t: float) -> Point3:
    u = 1.0 - float(t)
    a = u * u * u
    b = 3.0 * u * u * float(t)
    c = 3.0 * u * float(t) * float(t)
    d = float(t) * float(t) * float(t)
    return (
        a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
        a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
        a * p0[2] + b * p1[2] + c * p2[2] + d * p3[2],
    )


def sample_bezier(points: Iterable[Point3], *, segments: int = 96) -> tuple[Point3, ...]:
    p0, p1, p2, p3 = tuple(point3(value) for value in points)
    count = max(4, int(segments))
    return tuple(cubic_bezier(p0, p1, p2, p3, i / count) for i in range(count + 1))


def cumulative_lengths(samples: Iterable[Point3]) -> tuple[tuple[Point3, ...], tuple[float, ...]]:
    pts = tuple(point3(value) for value in samples)
    if not pts:
        return (), ()
    values = [0.0]
    for previous, current in zip(pts, pts[1:]):
        values.append(values[-1] + dist(previous, current))
    return pts, tuple(values)


def point_at_arc_fraction(samples: Iterable[Point3], fraction: float) -> Point3:
    pts, lengths = cumulative_lengths(samples)
    if not pts:
        return (0.0, 0.0, 0.0)
    if len(pts) == 1 or lengths[-1] <= 1e-12:
        return pts[0]
    wanted = max(0.0, min(1.0, float(fraction))) * lengths[-1]
    index = min(len(lengths) - 1, max(1, bisect_left(lengths, wanted)))
    before = lengths[index - 1]
    after = lengths[index]
    local = 0.0 if after <= before else (wanted - before) / (after - before)
    a, b = pts[index - 1], pts[index]
    return (
        a[0] + (b[0] - a[0]) * local,
        a[1] + (b[1] - a[1]) * local,
        a[2] + (b[2] - a[2]) * local,
    )


def equally_spaced_curve_points(points: Iterable[Point3], count: int, *, samples: int = 384) -> tuple[Point3, ...]:
    amount = max(2, int(count))
    curve = sample_bezier(points, segments=max(samples, amount * 32))
    result = [point_at_arc_fraction(curve, i / (amount - 1)) for i in range(amount)]
    source = tuple(point3(value) for value in points)
    result[0] = source[0]
    result[-1] = source[-1]
    return tuple(result)


def default_controls(start: Point3, end: Point3, *, bulge: float = 0.0) -> tuple[Point3, Point3]:
    start = point3(start)
    end = point3(end)
    dx, dy, dz = end[0] - start[0], end[1] - start[1], end[2] - start[2]
    planar_length = max(1e-9, (dx * dx + dy * dy) ** 0.5)
    nx, ny = -dy / planar_length, dx / planar_length
    offset = float(bulge) * planar_length
    return (
        (start[0] + dx / 3.0 + nx * offset, start[1] + dy / 3.0 + ny * offset, start[2] + dz / 3.0),
        (start[0] + 2.0 * dx / 3.0 + nx * offset, start[1] + 2.0 * dy / 3.0 + ny * offset, start[2] + 2.0 * dz / 3.0),
    )


__all__ = [
    "cubic_bezier",
    "cumulative_lengths",
    "default_controls",
    "equally_spaced_curve_points",
    "point_at_arc_fraction",
    "sample_bezier",
]

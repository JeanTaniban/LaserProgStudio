"""Curve sampling helpers for sketch previews and face solving."""
from __future__ import annotations

import math

Point2 = tuple[float, float]


def sample_circle(center: Point2, radius: float, *, segments: int = 64) -> list[Point2]:
    if radius <= 0.0:
        return []
    segments = max(12, int(segments))
    return [
        (center[0] + math.cos(index * math.tau / segments) * radius, center[1] + math.sin(index * math.tau / segments) * radius)
        for index in range(segments)
    ]


def sample_quadratic_arc(start: Point2, end: Point2, control: Point2, *, segments: int = 24) -> list[Point2]:
    segments = max(4, int(segments))
    points: list[Point2] = []
    for index in range(segments + 1):
        t = index / segments
        omt = 1.0 - t
        x = omt * omt * start[0] + 2.0 * omt * t * control[0] + t * t * end[0]
        y = omt * omt * start[1] + 2.0 * omt * t * control[1] + t * t * end[1]
        points.append((x, y))
    return points




def sample_cubic_bezier(
    start: Point2,
    control_1: Point2,
    control_2: Point2,
    end: Point2,
    *,
    segments: int = 48,
) -> list[Point2]:
    """Sample a cubic Bézier curve with exact authored endpoints."""

    segments = max(8, int(segments))
    points: list[Point2] = []
    for index in range(segments + 1):
        t = index / segments
        omt = 1.0 - t
        x = (
            omt * omt * omt * float(start[0])
            + 3.0 * omt * omt * t * float(control_1[0])
            + 3.0 * omt * t * t * float(control_2[0])
            + t * t * t * float(end[0])
        )
        y = (
            omt * omt * omt * float(start[1])
            + 3.0 * omt * omt * t * float(control_1[1])
            + 3.0 * omt * t * t * float(control_2[1])
            + t * t * t * float(end[1])
        )
        points.append((x, y))
    points[0] = (float(start[0]), float(start[1]))
    points[-1] = (float(end[0]), float(end[1]))
    return points

def sample_circular_arc_through_points(start: Point2, end: Point2, control: Point2, *, segments: int = 24) -> list[Point2]:
    """Sample the circular arc from ``start`` to ``end`` passing through ``control``.

    If the three points are collinear or too close to define a stable circle, the
    function falls back to the existing quadratic arc sampler.  The chosen sweep
    is the one that contains the control point, which is exactly what sketch
    tools expect when a user defines an arc with three points.
    """

    segments = max(4, int(segments))
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    cx, cy = float(control[0]), float(control[1])
    det = 2.0 * (sx * (cy - ey) + cx * (ey - sy) + ex * (sy - cy))
    if abs(det) <= 1.0e-12:
        return sample_quadratic_arc(start, end, control, segments=segments)

    s2 = sx * sx + sy * sy
    c2 = cx * cx + cy * cy
    e2 = ex * ex + ey * ey
    ox = (s2 * (cy - ey) + c2 * (ey - sy) + e2 * (sy - cy)) / det
    oy = (s2 * (ex - cx) + c2 * (sx - ex) + e2 * (cx - sx)) / det
    radius = math.hypot(sx - ox, sy - oy)
    if radius <= 1.0e-12 or not math.isfinite(radius):
        return sample_quadratic_arc(start, end, control, segments=segments)

    a0 = math.atan2(sy - oy, sx - ox)
    a1 = math.atan2(ey - oy, ex - ox)
    ac = math.atan2(cy - oy, cx - ox)

    def ccw_delta(a: float, b: float) -> float:
        return (b - a) % math.tau

    ccw_sweep = ccw_delta(a0, a1)
    control_on_ccw = ccw_delta(a0, ac) <= ccw_sweep + 1.0e-9
    sweep = ccw_sweep if control_on_ccw else -ccw_delta(a1, a0)

    return [
        (
            ox + math.cos(a0 + sweep * (index / segments)) * radius,
            oy + math.sin(a0 + sweep * (index / segments)) * radius,
        )
        for index in range(segments + 1)
    ]

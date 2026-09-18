# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Iterable

from .contracts import Vec2
from .validation import dedupe_consecutive_points, distance2d


def catmull_rom_point(p0: Vec2, p1: Vec2, p2: Vec2, p3: Vec2, t: float) -> Vec2:
    """Return a deterministic Catmull-Rom sample for geometry tests.

    The vent tool no longer uses Catmull-Rom for its generated centerline,
    because it can overshoot at tight turns and invalidate an otherwise safe
    compact duct.  The function remains exported for callers that need the
    classic interpolation explicitly.
    """

    tt = float(t)
    t2 = tt * tt
    t3 = t2 * tt
    return (
        0.5
        * (
            (2.0 * float(p1[0]))
            + (-float(p0[0]) + float(p2[0])) * tt
            + (2.0 * float(p0[0]) - 5.0 * float(p1[0]) + 4.0 * float(p2[0]) - float(p3[0])) * t2
            + (-float(p0[0]) + 3.0 * float(p1[0]) - 3.0 * float(p2[0]) + float(p3[0])) * t3
        ),
        0.5
        * (
            (2.0 * float(p1[1]))
            + (-float(p0[1]) + float(p2[1])) * tt
            + (2.0 * float(p0[1]) - 5.0 * float(p1[1]) + 4.0 * float(p2[1]) - float(p3[1])) * t2
            + (-float(p0[1]) + 3.0 * float(p1[1]) - 3.0 * float(p2[1]) + float(p3[1])) * t3
        ),
    )


def _sub(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _add(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]))


def _scale(v: Vec2, k: float) -> Vec2:
    return (float(v[0]) * float(k), float(v[1]) * float(k))


def _unit(v: Vec2) -> Vec2:
    n = math.hypot(float(v[0]), float(v[1]))
    if n <= 1e-12 or not math.isfinite(n):
        return (1.0, 0.0)
    return (float(v[0]) / n, float(v[1]) / n)


def _quadratic_bezier(a: Vec2, control: Vec2, b: Vec2, t: float) -> Vec2:
    u = 1.0 - float(t)
    return (
        u * u * float(a[0]) + 2.0 * u * float(t) * float(control[0]) + float(t) * float(t) * float(b[0]),
        u * u * float(a[1]) + 2.0 * u * float(t) * float(control[1]) + float(t) * float(t) * float(b[1]),
    )


def smooth_path_points(points: Iterable[Vec2], *, samples_per_segment: int = 10) -> list[Vec2]:
    """Sample the centerline used by the vent preview and mesh generator.

    The sampler uses non-overshooting rounded corners rather than Catmull-Rom.
    That is safer for ducts: a path that respects the minimum wall distance at
    the waypoints should not become invalid simply because the visual smoothing
    curve overshot into a neighboring airway.
    """

    pts = dedupe_consecutive_points(points)
    if len(pts) <= 2:
        return pts
    samples = max(2, int(samples_per_segment))
    out: list[Vec2] = [pts[0]]
    for i in range(1, len(pts) - 1):
        prev_pt, corner, next_pt = pts[i - 1], pts[i], pts[i + 1]
        d_prev = distance2d(prev_pt, corner)
        d_next = distance2d(corner, next_pt)
        if d_prev <= 1e-9 or d_next <= 1e-9:
            continue
        # Keep the fillet local and inside the two adjacent segments.
        cut = min(d_prev, d_next) * 0.33
        start = _add(corner, _scale(_unit(_sub(prev_pt, corner)), cut))
        end = _add(corner, _scale(_unit(_sub(next_pt, corner)), cut))
        if distance2d(out[-1], start) > 1e-6:
            out.append(start)
        for s in range(1, samples + 1):
            out.append(_quadratic_bezier(start, corner, end, s / samples))
    if distance2d(out[-1], pts[-1]) > 1e-6:
        out.append(pts[-1])
    cleaned: list[Vec2] = []
    for p in out:
        if not cleaned or distance2d(cleaned[-1], p) > 1e-6:
            cleaned.append((float(p[0]), float(p[1])))
    return cleaned


def polyline_length(points: Iterable[Vec2]) -> float:
    pts = [(float(u), float(v)) for u, v in points]
    if len(pts) < 2:
        return 0.0
    return float(sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1)))

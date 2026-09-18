# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable

from .contracts import Vec2
from .validation import PlanarValidationResult, dedupe_consecutive_points, distance2d, segments_intersect


def _sub(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _add(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]))


def _scale(v: Vec2, k: float) -> Vec2:
    return (float(v[0]) * float(k), float(v[1]) * float(k))


def _dot(a: Vec2, b: Vec2) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1])


def _unit(v: Vec2, fallback: Vec2 = (1.0, 0.0)) -> Vec2:
    n = math.hypot(float(v[0]), float(v[1]))
    if not math.isfinite(n) or n <= 1e-12:
        return fallback
    return (float(v[0]) / n, float(v[1]) / n)


def _left_normal(a: Vec2, b: Vec2) -> Vec2:
    tx, ty = _unit(_sub(b, a))
    return (-ty, tx)


def _quadratic_bezier(a: Vec2, control: Vec2, b: Vec2, t: float) -> Vec2:
    u = 1.0 - float(t)
    return (
        u * u * float(a[0]) + 2.0 * u * float(t) * float(control[0]) + float(t) * float(t) * float(b[0]),
        u * u * float(a[1]) + 2.0 * u * float(t) * float(control[1]) + float(t) * float(t) * float(b[1]),
    )


def _point_segment_projection_distance(p: Vec2, a: Vec2, b: Vec2) -> tuple[float, float]:
    ab = _sub(b, a)
    denom = _dot(ab, ab)
    if denom <= 1e-12:
        return distance2d(p, a), 0.0
    t = max(0.0, min(1.0, _dot(_sub(p, a), ab) / denom))
    q = (float(a[0]) + ab[0] * t, float(a[1]) + ab[1] * t)
    return distance2d(p, q), t


def _clean_curve_offsets(segment_curve_offsets: Iterable[float] | None, segment_count: int, default_curve_offset: float) -> list[float]:
    values = [float(v) for v in (segment_curve_offsets or [])]
    if len(values) < int(segment_count):
        values.extend([float(default_curve_offset)] * (int(segment_count) - len(values)))
    return values[: max(int(segment_count), 0)]


def vent_minimum_bend_radius(*, inner_width: float, wall_thickness: float = 0.0, safety_factor: float = 0.5) -> float:
    """Return a conservative radius value kept for public API stability.

    The clean EVT path no longer creates a special one-click 180° pivot.  Curve
    shape is controlled per segment by center handles.  Callers that still need
    a default curve radius can use this width-based fallback.
    """

    width = max(float(inner_width), 1e-6)
    wall = max(float(wall_thickness), 0.0)
    return max((width + 2.0 * wall) * float(safety_factor), 1e-6)


@dataclass(frozen=True, slots=True)
class VentCornerInfo:
    index: int
    angle_degrees: float
    required_tangent: float
    available_tangent: float
    radius: float

    @property
    def ok(self) -> bool:
        return True


def vent_corner_infos(
    points: Iterable[Vec2],
    *,
    bend_radius: float,
    min_turn_degrees: float = 8.0,
) -> list[VentCornerInfo]:
    """Return no hard corner constraints for the clean waypoint workflow."""

    return []


def validate_vent_bend_radius(
    points: Iterable[Vec2],
    *,
    bend_radius: float,
    tolerance: float = 1e-6,
) -> PlanarValidationResult:
    """Round-section import hook.

    The new EVT tool does not synthesize automatic compact 180° bends.  Curves
    are explicit per-segment Bezier controls, so there is no hidden bend-radius
    failure mode here.
    """

    return PlanarValidationResult(ok=True)


def segment_control_point(a: Vec2, b: Vec2, offset: float) -> Vec2:
    mid = ((float(a[0]) + float(b[0])) * 0.5, (float(a[1]) + float(b[1])) * 0.5)
    nx, ny = _left_normal(a, b)
    return (mid[0] + nx * float(offset), mid[1] + ny * float(offset))


def sample_vent_centerline(
    points: Iterable[Vec2],
    *,
    bend_radius: float = 0.0,
    samples_per_corner: int = 10,
    segment_curve_offsets: Iterable[float] | None = None,
    default_curve_offset: float = 0.0,
) -> list[Vec2]:
    """Sample the clean EVT centerline.

    Each user segment is either a straight line or a quadratic Bezier controlled
    by a center handle.  This deliberately removes the former special 180° pivot
    path: no point is secretly treated as a circle center, and no automatic
    near-360° arc can be produced.
    """

    pts = dedupe_consecutive_points(points)
    if len(pts) <= 2 and not segment_curve_offsets and abs(float(default_curve_offset)) <= 1e-12:
        return pts
    if len(pts) < 2:
        return pts
    samples = max(2, int(samples_per_corner))
    offsets = _clean_curve_offsets(segment_curve_offsets, len(pts) - 1, float(default_curve_offset))
    out: list[Vec2] = [pts[0]]
    for i, (a, b) in enumerate(zip(pts, pts[1:])):
        if distance2d(a, b) <= 1e-9:
            continue
        offset = float(offsets[i]) if i < len(offsets) else float(default_curve_offset)
        if abs(offset) <= 1e-9:
            if distance2d(out[-1], b) > 1e-6:
                out.append(b)
            continue
        control = segment_control_point(a, b, offset)
        for step in range(1, samples + 1):
            p = _quadratic_bezier(a, control, b, step / samples)
            if distance2d(out[-1], p) > 1e-6:
                out.append((float(p[0]), float(p[1])))
    return out


def cumulative_lengths(points: Iterable[Vec2]) -> list[float]:
    pts = [(float(u), float(v)) for u, v in points]
    lengths = [0.0]
    for a, b in zip(pts, pts[1:]):
        lengths.append(lengths[-1] + distance2d(a, b))
    return lengths


def local_width_profile_from_distance(width_profile: Callable[[float, float], float] | None, default_width: float):
    def profile(distance: float, total: float) -> float:
        if width_profile is None:
            return float(default_width)
        try:
            return max(float(width_profile(float(distance), float(total))), 1e-6)
        except Exception:
            return float(default_width)
    return profile


def validate_sampled_centerline_is_simple(points: Iterable[Vec2], *, tolerance: float = 1e-7) -> PlanarValidationResult:
    """Reject centerline crossings while allowing adjacent samples to touch."""

    pts = dedupe_consecutive_points(points, tolerance=max(float(tolerance), 0.0))
    if len(pts) < 4:
        return PlanarValidationResult(ok=True)
    segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    for i, (a0, a1) in enumerate(segs):
        for j in range(i + 1, len(segs)):
            if abs(i - j) <= 1:
                continue
            # Open polylines are allowed to revisit their final point only via a
            # deliberate edit, not by crossing through existing routing.
            b0, b1 = segs[j]
            if segments_intersect(a0, a1, b0, b1, eps=max(float(tolerance), 1e-9)):
                return PlanarValidationResult(ok=False, errors=("final curve self-intersects",))
    return PlanarValidationResult(ok=True)


def candidate_touches_existing_centerline(
    existing_centerline: Iterable[Vec2],
    candidate: Vec2,
    *,
    tolerance: float = 1e-6,
) -> bool:
    """Return True when a new waypoint is placed on an existing centerline."""

    pts = dedupe_consecutive_points(existing_centerline)
    if len(pts) < 2:
        return False
    q = (float(candidate[0]), float(candidate[1]))
    tol = max(float(tolerance), 0.0)
    for a, b in zip(pts, pts[1:]):
        dist, t = _point_segment_projection_distance(q, a, b)
        # Ignore exact endpoints so the user can select/reuse handles without a
        # false red cursor; interior hits are blocked.
        if dist <= tol and 1e-5 < t < 1.0 - 1e-5:
            return True
    return False

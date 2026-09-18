# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable

from .contracts import Vec2, VentSectionKind
from .validation import PlanarValidationResult, dedupe_consecutive_points, distance2d, segments_intersect
from .vent_path_geometry import (
    sample_vent_centerline,
    validate_sampled_centerline_is_simple,
    validate_vent_bend_radius,
    vent_minimum_bend_radius,
)


@dataclass(frozen=True, slots=True)
class VentClearancePolicy:
    """Lightweight 2D routing contract for the clean EVT workflow."""

    section_kind: VentSectionKind = VentSectionKind.ROUND
    inner_width: float = 10.0
    wall_thickness: float = 3.0
    compact_wall_fusion: bool = False

    @property
    def allows_shared_walls(self) -> bool:
        return (self.section_kind is VentSectionKind.RECTANGLE or str(self.section_kind) == VentSectionKind.RECTANGLE.value) and bool(self.compact_wall_fusion)

    @property
    def min_centerline_spacing(self) -> float:
        width = max(float(self.inner_width), 1e-6)
        wall = max(float(self.wall_thickness), 1e-6)
        return width + (wall if self.allows_shared_walls else 2.0 * wall)

    @property
    def outer_width(self) -> float:
        return max(float(self.inner_width) + 2.0 * float(self.wall_thickness), 1e-6)

    @property
    def mode_label(self) -> str:
        return "preview lignes / validation croisement"


@dataclass(frozen=True, slots=True)
class VentClampResult:
    """Validation result for a waypoint candidate.

    The previous EVT tool tried to clamp/reposition invalid points.  The clean
    workflow intentionally does not: invalid points stay red and are not placed.
    """

    point: Vec2
    raw_point: Vec2
    valid: bool
    was_clamped: bool = False
    message: str = ""


def make_vent_clearance_policy(
    *,
    section_kind: VentSectionKind | str,
    section_width: float,
    wall_thickness: float,
    compact_wall_fusion: bool = False,
) -> VentClearancePolicy:
    kind = section_kind if isinstance(section_kind, VentSectionKind) else VentSectionKind(str(section_kind))
    return VentClearancePolicy(
        section_kind=kind,
        inner_width=max(float(section_width), 1e-6),
        wall_thickness=max(float(wall_thickness), 1e-6),
        compact_wall_fusion=bool(compact_wall_fusion),
    )


def _sub(a: Vec2, b: Vec2) -> Vec2:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _dot(a: Vec2, b: Vec2) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1])


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _point_segment_distance(p: Vec2, a: Vec2, b: Vec2) -> float:
    ab = _sub(b, a)
    denom = _dot(ab, ab)
    if denom <= 1e-12:
        return distance2d(p, a)
    t = _clamp01(_dot(_sub(p, a), ab) / denom)
    q = (float(a[0]) + ab[0] * t, float(a[1]) + ab[1] * t)
    return distance2d(p, q)


def segment_distance(a: Vec2, b: Vec2, c: Vec2, d: Vec2) -> float:
    """Minimum distance between two 2D segments."""

    if segments_intersect(a, b, c, d, eps=1e-9):
        return 0.0
    return min(
        _point_segment_distance(a, c, d),
        _point_segment_distance(b, c, d),
        _point_segment_distance(c, a, b),
        _point_segment_distance(d, a, b),
    )


def _sample_with_profile(
    waypoints: Iterable[Vec2],
    *,
    bend_radius: float | None = None,
    samples_per_segment: int = 8,
    segment_curve_offsets: Iterable[float] | None = None,
    default_curve_offset: float = 0.0,
) -> list[Vec2]:
    return sample_vent_centerline(
        waypoints,
        bend_radius=float(bend_radius or 0.0),
        samples_per_corner=max(2, int(samples_per_segment)),
        segment_curve_offsets=segment_curve_offsets,
        default_curve_offset=float(default_curve_offset),
    )


def validate_vent_centerline_clearance(
    waypoints: Iterable[Vec2],
    policy: VentClearancePolicy,
    *,
    tolerance: float = 1e-6,
    adjacency_window: int = 1,
) -> PlanarValidationResult:
    """Validate that the edited centerline does not self-cross.

    The clean EVT editor no longer blocks merely-close parallel passes.  Widths
    are shown in preview and grid spacing helps place adjacent ducts.  We still
    block true centerline crossings because they produce ambiguous meshes.
    """

    return validate_sampled_centerline_is_simple(waypoints, tolerance=tolerance)


def validate_vent_centerline_clearance_variable(
    waypoints: Iterable[Vec2],
    policy: VentClearancePolicy,
    width_profile: Callable[[float, float], float],
    *,
    tolerance: float = 1e-6,
    adjacency_window: int = 1,
    local_skip_factor: float = 0.0,
) -> PlanarValidationResult:
    return validate_vent_centerline_clearance(waypoints, policy, tolerance=tolerance, adjacency_window=adjacency_window)


def validate_vent_waypoints_and_curve(
    waypoints: Iterable[Vec2],
    policy: VentClearancePolicy,
    *,
    tolerance: float = 1e-6,
    samples_per_segment: int = 8,
    width_profile: Callable[[float, float], float] | None = None,
    bend_radius: float | None = None,
    segment_curve_offsets: Iterable[float] | None = None,
    default_curve_offset: float = 0.0,
) -> PlanarValidationResult:
    """Validate the final centerline used by preview and mesh generation."""

    bend_result = validate_vent_bend_radius(waypoints, bend_radius=float(bend_radius or 0.0), tolerance=tolerance)
    sampled = _sample_with_profile(
        waypoints,
        bend_radius=bend_radius,
        samples_per_segment=samples_per_segment,
        segment_curve_offsets=segment_curve_offsets,
        default_curve_offset=default_curve_offset,
    )
    curve_result = validate_sampled_centerline_is_simple(sampled, tolerance=tolerance)
    curve_errors = tuple(f"final curve: {err}" for err in curve_result.errors)
    curve_warnings = tuple(f"final curve: {warn}" for warn in curve_result.warnings)
    return PlanarValidationResult(
        ok=bool(bend_result.ok and curve_result.ok),
        errors=tuple(bend_result.errors) + curve_errors,
        warnings=tuple(bend_result.warnings) + curve_warnings,
    )


def _with_candidate(points: list[Vec2], candidate: Vec2, *, index: int | None) -> list[Vec2]:
    cand = (float(candidate[0]), float(candidate[1]))
    out = list(points)
    if index is None:
        out.append(cand)
    elif 0 <= int(index) < len(out):
        out[int(index)] = cand
    else:
        out.append(cand)
    return out


def clamp_vent_waypoint_candidate(
    waypoints: Iterable[Vec2],
    candidate: Vec2,
    policy: VentClearancePolicy,
    *,
    index: int | None = None,
    anchor: Vec2 | None = None,
    tolerance: float = 1e-6,
    iterations: int = 24,
    width_profile_factory: Callable[[list[Vec2]], Callable[[float, float], float] | None] | None = None,
    bend_radius: float | None = None,
    segment_curve_offsets: Iterable[float] | None = None,
    default_curve_offset: float = 0.0,
) -> VentClampResult:
    """Validate a waypoint candidate without moving it.

    Invalid candidates are returned unchanged with ``valid=False``.  This gives
    the UI a red cursor and prevents placement instead of inventing a nearby
    replacement point.
    """

    pts = [(float(u), float(v)) for u, v in waypoints]
    raw = (float(candidate[0]), float(candidate[1]))
    # A waypoint may now be placed on or near an existing centerline.  The UI no
    # longer tries to prevent that touch case: only the final centerline
    # self-crossing validation below can refuse an edit.

    proposed = _with_candidate(pts, raw, index=index)
    validation = validate_vent_waypoints_and_curve(
        proposed,
        policy,
        tolerance=tolerance,
        width_profile=width_profile_factory(proposed) if width_profile_factory is not None else None,
        bend_radius=bend_radius,
        segment_curve_offsets=segment_curve_offsets,
        default_curve_offset=default_curve_offset,
    )
    if validation.ok:
        return VentClampResult(point=raw, raw_point=raw, valid=True, was_clamped=False, message="")
    return VentClampResult(point=raw, raw_point=raw, valid=False, was_clamped=False, message=validation.message())

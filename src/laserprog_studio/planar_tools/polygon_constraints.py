# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .contracts import Vec2
from .validation import (
    PlanarValidationResult,
    dedupe_consecutive_points,
    distance2d,
    polygon_self_intersections,
    validate_polygon_for_extrusion,
)


@dataclass(frozen=True, slots=True)
class PolygonClampResult:
    """Result of a safe polygon point placement/edit attempt.

    The polygon trace tool uses this to keep the drawn polygon simple while the
    pointer is dragged.  ``point`` is always the point that should be displayed
    and committed.  ``raw_point`` preserves the position requested by the user
    so the preview can draw a red helper when the edit had to be clamped.
    """

    point: Vec2
    raw_point: Vec2
    valid: bool = True
    was_clamped: bool = False
    message: str = ""


def _as_point(point: Vec2) -> Vec2:
    return (float(point[0]), float(point[1]))


def _open_polyline_intersections(points: Iterable[Vec2], *, tolerance: float = 1e-9) -> tuple[tuple[int, int], ...]:
    """Return intersections between non-adjacent open polyline segments."""

    from .validation import segments_intersect

    pts = dedupe_consecutive_points(points, tolerance=tolerance)
    if len(pts) < 4:
        return ()
    hits: list[tuple[int, int]] = []
    for i in range(len(pts) - 1):
        a0, a1 = pts[i], pts[i + 1]
        for j in range(i + 1, len(pts) - 1):
            if abs(i - j) <= 1:
                continue
            b0, b1 = pts[j], pts[j + 1]
            if segments_intersect(a0, a1, b0, b1, eps=tolerance):
                hits.append((i, j))
    return tuple(hits)


def validate_open_polygon_trace(points: Iterable[Vec2], *, tolerance: float = 1e-7) -> PlanarValidationResult:
    """Validate the editable/open state of a polygon trace.

    A not-yet-closed polygon is allowed to have fewer than three points and no
    area, but its visible segments must stay non self-crossing.  This is the
    rule used while the pointer follows the mouse in ADD or MOD mode.
    """

    original = [_as_point(p) for p in points]
    pts = dedupe_consecutive_points(original, tolerance=tolerance)
    errors: list[str] = []
    warnings: list[str] = []
    if _open_polyline_intersections(pts, tolerance=tolerance):
        errors.append("self-intersecting segment")
    if len(pts) != len(original):
        warnings.append("duplicate points ignored")
    return PlanarValidationResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def validate_polygon_edit_state(
    points: Iterable[Vec2],
    *,
    closed: bool,
    extrusion_depth: float = 1.0,
    tolerance: float = 1e-7,
) -> PlanarValidationResult:
    """Validate an intermediate polygon edit according to its closed state."""

    if bool(closed):
        return validate_polygon_for_extrusion(points, closed=True, extrusion_depth=max(abs(float(extrusion_depth)), 1.0), tolerance=tolerance)
    return validate_open_polygon_trace(points, tolerance=tolerance)


def polygon_edit_is_valid(
    points: Iterable[Vec2],
    *,
    closed: bool,
    extrusion_depth: float = 1.0,
    tolerance: float = 1e-7,
) -> bool:
    return validate_polygon_edit_state(points, closed=closed, extrusion_depth=extrusion_depth, tolerance=tolerance).ok


def polygon_close_is_valid(
    points: Iterable[Vec2],
    *,
    extrusion_depth: float = 1.0,
    tolerance: float = 1e-7,
) -> PlanarValidationResult:
    """Validate the shape that would be produced by closing the polygon."""

    return validate_polygon_for_extrusion(points, closed=True, extrusion_depth=max(abs(float(extrusion_depth)), 1.0), tolerance=tolerance)


def _replace_point(points: list[Vec2], index: int, point: Vec2) -> list[Vec2]:
    edited = list(points)
    edited[int(index)] = _as_point(point)
    return edited


def _append_point(points: list[Vec2], point: Vec2) -> list[Vec2]:
    return list(points) + [_as_point(point)]


def clamp_polygon_point_candidate(
    points: Iterable[Vec2],
    candidate: Vec2,
    *,
    index: int | None = None,
    closed: bool = False,
    extrusion_depth: float = 1.0,
    anchor: Vec2 | None = None,
    tolerance: float = 1e-7,
    iterations: int = 24,
) -> PolygonClampResult:
    """Clamp a candidate polygon point so the sketch stays non self-crossing.

    For ADD, pass ``index=None`` and the candidate is tested as a new trailing
    point.  For MOD, pass the edited point index.  If the raw candidate is
    invalid, the function binary-searches from a safe anchor toward the raw
    point and returns the farthest valid position found.
    """

    base = [_as_point(p) for p in points]
    raw = _as_point(candidate)
    if index is not None and not (0 <= int(index) < len(base)):
        return PolygonClampResult(point=raw, raw_point=raw, valid=False, was_clamped=False, message="invalid selected point")

    def make_shape(point: Vec2) -> list[Vec2]:
        return _replace_point(base, int(index), point) if index is not None else _append_point(base, point)

    if polygon_edit_is_valid(make_shape(raw), closed=closed, extrusion_depth=extrusion_depth, tolerance=tolerance):
        return PolygonClampResult(point=raw, raw_point=raw)

    if anchor is None:
        if index is not None:
            anchor = base[int(index)]
        elif base:
            anchor = base[-1]
        else:
            anchor = raw
    safe_anchor = _as_point(anchor)
    if not polygon_edit_is_valid(make_shape(safe_anchor), closed=closed, extrusion_depth=extrusion_depth, tolerance=tolerance):
        return PolygonClampResult(point=safe_anchor, raw_point=raw, valid=False, was_clamped=True, message="self-intersecting shape")

    lo = safe_anchor
    ax, ay = safe_anchor
    rx, ry = raw
    for _ in range(max(int(iterations), 1)):
        mid = ((ax + rx) * 0.5, (ay + ry) * 0.5)
        if polygon_edit_is_valid(make_shape(mid), closed=closed, extrusion_depth=extrusion_depth, tolerance=tolerance):
            lo = mid
            ax, ay = mid
        else:
            rx, ry = mid
    if distance2d(lo, raw) <= max(float(tolerance), 1e-9):
        return PolygonClampResult(point=raw, raw_point=raw)
    return PolygonClampResult(point=lo, raw_point=raw, valid=True, was_clamped=True, message="point clamped to avoid self-intersection")

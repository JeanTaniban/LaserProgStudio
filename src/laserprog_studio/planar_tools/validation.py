# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

from .contracts import Vec2


@dataclass(frozen=True, slots=True)
class PlanarValidationResult:
    """Small UI-independent validation result for planar drafts."""

    ok: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def message(self) -> str:
        return "; ".join(self.errors or self.warnings)


def distance2d(a: Vec2, b: Vec2) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def dedupe_consecutive_points(points: Iterable[Vec2], *, tolerance: float = 1e-7) -> list[Vec2]:
    """Return points without consecutive duplicates, including duplicate closure."""

    cleaned: list[Vec2] = []
    tol = max(float(tolerance), 0.0)
    for u, v in points:
        point = (float(u), float(v))
        if cleaned and distance2d(cleaned[-1], point) <= tol:
            continue
        cleaned.append(point)
    if len(cleaned) > 2 and distance2d(cleaned[0], cleaned[-1]) <= tol:
        cleaned.pop()
    return cleaned


def signed_area(points: Iterable[Vec2]) -> float:
    pts = [(float(u), float(v)) for u, v in points]
    if len(pts) < 3:
        return 0.0
    total = 0.0
    for i, (x0, y0) in enumerate(pts):
        x1, y1 = pts[(i + 1) % len(pts)]
        total += x0 * y1 - x1 * y0
    return total * 0.5


def polygon_area(points: Iterable[Vec2]) -> float:
    return abs(signed_area(points))


def _orientation(a: Vec2, b: Vec2, c: Vec2) -> float:
    return (float(b[0]) - float(a[0])) * (float(c[1]) - float(a[1])) - (float(b[1]) - float(a[1])) * (float(c[0]) - float(a[0]))


def _on_segment(a: Vec2, b: Vec2, p: Vec2, *, eps: float) -> bool:
    return (
        min(float(a[0]), float(b[0])) - eps <= float(p[0]) <= max(float(a[0]), float(b[0])) + eps
        and min(float(a[1]), float(b[1])) - eps <= float(p[1]) <= max(float(a[1]), float(b[1])) + eps
        and abs(_orientation(a, b, p)) <= eps
    )


def segments_intersect(a: Vec2, b: Vec2, c: Vec2, d: Vec2, *, eps: float = 1e-9) -> bool:
    o1 = _orientation(a, b, c)
    o2 = _orientation(a, b, d)
    o3 = _orientation(c, d, a)
    o4 = _orientation(c, d, b)
    if (o1 > eps and o2 < -eps or o1 < -eps and o2 > eps) and (o3 > eps and o4 < -eps or o3 < -eps and o4 > eps):
        return True
    return (
        _on_segment(a, b, c, eps=eps)
        or _on_segment(a, b, d, eps=eps)
        or _on_segment(c, d, a, eps=eps)
        or _on_segment(c, d, b, eps=eps)
    )


def polygon_self_intersections(points: Iterable[Vec2], *, tolerance: float = 1e-9) -> tuple[tuple[int, int], ...]:
    """Return pairs of non-adjacent edges that intersect."""

    pts = dedupe_consecutive_points(points, tolerance=tolerance)
    n = len(pts)
    if n < 4:
        return ()
    hits: list[tuple[int, int]] = []
    for i in range(n):
        a0, a1 = pts[i], pts[(i + 1) % n]
        for j in range(i + 1, n):
            # Same edge, adjacent edges and first/last edge share a vertex and
            # are legal in a closed polygon.
            if j == i or j == (i + 1) % n or i == (j + 1) % n:
                continue
            if i == 0 and j == n - 1:
                continue
            b0, b1 = pts[j], pts[(j + 1) % n]
            if segments_intersect(a0, a1, b0, b1, eps=tolerance):
                hits.append((i, j))
    return tuple(hits)


def validate_polygon_for_extrusion(
    points: Iterable[Vec2],
    *,
    closed: bool,
    extrusion_depth: float,
    min_area: float = 1e-6,
    tolerance: float = 1e-7,
) -> PlanarValidationResult:
    original = [(float(u), float(v)) for u, v in points]
    pts = dedupe_consecutive_points(original, tolerance=tolerance)
    errors: list[str] = []
    warnings: list[str] = []
    if not bool(closed):
        errors.append("close the polygon")
    if len(pts) < 3:
        errors.append("add at least 3 points")
    if abs(float(extrusion_depth)) <= tolerance:
        errors.append("zero depth")
    area = polygon_area(pts)
    if len(pts) >= 3 and area <= max(float(min_area), tolerance):
        errors.append("area too small")
    intersections = polygon_self_intersections(pts, tolerance=tolerance)
    if intersections:
        errors.append("self-intersecting polygon")
    if len(pts) != len(original):
        warnings.append("duplicate points ignored")
    return PlanarValidationResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))


def validate_vent_path(
    waypoints: Iterable[Vec2],
    *,
    section_area: float,
    wall_thickness: float,
    min_length: float = 1e-6,
    tolerance: float = 1e-7,
) -> PlanarValidationResult:
    original = [(float(u), float(v)) for u, v in waypoints]
    pts = dedupe_consecutive_points(original, tolerance=tolerance)
    errors: list[str] = []
    warnings: list[str] = []
    if len(pts) < 2:
        errors.append("add at least 2 waypoints")
    if float(section_area) <= 0.0:
        errors.append("zero section")
    if float(wall_thickness) <= 0.0:
        errors.append("zero wall thickness")
    length = sum(distance2d(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) if len(pts) >= 2 else 0.0
    if len(pts) >= 2 and length <= max(float(min_length), tolerance):
        errors.append("path too short")
    if len(pts) != len(original):
        warnings.append("duplicate waypoints ignored")
    return PlanarValidationResult(ok=not errors, errors=tuple(errors), warnings=tuple(warnings))

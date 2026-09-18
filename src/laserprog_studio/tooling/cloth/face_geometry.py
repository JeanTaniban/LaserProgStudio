"""Robust geometric analysis for Cloth face boundaries.

Topology tells us that curve endpoints close.  This module additionally proves
that the *sampled geometric boundary* is a simple, usable panel before a face is
created.  It is intentionally shared by automatic face discovery, manual Face
mode and mesh generation so all three paths agree.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .models import ClothDocument, Point3
from .topology import PatchFrame, best_fit_boundary_frame, polygon_signed_area, sample_curve_loop_boundary

Point2 = tuple[float, float]
_EPS = 1.0e-9


@dataclass(frozen=True, slots=True)
class ClothLoopAnalysis:
    curve_ids: tuple[str, ...]
    boundary3: tuple[Point3, ...] = ()
    projected: tuple[Point2, ...] = ()
    frame: PatchFrame | None = None
    area: float = 0.0
    max_planarity_error_mm: float = 0.0
    self_intersects: bool = False
    valid: bool = False
    reason: str = ""


def analyze_curve_loop(
    document: ClothDocument,
    curve_ids: Sequence[str],
    *,
    arc_segments: int = 16,
    chord_tolerance_mm: float = 0.05,
    planarity_tolerance_mm: float = 0.05,
) -> ClothLoopAnalysis:
    ids = tuple(str(value) for value in curve_ids)
    boundary = sample_curve_loop_boundary(
        document,
        ids,
        arc_segments=arc_segments,
        chord_tolerance_mm=chord_tolerance_mm,
    )
    if len(boundary) < 3:
        return ClothLoopAnalysis(ids, boundary3=boundary, reason="The boundary does not form one closed connected loop.")
    frame = best_fit_boundary_frame(boundary)
    if frame is None:
        return ClothLoopAnalysis(ids, boundary3=boundary, reason="The boundary cannot define a stable panel plane.")
    projected = tuple(frame.project(point) for point in boundary)
    max_deviation = max((frame.deviation(point) for point in boundary), default=0.0)
    area = abs(polygon_signed_area(projected))
    if area <= 1.0e-8:
        return ClothLoopAnalysis(
            ids,
            boundary,
            projected,
            frame,
            area,
            max_deviation,
            False,
            False,
            "The boundary has no usable surface area.",
        )
    self_intersects = polygon_self_intersects(projected)
    if self_intersects:
        return ClothLoopAnalysis(
            ids,
            boundary,
            projected,
            frame,
            area,
            max_deviation,
            True,
            False,
            "The selected boundary crosses itself. Check the arc side or select the intended curves in Face mode.",
        )
    if max_deviation > max(1.0e-6, float(planarity_tolerance_mm)):
        return ClothLoopAnalysis(
            ids,
            boundary,
            projected,
            frame,
            area,
            max_deviation,
            False,
            False,
            f"The curved boundary is not planar enough for one panel (deviation {max_deviation:.4g} mm).",
        )
    return ClothLoopAnalysis(ids, boundary, projected, frame, area, max_deviation, False, True, "")


def polygon_self_intersects(points: Sequence[Point2]) -> bool:
    if len(points) < 4:
        return False
    try:
        from shapely.geometry import LinearRing

        ring = LinearRing(points)
        return not bool(ring.is_simple)
    except Exception:
        pass
    count = len(points)
    for first in range(count):
        a0 = points[first]
        a1 = points[(first + 1) % count]
        for second in range(first + 1, count):
            if second in {first, (first + 1) % count}:
                continue
            if first == 0 and second == count - 1:
                continue
            b0 = points[second]
            b1 = points[(second + 1) % count]
            if _segments_intersect(a0, a1, b0, b1):
                return True
    return False


def _segments_intersect(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    def cross(p: Point2, q: Point2, r: Point2) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    ab_c = cross(a, b, c)
    ab_d = cross(a, b, d)
    cd_a = cross(c, d, a)
    cd_b = cross(c, d, b)
    return (ab_c * ab_d < -_EPS) and (cd_a * cd_b < -_EPS)


__all__ = ["ClothLoopAnalysis", "analyze_curve_loop", "polygon_self_intersects"]

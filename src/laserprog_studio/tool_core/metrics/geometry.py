"""Geometry helpers for temporary metric placement transactions.

These helpers are deliberately independent from SketchDocument and Qt.  They
turn typed metric values into plain 2D construction points so tools can rebuild a
draft element from a clean snapshot instead of editing already-compiled topology
in place.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import asin, atan2, cos, degrees, hypot, radians, sin, sqrt

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class LineMetricGeometry:
    length: float
    angle_degrees: float


@dataclass(frozen=True, slots=True)
class RectangleMetricGeometry:
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class CircleMetricGeometry:
    radius: float
    diameter: float


@dataclass(frozen=True, slots=True)
class ArcMetricGeometry:
    radius: float
    angle_degrees: float


def distance(a: Point2, b: Point2) -> float:
    return hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1]))


def line_metrics(start: Point2, end: Point2) -> LineMetricGeometry:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    return LineMetricGeometry(hypot(dx, dy), degrees(atan2(dy, dx)))


def line_end_from_metrics(start: Point2, *, length: float, angle_degrees: float) -> Point2:
    angle = radians(float(angle_degrees))
    length = max(float(length), 0.0)
    return (float(start[0]) + cos(angle) * length, float(start[1]) + sin(angle) * length)


def rectangle_metrics(first: Point2, opposite: Point2) -> RectangleMetricGeometry:
    return RectangleMetricGeometry(abs(float(opposite[0]) - float(first[0])), abs(float(opposite[1]) - float(first[1])))


def rectangle_opposite_from_metrics(first: Point2, original_opposite: Point2, *, width: float, height: float) -> Point2:
    sx = 1.0 if float(original_opposite[0]) >= float(first[0]) else -1.0
    sy = 1.0 if float(original_opposite[1]) >= float(first[1]) else -1.0
    return (float(first[0]) + sx * max(float(width), 0.0), float(first[1]) + sy * max(float(height), 0.0))


def circle_metrics(center: Point2, radius_point: Point2) -> CircleMetricGeometry:
    radius = distance(center, radius_point)
    return CircleMetricGeometry(radius, radius * 2.0)


def circle_radius_point_from_metrics(center: Point2, original_radius_point: Point2, *, radius: float) -> Point2:
    current = distance(center, original_radius_point)
    if current <= 1.0e-9:
        direction = (1.0, 0.0)
    else:
        direction = ((float(original_radius_point[0]) - float(center[0])) / current, (float(original_radius_point[1]) - float(center[1])) / current)
    radius = max(float(radius), 0.0)
    return (float(center[0]) + direction[0] * radius, float(center[1]) + direction[1] * radius)


def half_circle_metrics(start: Point2, end: Point2) -> tuple[CircleMetricGeometry, float]:
    diameter = distance(start, end)
    angle = line_metrics(start, end).angle_degrees
    return CircleMetricGeometry(diameter * 0.5, diameter), angle


def half_circle_end_from_metrics(start: Point2, *, diameter: float, angle_degrees: float) -> Point2:
    return line_end_from_metrics(start, length=max(float(diameter), 0.0), angle_degrees=float(angle_degrees))


def _circle_from_three_points(start: Point2, end: Point2, through: Point2) -> tuple[Point2, float] | None:
    ax, ay = float(start[0]), float(start[1])
    bx, by = float(end[0]), float(end[1])
    cx, cy = float(through[0]), float(through[1])
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) <= 1.0e-12:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    radius = hypot(ax - ux, ay - uy)
    if radius <= 1.0e-9:
        return None
    return (ux, uy), radius


def _signed_side(start: Point2, end: Point2, point: Point2) -> float:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    return dx * (float(point[1]) - float(start[1])) - dy * (float(point[0]) - float(start[0]))


def _minor_sweep_degrees(radius: float, chord: float) -> float:
    if radius <= 1.0e-9 or chord <= 1.0e-9:
        return 0.0
    ratio = max(-1.0, min(1.0, chord / (2.0 * radius)))
    return degrees(2.0 * asin(ratio))


def arc_metrics(start: Point2, end: Point2, through: Point2) -> ArcMetricGeometry:
    chord = distance(start, end)
    circle = _circle_from_three_points(start, end, through)
    if circle is None:
        # Degenerate fallback: treat the through-point height as a shallow arc.
        radius = max(chord * 0.5, 0.0)
    else:
        _center, radius = circle
    return ArcMetricGeometry(radius, _minor_sweep_degrees(radius, chord))


def arc_control_from_metrics(start: Point2, end: Point2, original_through: Point2, *, radius: float | None = None, angle_degrees: float | None = None) -> Point2:
    chord = distance(start, end)
    if chord <= 1.0e-9:
        return (float(start[0]), float(start[1]))
    if angle_degrees is not None:
        half = radians(max(1.0e-6, min(359.999, abs(float(angle_degrees)))) * 0.5)
        radius_value = chord / max(2.0 * sin(half), 1.0e-9)
    else:
        radius_value = max(float(radius if radius is not None else chord * 0.5), chord * 0.5 + 1.0e-9)
    radius_value = max(radius_value, chord * 0.5 + 1.0e-9)
    sagitta = radius_value - sqrt(max(radius_value * radius_value - (chord * 0.5) ** 2, 0.0))
    sx, sy = float(start[0]), float(start[1])
    ex, ey = float(end[0]), float(end[1])
    mid = ((sx + ex) * 0.5, (sy + ey) * 0.5)
    dx, dy = ex - sx, ey - sy
    inv = 1.0 / chord
    perp = (-dy * inv, dx * inv)
    side = 1.0 if _signed_side(start, end, original_through) >= 0.0 else -1.0
    return (mid[0] + perp[0] * sagitta * side, mid[1] + perp[1] * sagitta * side)


__all__ = [
    "ArcMetricGeometry",
    "CircleMetricGeometry",
    "LineMetricGeometry",
    "RectangleMetricGeometry",
    "arc_control_from_metrics",
    "arc_metrics",
    "circle_metrics",
    "circle_radius_point_from_metrics",
    "distance",
    "half_circle_end_from_metrics",
    "half_circle_metrics",
    "line_end_from_metrics",
    "line_metrics",
    "rectangle_metrics",
    "rectangle_opposite_from_metrics",
]

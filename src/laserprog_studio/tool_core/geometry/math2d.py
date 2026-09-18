"""Small geometry helpers shared by sketch, snap and preview layers."""
from __future__ import annotations

import math

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


def distance_2d(a: Point2, b: Point2) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def distance_3d(a: Point3, b: Point3) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def almost_equal_2d(a: Point2, b: Point2, tolerance: float) -> bool:
    return distance_2d(a, b) <= tolerance


def polygon_area(points: list[Point2]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        area += point[0] * nxt[1] - nxt[0] * point[1]
    return area * 0.5


def remove_consecutive_duplicates(points: list[Point2], tolerance: float) -> list[Point2]:
    cleaned: list[Point2] = []
    for point in points:
        if not cleaned or distance_2d(cleaned[-1], point) > tolerance:
            cleaned.append(point)
    if len(cleaned) > 1 and distance_2d(cleaned[0], cleaned[-1]) <= tolerance:
        cleaned.pop()
    return cleaned


def closest_point_on_segment_2d(p: Point2, a: Point2, b: Point2) -> Point2:
    ax, ay = a
    bx, by = b
    px, py = p
    abx = bx - ax
    aby = by - ay
    denom = abx * abx + aby * aby
    if denom <= 1e-12:
        return a
    t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / denom))
    return (ax + abx * t, ay + aby * t)


def point3_to_xy(point: Point3) -> Point2:
    return (float(point[0]), float(point[1]))


def xy_to_point3(point: Point2, z: float = 0.0) -> Point3:
    return (float(point[0]), float(point[1]), float(z))

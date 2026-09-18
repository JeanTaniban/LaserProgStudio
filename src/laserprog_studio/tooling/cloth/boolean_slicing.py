"""Intersection of persisted Cloth boolean cutters with panel mid-planes."""
from __future__ import annotations

import math
from typing import Any, Iterable

from .boolean_modifiers import ClothBooleanModifier
from .topology import PatchFrame

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
_EPS = 1.0e-9


def _signed_distance(frame: PatchFrame, point: Point3) -> float:
    delta = (
        point[0] - frame.origin[0],
        point[1] - frame.origin[1],
        point[2] - frame.origin[2],
    )
    return delta[0] * frame.normal[0] + delta[1] * frame.normal[1] + delta[2] * frame.normal[2]


def _bounds_cross_plane(
    modifier: ClothBooleanModifier,
    frame: PatchFrame,
    *,
    tolerance_mm: float,
) -> bool:
    """Cheap conservative rejection before scanning every cutter triangle."""

    minimum, maximum = modifier.bounds
    distances = (
        _signed_distance(frame, (x, y, z))
        for x in (minimum[0], maximum[0])
        for y in (minimum[1], maximum[1])
        for z in (minimum[2], maximum[2])
    )
    values = tuple(distances)
    tolerance = max(1.0e-7, float(tolerance_mm))
    return not (min(values) > tolerance or max(values) < -tolerance)


def _interpolate(a: Point3, b: Point3, da: float, db: float) -> Point3:
    denominator = da - db
    if abs(denominator) <= _EPS:
        return a
    parameter = max(0.0, min(1.0, da / denominator))
    return (
        a[0] + (b[0] - a[0]) * parameter,
        a[1] + (b[1] - a[1]) * parameter,
        a[2] + (b[2] - a[2]) * parameter,
    )


def _unique_points(points: Iterable[Point3], tolerance: float) -> list[Point3]:
    # A triangle contributes at most six raw candidates, so this tiny quadratic
    # deduplication is clearer and faster than constructing a spatial index.
    output: list[Point3] = []
    for point in points:
        if all(math.dist(point, existing) > tolerance for existing in output):
            output.append(point)
    return output


def slice_cloth_boolean_modifier(
    modifier: ClothBooleanModifier,
    frame: PatchFrame,
    *,
    tolerance_mm: float,
) -> Any | None:
    """Return the cutter cross-section in panel-local 2D coordinates."""

    if not _bounds_cross_plane(modifier, frame, tolerance_mm=tolerance_mm):
        return None

    from shapely import set_precision
    from shapely.geometry import LineString, Polygon
    from shapely.ops import polygonize, unary_union

    lines: list[Any] = []
    coplanar_polygons: list[Any] = []
    plane_tolerance = max(1.0e-7, float(tolerance_mm))
    vertices = modifier.vertices

    for face in modifier.triangles:
        points = [vertices[index] for index in face]
        distances = [_signed_distance(frame, point) for point in points]
        if min(distances) > plane_tolerance or max(distances) < -plane_tolerance:
            continue
        if all(abs(value) <= plane_tolerance for value in distances):
            polygon = Polygon([frame.project(point) for point in points])
            if not polygon.is_empty and polygon.area > _EPS:
                coplanar_polygons.append(polygon)
            continue

        intersections: list[Point3] = []
        for index in range(3):
            following = (index + 1) % 3
            first, second = points[index], points[following]
            first_distance, second_distance = distances[index], distances[following]
            if abs(first_distance) <= plane_tolerance:
                intersections.append(first)
            if first_distance * second_distance < -(plane_tolerance * plane_tolerance):
                intersections.append(
                    _interpolate(first, second, first_distance, second_distance)
                )
        intersections = _unique_points(intersections, plane_tolerance)
        if len(intersections) < 2:
            continue
        if len(intersections) > 2:
            # Tolerance can make all three triangle vertices appear on the plane.
            # Keep the longest segment; a true non-coplanar intersection is one
            # segment and this choice is stable under small numerical noise.
            first, second = max(
                (
                    (first, second)
                    for first_index, first in enumerate(intersections)
                    for second in intersections[first_index + 1 :]
                ),
                key=lambda pair: math.dist(pair[0], pair[1]),
            )
        else:
            first, second = intersections
        first2, second2 = frame.project(first), frame.project(second)
        if math.dist(first2, second2) > plane_tolerance:
            lines.append(LineString((first2, second2)))

    polygons: list[Any] = list(coplanar_polygons)
    if lines:
        merged = unary_union(lines)
        try:
            merged = set_precision(merged, grid_size=max(1.0e-7, plane_tolerance * 0.25))
        except (TypeError, ValueError):
            # Precision reduction is an optimisation, not a correctness
            # requirement.  GEOS can still polygonise the original segments.
            pass
        polygons.extend(polygonize(merged))
    if not polygons:
        return None

    geometry = unary_union(polygons)
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    return geometry if not geometry.is_empty else None


__all__ = ["slice_cloth_boolean_modifier"]

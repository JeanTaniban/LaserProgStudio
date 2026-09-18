"""2D triangulation utilities used by Cloth preview and output generation."""
from __future__ import annotations

import math
from typing import Any

from .topology import polygon_signed_area

Point2 = tuple[float, float]
_EPS = 1.0e-9


class ClothTriangulationError(ValueError):
    """Raised when GEOS cannot triangulate an otherwise valid panel region."""


def _cross2(a: Point2, b: Point2, c: Point2) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_in_triangle(point: Point2, a: Point2, b: Point2, c: Point2) -> bool:
    first = _cross2(a, b, point)
    second = _cross2(b, c, point)
    third = _cross2(c, a, point)
    return first >= -_EPS and second >= -_EPS and third >= -_EPS


def _triangulate_ear_clip(points: list[Point2]) -> list[tuple[int, int, int]]:
    """Dependency-free fallback for one simple polygon without holes."""

    if len(points) < 3:
        return []
    order = list(range(len(points)))
    if polygon_signed_area(points) < 0.0:
        order.reverse()
    triangles: list[tuple[int, int, int]] = []
    guard = 0
    while len(order) > 3 and guard < len(points) * len(points):
        guard += 1
        clipped = False
        for offset, current in enumerate(order):
            previous = order[offset - 1]
            following = order[(offset + 1) % len(order)]
            a, b, c = points[previous], points[current], points[following]
            if _cross2(a, b, c) <= _EPS:
                continue
            if any(
                _point_in_triangle(points[candidate], a, b, c)
                for candidate in order
                if candidate not in {previous, current, following}
            ):
                continue
            triangles.append((previous, current, following))
            order.pop(offset)
            clipped = True
            break
        if not clipped:
            return []
    if len(order) == 3:
        triangles.append((order[0], order[1], order[2]))
    return triangles


def triangulate_simple_polygon(points: list[Point2]) -> list[tuple[int, int, int]]:
    """Triangulate one simple polygon while preserving source vertex indices."""

    if len(points) < 3:
        return []
    try:
        from shapely import constrained_delaunay_triangles
        from shapely.geometry import Polygon

        polygon = Polygon(points)
        if polygon.is_valid and not polygon.is_empty and float(polygon.area) > _EPS:
            result = constrained_delaunay_triangles(polygon)
            scale = max(1.0, max((abs(value) for point in points for value in point), default=1.0))
            tolerance = max(1.0e-8, scale * 1.0e-9)

            def source_index(coordinate: Point2) -> int | None:
                best: tuple[float, int] | None = None
                for index, point in enumerate(points):
                    distance = math.hypot(
                        float(coordinate[0]) - point[0],
                        float(coordinate[1]) - point[1],
                    )
                    if distance <= tolerance and (best is None or distance < best[0]):
                        best = distance, index
                return best[1] if best is not None else None

            triangles: list[tuple[int, int, int]] = []
            for triangle in tuple(getattr(result, "geoms", ())):
                coordinates = tuple(
                    (float(x), float(y))
                    for x, y in tuple(triangle.exterior.coords)[:3]
                )
                mapped = tuple(source_index(value) for value in coordinates)
                if any(value is None for value in mapped):
                    triangles = []
                    break
                indices = tuple(int(value) for value in mapped if value is not None)
                if len(set(indices)) != 3:
                    continue
                if _cross2(points[indices[0]], points[indices[1]], points[indices[2]]) < 0.0:
                    indices = indices[0], indices[2], indices[1]
                triangles.append(indices)
            if len(triangles) == len(points) - 2:
                return triangles
    except Exception:
        # Preview triangulation has a deterministic dependency-free fallback.
        pass
    return _triangulate_ear_clip(points)


def polygon_parts(geometry: Any) -> tuple[Any, ...]:
    if geometry is None or getattr(geometry, "is_empty", True):
        return ()
    geometry_type = str(getattr(geometry, "geom_type", ""))
    if geometry_type == "Polygon":
        return (geometry,)
    if geometry_type in {"MultiPolygon", "GeometryCollection"}:
        return tuple(
            part
            for part in getattr(geometry, "geoms", ())
            if str(getattr(part, "geom_type", "")) == "Polygon"
            and float(getattr(part, "area", 0.0)) > _EPS
        )
    return ()


def triangulate_region_geometry(geometry: Any) -> list[tuple[Point2, Point2, Point2]]:
    """Triangulate Polygon/MultiPolygon geometry, including holes and notches."""

    try:
        from shapely import constrained_delaunay_triangles
    except ImportError:
        return []
    triangles: list[tuple[Point2, Point2, Point2]] = []
    try:
        for polygon in polygon_parts(geometry):
            if not polygon.is_valid or polygon.is_empty or float(polygon.area) <= _EPS:
                continue
            result = constrained_delaunay_triangles(polygon)
            for triangle in getattr(result, "geoms", ()):
                coordinates = tuple(
                    (float(x), float(y))
                    for x, y in tuple(triangle.exterior.coords)[:3]
                )
                if len(coordinates) != 3 or len(set(coordinates)) != 3:
                    continue
                if not polygon.covers(triangle.representative_point()):
                    continue
                if _cross2(coordinates[0], coordinates[1], coordinates[2]) < 0.0:
                    coordinates = coordinates[0], coordinates[2], coordinates[1]
                triangles.append(coordinates)
    except Exception as exc:
        raise ClothTriangulationError(
            f"Panel region triangulation failed ({type(exc).__name__}: {exc})."
        ) from exc
    return triangles


__all__ = [
    "ClothTriangulationError",
    "polygon_parts",
    "triangulate_region_geometry",
    "triangulate_simple_polygon",
]

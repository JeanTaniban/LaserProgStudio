# -*- coding: utf-8 -*-
"""Robust indexed triangulation for projected drawing faces.

``vtkPolyDataMapper2D`` does not reliably tessellate concave polygon cells.  In
practice it may render them as a fan from one vertex, producing long crossing
triangles.  This module converts a simple planar polygon to stable triangle
indices once, while keeping the original point array unchanged so coordinate
patches remain O(changed vertices).
"""
from __future__ import annotations

from functools import lru_cache
from math import isfinite
from typing import Iterable

Point3 = tuple[float, float, float]
Cell = tuple[int, int, int]


def _dominant_axis(vertices: tuple[Point3, ...]) -> int:
    nx = ny = nz = 0.0
    count = len(vertices)
    for index, current in enumerate(vertices):
        following = vertices[(index + 1) % count]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    return max(range(3), key=lambda item: abs((nx, ny, nz)[item]))


def _project_point(point: Point3, axis: int) -> tuple[float, float]:
    if axis == 0:
        return (float(point[1]), float(point[2]))
    if axis == 1:
        return (float(point[0]), float(point[2]))
    return (float(point[0]), float(point[1]))


def _project_to_dominant_plane(vertices: tuple[Point3, ...]) -> tuple[tuple[float, float], ...]:
    """Project a planar 3D loop to the least-degenerate coordinate plane."""

    axis = _dominant_axis(vertices)
    return tuple(_project_point(point, axis) for point in vertices)


def _signed_area(points: tuple[tuple[float, float], ...]) -> float:
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )


def _is_convex(points: tuple[tuple[float, float], ...], epsilon: float) -> bool:
    direction = 0
    count = len(points)
    for index in range(count):
        a = points[index]
        b = points[(index + 1) % count]
        c = points[(index + 2) % count]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) <= epsilon:
            continue
        sign = 1 if cross > 0.0 else -1
        if direction == 0:
            direction = sign
        elif sign != direction:
            return False
    return direction != 0


def _orient_triangle(cell: Cell, points: tuple[tuple[float, float], ...], polygon_sign: int) -> Cell:
    a, b, c = (points[cell[0]], points[cell[1]], points[cell[2]])
    cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    if (cross > 0.0) != (polygon_sign > 0):
        return (cell[0], cell[2], cell[1])
    return cell


def _coordinate_index(
    coordinate: tuple[float, float],
    points: tuple[tuple[float, float], ...],
    exact: dict[tuple[float, float], int],
    tolerance_sq: float,
) -> int | None:
    found = exact.get((float(coordinate[0]), float(coordinate[1])))
    if found is not None:
        return found
    best_index = -1
    best_distance = float("inf")
    x, y = float(coordinate[0]), float(coordinate[1])
    for index, point in enumerate(points):
        distance = (point[0] - x) ** 2 + (point[1] - y) ** 2
        if distance < best_distance:
            best_distance = distance
            best_index = index
    return best_index if best_index >= 0 and best_distance <= tolerance_sq else None


def _shapely_cells(points: tuple[tuple[float, float], ...], polygon_sign: int) -> tuple[Cell, ...]:
    try:
        from shapely.geometry import Polygon
        try:
            from shapely import constrained_delaunay_triangles
        except Exception:  # pragma: no cover - Shapely < 2.1 fallback
            constrained_delaunay_triangles = None
        from shapely.ops import triangulate
    except Exception:
        return ()

    polygon = Polygon(points)
    if polygon.is_empty or not polygon.is_valid or polygon.area <= 0.0:
        return ()
    triangle_coordinate_rows: Iterable[object]
    if constrained_delaunay_triangles is not None:
        collection = constrained_delaunay_triangles(polygon)
        try:
            from shapely import get_coordinates, get_parts

            parts = get_parts(collection)
            coordinates = get_coordinates(parts)
            if len(parts) and len(coordinates) == len(parts) * 4:
                triangle_coordinate_rows = coordinates.reshape((-1, 4, 2))[:, :3, :]
            else:
                triangle_coordinate_rows = (list(item.exterior.coords)[:-1] for item in parts)
        except Exception:  # pragma: no cover - conservative compatibility path
            triangle_coordinate_rows = (list(item.exterior.coords)[:-1] for item in collection.geoms)
    else:  # pragma: no cover - production requirements pin Shapely 2.1.2
        coverage = polygon.buffer(max(1.0e-12, polygon.length * 1.0e-12))
        triangle_coordinate_rows = (
            list(triangle.exterior.coords)[:-1]
            for triangle in triangulate(polygon)
            if coverage.covers(triangle)
        )

    exact: dict[tuple[float, float], int] = {}
    for index, point in enumerate(points):
        exact.setdefault((float(point[0]), float(point[1])), index)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    scale = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    tolerance_sq = (scale * 1.0e-9) ** 2
    cells: list[Cell] = []
    seen: set[tuple[int, int, int]] = set()
    for coordinates in triangle_coordinate_rows:
        if len(coordinates) != 3:
            continue
        mapped = tuple(_coordinate_index((value[0], value[1]), points, exact, tolerance_sq) for value in coordinates)
        if any(index is None for index in mapped):
            continue
        cell = (int(mapped[0]), int(mapped[1]), int(mapped[2]))
        if len(set(cell)) != 3:
            continue
        canonical = tuple(sorted(cell))
        if canonical in seen:
            continue
        seen.add(canonical)
        cells.append(_orient_triangle(cell, points, polygon_sign))
    return tuple(cells)


@lru_cache(maxsize=512)
def triangulate_polygon_cells(vertices: tuple[Point3, ...]) -> tuple[Cell, ...]:
    """Return triangle cells referencing the original vertex array.

    Convex polygons use a zero-allocation fan. Concave polygons are handled by
    GEOS/Shapely constrained Delaunay triangulation, then mapped back to the
    original local indices. Invalid/self-intersecting loops return no fill
    cells; callers can still render their outline safely.
    """

    if len(vertices) < 3:
        return ()
    if not all(isfinite(value) for point in vertices for value in point):
        return ()
    points = _project_to_dominant_plane(vertices)
    area = _signed_area(points)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    scale = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    epsilon = scale * scale * 1.0e-14
    if abs(area) <= epsilon:
        return ()
    polygon_sign = 1 if area > 0.0 else -1
    if len(vertices) == 3:
        return (_orient_triangle((0, 1, 2), points, polygon_sign),)
    if _is_convex(points, epsilon):
        return tuple(_orient_triangle((0, index, index + 1), points, polygon_sign) for index in range(1, len(points) - 1))
    return _shapely_cells(points, polygon_sign)


@lru_cache(maxsize=64)
def _triangulate_polygon_with_holes_cells_canonical(
    vertices: tuple[Point3, ...],
    holes: tuple[tuple[Point3, ...], ...] = (),
) -> tuple[Cell, ...]:
    """Return triangle cells for an outer loop and zero or more hole loops.

    Indices reference the flattened point order ``outer + hole0 + hole1 + ...``.
    The function deliberately rejects triangulations that introduce Steiner
    points because the projected renderer keeps the caller's point array stable
    for coordinate-only patches.
    """

    if not holes:
        return triangulate_polygon_cells(vertices)
    if len(vertices) < 3 or any(len(ring) < 3 for ring in holes):
        return ()
    all_vertices = tuple(vertices) + tuple(point for ring in holes for point in ring)
    if not all(isfinite(value) for point in all_vertices for value in point):
        return ()

    axis = _dominant_axis(vertices)
    outer_2d = tuple(_project_point(point, axis) for point in vertices)
    # Every hole must use the same projection plane as the outer loop.
    hole_2d = tuple(tuple(_project_point(point, axis) for point in ring) for ring in holes)
    flattened_2d = tuple(outer_2d) + tuple(point for ring in hole_2d for point in ring)
    area = _signed_area(outer_2d)
    if abs(area) <= 1.0e-14:
        return ()
    polygon_sign = 1 if area > 0.0 else -1

    try:
        from shapely.geometry import Polygon
        try:
            from shapely import constrained_delaunay_triangles
        except Exception:  # pragma: no cover - Shapely < 2.1 fallback
            constrained_delaunay_triangles = None
        from shapely.ops import triangulate
    except Exception:
        return ()

    polygon = Polygon(outer_2d, holes=hole_2d)
    if not polygon.is_valid:
        # Union motifs can cross an internal boundary between two selected
        # faces.  Each source face then receives a clipped opening whose ring
        # touches its outer boundary.  GEOS represents that as an invalid
        # "hole", but ``buffer(0)`` converts it exactly into an outer-boundary
        # notch.  The repair normally reuses the original intersection
        # vertices, so stable indexed triangulation remains possible.
        try:
            polygon = polygon.buffer(0)
        except Exception:
            return ()
    if polygon.is_empty or polygon.area <= 0.0:
        return ()
    if constrained_delaunay_triangles is not None:
        collection = constrained_delaunay_triangles(polygon)
        parts = tuple(collection.geoms) if hasattr(collection, "geoms") else tuple(collection)
    else:  # pragma: no cover - production requirements pin Shapely 2.1.2
        coverage = polygon.buffer(max(1.0e-12, polygon.length * 1.0e-12))
        parts = tuple(triangle for triangle in triangulate(polygon) if coverage.covers(triangle))

    exact: dict[tuple[float, float], int] = {}
    for index, point in enumerate(flattened_2d):
        exact.setdefault((float(point[0]), float(point[1])), index)
    xs = [point[0] for point in flattened_2d]
    ys = [point[1] for point in flattened_2d]
    scale = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    tolerance_sq = (scale * 1.0e-9) ** 2
    cells: list[Cell] = []
    seen: set[tuple[int, int, int]] = set()
    for triangle in parts:
        coordinates = list(triangle.exterior.coords)[:-1]
        if len(coordinates) != 3:
            continue
        mapped = tuple(_coordinate_index((value[0], value[1]), flattened_2d, exact, tolerance_sq) for value in coordinates)
        if any(index is None for index in mapped):
            # A Steiner point would invalidate stable point-array patching.
            return ()
        cell = (int(mapped[0]), int(mapped[1]), int(mapped[2]))
        if len(set(cell)) != 3:
            continue
        canonical = tuple(sorted(cell))
        if canonical in seen:
            continue
        seen.add(canonical)
        cells.append(_orient_triangle(cell, flattened_2d, polygon_sign))
    return tuple(cells)


def _canonical_ring(
    ring: tuple[Point3, ...],
    *,
    axis: int,
    desired_sign: int,
) -> tuple[tuple[Point3, ...], tuple[int, ...]]:
    """Return a rotation/orientation-stable ring and canonical->source map."""

    if not ring:
        return (), ()
    projected = tuple(_project_point(point, axis) for point in ring)
    order = list(range(len(ring)))
    area = _signed_area(projected)
    if area != 0.0 and ((area > 0.0) != (desired_sign > 0)):
        order.reverse()
    # Rotating an otherwise identical loop is a common side effect of Shapely
    # unions.  Start at a deterministic coordinate while keeping the selected
    # winding.  Include the source index only as a final tie breaker for exact
    # duplicate coordinates.
    start = min(
        range(len(order)),
        key=lambda offset: (
            float(ring[order[offset]][0]),
            float(ring[order[offset]][1]),
            float(ring[order[offset]][2]),
            int(order[offset]),
        ),
    )
    order = order[start:] + order[:start]
    return tuple(ring[index] for index in order), tuple(order)


def _canonical_polygon_with_holes(
    vertices: tuple[Point3, ...],
    holes: tuple[tuple[Point3, ...], ...],
) -> tuple[
    tuple[Point3, ...],
    tuple[tuple[Point3, ...], ...],
    tuple[int, ...],
    int,
]:
    """Canonicalize loop winding, rotation and hole order.

    The returned index map converts canonical flattened indices back to the
    caller's ``outer + holes`` point order.  This lets the expensive GEOS
    triangulation cache survive harmless ring reordering while preserving the
    public stable-index contract.
    """

    axis = _dominant_axis(vertices) if len(vertices) >= 3 else 2
    source_sign = 1 if _signed_area(tuple(_project_point(point, axis) for point in vertices)) >= 0.0 else -1
    outer, outer_map = _canonical_ring(vertices, axis=axis, desired_sign=1)

    source_offsets: list[int] = []
    running = len(vertices)
    for ring in holes:
        source_offsets.append(running)
        running += len(ring)

    canonical_holes: list[tuple[tuple[Point3, ...], tuple[int, ...], int]] = []
    for hole_index, ring in enumerate(holes):
        canonical, local_map = _canonical_ring(ring, axis=axis, desired_sign=-1)
        canonical_holes.append((canonical, local_map, hole_index))
    canonical_holes.sort(key=lambda item: item[0])

    index_map: list[int] = list(outer_map)
    ordered_holes: list[tuple[Point3, ...]] = []
    for canonical, local_map, source_hole_index in canonical_holes:
        ordered_holes.append(canonical)
        offset = source_offsets[source_hole_index]
        index_map.extend(offset + local_index for local_index in local_map)
    return outer, tuple(ordered_holes), tuple(index_map), source_sign


@lru_cache(maxsize=64)
def triangulate_polygon_with_holes_cells(
    vertices: tuple[Point3, ...],
    holes: tuple[tuple[Point3, ...], ...] = (),
) -> tuple[Cell, ...]:
    """Return stable indexed cells while reusing equivalent ring geometries.

    A raw cache handles the frequent exact-repeat path (hover/selection style
    changes).  The internal canonical cache additionally recognises the same
    polygon after Shapely changed ring winding, start vertex or hole order, as
    happens between the projected preview and Apply extrusion.
    """

    if not holes:
        return triangulate_polygon_cells(vertices)
    if len(vertices) < 3 or any(len(ring) < 3 for ring in holes):
        return ()
    canonical_outer, canonical_holes, canonical_to_source, source_sign = _canonical_polygon_with_holes(vertices, holes)
    canonical_cells = _triangulate_polygon_with_holes_cells_canonical(canonical_outer, canonical_holes)
    if not canonical_cells:
        return ()
    mapped: list[Cell] = []
    for a, b, c in canonical_cells:
        cell = (canonical_to_source[a], canonical_to_source[b], canonical_to_source[c])
        if source_sign < 0:
            cell = (cell[0], cell[2], cell[1])
        mapped.append(cell)
    return tuple(mapped)


def clear_triangulation_caches() -> None:
    """Clear raw and canonical caches, primarily for deterministic tests."""

    triangulate_polygon_cells.cache_clear()
    triangulate_polygon_with_holes_cells.cache_clear()
    _triangulate_polygon_with_holes_cells_canonical.cache_clear()


def triangulation_cache_snapshot() -> dict[str, int]:
    """Return bounded cache diagnostics for performance reports.

    Face triangulation is geometry-only.  Hover, selection and camera changes
    alter styles or projection but not polygon topology, so reusing these cells
    is both exact and substantially cheaper for motif faces containing hundreds
    of holes.
    """

    simple = triangulate_polygon_cells.cache_info()
    holes = triangulate_polygon_with_holes_cells.cache_info()
    canonical = _triangulate_polygon_with_holes_cells_canonical.cache_info()
    return {
        "simple_hits": int(simple.hits),
        "simple_misses": int(simple.misses),
        "simple_size": int(simple.currsize),
        "holes_hits": int(holes.hits),
        "holes_misses": int(holes.misses),
        "holes_size": int(holes.currsize),
        "holes_canonical_hits": int(canonical.hits),
        "holes_canonical_misses": int(canonical.misses),
        "holes_canonical_size": int(canonical.currsize),
    }


__all__ = [
    "triangulate_polygon_cells",
    "triangulate_polygon_with_holes_cells",
    "clear_triangulation_caches",
    "triangulation_cache_snapshot",
]

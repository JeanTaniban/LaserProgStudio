# -*- coding: utf-8 -*-
"""Triangulation helpers for Plan Tracer preview faces."""
from __future__ import annotations

from math import sqrt

def _triangulate_preview_face_points(
    outer_points: tuple[tuple[float, float, float], ...] | list[tuple[float, float, float]],
    hole_polygons: tuple[tuple[tuple[float, float, float], ...], ...] | list[tuple[tuple[float, float, float], ...]] = (),
) -> tuple[list[tuple[float, float, float]], list[int]] | None:
    """Triangulate a preview face before handing it to PyVista/VTK.

    PyVista/VTK is reliable for triangles, but a single high-vertex polygon can
    be triangulated as a fan by the renderer.  That is visually wrong for
    concave Plan Tracer cells: the fill jumps across re-entrant corners and
    creates the diagonal/stacked triangles reported by users.  Holes also cannot
    be encoded by one PolyData polygon.

    This helper therefore projects the planar loops to 2D, triangulates the
    actual polygon area, filters out triangles outside the polygon or inside
    holes, then maps triangles back to the original 3D plane.  Convex polygons
    also pass through this path so all preview faces use the same safe contract.
    """

    outer = [tuple(float(v) for v in point) for point in outer_points]
    holes = [[tuple(float(v) for v in point) for point in hole] for hole in (hole_polygons or ()) if len(hole) >= 3]
    if len(outer) < 3:
        return None

    def sub(a, b):
        return (a[0] - b[0], a[1] - b[1], a[2] - b[2])

    def dot(a, b):
        return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]

    def cross(a, b):
        return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])

    def norm(a):
        return sqrt(dot(a, a))

    origin = outer[0]
    u = None
    normal = None
    for candidate in outer[1:]:
        direction = sub(candidate, origin)
        length = norm(direction)
        if length > 1.0e-9:
            u = (direction[0] / length, direction[1] / length, direction[2] / length)
            break
    if u is None:
        return None
    for candidate in outer[2:]:
        n = cross(u, sub(candidate, origin))
        length = norm(n)
        if length > 1.0e-9:
            normal = (n[0] / length, n[1] / length, n[2] / length)
            break
    if normal is None:
        # Degenerate or nearly collinear input: let the old simple polygon path
        # deal with it rather than producing broken triangles.
        return None
    v = cross(normal, u)

    def to_2d(point):
        d = sub(point, origin)
        return (dot(d, u), dot(d, v))

    def to_3d(point):
        x, y = float(point[0]), float(point[1])
        return (origin[0] + x * u[0] + y * v[0], origin[1] + x * u[1] + y * v[1], origin[2] + x * u[2] + y * v[2])

    try:
        from shapely.geometry import Polygon
        from shapely.ops import triangulate
    except Exception:  # pragma: no cover - optional geometry dependency
        return None

    try:
        polygon = Polygon([to_2d(point) for point in outer], [[to_2d(point) for point in hole] for hole in holes])
        if polygon.is_empty or not polygon.is_valid or polygon.area <= 1.0e-9:
            return None
        # ``shapely.ops.triangulate`` returns a Delaunay triangulation of the
        # input vertices, not a constrained triangulation.  For concave outlines
        # and holes it may emit triangles over the convex hull.  Keep only
        # triangles that are fully covered by the target polygon.  The tiny
        # buffer absorbs round-off on boundary-aligned triangle edges without
        # letting a visible triangle bridge across a notch or hole.
        coverage = polygon.buffer(1.0e-9)
        triangles = []
        for tri in triangulate(polygon):
            if tri.is_empty or tri.area <= 1.0e-9:
                continue
            if not coverage.covers(tri):
                continue
            coords = list(tri.exterior.coords)[:-1]
            if len(coords) != 3:
                continue
            triangles.append(coords)
    except Exception:
        return None
    if not triangles:
        return None
    vertices: list[tuple[float, float, float]] = []
    faces: list[int] = []
    for coords in triangles:
        start = len(vertices)
        vertices.extend(to_3d(point) for point in coords)
        faces.extend([3, start, start + 1, start + 2])
    return vertices, faces

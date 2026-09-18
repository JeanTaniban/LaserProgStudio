"""Plan a face-only surface from a freely placed closed 3D point loop.

A closed loop with coplanar points remains one editable panel.  A non-planar
loop is triangulated into planar panels joined by internal fold edges.  This is
the smallest exact representation that keeps every clicked 3D point and still
allows a rigid flat-pattern calculation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .models import ClothDocument, Point3

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class ClosedLoopSurfacePlan:
    point_ids: tuple[str, ...]
    triangles: tuple[tuple[int, int, int], ...]
    planar: bool
    max_planarity_error_mm: float
    message: str = ""

    @property
    def valid(self) -> bool:
        return len(self.point_ids) >= 3 and (self.planar or bool(self.triangles))


def plan_closed_loop_surface(
    document: ClothDocument,
    point_ids: Iterable[str],
    *,
    planarity_tolerance_mm: float = 1.0e-4,
) -> ClosedLoopSurfacePlan:
    ids = tuple(str(value) for value in point_ids)
    if len(ids) < 3 or len(set(ids)) < 3:
        return ClosedLoopSurfacePlan(ids, (), False, 0.0, "A textile face needs at least three distinct points.")
    try:
        points = tuple(document.points[point_id].position for point_id in ids)
    except KeyError:
        return ClosedLoopSurfacePlan(ids, (), False, 0.0, "The closed loop references a missing point.")

    frame = _best_fit_frame(points)
    if frame is None:
        return ClosedLoopSurfacePlan(ids, (), False, 0.0, "The closed loop is degenerate and cannot form a surface.")
    origin, axis_u, axis_v, normal = frame
    distances = tuple(abs(_dot(_sub(point, origin), normal)) for point in points)
    max_error = max(distances, default=0.0)
    if max_error <= max(0.0, float(planarity_tolerance_mm)):
        return ClosedLoopSurfacePlan(ids, (), True, max_error)

    points2 = tuple((_dot(_sub(point, origin), axis_u), _dot(_sub(point, origin), axis_v)) for point in points)
    from .mesh_builder import triangulate_simple_polygon

    triangles = tuple(triangulate_simple_polygon(list(points2)))
    if not triangles:
        return ClosedLoopSurfacePlan(
            ids,
            (),
            False,
            max_error,
            "The non-planar loop could not be triangulated. Split it into smaller loops.",
        )
    return ClosedLoopSurfacePlan(ids, triangles, False, max_error)


def _best_fit_frame(points: tuple[Point3, ...]):
    if len(points) < 3:
        return None
    origin = points[0]
    # Newell's method is stable for arbitrary polygon orientation and gives a
    # useful projection plane even when the loop is not perfectly planar.
    nx = ny = nz = 0.0
    for index, current in enumerate(points):
        following = points[(index + 1) % len(points)]
        nx += (current[1] - following[1]) * (current[2] + following[2])
        ny += (current[2] - following[2]) * (current[0] + following[0])
        nz += (current[0] - following[0]) * (current[1] + following[1])
    normal = _normalize((nx, ny, nz))
    if normal is None:
        for index in range(1, len(points) - 1):
            normal = _normalize(_cross(_sub(points[index], origin), _sub(points[index + 1], origin)))
            if normal is not None:
                break
    if normal is None:
        return None

    axis_u = None
    for point in points[1:]:
        edge = _sub(point, origin)
        projected = _sub(edge, _scale(normal, _dot(edge, normal)))
        axis_u = _normalize(projected)
        if axis_u is not None:
            break
    if axis_u is None:
        return None
    axis_v = _normalize(_cross(normal, axis_u))
    if axis_v is None:
        return None
    return origin, axis_u, axis_v, normal


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(value: Point3, factor: float) -> Point3:
    return (value[0] * factor, value[1] * factor, value[2] * factor)


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _normalize(value: Point3) -> Point3 | None:
    length = math.sqrt(_dot(value, value))
    if length <= 1.0e-12:
        return None
    return (value[0] / length, value[1] / length, value[2] / length)


__all__ = ["ClosedLoopSurfacePlan", "plan_closed_loop_surface"]

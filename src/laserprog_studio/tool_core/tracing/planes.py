"""Shared arbitrary-plane helpers for 2D/3D tracing tools.

The functions are UI-neutral and deliberately live beside the shared trace
state machine.  Folding, Cloth and future curve tools can therefore agree on
one stable plane construction contract without importing each other's modules.
"""
from __future__ import annotations

import math
from typing import Iterable

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec, make_locked_plane

Point3 = tuple[float, float, float]


def _point3(values: Iterable[float]) -> Point3:
    result = tuple(float(value) for value in values)
    if len(result) != 3:
        raise ValueError("A 3D vector needs exactly three coordinates.")
    return (result[0], result[1], result[2])


def _dot(a: Point3, b: Point3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _unit(vector: Point3) -> Point3:
    length = math.sqrt(max(_dot(vector, vector), 0.0))
    if not math.isfinite(length) or length <= 1.0e-12:
        raise ValueError("The plane normal must be non-zero.")
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def plane_from_origin_normal(origin: Iterable[float], normal: Iterable[float]) -> LockedPlaneSpec:
    """Build a stable local drawing plane from one point and one normal.

    ``LockedPlaneSpec.view`` is retained for compatibility with the existing
    planar SDK; arbitrary planes use the closest semantic view only as a label.
    Geometry is entirely defined by the returned normal/u/v axes and depth.
    """

    point = _point3(origin)
    n = _unit(_point3(normal))
    # Pick the least parallel helper axis to avoid numerical instability.
    helper = min(((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), key=lambda axis: abs(_dot(axis, n)))
    u = _unit(_cross(helper, n))
    v = _unit(_cross(n, u))
    dominant = max(range(3), key=lambda index: abs(n[index]))
    if dominant == 2:
        view = FixedPlanarView.TOP if n[2] >= 0.0 else FixedPlanarView.BOTTOM
    elif dominant == 1:
        view = FixedPlanarView.BACK if n[1] >= 0.0 else FixedPlanarView.FRONT
    else:
        view = FixedPlanarView.RIGHT if n[0] >= 0.0 else FixedPlanarView.LEFT
    return LockedPlaneSpec(view=view, normal=n, u_axis=u, v_axis=v, depth=_dot(n, point))


def world_plane(view: FixedPlanarView | str = FixedPlanarView.TOP, *, depth: float = 0.0) -> LockedPlaneSpec:
    """Return a shared world-aligned drawing plane."""

    return make_locked_plane(view, depth=float(depth))


def point_plane_distance(plane: LockedPlaneSpec, point: Iterable[float]) -> float:
    value = _point3(point)
    return abs(_dot(plane.normal, value) - float(plane.depth))


__all__ = ["Point3", "plane_from_origin_normal", "point_plane_distance", "world_plane"]

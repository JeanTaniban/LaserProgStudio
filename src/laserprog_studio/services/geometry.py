# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any, Iterable, Sequence

from ..mesh_ops import translate_mesh

Bounds = tuple[float, float, float, float, float, float]
Vector3 = tuple[float, float, float]


def bounds_from_vertices_list(vertices: Iterable[Sequence[float]]) -> Bounds:
    """Return ``(xmin, xmax, ymin, ymax, zmin, zmax)`` for a vertex iterable."""
    verts = [(float(v[0]), float(v[1]), float(v[2])) for v in vertices]
    if not verts:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def bounds_axis_size(bounds: Bounds, axis: str) -> float:
    """Return the size of a bounds tuple along ``x``, ``y`` or ``z``."""
    axis_key = (axis or "x").lower()
    if axis_key == "y":
        return abs(float(bounds[3]) - float(bounds[2]))
    if axis_key == "z":
        return abs(float(bounds[5]) - float(bounds[4]))
    return abs(float(bounds[1]) - float(bounds[0]))


def translated_mesh_copies(source_meshes: Iterable[Any], delta: Vector3) -> list[Any]:
    """Deep-copy meshes and translate every copy by ``delta``."""
    dx, dy, dz = (float(delta[0]), float(delta[1]), float(delta[2]))
    out = [copy.deepcopy(mesh) for mesh in source_meshes]
    try:
        from laserprog_studio.domain.work_model import reset_mesh_id
    except Exception:  # pragma: no cover - package import fallback
        try:
            from laserprog_studio.domain.work_model import reset_mesh_id
        except Exception:  # pragma: no cover
            reset_mesh_id = None
    for mesh in out:
        if reset_mesh_id is not None:
            reset_mesh_id(mesh)
        translate_mesh(mesh, dx, dy, dz)
    return out

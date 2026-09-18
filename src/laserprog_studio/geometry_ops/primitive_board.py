# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..domain.work_model import WorkMesh

Vec3 = tuple[float, float, float]


@dataclass(frozen=True)
class BoardPrimitiveSpec:
    width_mm: float
    height_mm: float
    thickness_mm: float
    center: Vec3
    normal: Vec3 = (0.0, 0.0, 1.0)
    name: str = "Primitive board"
    color: str = "#C9A36A"


def _dot(a: Vec3, b: Vec3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(v: Vec3, fallback: Vec3 = (0.0, 0.0, 1.0)) -> Vec3:
    length = math.sqrt(max(_dot(v, v), 0.0))
    if not math.isfinite(length) or length <= 1e-12:
        return fallback
    return (float(v[0]) / length, float(v[1]) / length, float(v[2]) / length)


def board_axes_from_normal(normal: Vec3) -> tuple[Vec3, Vec3, Vec3]:
    """Return a stable orthonormal (u, v, n) basis for a board face."""

    n = _norm(normal)
    # Keep floor/top boards aligned to world X/Y.  For side faces, use world Z as
    # a preferred visual vertical so boards feel predictable on vertical faces.
    if abs(n[2]) > 0.92:
        u = (1.0, 0.0, 0.0)
    else:
        u = _norm(_cross((0.0, 0.0, 1.0), n), fallback=(1.0, 0.0, 0.0))
    v = _norm(_cross(n, u), fallback=(0.0, 1.0, 0.0))
    # Recompute u to remove any numerical drift and guarantee right-handed axes.
    u = _norm(_cross(v, n), fallback=u)
    return u, v, n


def _add_scaled(a: Vec3, u: Vec3, us: float, v: Vec3, vs: float, n: Vec3, ns: float) -> Vec3:
    return (
        float(a[0]) + float(u[0]) * float(us) + float(v[0]) * float(vs) + float(n[0]) * float(ns),
        float(a[1]) + float(u[1]) * float(us) + float(v[1]) * float(vs) + float(n[1]) * float(ns),
        float(a[2]) + float(u[2]) * float(us) + float(v[2]) * float(vs) + float(n[2]) * float(ns),
    )


def make_board_primitive_mesh(spec: BoardPrimitiveSpec) -> WorkMesh:
    width = max(float(spec.width_mm), 0.001)
    height = max(float(spec.height_mm), 0.001)
    thickness = max(float(spec.thickness_mm), 0.001)
    center = (float(spec.center[0]), float(spec.center[1]), float(spec.center[2]))
    u, v, n = board_axes_from_normal(spec.normal)
    hw, hh, ht = width * 0.5, height * 0.5, thickness * 0.5
    vertices = [
        _add_scaled(center, u, -hw, v, -hh, n, -ht),
        _add_scaled(center, u, hw, v, -hh, n, -ht),
        _add_scaled(center, u, hw, v, hh, n, -ht),
        _add_scaled(center, u, -hw, v, hh, n, -ht),
        _add_scaled(center, u, -hw, v, -hh, n, ht),
        _add_scaled(center, u, hw, v, -hh, n, ht),
        _add_scaled(center, u, hw, v, hh, n, ht),
        _add_scaled(center, u, -hw, v, hh, n, ht),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    mesh = WorkMesh(
        name=str(spec.name or "Primitive board"),
        vertices=vertices,
        triangles=triangles,
        color=str(spec.color or "#C9A36A"),
    )
    try:
        mesh.metadata["primitive_board"] = {
            "width_mm": width,
            "height_mm": height,
            "thickness_mm": thickness,
            "center": [float(v) for v in center],
            "normal": [float(v) for v in n],
            "u_axis": [float(v) for v in u],
            "v_axis": [float(v) for v in v],
        }
    except Exception:
        pass
    return mesh


def board_spec_from_preferences(
    preferences: Any,
    *,
    center: Vec3,
    normal: Vec3 = (0.0, 0.0, 1.0),
    name: str = "Primitive board",
) -> BoardPrimitiveSpec:
    laser = getattr(preferences, "laser", preferences)
    return BoardPrimitiveSpec(
        width_mm=float(getattr(laser, "primitive_board_x_mm", 200.0)),
        height_mm=float(getattr(laser, "primitive_board_y_mm", 100.0)),
        thickness_mm=float(getattr(laser, "default_board_thickness_mm", 3.0)),
        center=center,
        normal=normal,
        name=name,
    )


__all__ = ["BoardPrimitiveSpec", "board_axes_from_normal", "board_spec_from_preferences", "make_board_primitive_mesh"]

# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any

Vec3 = tuple[float, float, float]


def vadd(a: Vec3, b: Vec3) -> Vec3:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def vsub(a: Vec3, b: Vec3) -> Vec3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def vscale(v: Vec3, s: float) -> Vec3:
    return (float(v[0]) * float(s), float(v[1]) * float(s), float(v[2]) * float(s))


def vdot(a: Vec3, b: Vec3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def vcross(a: Vec3, b: Vec3) -> Vec3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def vlen(v: Vec3) -> float:
    return math.sqrt(max(vdot(v, v), 0.0))


def vnorm(v: Vec3, fallback: Vec3 = (0.0, 0.0, 1.0)) -> Vec3:
    length = vlen(v)
    if length <= 1e-12:
        return tuple(float(x) for x in fallback)  # type: ignore[return-value]
    return (float(v[0]) / length, float(v[1]) / length, float(v[2]) / length)


def basis_from_normal(normal: Vec3, rotation_deg: float = 0.0) -> tuple[Vec3, Vec3, Vec3]:
    w = vnorm(normal)
    up = (0.0, 0.0, 1.0)
    if abs(vdot(w, up)) > 0.92:
        up = (0.0, 1.0, 0.0)
    u = vnorm(vcross(up, w), fallback=(1.0, 0.0, 0.0))
    v = vnorm(vcross(w, u), fallback=(0.0, 1.0, 0.0))
    angle = math.radians(float(rotation_deg))
    ca, sa = math.cos(angle), math.sin(angle)
    ru = vnorm((u[0] * ca + v[0] * sa, u[1] * ca + v[1] * sa, u[2] * ca + v[2] * sa), fallback=u)
    rv = vnorm((-u[0] * sa + v[0] * ca, -u[1] * sa + v[1] * ca, -u[2] * sa + v[2] * ca), fallback=v)
    return ru, rv, w


def mesh_center(mesh: Any) -> Vec3:
    verts = getattr(mesh, "vertices", None) or ()
    if not verts:
        return (0.0, 0.0, 0.0)
    xs = [float(p[0]) for p in verts]
    ys = [float(p[1]) for p in verts]
    zs = [float(p[2]) for p in verts]
    return ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5)


def mesh_span(mesh: Any) -> float:
    verts = getattr(mesh, "vertices", None) or ()
    if not verts:
        return 10.0
    xs = [float(p[0]) for p in verts]
    ys = [float(p[1]) for p in verts]
    zs = [float(p[2]) for p in verts]
    return max(max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs), 1.0)


def screen_pos(owner: Any, point: Vec3) -> Vec3 | None:
    """Return a Qt-style screen coordinate for a world point.

    ``owner._world_to_display`` returns VTK display coordinates, whose Y origin is
    at the bottom of the viewport.  Creator mouse events use Qt coordinates,
    whose Y origin is at the top.  Texture Projection has a small manual picker
    for camera pass-through and drag bootstrap; mixing the two coordinate spaces
    made handles look far from the cursor but still be picked, especially on
    oblique camera views where users tend to click below the visible handle.

    Keep the display depth unchanged for back-projection, but convert Y to the
    same Qt space as ``ToolEvent.screen_pos`` and ``ctx.viewport.world_to_screen``.
    """
    try:
        method = getattr(owner, "_world_to_display", None)
        if callable(method):
            result = method(point)
            if result is not None:
                x = float(result[0])
                y_vtk = float(result[1])
                depth = float(result[2])
                height = None
                try:
                    plotter = getattr(owner, "plotter", None)
                    raw_height = getattr(plotter, "height", None)
                    height = float(raw_height() if callable(raw_height) else raw_height)
                except Exception:
                    height = None
                y_qt = float(height) - y_vtk if height is not None and height > 0.0 else y_vtk
                return (x, y_qt, depth)
    except Exception:
        return None
    return None


def display_to_world_at_depth(owner: Any, qx: float, qy: float, depth: float) -> Vec3 | None:
    try:
        plotter = getattr(owner, "plotter", None)
        height = int(getattr(plotter, "height", lambda: 0)() if callable(getattr(plotter, "height", None)) else getattr(plotter, "height", 0) or 0)
        vtk_y = float(height) - float(qy) if height > 0 else float(qy)
        method = getattr(owner, "_display_to_world_at_depth", None)
        if callable(method):
            p = method(float(qx), vtk_y, float(depth))
            if p is not None:
                return (float(p[0]), float(p[1]), float(p[2]))
    except Exception:
        return None
    return None


def display_ray_from_qt(owner: Any, qx: float, qy: float) -> tuple[Vec3, Vec3] | None:
    """Return a world-space ray for a Qt display coordinate.

    TEX handles are drawn in 3D on the texture plane.  A screen-space angle only
    works when the camera is square to that plane; for oblique views the ring is
    projected as an ellipse and the cursor no longer follows the handle.  The
    stable path is to reconstruct the camera ray and intersect it with the
    texture plane.
    """

    near = display_to_world_at_depth(owner, qx, qy, 0.0)
    far = display_to_world_at_depth(owner, qx, qy, 1.0)
    if near is None or far is None:
        return None
    direction = vsub(far, near)
    if vlen(direction) <= 1e-12:
        return None
    return near, vnorm(direction)


def intersect_ray_plane(ray_origin: Vec3, ray_direction: Vec3, plane_origin: Vec3, plane_normal: Vec3, *, epsilon: float = 1e-9) -> Vec3 | None:
    normal = vnorm(plane_normal)
    denom = vdot(ray_direction, normal)
    if abs(denom) <= float(epsilon):
        return None
    t = vdot(vsub(plane_origin, ray_origin), normal) / denom
    if not math.isfinite(t):
        return None
    return vadd(ray_origin, vscale(ray_direction, t))


def display_to_world_on_plane(owner: Any, qx: float, qy: float, plane_origin: Vec3, plane_normal: Vec3) -> Vec3 | None:
    ray = display_ray_from_qt(owner, qx, qy)
    if ray is None:
        return None
    ray_origin, ray_direction = ray
    return intersect_ray_plane(ray_origin, ray_direction, plane_origin, plane_normal)


def signed_angle_between_on_plane(start_vec: Vec3, current_vec: Vec3, plane_normal: Vec3) -> float | None:
    a = vnorm(start_vec)
    b = vnorm(current_vec)
    n = vnorm(plane_normal)
    if vlen(a) <= 1e-12 or vlen(b) <= 1e-12 or vlen(n) <= 1e-12:
        return None
    cross = vcross(a, b)
    return math.atan2(vdot(n, cross), vdot(a, b))


def vec3_or_none(value: Any) -> Vec3 | None:
    try:
        vec = tuple(float(v) for v in value)
        return vec if len(vec) == 3 else None  # type: ignore[return-value]
    except Exception:
        return None


__all__ = [
    "Vec3",
    "basis_from_normal",
    "display_ray_from_qt",
    "display_to_world_at_depth",
    "display_to_world_on_plane",
    "intersect_ray_plane",
    "signed_angle_between_on_plane",
    "mesh_center",
    "mesh_span",
    "screen_pos",
    "vadd",
    "vdot",
    "vnorm",
    "vscale",
    "vsub",
    "vec3_or_none",
]

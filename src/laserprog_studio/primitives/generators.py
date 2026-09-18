# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any

from laserprog_studio.domain.work_model import WorkMesh

from .base import PrimitiveBuildRequest


def _color(values: dict[str, Any]) -> str:
    color = str(values.get("color", "#B8B8B8") or "#B8B8B8").strip()
    if not color.startswith("#") or len(color) not in (7, 9):
        return "#B8B8B8"
    return color


def _float(values: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(values.get(key, default))
    except Exception:
        return default


def _int(values: dict[str, Any], key: str, default: int, *, minimum: int = 1, maximum: int = 4096) -> int:
    try:
        value = int(values.get(key, default))
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _common(values: dict[str, Any]) -> tuple[float, float, float, float, float, float, str]:
    sx = max(0.001, _float(values, "size_x", 40.0))
    sy = max(0.001, _float(values, "size_y", 40.0))
    sz = max(0.001, _float(values, "size_z", 40.0))
    px = _float(values, "pos_x", 0.0)
    py = _float(values, "pos_y", 0.0)
    pz = _float(values, "pos_z", 0.0)
    return sx, sy, sz, px, py, pz, _color(values)


def _mesh(prefix: str, req: PrimitiveBuildRequest, vertices, triangles, color: str) -> WorkMesh:
    return WorkMesh(
        name=f"{prefix}_{int(req.name_index):02d}",
        vertices=[(float(x), float(y), float(z)) for x, y, z in vertices],
        triangles=[(int(a), int(b), int(c)) for a, b, c in triangles],
        color=color,
    )


def build_box(req: PrimitiveBuildRequest) -> WorkMesh:
    sx, sy, sz, px, py, pz, color = _common(req.values)
    x0, x1 = px - sx / 2.0, px + sx / 2.0
    y0, y1 = py - sy / 2.0, py + sy / 2.0
    z0, z1 = pz - sz / 2.0, pz + sz / 2.0
    v = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    t = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    return _mesh("box", req, v, t, color)


def build_cylinder(req: PrimitiveBuildRequest, *, force_segments: int | None = None) -> WorkMesh:
    sx, sy, sz, px, py, pz, color = _common(req.values)
    segments = force_segments or _int(req.values, "segments", 64, minimum=3, maximum=512)
    rx, ry = sx / 2.0, sy / 2.0
    z0, z1 = pz - sz / 2.0, pz + sz / 2.0
    verts = []
    for z in (z0, z1):
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            verts.append((px + math.cos(a) * rx, py + math.sin(a) * ry, z))
    bottom_center = len(verts); verts.append((px, py, z0))
    top_center = len(verts); verts.append((px, py, z1))
    tris = []
    for i in range(segments):
        j = (i + 1) % segments
        b0, b1 = i, j
        t0, t1 = segments + i, segments + j
        # Side faces must be wound outward. Older builds used the opposite
        # side winding, which still looked correct in the viewport but broke
        # manifold3d booleans, especially cube - cylinder cuts.
        tris.extend([(b0, t1, t0), (b0, b1, t1), (bottom_center, b1, b0), (top_center, t0, t1)])
    prefix = "hex_prism" if segments == 6 and req.primitive_id == "hex_prism" else "cylinder"
    return _mesh(prefix, req, verts, tris, color)


def build_custom(req: PrimitiveBuildRequest) -> WorkMesh:
    """Build the user-configurable primitive.

    The fixed primitive entries remain available for fast creation.  This entry
    intentionally groups the predictable low-poly variants in a single final
    menu item so the main primitive list does not become noisy.
    """

    kind = str(req.values.get("custom_kind", "cylinder") or "cylinder").strip().lower()
    custom_req = PrimitiveBuildRequest(primitive_id=kind, values=req.values, name_index=req.name_index)
    if kind == "sphere":
        mesh = build_sphere(custom_req)
    elif kind == "cone":
        mesh = build_cone(custom_req)
    else:
        mesh = build_cylinder(custom_req)
    mesh.name = f"custom_{kind}_{int(req.name_index):02d}"
    return mesh


def estimate_triangle_count(values: dict[str, Any]) -> int:
    primitive_id = str(values.get("primitive_id", "box") or "box")
    if primitive_id == "custom":
        primitive_id = str(values.get("custom_kind", "cylinder") or "cylinder")

    if primitive_id == "box":
        return 12
    if primitive_id == "pyramid":
        return 6
    if primitive_id == "triangular_prism":
        return 8
    if primitive_id == "hex_prism":
        return 24
    if primitive_id == "cylinder":
        return 4 * _int(values, "segments", 64, minimum=3, maximum=512)
    if primitive_id == "cone":
        return 2 * _int(values, "segments", 64, minimum=3, maximum=512)
    if primitive_id == "sphere":
        theta = _int(values, "theta_resolution", 64, minimum=3, maximum=512)
        phi = _int(values, "phi_resolution", 32, minimum=3, maximum=256)
        return max(0, 2 * theta * max(1, phi - 1))
    return 0


def build_hex_prism(req: PrimitiveBuildRequest) -> WorkMesh:
    return build_cylinder(req, force_segments=6)


def build_cone(req: PrimitiveBuildRequest) -> WorkMesh:
    sx, sy, sz, px, py, pz, color = _common(req.values)
    segments = _int(req.values, "segments", 64, minimum=3, maximum=512)
    rx, ry = sx / 2.0, sy / 2.0
    z0, z1 = pz - sz / 2.0, pz + sz / 2.0
    verts = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        verts.append((px + math.cos(a) * rx, py + math.sin(a) * ry, z0))
    apex = len(verts); verts.append((px, py, z1))
    center = len(verts); verts.append((px, py, z0))
    tris = []
    for i in range(segments):
        j = (i + 1) % segments
        # Keep cone side faces outward for reliable manifold3d booleans.
        tris.extend([(i, j, apex), (center, j, i)])
    return _mesh("cone", req, verts, tris, color)


def build_pyramid(req: PrimitiveBuildRequest) -> WorkMesh:
    sx, sy, sz, px, py, pz, color = _common(req.values)
    x0, x1 = px - sx / 2.0, px + sx / 2.0
    y0, y1 = py - sy / 2.0, py + sy / 2.0
    z0, z1 = pz - sz / 2.0, pz + sz / 2.0
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0), (px, py, z1)]
    t = [(0, 2, 1), (0, 3, 2), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    return _mesh("pyramid", req, v, t, color)


def build_triangular_prism(req: PrimitiveBuildRequest) -> WorkMesh:
    sx, sy, sz, px, py, pz, color = _common(req.values)
    x0, x1 = px - sx / 2.0, px + sx / 2.0
    y0, y1 = py - sy / 2.0, py + sy / 2.0
    z0, z1 = pz - sz / 2.0, pz + sz / 2.0
    v = [
        (x0, y0, z0), (x0, y1, z0), (x0, py, z1),
        (x1, y0, z0), (x1, y1, z0), (x1, py, z1),
    ]
    t = [(0, 2, 1), (3, 4, 5), (0, 3, 5), (0, 5, 2), (1, 2, 5), (1, 5, 4), (0, 1, 4), (0, 4, 3)]
    return _mesh("tri_prism", req, v, t, color)


def build_sphere(req: PrimitiveBuildRequest) -> WorkMesh:
    sx, sy, sz, px, py, pz, color = _common(req.values)
    theta = _int(req.values, "theta_resolution", _int(req.values, "segments", 64, minimum=3), minimum=3, maximum=512)
    phi = _int(req.values, "phi_resolution", 32, minimum=3, maximum=256)
    rx, ry, rz = sx / 2.0, sy / 2.0, sz / 2.0
    verts = [(px, py, pz + rz)]
    # Internal latitude rings, excluding poles.
    for p in range(1, phi):
        polar = math.pi * p / phi
        sp, cp = math.sin(polar), math.cos(polar)
        for i in range(theta):
            a = 2.0 * math.pi * i / theta
            verts.append((px + math.cos(a) * sp * rx, py + math.sin(a) * sp * ry, pz + cp * rz))
    bottom = len(verts); verts.append((px, py, pz - rz))
    tris = []
    first_ring = 1
    for i in range(theta):
        j = (i + 1) % theta
        tris.append((0, first_ring + i, first_ring + j))
    for ring in range(phi - 2):
        a0 = 1 + ring * theta
        a1 = a0 + theta
        for i in range(theta):
            j = (i + 1) % theta
            tris.extend([(a0 + i, a1 + i, a1 + j), (a0 + i, a1 + j, a0 + j)])
    last_ring = 1 + (phi - 2) * theta
    for i in range(theta):
        j = (i + 1) % theta
        tris.append((bottom, last_ring + j, last_ring + i))
    return _mesh("sphere", req, verts, tris, color)

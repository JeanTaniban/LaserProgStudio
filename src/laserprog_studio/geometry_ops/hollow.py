# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import copy
import math

from .mesh_metadata import copy_runtime_mesh_metadata
from .result import OperationResult


@dataclass(frozen=True)
class HollowStats:
    triangles_before: int = 0
    triangles_after: int = 0
    vertices_before: int = 0
    vertices_after: int = 0


def _as_vec3(value) -> tuple[float, float, float]:
    x, y, z = value[:3]
    return (float(x), float(y), float(z))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a, b) -> float:
    return float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])


def _norm(v) -> float:
    return math.sqrt(_dot(v, v))


def _normalize(v) -> tuple[float, float, float]:
    n = _norm(v)
    if n <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(v, s: float):
    return (v[0] * s, v[1] * s, v[2] * s)


def _triangle_count(mesh: Any) -> int:
    try:
        return int(len(getattr(mesh, "triangles", []) or []))
    except Exception:
        return 0


def _bounds(vertices: list[tuple[float, float, float]]) -> tuple[float, float, float, float, float, float]:
    xs = [p[0] for p in vertices]
    ys = [p[1] for p in vertices]
    zs = [p[2] for p in vertices]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def _mesh_name(mesh: Any) -> str:
    return str(getattr(mesh, "name", "Part") or "Part")


def _validate_closed_manifold(vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]]) -> str | None:
    if len(vertices) < 4 or len(triangles) < 4:
        return "mesh is too small to hollow."
    edge_count: dict[tuple[int, int], int] = {}
    used: set[int] = set()
    for tri_idx, tri in enumerate(triangles):
        a, b, c = tri
        if a == b or b == c or c == a:
            return f"degenerate triangle detected (triangle {tri_idx})."
        if min(a, b, c) < 0 or max(a, b, c) >= len(vertices):
            return f"invalid triangle index (triangle {tri_idx})."
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        area2 = _norm(_cross(_sub(pb, pa), _sub(pc, pa)))
        if area2 <= 1e-10:
            return f"zero-area triangle detected (triangle {tri_idx})."
        used.update((a, b, c))
        for i, j in ((a, b), (b, c), (c, a)):
            edge = (min(i, j), max(i, j))
            edge_count[edge] = edge_count.get(edge, 0) + 1
    if len(used) != len(vertices):
        return "the mesh contains unused vertices. Clean or regenerate the part before Hollow."
    bad = [(edge, count) for edge, count in edge_count.items() if count != 2]
    if bad:
        edge, count = bad[0]
        if count == 1:
            return f"open mesh: edge {edge} has only one face."
        return f"non-manifold mesh: edge {edge} is shared by {count} faces."
    return None


def _signed_volume(vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]]) -> float:
    volume = 0.0
    for a, b, c in triangles:
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        volume += _dot(pa, _cross(pb, pc)) / 6.0
    return volume


def _vertex_normals(vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]]) -> tuple[list[tuple[float, float, float]], str | None]:
    normals = [(0.0, 0.0, 0.0) for _ in vertices]
    for a, b, c in triangles:
        pa, pb, pc = vertices[a], vertices[b], vertices[c]
        n = _cross(_sub(pb, pa), _sub(pc, pa))
        normals[a] = _add(normals[a], n)
        normals[b] = _add(normals[b], n)
        normals[c] = _add(normals[c], n)
    orient = 1.0 if _signed_volume(vertices, triangles) >= 0.0 else -1.0
    out: list[tuple[float, float, float]] = []
    for idx, n in enumerate(normals):
        nn = _normalize(_mul(n, orient))
        if _norm(nn) <= 1e-12:
            return [], f"invalid vertex normal at vertex {idx}."
        out.append(nn)
    return out, None


def _make_hollow_mesh(mesh: Any, *, thickness: float) -> tuple[Any | None, HollowStats, str | None]:
    vertices = [_as_vec3(v) for v in (getattr(mesh, "vertices", []) or [])]
    triangles = [tuple(int(v) for v in tri[:3]) for tri in (getattr(mesh, "triangles", []) or [])]
    if not vertices or not triangles:
        return None, HollowStats(), "empty or invalid object."
    if float(thickness) <= 0.0:
        return None, HollowStats(), "thickness must be strictly positive."

    invalid = _validate_closed_manifold(vertices, triangles)
    if invalid:
        return None, HollowStats(len(triangles), len(triangles), len(vertices), len(vertices)), invalid

    b = _bounds(vertices)
    dims = (float(b[1] - b[0]), float(b[3] - b[2]), float(b[5] - b[4]))
    positive_dims = [d for d in dims if d > 1e-8]
    if len(positive_dims) < 3:
        return None, HollowStats(len(triangles), len(triangles), len(vertices), len(vertices)), "the part has no usable 3D volume."
    min_dim = min(positive_dims)
    if float(thickness) >= min_dim * 0.45:
        return None, HollowStats(len(triangles), len(triangles), len(vertices), len(vertices)), (
            f"thickness is too large for this part ({thickness:.3f} mm). "
            f"Suggested maximum: {min_dim * 0.45:.3f} mm."
        )

    normals, normal_error = _vertex_normals(vertices, triangles)
    if normal_error:
        return None, HollowStats(len(triangles), len(triangles), len(vertices), len(vertices)), normal_error

    inner_vertices = []
    for p, n in zip(vertices, normals):
        inner_vertices.append((
            float(p[0] - n[0] * thickness),
            float(p[1] - n[1] * thickness),
            float(p[2] - n[2] * thickness),
        ))

    offset = len(vertices)
    inner_triangles = [(c + offset, b + offset, a + offset) for a, b, c in triangles]
    out = copy.deepcopy(mesh)
    out.vertices = vertices + inner_vertices
    out.triangles = triangles + inner_triangles
    try:
        if "hollow" not in str(out.name).lower():
            out.name = f"{out.name} hollow"
    except Exception:
        pass
    copy_runtime_mesh_metadata(mesh, out)
    return out, HollowStats(len(triangles), len(out.triangles), len(vertices), len(out.vertices)), None


def hollow_selected_meshes(meshes: list[Any], selected_indices: list[int], *, thickness: float) -> OperationResult:
    if not selected_indices:
        return OperationResult.failure("Select at least one part to hollow.")
    out = [copy.deepcopy(m) for m in meshes]
    warnings: list[str] = []
    changed = 0
    before_tris = 0
    after_tris = 0
    for raw_idx in selected_indices:
        idx = int(raw_idx)
        if not (0 <= idx < len(out)):
            continue
        new_mesh, stats, error = _make_hollow_mesh(out[idx], thickness=float(thickness))
        before_tris += int(stats.triangles_before)
        after_tris += int(stats.triangles_after)
        if error or new_mesh is None:
            return OperationResult.failure(f"{_mesh_name(out[idx])}: {error or 'cut impossible.'}", warnings=warnings)
        out[idx] = new_mesh
        changed += 1
    if changed <= 0:
        return OperationResult.failure("No valid selected part to hollow.")
    warnings.append(f"Hollowed parts: {changed}; selected triangles: {before_tris} → {after_tris}")
    return OperationResult.success(out, warnings=warnings)


__all__ = ["HollowStats", "hollow_selected_meshes"]

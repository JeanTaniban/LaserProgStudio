# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import copy
import math

from laserprog_studio.domain.work_model import WorkMesh


@dataclass(frozen=True, slots=True)
class MeshRepairReport:
    input_vertices: int
    input_triangles: int
    output_vertices: int
    output_triangles: int
    removed_degenerate: int = 0
    removed_duplicate_triangles: int = 0
    closed_before: bool = False
    closed_after: bool = False
    boundary_edges_before: int = 0
    boundary_edges_after: int = 0
    nonmanifold_edges_before: int = 0
    nonmanifold_edges_after: int = 0
    trimesh_repair_used: bool = False


def _closed_stats(vertices: Any, triangles: Any) -> tuple[bool, int, int]:
    try:
        from laserprog_studio.boolean_ops import is_closed_triangle_mesh
        return is_closed_triangle_mesh(vertices, triangles)
    except Exception:
        try:
            from boolean_ops import is_closed_triangle_mesh  # type: ignore
            return is_closed_triangle_mesh(vertices, triangles)
        except Exception:
            return (False, 0, 0)


def _orient(vertices: Any, triangles: Any):
    try:
        from laserprog_studio.boolean_ops import _orient_triangles_for_manifold
        return _orient_triangles_for_manifold(vertices, triangles)
    except Exception:
        try:
            from boolean_ops import _orient_triangles_for_manifold  # type: ignore
            return _orient_triangles_for_manifold(vertices, triangles)
        except Exception:
            return triangles


def _copy_runtime_attrs(src: Any, dst: Any) -> None:
    for attr in (
        "material",
        "engraving",
        "uvs",
        "texture_projections",
        "metadata",
        "is_texture_decal",
        "texture_decal_for",
        "texture_decal_source_face",
        "texture_decal_origin",
        "texture_decal_normal",
        "texture_decal_u_axis",
        "texture_decal_v_axis",
        "texture_decal_tile_width",
        "texture_decal_tile_height",
        "_lps_scene_helper",
        "_lps_skip_boolean_merge",
    ):
        try:
            if hasattr(src, attr):
                setattr(dst, attr, copy.deepcopy(getattr(src, attr)))
        except Exception:
            pass
    try:
        for name in dir(src):
            if name.startswith("_lps_") and not hasattr(dst, name):
                try:
                    setattr(dst, name, copy.deepcopy(getattr(src, name)))
                except Exception:
                    pass
    except Exception:
        pass


def _mesh_bounds(vertices: list[tuple[float, float, float]]) -> tuple[float, float, float, float, float, float]:
    if not vertices:
        return (0, 0, 0, 0, 0, 0)
    xs = [p[0] for p in vertices]
    ys = [p[1] for p in vertices]
    zs = [p[2] for p in vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _mesh_size(vertices: list[tuple[float, float, float]]) -> float:
    b = _mesh_bounds(vertices)
    return max(b[1] - b[0], b[3] - b[2], b[5] - b[4], 1.0)


def _numpy_repair(mesh: Any, *, tolerance_mm: float, remove_tiny_faces: bool = True):
    import numpy as np

    verts_raw = np.asarray(getattr(mesh, "vertices", []) or [], dtype=float)
    tris_raw = np.asarray(getattr(mesh, "triangles", []) or [], dtype=np.int64)
    if verts_raw.ndim != 2 or verts_raw.shape[1] < 3 or tris_raw.size == 0:
        return [], [], 0, 0
    verts = verts_raw[:, :3].copy()
    if tris_raw.ndim == 1:
        if tris_raw.size % 3 != 0:
            return [], [], 0, 0
        tris = tris_raw.reshape((-1, 3)).copy()
    else:
        tris = tris_raw[:, :3].copy()

    tol = max(float(tolerance_mm), 1e-9)
    q = np.round(verts / tol).astype(np.int64)
    remap: dict[tuple[int, int, int], int] = {}
    new_verts: list[tuple[float, float, float]] = []
    old_to_new: list[int] = []
    accum: dict[tuple[int, int, int], list[float]] = {}
    counts: dict[tuple[int, int, int], int] = {}
    for i, key_arr in enumerate(q):
        key = (int(key_arr[0]), int(key_arr[1]), int(key_arr[2]))
        idx = remap.get(key)
        if idx is None:
            idx = len(new_verts)
            remap[key] = idx
            accum[key] = [float(verts[i, 0]), float(verts[i, 1]), float(verts[i, 2])]
            counts[key] = 1
            new_verts.append((0.0, 0.0, 0.0))
        else:
            accum[key][0] += float(verts[i, 0])
            accum[key][1] += float(verts[i, 1])
            accum[key][2] += float(verts[i, 2])
            counts[key] += 1
        old_to_new.append(idx)
    for key, idx in remap.items():
        c = max(int(counts[key]), 1)
        a = accum[key]
        new_verts[idx] = (a[0] / c, a[1] / c, a[2] / c)

    tri_out: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    removed_deg = 0
    removed_dup = 0
    verts_np = np.asarray(new_verts, dtype=float)
    tiny_area = max(tol * tol * 1e-3, 1e-14)
    for tri in tris:
        try:
            a, b, c = int(old_to_new[int(tri[0])]), int(old_to_new[int(tri[1])]), int(old_to_new[int(tri[2])])
        except Exception:
            removed_deg += 1
            continue
        if a == b or b == c or a == c:
            removed_deg += 1
            continue
        if remove_tiny_faces:
            pa, pb, pc = verts_np[a], verts_np[b], verts_np[c]
            area2 = float(np.linalg.norm(np.cross(pb - pa, pc - pa)))
            if area2 <= tiny_area:
                removed_deg += 1
                continue
        key = tuple(sorted((a, b, c)))
        if key in seen:
            removed_dup += 1
            continue
        seen.add(key)
        tri_out.append((a, b, c))
    try:
        tri_arr = _orient(np.asarray(new_verts, dtype=float), np.asarray(tri_out, dtype=np.int32))
        tri_out = [(int(a), int(b), int(c)) for a, b, c in tri_arr]
    except Exception:
        pass
    return new_verts, tri_out, removed_deg, removed_dup


def _trimesh_repair_vertices_triangles(
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    *,
    fill_holes: bool,
):
    """Optional high-level repair using trimesh when available.

    The application does not require trimesh, but many Python installations have
    it.  When present, it gives us a good additional pass for winding, normals,
    duplicate faces and small holes without making the Studio startup depend on
    it.  If anything looks suspicious, callers simply keep the previous mesh.
    """

    try:
        import numpy as np
        import trimesh

        if not vertices or not triangles:
            return vertices, triangles, False
        tm = trimesh.Trimesh(vertices=np.asarray(vertices, dtype=float), faces=np.asarray(triangles, dtype=np.int64), process=False)
        try:
            tm.remove_degenerate_faces()
        except Exception:
            pass
        try:
            tm.remove_duplicate_faces()
        except Exception:
            pass
        try:
            tm.remove_unreferenced_vertices()
        except Exception:
            pass
        try:
            trimesh.repair.fix_normals(tm)
        except Exception:
            pass
        if bool(fill_holes):
            try:
                trimesh.repair.fill_holes(tm)
            except Exception:
                pass
        try:
            tm.remove_unreferenced_vertices()
        except Exception:
            pass
        pts = [(float(x), float(y), float(z)) for x, y, z in np.asarray(tm.vertices, dtype=float)[:, :3]]
        tris = [(int(a), int(b), int(c)) for a, b, c in np.asarray(tm.faces, dtype=np.int64)[:, :3]]
        if pts and tris:
            return pts, tris, True
    except Exception:
        pass
    return vertices, triangles, False


def _pyvista_repair_vertices_triangles(
    vertices: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
    *,
    tolerance_mm: float,
    fill_holes: bool,
):
    try:
        import numpy as np
        import pyvista as pv

        if not vertices or not triangles:
            return vertices, triangles
        faces = []
        for a, b, c in triangles:
            faces.extend([3, int(a), int(b), int(c)])
        poly = pv.PolyData(np.asarray(vertices, dtype=float), np.asarray(faces, dtype=np.int64))
        try:
            poly = poly.clean(tolerance=max(float(tolerance_mm), 0.0), absolute=True, point_merging=True)
        except TypeError:
            poly = poly.clean(tolerance=max(float(tolerance_mm), 0.0), point_merging=True)
        if bool(fill_holes):
            try:
                size = max(_mesh_size(vertices) * 10.0, 1e3)
                poly = poly.fill_holes(size)
            except Exception:
                pass
        try:
            poly = poly.triangulate()
        except Exception:
            pass
        pts = [(float(x), float(y), float(z)) for x, y, z in np.asarray(poly.points, dtype=float)[:, :3]]
        arr = np.asarray(poly.faces, dtype=np.int64)
        tris_out: list[tuple[int, int, int]] = []
        i = 0
        while i < len(arr):
            n = int(arr[i]); i += 1
            ids = [int(v) for v in arr[i:i+n]]; i += n
            if n == 3:
                tris_out.append((ids[0], ids[1], ids[2]))
            elif n > 3:
                for k in range(1, n - 1):
                    tris_out.append((ids[0], ids[k], ids[k + 1]))
        if pts and tris_out:
            return pts, tris_out
    except Exception:
        pass
    return vertices, triangles


def repair_work_mesh(
    mesh: Any,
    *,
    tolerance_mm: float = 0.01,
    fill_holes: bool = True,
    remove_tiny_faces: bool = True,
    name_suffix: str = "",
    optional_backends: bool = True,
) -> tuple[Any, MeshRepairReport]:
    """Best-effort robust mesh repair for Studio parts.

    It performs conservative operations first: merge very close vertices, remove
    degenerate/duplicate triangles and orient connected faces.  When
    optional_backends=True it may also use trimesh/PyVista for imported or damaged
    meshes.  Boolean result cleanup passes optional_backends=False to avoid paying
    heavy optional import costs for already-closed generated meshes.
    """

    verts_in = list(getattr(mesh, "vertices", []) or [])
    tris_in = list(getattr(mesh, "triangles", []) or [])
    closed_before, be_before, ne_before = _closed_stats(verts_in, tris_in)

    verts, tris, rem_deg, rem_dup = _numpy_repair(mesh, tolerance_mm=tolerance_mm, remove_tiny_faces=remove_tiny_faces)
    trimesh_used = False
    if bool(optional_backends):
        verts, tris, trimesh_used = _trimesh_repair_vertices_triangles(verts, tris, fill_holes=fill_holes)
        verts, tris = _pyvista_repair_vertices_triangles(verts, tris, tolerance_mm=tolerance_mm, fill_holes=fill_holes)
        verts, tris, trimesh_used_2 = _trimesh_repair_vertices_triangles(verts, tris, fill_holes=False)
        trimesh_used = bool(trimesh_used or trimesh_used_2)
    tmp = WorkMesh(name=str(getattr(mesh, "name", "part") or "part"), vertices=verts, triangles=tris, color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"))
    verts, tris, rem_deg2, rem_dup2 = _numpy_repair(tmp, tolerance_mm=tolerance_mm, remove_tiny_faces=remove_tiny_faces)
    rem_deg += rem_deg2
    rem_dup += rem_dup2

    closed_after, be_after, ne_after = _closed_stats(verts, tris)
    out = WorkMesh(
        name=(str(getattr(mesh, "name", "part") or "part") + str(name_suffix or "")),
        vertices=verts,
        triangles=tris,
        color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
    )
    _copy_runtime_attrs(mesh, out)
    try:
        if getattr(out, "uvs", None) is not None and len(getattr(out, "uvs", []) or []) != len(out.vertices):
            out.uvs = None
            out.texture_projections = []
            mat = getattr(out, "material", None)
            if mat is not None and not isinstance(mat, dict):
                mat.texture_id = None
    except Exception:
        pass
    report = MeshRepairReport(
        input_vertices=len(verts_in),
        input_triangles=len(tris_in),
        output_vertices=len(verts),
        output_triangles=len(tris),
        removed_degenerate=int(rem_deg),
        removed_duplicate_triangles=int(rem_dup),
        closed_before=bool(closed_before),
        closed_after=bool(closed_after),
        boundary_edges_before=int(be_before),
        boundary_edges_after=int(be_after),
        nonmanifold_edges_before=int(ne_before),
        nonmanifold_edges_after=int(ne_after),
        trimesh_repair_used=bool(locals().get("trimesh_used", False)),
    )
    return out, report


def offset_mesh_uniform_by_face_planes(mesh: Any, *, margin_mm: float = 0.0) -> Any:
    """Return a copy whose closed surfaces are offset by a uniform distance.

    This is intentionally *not* a bounding-box scale.  For each vertex we solve
    the intersection of its incident face planes after every plane has been
    shifted by ``margin_mm`` along its outward normal.  On boxes/prisms this
    gives a true constant wall offset: a +0.20 mm margin moves each side face by
    0.20 mm, whether the cutter is square, rectangular or rotated in world
    space.  Negative values shrink the cutter and therefore make the boolean
    hole smaller.
    """

    try:
        margin = float(margin_mm)
    except Exception:
        margin = 0.0
    if abs(margin) <= 1e-12:
        return copy.deepcopy(mesh)

    try:
        import numpy as np
    except Exception:
        return copy.deepcopy(mesh)

    verts = np.asarray(getattr(mesh, "vertices", []) or [], dtype=np.float64)
    tris_raw = np.asarray(getattr(mesh, "triangles", []) or [], dtype=np.int64)
    if verts.ndim != 2 or verts.shape[1] < 3 or tris_raw.size == 0:
        return copy.deepcopy(mesh)
    if tris_raw.ndim == 1:
        if tris_raw.size % 3 != 0:
            return copy.deepcopy(mesh)
        tris_raw = tris_raw.reshape((-1, 3))
    tris = tris_raw[:, :3].astype(np.int64, copy=False)
    try:
        tris = np.asarray(_orient(verts[:, :3], tris.astype(np.int32)), dtype=np.int64)
    except Exception:
        pass

    vertex_planes: list[list[tuple[tuple[int, int, int], np.ndarray, float]]] = [[] for _ in range(len(verts))]
    quant = 1e8
    for tri in tris:
        try:
            a, b, c = int(tri[0]), int(tri[1]), int(tri[2])
            if not (0 <= a < len(verts) and 0 <= b < len(verts) and 0 <= c < len(verts)):
                continue
            pa, pb, pc = verts[a, :3], verts[b, :3], verts[c, :3]
            n = np.cross(pb - pa, pc - pa)
            length = float(np.linalg.norm(n))
            if length <= 1e-12:
                continue
            n = n / length
            d = float(np.dot(n, pa)) + margin
            key = (int(round(float(n[0]) * quant)), int(round(float(n[1]) * quant)), int(round(float(n[2]) * quant)))
            for vi in (a, b, c):
                planes = vertex_planes[vi]
                # Avoid overweighting triangulated coplanar quads.  Two triangles
                # from the same planar face must count as one shifted plane.
                duplicate = False
                for existing_key, _existing_n, existing_d in planes:
                    if existing_key == key and abs(existing_d - d) <= 1e-7:
                        duplicate = True
                        break
                if not duplicate:
                    planes.append((key, n, d))
        except Exception:
            continue

    out_vertices = verts[:, :3].copy()
    for vi, planes in enumerate(vertex_planes):
        if not planes:
            continue
        A = np.asarray([p[1] for p in planes], dtype=np.float64)
        b = np.asarray([p[2] for p in planes], dtype=np.float64)
        try:
            if len(planes) >= 3 and np.linalg.matrix_rank(A) >= 3:
                solved, *_ = np.linalg.lstsq(A, b, rcond=None)
                out_vertices[vi, :] = solved[:3]
            else:
                # Smooth or under-constrained vertices: use averaged incident
                # normals.  This keeps cylinders usable while exact corner
                # vertices still use the plane-intersection path above.
                avg = np.sum(A, axis=0)
                norm = float(np.linalg.norm(avg))
                if norm > 1e-12:
                    out_vertices[vi, :] = verts[vi, :3] + (avg / norm) * margin
        except Exception:
            pass

    out = copy.deepcopy(mesh)
    out.vertices = [(float(x), float(y), float(z)) for x, y, z in out_vertices[:, :3]]
    return out


def expand_mesh_about_center(mesh: Any, *, margin_mm: float = 0.03) -> Any:
    """Backward-compatible wrapper for boolean cutter growth.

    Older code called this helper even though a centre-scale is exactly the
    behaviour we do *not* want for production clearances.  Keep the public name
    to avoid breaking imports, but delegate to the uniform face-plane offset.
    """

    try:
        margin = float(margin_mm)
    except Exception:
        margin = 0.0
    if abs(margin) <= 1e-12:
        return copy.deepcopy(mesh)
    return offset_mesh_uniform_by_face_planes(mesh, margin_mm=margin)


__all__ = ["MeshRepairReport", "repair_work_mesh", "expand_mesh_about_center", "offset_mesh_uniform_by_face_planes"]

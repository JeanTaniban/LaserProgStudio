# -*- coding: utf-8 -*-
from __future__ import annotations

from .joint_builder_contact import *  # type: ignore  # noqa: F401,F403

def _merge_work_meshes(meshes: list[WorkMesh], *, name: str, color: str = "#FF7F7F") -> WorkMesh:
    """Merge several WorkMesh objects into one multi-component mesh.

    Important: this is NOT a boolean. It simply concatenates triangles.
    This is intentional: manifold3d can receive a tool made of several
    separate closed solids, which then allows a single union/difference
    heavy operation with the real part.
    """
    vertices_out: list[tuple[float, float, float]] = []
    triangles_out: list[tuple[int, int, int]] = []
    offset = 0
    for mesh in meshes:
        if not mesh.vertices or not mesh.triangles:
            continue
        vertices_out.extend((float(x), float(y), float(z)) for x, y, z in mesh.vertices)
        for a, b, c in mesh.triangles:
            triangles_out.append((int(a) + offset, int(b) + offset, int(c) + offset))
        offset += len(mesh.vertices)
    if not vertices_out or not triangles_out:
        raise ValueError("Empty boolean tool: no boxes to merge.")
    return WorkMesh(name=name, vertices=vertices_out, triangles=triangles_out, color=color)

def _boolean_3d(mesh_a: WorkMesh, mesh_b: WorkMesh, *, op: str) -> WorkMesh:
    """Shared 3D boolean with the Cubes / booleans tool."""
    try:
        from .cube_boolean import _bool_mesh_3d_manifold
    except Exception as exc:
        raise RuntimeError("Cannot load 3D booleans from the Cubes / booleans tool.") from exc
    return _bool_mesh_3d_manifold(mesh_a, mesh_b, op=op)

def _ray_triangle_hit_t(
    origin: np.ndarray,
    direction: np.ndarray,
    p0: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    *,
    eps: float = 1e-9,
) -> float | None:
    """Double-sided ray/triangle intersection. Returns t on hit, otherwise None.

    Uses Moller-Trumbore without culling. This function is only used to measure local
    thickness, so it does not depend on triangle orientation.
    """
    o = np.array(origin, dtype=float)
    d = _normalize(np.array(direction, dtype=float))
    if float(np.linalg.norm(d)) <= 1e-12:
        return None

    e1 = p1 - p0
    e2 = p2 - p0
    h = np.cross(d, e2)
    a = float(np.dot(e1, h))
    if abs(a) <= eps:
        return None
    f = 1.0 / a
    svec = o - p0
    u = f * float(np.dot(svec, h))
    if u < -1e-7 or u > 1.0 + 1e-7:
        return None
    q = np.cross(svec, e1)
    v = f * float(np.dot(d, q))
    if v < -1e-7 or (u + v) > 1.0 + 1e-7:
        return None
    t = f * float(np.dot(e2, q))
    if t <= eps:
        return None
    return float(t)

def _positive_ray_hits_mm(mesh: WorkMesh, origin: np.ndarray, direction: np.ndarray) -> list[float]:
    """Sorted list of positive distances where a ray intersects the mesh."""
    verts = np.array(mesh.vertices, dtype=float)
    hits: list[float] = []
    for ia, ib, ic in mesh.triangles:
        try:
            t = _ray_triangle_hit_t(origin, direction, verts[ia], verts[ib], verts[ic])
        except Exception:
            t = None
        if t is not None and math.isfinite(t) and t > 0.0:
            hits.append(float(t))
    if not hits:
        return []

    hits.sort()
    # Deduplicate double hits caused by the two triangles of the same square face.
    merged: list[float] = []
    for t in hits:
        if not merged or abs(t - merged[-1]) > 0.025:
            merged.append(float(t))
        else:
            merged[-1] = (merged[-1] + float(t)) / 2.0
    return merged

def _positive_ray_hit_details_mm(
    mesh: WorkMesh,
    origin: np.ndarray,
    direction: np.ndarray,
    *,
    max_hits: int = 80,
) -> dict:
    """Diagnostic version of _positive_ray_hits_mm.

    Returns raw hits and groups with triangle, point, normal, and geometric context.
    This function is intentionally verbose to understand false raycasts that measure
    a part length instead of its thickness.
    """
    verts = np.array(mesh.vertices, dtype=float)
    o = np.array(origin, dtype=float)
    d = _normalize(np.array(direction, dtype=float))
    raw: list[dict] = []
    skipped = 0
    for tri_index, (ia, ib, ic) in enumerate(mesh.triangles):
        try:
            p0 = verts[ia]
            p1 = verts[ib]
            p2 = verts[ic]
            t = _ray_triangle_hit_t(o, d, p0, p1, p2)
        except Exception:
            t = None
        if t is None or not math.isfinite(float(t)) or float(t) <= 0.0:
            continue
        e1 = p1 - p0
        e2 = p2 - p0
        n = np.cross(e1, e2)
        area2 = float(np.linalg.norm(n))
        tri_n = _normalize(n) if area2 > 1e-12 else np.array([0.0, 0.0, 0.0], dtype=float)
        point = o + d * float(t)
        item = {
            "t": float(t),
            "tri_index": int(tri_index),
            "vertex_indices": [int(ia), int(ib), int(ic)],
            "point": [float(x) for x in point.tolist()],
            "triangle_center": [float(x) for x in ((p0 + p1 + p2) / 3.0).tolist()],
            "triangle_normal": [float(x) for x in tri_n.tolist()],
            "normal_dot_ray": float(np.dot(tri_n, d)),
            "area_mm2": float(area2 * 0.5),
        }
        raw.append(item)
    raw.sort(key=lambda x: x["t"])

    groups: list[dict] = []
    for h in raw:
        if not groups or abs(float(h["t"]) - float(groups[-1]["t"])) > 0.025:
            groups.append({
                "t": float(h["t"]),
                "count": 1,
                "triangles": [int(h["tri_index"])],
                "first_point": h["point"],
                "first_normal": h["triangle_normal"],
                "first_normal_dot_ray": float(h["normal_dot_ray"]),
            })
        else:
            g = groups[-1]
            old_count = int(g["count"])
            new_count = old_count + 1
            g["t"] = (float(g["t"]) * old_count + float(h["t"])) / new_count
            g["count"] = new_count
            if len(g["triangles"]) < 12:
                g["triangles"].append(int(h["tri_index"]))
    if len(raw) > max_hits:
        skipped = len(raw) - max_hits
    return {
        "raw_hit_count": int(len(raw)),
        "merged_hit_count": int(len(groups)),
        "raw_hits_first": raw[:max_hits],
        "raw_hits_omitted": int(skipped),
        "merged_hits": groups[:max_hits],
        "merged_hits_omitted": max(0, len(groups) - max_hits),
    }

def _ray_hit_count_in_direction(mesh: WorkMesh, origin: np.ndarray, direction: np.ndarray, *, min_t: float = 1e-5) -> int:
    """Count grouped positive intersections in one direction.

    Diagnostics only: used to tell whether a point seems inside/outside by parity.
    For a closed mesh, an odd number of exits in one direction generally indicates
    that the point is inside the volume. An even number generally indicates the outside.
    """
    hits = [float(t) for t in _positive_ray_hits_mm(mesh, origin, direction) if float(t) > float(min_t)]
    if not hits:
        return 0
    hits.sort()
    groups: list[float] = []
    for t in hits:
        if not groups or abs(t - groups[-1]) > 0.025:
            groups.append(t)
    return len(groups)

def _point_inside_diagnostic(mesh: WorkMesh, point: np.ndarray) -> dict:
    """Point position diagnostic: bounding box + ray parity along multiple axes."""
    verts = np.array(mesh.vertices, dtype=float)
    p = np.array(point, dtype=float)
    if len(verts) == 0:
        return {"point": p.tolist(), "has_vertices": False}
    bmin = verts.min(axis=0)
    bmax = verts.max(axis=0)
    eps = 1e-6
    in_bbox = bool(np.all(p >= bmin - eps) and np.all(p <= bmax + eps))
    axes = {
        "+X": np.array([1.0, 0.0, 0.0]),
        "-X": np.array([-1.0, 0.0, 0.0]),
        "+Y": np.array([0.0, 1.0, 0.0]),
        "-Y": np.array([0.0, -1.0, 0.0]),
        "+Z": np.array([0.0, 0.0, 1.0]),
        "-Z": np.array([0.0, 0.0, -1.0]),
    }
    parity = {}
    odd_votes = 0
    for name, d in axes.items():
        try:
            count = _ray_hit_count_in_direction(mesh, p, d)
        except Exception:
            count = -1
        is_odd = bool(count >= 0 and (count % 2 == 1))
        if is_odd:
            odd_votes += 1
        parity[name] = {"hit_group_count": int(count), "odd_inside_vote": is_odd}
    return {
        "point": [float(x) for x in p.tolist()],
        "bbox_min": [float(x) for x in bmin.tolist()],
        "bbox_max": [float(x) for x in bmax.tolist()],
        "bbox_dims": [float(x) for x in (bmax - bmin).tolist()],
        "inside_bbox": in_bbox,
        "parity_votes": parity,
        "odd_inside_votes": int(odd_votes),
        "likely_inside_by_parity": bool(odd_votes >= 3),
        "note": "Approximate diagnostic: mostly reliable on a closed/manifold mesh. Used to verify whether the offset start is really inside the material.",
    }

def _direction_extent_diagnostic(mesh: WorkMesh, origin: np.ndarray, direction: np.ndarray) -> dict:
    """Mesh projection in one direction from origin: useful to see whether a ray measures height/length."""
    verts = np.array(mesh.vertices, dtype=float)
    o = np.array(origin, dtype=float)
    d = _normalize(np.array(direction, dtype=float))
    if len(verts) == 0 or float(np.linalg.norm(d)) <= 1e-12:
        return {"valid": False}
    vals = (verts - o) @ d
    pos = vals[vals >= 0.0]
    neg = vals[vals <= 0.0]
    return {
        "valid": True,
        "dir": [float(x) for x in d.tolist()],
        "projection_min_from_origin": float(vals.min()),
        "projection_max_from_origin": float(vals.max()),
        "projection_span": float(vals.max() - vals.min()),
        "positive_extent": None if len(pos) == 0 else float(pos.max()),
        "negative_extent_abs": None if len(neg) == 0 else float(abs(neg.min())),
        "nearest_positive_vertex_projection": None if len(pos) == 0 else float(pos.min()),
        "nearest_negative_vertex_projection_abs": None if len(neg) == 0 else float(abs(neg.max())),
    }

def _mesh_basis_diagnostic(mesh: WorkMesh, basis: PlankBasis, *, label: str) -> dict:
    verts = np.array(mesh.vertices, dtype=float)
    if len(verts) == 0:
        return {"label": label, "vertex_count": 0, "triangle_count": len(mesh.triangles)}
    centered = verts - basis.origin
    uvals = centered @ basis.u
    vvals = centered @ basis.v
    wvals = centered @ basis.n
    bbox_min = verts.min(axis=0)
    bbox_max = verts.max(axis=0)
    dims = bbox_max - bbox_min
    return {
        "label": label,
        "name": getattr(mesh, "name", ""),
        "vertex_count": int(len(mesh.vertices)),
        "triangle_count": int(len(mesh.triangles)),
        "bbox_min": [float(x) for x in bbox_min.tolist()],
        "bbox_max": [float(x) for x in bbox_max.tolist()],
        "bbox_dims_xyz": [float(x) for x in dims.tolist()],
        "basis_origin": [float(x) for x in basis.origin.tolist()],
        "basis_u": [float(x) for x in basis.u.tolist()],
        "basis_v": [float(x) for x in basis.v.tolist()],
        "basis_n": [float(x) for x in basis.n.tolist()],
        "basis_thickness": float(basis.thickness),
        "basis_ranges": {
            "u": [float(uvals.min()), float(uvals.max()), float(uvals.max() - uvals.min())],
            "v": [float(vvals.min()), float(vvals.max()), float(vvals.max() - vvals.min())],
            "n": [float(wvals.min()), float(wvals.max()), float(wvals.max() - wvals.min())],
        },
    }

__all__ = [name for name in globals() if not name.startswith("__")]

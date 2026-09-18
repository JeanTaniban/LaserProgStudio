# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
from typing import Any, Iterable


def _workmesh_class():
    try:
        from laserprog_studio.domain.work_model import WorkMesh
        return WorkMesh
    except Exception:
        return None


def _normalize3(vec: Iterable[float]) -> tuple[float, float, float]:
    x, y, z = [float(v) for v in list(vec)[:3]]
    n = math.sqrt(x * x + y * y + z * z)
    if n <= 1e-12:
        return (0.0, 0.0, 1.0)
    return (x / n, y / n, z / n)


def _copy_runtime_mesh_attrs(src: Any, dst: Any) -> None:
    try:
        for name in dir(src):
            if name.startswith("_lps_"):
                try:
                    setattr(dst, name, getattr(src, name))
                except Exception:
                    pass
    except Exception:
        pass


def _mesh_to_polydata(mesh: Any):
    import numpy as np
    import pyvista as pv

    pts = np.asarray(getattr(mesh, "vertices", []) or [], dtype=float)
    tris = np.asarray(getattr(mesh, "triangles", []) or [], dtype=int)
    if pts.ndim != 2 or pts.shape[1] < 3:
        raise ValueError("Split modifier failed: invalid vertices.")
    if tris.ndim != 2 or tris.shape[1] != 3:
        raise ValueError("Split modifier failed: invalid triangles.")
    faces = np.empty((tris.shape[0], 4), dtype=int)
    faces[:, 0] = 3
    faces[:, 1:] = tris[:, :3]
    return pv.PolyData(pts[:, :3], faces.ravel()).triangulate().clean()


def _polydata_to_workmesh(poly: Any, *, name: str, color: str, source_mesh: Any) -> Any | None:
    import numpy as np

    WorkMesh = _workmesh_class()
    if WorkMesh is None:
        raise RuntimeError("Split modifier failed: WorkMesh class is unavailable.")

    try:
        pdata = poly.triangulate().clean()
    except Exception:
        pdata = poly
    try:
        if int(pdata.n_points) <= 0 or int(pdata.n_cells) <= 0:
            return None
    except Exception:
        return None

    points_np = np.asarray(pdata.points, dtype=float)
    faces = np.asarray(pdata.faces, dtype=int)
    triangles: list[tuple[int, int, int]] = []
    i = 0
    while i < len(faces):
        n = int(faces[i])
        if n == 3 and i + 3 < len(faces):
            triangles.append((int(faces[i + 1]), int(faces[i + 2]), int(faces[i + 3])))
        i += max(n + 1, 1)
    if len(points_np) == 0 or not triangles:
        return None

    out = WorkMesh(
        name=name,
        vertices=[(float(x), float(y), float(z)) for x, y, z in points_np[:, :3]],
        triangles=triangles,
        color=color,
    )
    _copy_runtime_mesh_attrs(source_mesh, out)
    return out


def _clip_closed_side(poly: Any, *, origin: tuple[float, float, float], normal: tuple[float, float, float], tolerance: float) -> Any | None:
    """Clip a closed mesh on one side of a plane.

    PyVista exposes vtkClipClosedSurface as clip_closed_surface in supported
    versions. If that is unavailable, fall back to clip(). The fallback may leave
    open caps, but it is still useful for preview and avoids a hard crash.
    """
    try:
        return poly.clip_closed_surface(normal=normal, origin=origin, tolerance=float(tolerance)).triangulate().clean()
    except TypeError:
        try:
            return poly.clip_closed_surface(normal=normal, origin=origin).triangulate().clean()
        except Exception:
            pass
    except Exception:
        pass
    try:
        return poly.clip(normal=normal, origin=origin, invert=False).triangulate().clean()
    except Exception:
        return None


def split_mesh_by_plane(
    mesh: Any,
    *,
    origin: tuple[float, float, float],
    normal: tuple[float, float, float],
    tolerance: float = 1e-5,
) -> list[Any]:
    """Split one WorkMesh with an infinite plane and return resulting pieces.

    The function expects a closed surface for the best result. It creates the two
    closed half meshes, then runs the existing separate operation to split any
    disconnected islands created by the cut.
    """
    import numpy as np

    vertices = np.asarray(getattr(mesh, "vertices", []) or [], dtype=float)
    triangles = np.asarray(getattr(mesh, "triangles", []) or [], dtype=int)
    if vertices.size == 0 or triangles.size == 0:
        return [copy.deepcopy(mesh)]
    if vertices.ndim != 2 or vertices.shape[1] < 3:
        raise ValueError("Split modifier failed: invalid mesh vertices.")

    origin_arr = np.asarray(origin, dtype=float)[:3]
    normal_tuple = _normalize3(normal)
    normal_arr = np.asarray(normal_tuple, dtype=float)
    distances = (vertices[:, :3] - origin_arr) @ normal_arr
    tol = max(float(tolerance), 1e-8)
    if float(distances.min()) >= -tol or float(distances.max()) <= tol:
        # Plane does not cross the mesh volume enough to split it.
        return [copy.deepcopy(mesh)]

    poly = _mesh_to_polydata(mesh)
    base_name = str(getattr(mesh, "name", "part") or "part")
    color = str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8")

    sides: list[Any] = []
    for label, side_normal in [("A", normal_tuple), ("B", tuple(-v for v in normal_tuple))]:
        clipped = _clip_closed_side(poly, origin=tuple(origin_arr.tolist()), normal=side_normal, tolerance=tol)
        if clipped is None:
            continue
        candidate = _polydata_to_workmesh(clipped, name=f"{base_name}_split_{label}", color=color, source_mesh=mesh)
        if candidate is not None:
            sides.append(candidate)

    if len(sides) < 2:
        return [copy.deepcopy(mesh)]

    try:
        from laserprog_studio.boolean_ops import split_disconnected_mesh
    except Exception:
        from ..boolean_ops import split_disconnected_mesh  # type: ignore

    pieces: list[Any] = []
    for side in sides:
        for comp in split_disconnected_mesh(side):
            pieces.append(comp)

    if len(pieces) < 2:
        return [copy.deepcopy(mesh)]

    def sort_key(part: Any) -> tuple[float, float, float, str]:
        pts = list(getattr(part, "vertices", []) or [])
        if not pts:
            return (0.0, 0.0, 0.0, str(getattr(part, "name", "")))
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        zs = [float(p[2]) for p in pts]
        return (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs), str(getattr(part, "name", "")))

    pieces.sort(key=sort_key)
    for i, part in enumerate(pieces, start=1):
        try:
            part.name = f"{base_name}_split_{i:02d}"
        except Exception:
            pass
    return pieces


def split_selected_meshes_by_plane(
    meshes: list[Any],
    indices: list[int],
    *,
    origin: tuple[float, float, float],
    normal: tuple[float, float, float],
    tolerance: float = 1e-5,
) -> tuple[list[Any], list[int], int, int]:
    """Split selected meshes while preserving non-selected meshes.

    Returns (new_meshes, new_selected_indices, split_mesh_count, new_piece_count).
    """
    selected = {int(i) for i in indices if 0 <= int(i) < len(meshes)}
    if not selected:
        raise ValueError("Split modifier: select at least one part to split.")

    out: list[Any] = []
    new_selected: list[int] = []
    split_count = 0
    new_piece_count = 0
    for idx, mesh in enumerate(meshes):
        if idx not in selected:
            out.append(copy.deepcopy(mesh))
            continue
        pieces = split_mesh_by_plane(mesh, origin=origin, normal=normal, tolerance=tolerance)
        if len(pieces) > 1:
            split_count += 1
            new_piece_count += len(pieces)
        for piece in pieces:
            out.append(piece)
            if idx in selected:
                new_selected.append(len(out) - 1)
    return out, new_selected, split_count, new_piece_count

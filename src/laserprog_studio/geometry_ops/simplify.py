# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any
import copy

from ..mesh_ops import workmesh_to_polydata
from .mesh_metadata import copy_runtime_mesh_metadata
from .result import OperationResult


def _triangle_count(mesh: Any) -> int:
    try:
        return int(len(getattr(mesh, "triangles", []) or []))
    except Exception:
        return 0


def _polydata_to_workmesh(poly, source: Any, *, suffix: str = " simplified") -> Any:
    """Convert a triangular PyVista PolyData back to the shared WorkMesh shape."""
    tri = poly.triangulate().clean()
    points = tri.points
    faces = tri.faces.reshape((-1, 4)) if tri.faces.size else []
    vertices = [(float(p[0]), float(p[1]), float(p[2])) for p in points]
    triangles: list[tuple[int, int, int]] = []
    for face in faces:
        if int(face[0]) != 3:
            continue
        triangles.append((int(face[1]), int(face[2]), int(face[3])))

    out = copy.deepcopy(source)
    out.vertices = vertices
    out.triangles = triangles
    copy_runtime_mesh_metadata(source, out)
    try:
        if suffix and not str(out.name).lower().endswith("simplified"):
            out.name = f"{out.name}{suffix}"
    except Exception:
        pass
    return out


def _boundary_problem(poly) -> bool:
    """Return True when the mesh has open/non-manifold edges.

    Physical holes through a closed object are OK: they do not create boundary
    edges. Accidental holes in the mesh do create boundary/non-manifold edges and
    are rejected because simplification would very likely damage the part.
    """
    try:
        edges = poly.extract_feature_edges(
            boundary_edges=True,
            non_manifold_edges=True,
            feature_edges=False,
            manifold_edges=False,
        )
        return int(getattr(edges, "n_cells", 0)) > 0
    except Exception:
        # If the diagnostic fails, do not block the user; the decimator may still
        # fail and surface a clearer error.
        return False


def simplify_mesh(mesh: Any, reduction: float, *, preserve_topology: bool = True) -> tuple[Any | None, str | None]:
    """Simplify one WorkMesh.

    reduction is in [0, 0.95], where 0.80 asks VTK to remove about 80% of faces.
    """
    reduction = max(0.0, min(0.95, float(reduction)))
    before = _triangle_count(mesh)
    if before <= 4 or reduction <= 0.0001:
        return copy.deepcopy(mesh), None

    try:
        poly = workmesh_to_polydata(mesh).triangulate().clean()
        if int(getattr(poly, "n_cells", 0)) <= 4:
            return copy.deepcopy(mesh), None
        if preserve_topology and _boundary_problem(poly):
            return None, f"{getattr(mesh, 'name', 'Mesh')}: open/non-manifold mesh, Simplify refused."

        try:
            simplified = poly.decimate_pro(
                reduction,
                preserve_topology=bool(preserve_topology),
                boundary_vertex_deletion=not bool(preserve_topology),
                inplace=False,
            )
        except TypeError:
            # Fallback for older PyVista/VTK signatures.
            simplified = poly.decimate_pro(reduction, preserve_topology=bool(preserve_topology), inplace=False)
        simplified = simplified.triangulate().clean()
        if int(getattr(simplified, "n_cells", 0)) <= 0:
            return None, f"{getattr(mesh, 'name', 'Mesh')}: la simplification a produit un mesh vide."
        return _polydata_to_workmesh(simplified, mesh), None
    except Exception as exc:
        return None, f"{getattr(mesh, 'name', 'Mesh')}: simplification impossible ({exc})."


def simplify_selected_meshes(
    meshes: list[Any],
    selected_indices: list[int],
    *,
    reduction: float,
    preserve_topology: bool = True,
) -> OperationResult:
    if not selected_indices:
        return OperationResult.failure("Select at least one part to simplify.")
    out = [copy.deepcopy(m) for m in meshes]
    warnings: list[str] = []
    before_total = 0
    after_total = 0
    changed = 0
    for raw_idx in selected_indices:
        idx = int(raw_idx)
        if not (0 <= idx < len(out)):
            continue
        before = _triangle_count(out[idx])
        before_total += before
        simplified, error = simplify_mesh(out[idx], reduction, preserve_topology=preserve_topology)
        if error:
            return OperationResult.failure(error, warnings=warnings)
        if simplified is None:
            return OperationResult.failure(f"Part {idx}: simplification failed.", warnings=warnings)
        after = _triangle_count(simplified)
        after_total += after
        out[idx] = simplified
        changed += 1
    if changed <= 0:
        return OperationResult.failure("No valid selected part to simplify.")
    warnings.append(f"Selected triangles: {before_total} → {after_total}")
    return OperationResult.success(out, warnings=warnings)


__all__ = ["simplify_mesh", "simplify_selected_meshes"]

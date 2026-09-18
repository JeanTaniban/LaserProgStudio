"""Boundary between generic 3-D booleans and editable Cloth outputs."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .boolean_pattern import append_cloth_boolean_modifier
from .serialization import attach_cloth_source_in_place, restore_cloth_source

_STALE_GENERATED_TOPOLOGY_KEYS = {
    "cloth_mid_surface_vertices",
    "cloth_mid_surface_triangles",
    "cloth_closed_mid_surface",
    "cloth_patch_triangle_ranges",
    "cloth_vertex_patch_ids",
}


def _closed_by_edges(mesh: Any) -> bool:
    from collections import Counter

    triangles = list(getattr(mesh, "triangles", []) or [])
    if not triangles:
        return False
    counts: Counter[tuple[int, int]] = Counter()
    for face in triangles:
        try:
            a, b, c = int(face[0]), int(face[1]), int(face[2])
        except Exception:
            return False
        for first, second in ((a, b), (b, c), (c, a)):
            if first == second:
                return False
            counts[tuple(sorted((first, second)))] += 1
    return bool(counts) and all(value == 2 for value in counts.values())


def is_editable_cloth_mesh(mesh: Any) -> bool:
    """Return whether the mesh carries a recoverable Cloth document."""

    return restore_cloth_source(mesh) is not None


def prepare_cloth_mesh_for_boolean(mesh: Any) -> Any:
    """Return a closed, topology-safe Cloth solid for the generic boolean engine.

    Older outputs are regenerated from their embedded Cloth document instead of
    spatially welding the displayed mesh.  This distinction matters when an
    explicit Cut edge occupies the same folded position as another panel edge:
    coordinate welding would create a four-face non-manifold edge.
    """

    restored = restore_cloth_source(mesh)
    if restored is None:
        return mesh
    document, output_kind = restored
    if output_kind != "folded":
        raise ValueError("Boolean operations must target the 3D Cloth output, not the flat-pattern scene.")
    metadata = dict(getattr(mesh, "metadata", {}) or {})
    if (
        _closed_by_edges(mesh)
        and not bool(metadata.get("cloth_surface_only", False))
        and bool(metadata.get("cloth_boolean_ready", False))
    ):
        return mesh

    from .mesh_builder import build_cloth_surface_mesh
    from .stitching import heal_cloth_stitches

    working = document.clone()
    heal_cloth_stitches(working)
    built = build_cloth_surface_mesh(
        working,
        name=str(getattr(mesh, "name", "Cloth") or "Cloth"),
        solid=True,
    )
    if built.mesh is None or built.issues:
        detail = "; ".join(built.issues) or "unknown Cloth solidification error"
        raise ValueError(detail)
    solid = attach_cloth_source_in_place(built.mesh, document=working, output_kind="folded")
    linked = {
        key: value
        for key, value in metadata.items()
        if key.startswith("cloth_linked_") or key in {"cloth_output_kind"}
    }
    solid.metadata.update(linked)
    solid.metadata.update(
        {
            "cloth_surface_only": False,
            "cloth_boolean_ready": True,
            "cloth_thickness_mm": float(working.metadata.get("cloth_thickness_mm", 0.2)),
            "cloth_stitch_tolerance_mm": float(working.metadata.get("cloth_stitch_tolerance_mm", 0.05)),
        }
    )
    return solid


def attach_boolean_operation_to_cloth_result(
    target: Any,
    cutter: Any,
    result: Any,
    *,
    operation: str,
    margin_mm: float = 0.0,
) -> Any:
    """Preserve Cloth editability and append one flatten-aware modifier."""

    restored = restore_cloth_source(target)
    if restored is None or restored[1] != "folded":
        return result
    document, output_kind = restored
    append_cloth_boolean_modifier(document, cutter, operation=operation, margin_mm=margin_mm)
    metadata = deepcopy(getattr(target, "metadata", {}) or {})
    # Counts and patch ranges describe the pre-boolean generated mesh and would
    # be misleading on the manifold result.  The editable source remains the
    # authority and will regenerate fresh values on the next Apply.
    for key in _STALE_GENERATED_TOPOLOGY_KEYS:
        metadata.pop(key, None)
    metadata.update(
        {
            "cloth_surface_only": False,
            "cloth_boolean_ready": True,
            "cloth_boolean_modified": True,
            "cloth_boolean_last_operation": str(operation),
            "cloth_boolean_modifier_count": len(
                document.metadata.get("cloth_boolean_modifiers", ()) or ()
            ),
        }
    )
    result.metadata = metadata
    return attach_cloth_source_in_place(result, document=document, output_kind=output_kind)


__all__ = [
    "attach_boolean_operation_to_cloth_result",
    "is_editable_cloth_mesh",
    "prepare_cloth_mesh_for_boolean",
]

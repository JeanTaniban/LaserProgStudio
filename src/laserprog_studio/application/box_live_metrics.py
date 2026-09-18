# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


def _mesh_bounds(meshes: list[Any], indices: list[int]) -> tuple[float, float, float] | None:
    vertices: list[tuple[float, float, float]] = []
    try:
        for idx in indices:
            if 0 <= int(idx) < len(meshes):
                vertices.extend(tuple(v) for v in getattr(meshes[int(idx)], "vertices", []) or [])
        if not vertices:
            return None
        xs = [float(v[0]) for v in vertices]
        ys = [float(v[1]) for v in vertices]
        zs = [float(v[2]) for v in vertices]
        return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    except Exception:
        return None


def selected_box_group_inputs(owner: Any) -> tuple[float, float, float, float, str, str, str] | None:
    """Infer current Box metrics inputs from a selected generated box group."""
    try:
        from laserprog_studio.fabrication.box_generator import box_metadata

        meshes = list(owner.current_meshes())
        if not meshes:
            return None
        candidates: list[int] = []
        for idx in list(getattr(owner, "selected_indices", []) or []):
            if 0 <= int(idx) < len(meshes):
                candidates.append(int(idx))
        active = getattr(owner, "active_index", None)
        if active is not None and 0 <= int(active) < len(meshes):
            candidates.append(int(active))
        meta = None
        for idx in candidates:
            meta = box_metadata(meshes[idx])
            if meta is not None:
                break
        if meta is None:
            return None
        group_id = str(meta.get("group_id") or "")
        group_indices = [i for i, mesh in enumerate(meshes) if (box_metadata(mesh) or {}).get("group_id") == group_id]
        dims = _mesh_bounds(meshes, group_indices)
        if dims is None:
            return None
        width, depth, height = dims
        thickness = float(meta.get("thickness_mm") or 0.0)
        if thickness <= 0.0 and hasattr(owner, "box_t"):
            thickness = float(owner.box_t.value())
        return (
            float(width),
            float(depth),
            float(height),
            float(thickness),
            str(meta.get("corner_joint") or "front_back_wrap"),
            str(meta.get("top_front_joint") or "top_bottom_wrap"),
            str(meta.get("top_side_joint") or "top_bottom_wrap"),
        )
    except Exception:
        return None


def make_box_preview_meshes(width: float, depth: float, height: float, thickness: float, corner: str, top_front: str, top_side: str):
    """Build tagged WorkMesh boards and metrics for the Studio Box preview.

    Stable bridge kept for existing controllers. New tools call the
    pure fabrication backend directly.
    """
    from laserprog_studio.fabrication.box_generator import build_box_meshes

    return build_box_meshes(width, depth, height, thickness, corner, top_front, top_side)

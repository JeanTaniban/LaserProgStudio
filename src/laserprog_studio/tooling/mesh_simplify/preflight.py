# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import SimplifyMeshSettings


@dataclass(frozen=True, slots=True)
class SimplifyMeshCheck:
    ok: bool
    message: str
    target_indices: tuple[int, ...] = ()
    before_triangles: int = 0


def triangle_count(mesh: Any) -> int:
    try:
        return int(len(getattr(mesh, "triangles", []) or []))
    except Exception:
        return 0


def validate_simplify_targets(ctx: Any, settings: SimplifyMeshSettings) -> SimplifyMeshCheck:
    try:
        ctx.document.ensure()
        base_meshes = list(ctx.document.meshes(include_preview=False))
    except Exception:
        return SimplifyMeshCheck(False, "Open or create a scene before simplifying meshes.")

    indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    if not indices:
        return SimplifyMeshCheck(False, "Select one or more parts to simplify.")
    valid = tuple(i for i in sorted(set(indices)) if 0 <= i < len(base_meshes))
    if not valid:
        return SimplifyMeshCheck(False, "The simplify selection contains no valid scene object.")
    before = sum(triangle_count(base_meshes[i]) for i in valid)
    if before <= 0:
        return SimplifyMeshCheck(False, "Selected parts contain no triangles to simplify.", target_indices=valid, before_triangles=before)
    if settings.reduction_percent <= 0.0:
        return SimplifyMeshCheck(False, "Reduction must be greater than zero before previewing.", target_indices=valid, before_triangles=before)
    if before <= 4 and settings.reduction_percent > 0.0:
        return SimplifyMeshCheck(True, "Selection is already very light; preview may keep the mesh unchanged.", target_indices=valid, before_triangles=before)
    return SimplifyMeshCheck(
        True,
        f"Ready to simplify {len(valid)} part{'s' if len(valid) != 1 else ''} · {before} triangles.",
        target_indices=valid,
        before_triangles=before,
    )


__all__ = ["SimplifyMeshCheck", "triangle_count", "validate_simplify_targets"]

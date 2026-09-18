# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import RepairMeshSettings


@dataclass(frozen=True, slots=True)
class RepairMeshCheck:
    ok: bool
    message: str
    target_indices: tuple[int, ...] = ()
    skipped_indices: tuple[int, ...] = ()


def is_helper_or_decal(mesh: Any) -> bool:
    return bool(
        getattr(mesh, "is_texture_decal", False)
        or getattr(mesh, "is_scene_helper", False)
        or getattr(mesh, "scene_helper", False)
        or str(getattr(mesh, "role", "")).lower() in {"helper", "gizmo"}
    )


def validate_repair_targets(ctx: Any, settings: RepairMeshSettings) -> RepairMeshCheck:
    try:
        ctx.document.ensure()
        base_meshes = list(ctx.document.meshes(include_preview=False))
    except Exception:
        return RepairMeshCheck(False, "Open or create a scene before repairing meshes.")

    indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    if not indices:
        return RepairMeshCheck(False, "Select one or more parts to repair.")
    valid = tuple(i for i in sorted(set(indices)) if 0 <= i < len(base_meshes))
    if not valid:
        return RepairMeshCheck(False, "The repair selection contains no valid scene object.")
    target = tuple(i for i in valid if not is_helper_or_decal(base_meshes[i]))
    skipped = tuple(i for i in valid if i not in target)
    if not target:
        return RepairMeshCheck(False, "No repairable part selected. Helpers and texture decals are skipped.", skipped_indices=skipped)
    if settings.tolerance_mm <= 0.0:
        return RepairMeshCheck(False, "Tolerance must be greater than zero.", target_indices=target, skipped_indices=skipped)
    message = f"Ready to repair {len(target)} part{'s' if len(target) != 1 else ''}."
    if skipped:
        message += f" Skipping {len(skipped)} helper/decal item{'s' if len(skipped) != 1 else ''}."
    return RepairMeshCheck(True, message, target_indices=target, skipped_indices=skipped)


__all__ = ["RepairMeshCheck", "is_helper_or_decal", "validate_repair_targets"]

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import MaterialPainterSettings


@dataclass(frozen=True, slots=True)
class MaterialApplyCheck:
    ok: bool
    target_indices: tuple[int, ...] = ()
    message: str = "Ready."

    @classmethod
    def failure(cls, message: str) -> "MaterialApplyCheck":
        return cls(False, (), str(message))

    @classmethod
    def success(cls, indices: tuple[int, ...], message: str) -> "MaterialApplyCheck":
        return cls(True, tuple(indices), str(message))


def validate_material_apply(ctx: Any, settings: MaterialPainterSettings) -> MaterialApplyCheck:
    try:
        meshes = tuple(ctx.document.meshes(include_preview=False))
    except Exception:
        meshes = ()
    if not meshes:
        return MaterialApplyCheck.failure("No mesh in the current scene.")
    if settings.target_scope == "all":
        return MaterialApplyCheck.success(tuple(range(len(meshes))), f"Ready to preview {len(meshes)} part(s).")
    try:
        raw = tuple(int(index) for index in ctx.scene_selection.selected_indices())
    except Exception:
        raw = ()
    indices = tuple(index for index in sorted(set(raw)) if 0 <= index < len(meshes))
    if not indices:
        return MaterialApplyCheck.failure("Select at least one part, or switch Target to All parts.")
    return MaterialApplyCheck.success(indices, f"Ready to preview {len(indices)} selected part(s).")

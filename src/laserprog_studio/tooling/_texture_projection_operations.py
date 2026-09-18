# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from laserprog_studio.geometry_ops.texture_projection import apply_texture_projection, clear_texture_projection
from laserprog_studio.tool_api.application import OperationResult

from ._texture_projection_params import texture_params_from_values


def selected_indices(ctx: Any, override: int | str | None = None) -> tuple[int, ...]:
    try:
        if override not in (None, "", -1, "-1"):
            return (int(override),)
    except Exception:
        pass
    return tuple(int(i) for i in ctx.scene_selection.selected_indices())


def texture_project_operation(_inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
    ctx.document.ensure()
    indices = selected_indices(ctx, params.get("target_index"))
    if not indices:
        return OperationResult.failure("Select at least one part to texture.")
    base = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
    valid = tuple(i for i in sorted(set(indices)) if 0 <= i < len(base))
    if not valid:
        return OperationResult.failure("The texture selection contains no valid scene object.")
    params_obj = texture_params_from_values(params, ctx=ctx)
    if not str(params_obj.texture_path).strip():
        return OperationResult.failure("Choose a PNG/JPG texture before previewing.")
    out = tuple(apply_texture_projection(base, list(valid), params_obj))
    face = f"\nTarget face: {params_obj.seed_face_index}" if params_obj.seed_face_index is not None else ""
    report = f"Texture preview ready.\nSelected parts: {len(valid)}\nTexture: {Path(str(params_obj.texture_path)).name}{face}"
    preview_indices = tuple(range(len(base), len(out))) if len(out) > len(base) else ()
    return OperationResult.success(
        out,
        report=report,
        metadata={
            "changed_indices": valid,
            "preview_indices": preview_indices,
            "selected_indices": valid,
            "target_index": int(valid[-1]),
            "texture_path": str(params_obj.texture_path),
            "texture_id": str(params_obj.texture_id),
        },
    )


def texture_clear_operation(_inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:  # noqa: ARG001
    ctx.document.ensure()
    # Clear is a selection operation, not an anchor operation. Do not reuse the
    # hidden target_index from the last face pick or a multi-select clear would
    # silently affect only one object.
    indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    if not indices:
        return OperationResult.failure("Select at least one part to clear.")
    base = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
    valid = tuple(i for i in sorted(set(indices)) if 0 <= i < len(base))
    if not valid:
        return OperationResult.failure("The texture clear selection contains no valid scene object.")
    out = tuple(clear_texture_projection(base, list(valid)))
    return OperationResult.success(out, report=f"Texture clear preview ready.\nSelected parts: {len(valid)}", metadata={"changed_indices": valid, "selected_indices": valid, "target_index": int(valid[-1])})


__all__ = ["selected_indices", "texture_clear_operation", "texture_project_operation"]

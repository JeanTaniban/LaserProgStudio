# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from laserprog_studio.tool_api.visual import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

from .settings import MaterialPainterSettings


def selected_indices_text(indices: Iterable[int]) -> str:
    values = tuple(int(i) for i in indices)
    if not values:
        return "No selection"
    return ", ".join(f"{i:02d}" for i in values)


def build_material_feedback_window(
    *,
    owner_tool: str,
    settings: MaterialPainterSettings,
    selected_indices: tuple[int, ...],
    status: str,
) -> OverlayWindowSpec:
    target = "All parts" if settings.target_scope == "all" else "Selected parts"
    return OverlayWindowSpec(
        id="material.painter.feedback",
        title="Material painter",
        owner_tool=owner_tool,
        overlay_kind="toolbar",
        anchor="viewport_bottom_center",
        width_px=620,
        movable=True,
        persistent=False,
        fields=[
            OverlayFieldSpec("material.feedback.material", "Material", settings.summary, kind="info"),
            OverlayFieldSpec("material.feedback.target", "Target", target, kind="info"),
            OverlayFieldSpec("material.feedback.selection", "Selection", selected_indices_text(selected_indices), kind="info"),
            OverlayFieldSpec("material.feedback.status", "Status", status, kind="info"),
        ],
        buttons=[
            ToolButtonSpec("material_overlay_preview", "Preview", tooltip="Preview current material settings.", style="primary"),
            ToolButtonSpec("material_overlay_apply", "Apply", tooltip="Commit the active material preview.", style="primary"),
            ToolButtonSpec("material_overlay_cancel", "Cancel", tooltip="Discard the material preview.", style="secondary"),
        ],
    )

# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from laserprog_studio.tool_api.visual import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

from .settings import SimplifyMeshSettings

SIMPLIFY_FEEDBACK_WINDOW_ID = "modifier.simplify.feedback"


def selected_indices_text(indices: Iterable[int]) -> str:
    values = tuple(int(i) for i in indices)
    if not values:
        return "No selection"
    return ", ".join(f"{i:02d}" for i in values)


def build_simplify_feedback_window(
    *,
    owner_tool: str,
    settings: SimplifyMeshSettings,
    selected_indices: tuple[int, ...],
    status: str,
) -> OverlayWindowSpec:
    return OverlayWindowSpec(
        id=SIMPLIFY_FEEDBACK_WINDOW_ID,
        title="Simplify",
        owner_tool=owner_tool,
        overlay_kind="toolbar",
        anchor="viewport_bottom_center",
        width_px=660,
        movable=True,
        persistent=False,
        fields=[
            OverlayFieldSpec("modifier.simplify.feedback.preset", "Preset", settings.preset_id.replace("_", " ").title(), kind="info"),
            OverlayFieldSpec("modifier.simplify.feedback.settings", "Settings", settings.summary, kind="info"),
            OverlayFieldSpec("modifier.simplify.feedback.selection", "Selection", selected_indices_text(selected_indices), kind="info"),
            OverlayFieldSpec("modifier.simplify.feedback.status", "Status", status, kind="info"),
        ],
        buttons=[
            ToolButtonSpec("simplify_overlay_preview", "Preview", tooltip="Preview current simplify settings.", style="primary"),
            ToolButtonSpec("simplify_overlay_apply", "Apply", tooltip="Commit the active simplify preview.", style="primary"),
            ToolButtonSpec("simplify_overlay_cancel", "Cancel", tooltip="Discard the simplify preview.", style="secondary"),
        ],
    )


__all__ = ["SIMPLIFY_FEEDBACK_WINDOW_ID", "build_simplify_feedback_window", "selected_indices_text"]

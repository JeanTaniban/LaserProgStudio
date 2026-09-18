# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from laserprog_studio.tool_api.visual import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

from .settings import HollowMeshSettings

HOLLOW_FEEDBACK_WINDOW_ID = "modifier.hollow.feedback"


def selected_indices_text(indices: Iterable[int]) -> str:
    values = tuple(int(i) for i in indices)
    if not values:
        return "No selection"
    return ", ".join(f"{i:02d}" for i in values)


def build_hollow_feedback_window(
    *,
    owner_tool: str,
    settings: HollowMeshSettings,
    selected_indices: tuple[int, ...],
    status: str,
) -> OverlayWindowSpec:
    return OverlayWindowSpec(
        id=HOLLOW_FEEDBACK_WINDOW_ID,
        title="Hollow",
        owner_tool=owner_tool,
        overlay_kind="toolbar",
        anchor="viewport_bottom_center",
        width_px=640,
        movable=True,
        persistent=False,
        fields=[
            OverlayFieldSpec("modifier.hollow.feedback.preset", "Preset", settings.preset_id.replace("_", " ").title(), kind="info"),
            OverlayFieldSpec("modifier.hollow.feedback.settings", "Settings", settings.summary, kind="info"),
            OverlayFieldSpec("modifier.hollow.feedback.selection", "Selection", selected_indices_text(selected_indices), kind="info"),
            OverlayFieldSpec("modifier.hollow.feedback.status", "Status", status, kind="info"),
        ],
        buttons=[
            ToolButtonSpec("hollow_overlay_preview", "Preview", tooltip="Preview current hollow settings.", style="primary"),
            ToolButtonSpec("hollow_overlay_apply", "Apply", tooltip="Commit the active hollow preview.", style="primary"),
            ToolButtonSpec("hollow_overlay_cancel", "Cancel", tooltip="Discard the hollow preview.", style="secondary"),
        ],
    )


__all__ = ["HOLLOW_FEEDBACK_WINDOW_ID", "build_hollow_feedback_window", "selected_indices_text"]

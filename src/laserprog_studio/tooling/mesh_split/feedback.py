# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Iterable

from laserprog_studio.tool_api.visual import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

from .settings import SplitPlaneSettings

SPLIT_FEEDBACK_WINDOW_ID = "modifier.split.feedback"


def selected_indices_text(indices: Iterable[int]) -> str:
    values = tuple(int(i) for i in indices)
    if not values:
        return "No selection"
    return ", ".join(f"{i:02d}" for i in values)


def _format_offset(value: float) -> str:
    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "0"


def build_split_feedback_window(
    *,
    owner_tool: str,
    settings: SplitPlaneSettings,
    selected_indices: tuple[int, ...],
    status: str,
    total_triangles: int = 0,
) -> OverlayWindowSpec:
    metrics = f"Offset {_format_offset(settings.offset_mm)} mm · snap 5° · {max(0, int(total_triangles))} triangles"
    if status:
        metrics = f"{metrics} · {status}"
    return OverlayWindowSpec(
        id=SPLIT_FEEDBACK_WINDOW_ID,
        title="Split",
        owner_tool=owner_tool,
        overlay_kind="toolbar",
        anchor="viewport_bottom_center",
        width_px=560,
        movable=True,
        persistent=False,
        fields=[
            OverlayFieldSpec("modifier.split.feedback.metrics", "", metrics, kind="info"),
        ],
        buttons=[
            ToolButtonSpec("split_overlay_reset", "Recenter", display_label="Center", tooltip="Recenter the split plane on the current selection.", style="secondary", slot_width_px=64),
            ToolButtonSpec("split_overlay_orient_xy", "XY", display_label="XY", tooltip="Snap the split plane to a horizontal XY cut.", style="secondary", slot_width_px=42),
            ToolButtonSpec("split_overlay_orient_yz", "YZ", display_label="YZ", tooltip="Snap the split plane to a vertical YZ cut.", style="secondary", slot_width_px=42),
            ToolButtonSpec("split_overlay_orient_xz", "XZ", display_label="XZ", tooltip="Snap the split plane to a vertical XZ cut.", style="secondary", slot_width_px=42),
            ToolButtonSpec("split_overlay_preview", "Preview", display_label="Preview", tooltip="Preview the current split plane.", style="primary", slot_width_px=72),
            ToolButtonSpec("split_overlay_apply", "Apply", display_label="Apply", tooltip="Commit the active split preview.", style="primary", slot_width_px=62),
            ToolButtonSpec("split_overlay_cancel", "Cancel", display_label="Cancel", tooltip="Discard the split preview.", style="secondary", slot_width_px=62),
        ],
    )


__all__ = ["SPLIT_FEEDBACK_WINDOW_ID", "build_split_feedback_window", "selected_indices_text"]

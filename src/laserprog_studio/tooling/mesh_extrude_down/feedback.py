# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.tool_api.visual import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

from .preflight import selected_indices_text
from .settings import ExtrudeDownSettings

EXTRUDE_DOWN_FEEDBACK_WINDOW_ID = "modifier.extrude_down.feedback"


def _format_mm(value: float) -> str:
    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "0"


def build_extrude_down_feedback_window(
    *,
    owner_tool: str,
    settings: ExtrudeDownSettings,
    selected_indices: tuple[int, ...],
    status: str,
    total_triangles: int = 0,
) -> OverlayWindowSpec:
    metrics = (
        f"Horizontal Z {_format_mm(settings.plane_z)} mm → ground {_format_mm(settings.ground_z)} mm"
        f" · {max(0, int(total_triangles))} triangles"
    )
    if status:
        metrics = f"{metrics} · {status}"
    return OverlayWindowSpec(
        id=EXTRUDE_DOWN_FEEDBACK_WINDOW_ID,
        title="Extrude Down",
        owner_tool=owner_tool,
        overlay_kind="toolbar",
        anchor="viewport_bottom_center",
        width_px=560,
        movable=True,
        persistent=False,
        fields=[
            OverlayFieldSpec("modifier.extrude_down.feedback.metrics", "", metrics, kind="info"),
        ],
        buttons=[
            ToolButtonSpec("extrude_down_overlay_preview", "Preview", display_label="Preview", tooltip="Preview the current downward extrusion.", style="primary", slot_width_px=72),
            ToolButtonSpec("extrude_down_overlay_apply", "Apply", display_label="Apply", tooltip="Preview if needed, commit the extrusion, then close the tool.", style="primary", slot_width_px=62),
            ToolButtonSpec("extrude_down_overlay_cancel", "Cancel", display_label="Cancel", tooltip="Discard the extrusion preview.", style="secondary", slot_width_px=62),
        ],
    )


__all__ = ["EXTRUDE_DOWN_FEEDBACK_WINDOW_ID", "build_extrude_down_feedback_window", "selected_indices_text"]

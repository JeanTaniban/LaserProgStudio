"""Shared visual constants for viewport tools.

The values live in one place so every tool uses the same readable UI scale.
They are pure data and intentionally do not import Qt, PyVista or VTK.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ToolStyle:
    handle_radius_px: int = 13
    handle_selected_radius_px: int = 17
    handle_hover_radius_px: int = 15
    snap_radius_px: int = 18
    grid_major_every: int = 5
    line_width_px: int = 3
    preview_line_width_px: int = 2
    face_alpha: float = 0.22
    button_size_px: int = 40
    icon_size_px: int = 28
    light_render_min_interval_ms: float = 16.0


DEFAULT_STYLE = ToolStyle()

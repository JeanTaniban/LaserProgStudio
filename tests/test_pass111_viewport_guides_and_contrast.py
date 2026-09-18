# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES, GizmoVisualState
from laserprog_studio.ui.floor_grid_model import floor_grid_layers, floor_grid_plan


def _luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_pass111_official_handle_styles_are_not_white_on_white() -> None:
    for style in DEFAULT_POINT_STYLES.values():
        fixed = style.color_for(GizmoVisualState.FIXED)
        grabbable = style.color_for(GizmoVisualState.GRABBABLE)
        ring = style.ring_color
        assert _luminance(fixed[:3]) < 0.55
        assert _luminance(grabbable[:3]) < 0.70
        assert _luminance(ring[:3]) < 0.45
        assert ring[:3] != (1.0, 1.0, 1.0)


def test_pass111_diag_painter_uses_non_white_batched_lines_and_style_guides() -> None:
    source = read_tool_core_diag_scene_runtime_source()

    assert 'color="#263445"' in source
    assert 'style.ring_color[:3]' in source
    assert 'style.cross_color[:3]' in source
    assert 'color="white"' not in source
    assert 'color="black"' not in source


def test_pass111_empty_floor_grid_plan_is_valid_and_visible() -> None:
    plan, layers = floor_grid_layers((-1.0, 1.0, -1.0, 1.0, -1.0, 1.0), requested_step=10.0)

    assert plan["xmin"] < 0.0 < plan["xmax"]
    assert plan["ymin"] < 0.0 < plan["ymax"]
    assert layers["minor"]
    assert layers["major"]
    assert layers["axis_x"]
    assert layers["axis_y"]
    assert layers["origin"]


def test_pass111_startup_initializes_empty_viewport_guides_before_first_mesh() -> None:
    floor_grid_source = Path("src/laserprog_studio/ui/floor_grid.py").read_text(encoding="utf-8")
    startup_source = Path("src/laserprog_studio/ui/status_startup.py").read_text(encoding="utf-8")
    layout_source = Path("src/laserprog_studio/ui/layout_panels.py").read_text(encoding="utf-8")

    assert "def initialize_empty_viewport_guides" in floor_grid_source
    assert 'plotter.set_background("#F3F6FA")' in floor_grid_source
    assert "self._update_floor_grid_actor(render=False)" in floor_grid_source
    assert "self.initialize_empty_viewport_guides(render=False)" in startup_source
    assert 'self.plotter.set_background("#F3F6FA")' in layout_source

def test_pass111_floor_grid_does_not_add_world_origin_axis_text_labels() -> None:
    floor_grid_source = Path("src/laserprog_studio/ui/floor_grid.py").read_text(encoding="utf-8")

    assert "plotter.add_point_labels" not in floor_grid_source
    assert "self.floor_grid_actor = actors" in floor_grid_source


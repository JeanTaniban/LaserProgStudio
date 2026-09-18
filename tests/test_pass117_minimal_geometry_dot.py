# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES, GizmoManager, GizmoVisualState


def test_pass117_minimal_uses_geometry_dot_fallback() -> None:
    style = DEFAULT_POINT_STYLES["minimal"]
    assert style.guide_shape == "none"
    assert style.draw_core is True
    assert style.geometry_dot is True
    manager = GizmoManager()
    manager.set_minimal_dot_radii(normal_px=4, active_px=10)
    assert manager.radius_for_style("minimal", 12, GizmoVisualState.GRABBABLE) == 4
    assert manager.radius_for_style("minimal", 12, GizmoVisualState.HOVER) == 10
    assert style.color_for(GizmoVisualState.GRABBABLE) != style.color_for(GizmoVisualState.HOVER)
    assert style.color_for(GizmoVisualState.HOVER) != style.color_for(GizmoVisualState.GRABBED)


def test_pass117_painter_builds_minimal_dot_discs_not_raw_point_sprites() -> None:
    source = read_tool_core_diag_scene_runtime_source()
    assert "minimal_dot_groups" in source
    assert "dotdisc_" in source
    assert "GL point-size support is limited" in source
    assert "not getattr(style, \"geometry_dot\", False)" in source


def test_pass117_mesh_actor_style_updates_in_place() -> None:
    source = read_tool_core_diag_scene_runtime_source()
    assert "_update_mesh_actor_style" in source
    assert "prop.SetColor" in source
    assert "prop.SetOpacity" in source
    assert "prop.SetLineWidth" in source

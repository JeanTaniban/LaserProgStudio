# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, HandleDemoBuilder
from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES


def test_pass112_new_grab_shapes_are_registered_and_demo_uses_only_s_size() -> None:
    assert {"arrow", "axis", "chevron", "triad"}.issubset(DEFAULT_POINT_STYLES)

    runner = CoreDiagRunner()
    snapshot = HandleDemoBuilder(runner.ctx).build_demo()
    handles = [h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.kind.startswith("demo_")]

    assert snapshot.rows == len(DEFAULT_POINT_STYLES)
    assert {h.base_radius_px for h in handles} == {12}
    assert {h.style_id for h in handles} == set(DEFAULT_POINT_STYLES)


def test_pass112_painter_contains_non_destructive_arrow_axis_shapes() -> None:
    text = read_tool_core_diag_scene_runtime_source()
    for shape in ["arrow", "axis", "chevron", "triad"]:
        assert f'guide_shape == "{shape}"' in text
    assert "arrowhead(" in text
    assert "plotter_pixel_radius_to_world" in text


def test_pass112_panel_exposes_camera_size_mode_switch() -> None:
    text = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    assert "Camera size: end" in text
    assert "set_camera_size_update_mode" in text
    assert "camera_size_mode" in text


def test_pass112_camera_refresh_mode_is_integrated_with_interaction_layer() -> None:
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    interaction = Path("src/laserprog_studio/controllers/interaction_gizmo_refresh.py").read_text(encoding="utf-8")
    mouse = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")

    assert "camera_size_update_mode" in controller
    assert "refresh_camera_sized_guides" in controller
    assert "refresh_camera_size_live_if_enabled" in controller
    assert "refresh_camera_size_after_move" in interaction
    assert "_request_live_gizmo_refresh" in mouse

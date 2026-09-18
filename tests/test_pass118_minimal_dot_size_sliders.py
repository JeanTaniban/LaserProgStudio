# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, HandleDemoBuilder
from laserprog_studio.tool_core.gizmos import GizmoVisualState


def test_pass118_gizmo_manager_exposes_minimal_dot_size_policy() -> None:
    runner = CoreDiagRunner()
    runner.ctx.gizmos.set_minimal_dot_radii(normal_px=4, active_px=11)

    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.GRABBABLE) == 4
    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.FIXED) == 4
    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.HOVER) == 11
    assert runner.ctx.gizmos.radius_for_style("minimal", 12, GizmoVisualState.GRABBED) == 11


def test_pass118_handle_demo_uses_minimal_dot_size_policy_and_updates_existing_handles() -> None:
    runner = CoreDiagRunner()
    runner.ctx.gizmos.set_minimal_dot_radii(normal_px=4, active_px=10)
    demo = HandleDemoBuilder(runner.ctx)
    demo.build_demo()

    minimal = [h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.style_id == "minimal"]
    assert minimal
    assert {h.radius_px for h in minimal} == {4}

    demo.apply_hover("demo:9:grab")
    hovered = next(h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.id == "demo:9:grab")
    assert hovered.radius_px == 10

    before = runner.backend_stats()
    runner.ctx.gizmos.set_minimal_dot_radii(normal_px=6, active_px=13)
    changed = runner.ctx.gizmos.update_style_metrics(owner_tool="tool_core_diag", style_id="minimal", kind_prefix="demo_")
    after = runner.backend_stats()
    hovered = next(h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.id == "demo:9:grab")
    normal = next(h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.style_id == "minimal" and h.id != "demo:9:grab")

    assert changed >= 1
    assert hovered.radius_px == 13
    assert normal.radius_px == 6
    assert after["created"] == before["created"]
    assert after["removed"] == before["removed"]


def test_pass118_ui_panel_has_two_minimal_dot_sliders() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    controller_source = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    painter_source = read_tool_core_diag_scene_runtime_source()

    assert "Minimal dot" in source
    assert "minimal_dot_normal" in source
    assert "minimal_dot_active" in source
    assert "set_minimal_dot_normal_px" in controller_source
    assert "set_minimal_dot_active_px" in controller_source
    assert "max(8.0" not in painter_source
    assert "diagnostic sliders drive handle.radius_px directly" in painter_source

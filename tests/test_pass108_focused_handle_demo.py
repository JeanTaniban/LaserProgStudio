# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, HandleDemoBuilder
from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES


def test_pass108_handle_demo_builds_required_primitives_and_sizes() -> None:
    runner = CoreDiagRunner()
    demo = HandleDemoBuilder(runner.ctx)

    snapshot = demo.build_demo()
    handles = [h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.kind.startswith("demo_")]
    radii = sorted({h.radius_px for h in handles if h.kind.startswith("demo_grab")})
    preview_ids = {p.id for p in runner.ctx.preview.items(owner_tool="tool_core_diag")}

    assert snapshot.rows == len(DEFAULT_POINT_STYLES)
    assert snapshot.fixed_handles == len(DEFAULT_POINT_STYLES) * 4
    assert snapshot.grabbable_handles == len(DEFAULT_POINT_STYLES) * 4
    assert 12 in radii
    assert 2 in radii  # minimal dot fixed normal value from Pass119
    assert "demo:0:standalone_line" in preview_ids
    assert "demo:0:line_fixed" in preview_ids
    assert "demo:0:line_grab" in preview_ids
    assert "demo:0:circle" in preview_ids


def test_pass108_handle_demo_has_hover_and_grabbed_states() -> None:
    runner = CoreDiagRunner()
    demo = HandleDemoBuilder(runner.ctx)
    demo.build_demo()

    hover = demo.apply_hover("demo:2:grab")
    assert hover.hover_handles == 1
    assert hover.grabbed_handles == 0

    grabbed = demo.apply_grabbed("demo:2:line_grab:a")
    assert grabbed.grabbed_handles == 1
    assert grabbed.hover_handles == 0


def test_pass108_handle_demo_moves_grabbable_line_endpoint_without_recreating_handles() -> None:
    runner = CoreDiagRunner()
    demo = HandleDemoBuilder(runner.ctx)
    demo.build_demo()
    stats_before = runner.backend_stats()

    assert demo.move_handle("demo:1:line_grab:a", (90.0, 20.0, 0.35))
    stats_after = runner.backend_stats()
    handles = {h.id: h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag")}
    line = next(p for p in runner.ctx.preview.items(owner_tool="tool_core_diag") if p.id == "demo:1:line_grab")

    assert handles["demo:1:line_grab:a"].position == (90.0, 20.0, 0.35)
    assert line.points[0] == (90.0, 20.0, 0.35)
    assert stats_after["created"] == stats_before["created"]
    assert stats_after["position_updates"] == stats_before["position_updates"] + 1


def test_pass108_live_scene_painter_draws_grabbable_guides_and_groups_by_style() -> None:
    source = read_tool_core_diag_scene_runtime_source()

    assert "grab_rings" in source
    assert "grab_crosses" in source
    assert "guide_shape == \"arrow\"" in source
    assert "handle.radius_px" in source
    assert "demo_grab" in source


def test_pass108_event_filter_routes_tool_core_diag_handle_events() -> None:
    source = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")

    assert "handle_pointer_press" in source
    assert "handle_pointer_move" in source
    assert "handle_pointer_release" in source
    assert "TOOL_CORE_DIAGNOSTIC" in source

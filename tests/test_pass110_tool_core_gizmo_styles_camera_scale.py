# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from math import isclose
from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, HandleDemoBuilder
from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES, GizmoVisualState, pixel_radius_to_world, world_units_per_pixel


class _ParallelCamera:
    def GetParallelProjection(self):
        return True

    def GetParallelScale(self):
        return 50.0


class _PerspectiveCamera:
    def GetParallelProjection(self):
        return False

    def GetPosition(self):
        return (0.0, 0.0, 100.0)

    def GetViewAngle(self):
        return 30.0


def test_pass110_five_official_point_styles_are_available() -> None:
    assert {"solid", "ring", "target", "diamond", "square"}.issubset(set(DEFAULT_POINT_STYLES))
    for style in DEFAULT_POINT_STYLES.values():
        assert style.radius_for(12, GizmoVisualState.HOVER) > 12
        assert style.radius_for(12, GizmoVisualState.GRABBED) > style.radius_for(12, GizmoVisualState.HOVER)
        assert len(style.color_for(GizmoVisualState.GRABBABLE)) == 4


def test_pass110_handle_demo_uses_five_styles_without_changing_core_counts() -> None:
    runner = CoreDiagRunner()
    demo = HandleDemoBuilder(runner.ctx)
    snapshot = demo.build_demo()
    handles = [h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.kind.startswith("demo_")]

    assert snapshot.fixed_handles == len(DEFAULT_POINT_STYLES) * 4
    assert snapshot.grabbable_handles == len(DEFAULT_POINT_STYLES) * 4
    assert {h.style_id for h in handles} == set(DEFAULT_POINT_STYLES)
    assert {h.base_radius_px for h in handles} == {12}
    assert all(h.base_radius_px is not None for h in handles)


def test_pass110_interaction_state_is_centralized_and_non_destructive() -> None:
    runner = CoreDiagRunner()
    demo = HandleDemoBuilder(runner.ctx)
    demo.build_demo()
    before = runner.backend_stats()

    changed = runner.ctx.gizmos.update_interaction_state(
        "tool_core_diag",
        hover_id="demo:2:grab",
        grabbed_id=None,
        kind_prefix="demo_",
    )
    after_hover = runner.backend_stats()
    changed_2 = runner.ctx.gizmos.update_interaction_state(
        "tool_core_diag",
        hover_id=None,
        grabbed_id="demo:2:grab",
        kind_prefix="demo_",
    )
    after_grab = runner.backend_stats()
    handle = next(h for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.id == "demo:2:grab")

    assert changed >= 1
    assert changed_2 >= 1
    assert after_hover["created"] == before["created"]
    assert after_grab["created"] == before["created"]
    assert after_grab["removed"] == before["removed"]
    assert handle.grabbed is True
    assert handle.radius_px > int(handle.base_radius_px or 0)


def test_pass110_camera_scale_matches_parallel_and_perspective_basics() -> None:
    units, mode = world_units_per_pixel(_ParallelCamera(), 1000, (0.0, 0.0, 0.0))
    assert mode == "parallel"
    assert isclose(units, 0.1, rel_tol=1e-6)

    result = pixel_radius_to_world(_PerspectiveCamera(), None, (0.0, 0.0, 0.0), 10.0)
    assert result.mode == "perspective"
    assert result.world_radius > 0.0
    assert isclose(result.world_radius, result.world_units_per_pixel * 10.0, rel_tol=1e-6)


def test_pass110_painter_uses_dynamic_camera_scale_and_stable_actor_names() -> None:
    source = read_tool_core_diag_scene_runtime_source()

    assert "plotter_pixel_radius_to_world" in source
    assert "handles_{safe_style}_{safe_state}_{size}" in source
    assert "visual_state_for_flags" in source
    assert "clear/rebuild during interaction" in source

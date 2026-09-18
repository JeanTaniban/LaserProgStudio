# -*- coding: utf-8 -*-
from __future__ import annotations
from _tool_core_diag_scene_sources import read_tool_core_diag_scene_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, HandleDemoBuilder
from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES, all_recommended_point_styles, recommendations_for_tool
from laserprog_studio.tool_core.overlay import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec


def test_pass113_target_is_crosshair_only_and_new_styles_are_registered() -> None:
    assert DEFAULT_POINT_STYLES["target"].guide_shape == "target"
    assert "minimal" in DEFAULT_POINT_STYLES
    assert "translate_arrow" in DEFAULT_POINT_STYLES
    assert DEFAULT_POINT_STYLES["translate_arrow"].guide_shape == "translate_axis"

    source = read_tool_core_diag_scene_runtime_source()
    assert 'if guide_shape == "ring"' in source
    assert 'if guide_shape in {"ring", "target"}' not in source
    assert 'if guide_shape == "target"' in source
    assert 'guide_shape == "minimal"' in source
    assert 'guide_shape == "translate_axis"' in source


def test_pass113_handle_demo_uses_new_styles_and_declares_overlay_window() -> None:
    runner = CoreDiagRunner()
    snapshot = HandleDemoBuilder(runner.ctx).build_demo()

    style_ids = {h.style_id for h in runner.ctx.gizmos.handles(owner_tool="tool_core_diag") if h.kind.startswith("demo_")}
    assert {"minimal", "translate_arrow", "target"}.issubset(style_ids)
    assert snapshot.rows == len(DEFAULT_POINT_STYLES)

    window = runner.ctx.overlay.window("diag.handle_demo.window")
    assert window is not None
    assert window.close_on_click_outside is True
    assert any(field.kind == "info" for field in window.fields)


def test_pass113_overlay_windows_support_clickaway_and_fields() -> None:
    runner = CoreDiagRunner()
    overlay = runner.ctx.overlay
    overlay.show_window(
        OverlayWindowSpec(
            id="test.window",
            title="Test",
            owner_tool="tool_core_diag",
            fields=[OverlayFieldSpec("test.window.value", "Value", "1")],
            buttons=[ToolButtonSpec("test.window.ok", "OK")],
            close_on_click_outside=True,
        )
    )
    assert overlay.update_field("test.window", "test.window.value", "2") is True
    assert overlay.window("test.window").fields[0].value == "2"  # type: ignore[union-attr]
    assert overlay.handle_click_outside(owner_tool="tool_core_diag") == 1
    assert overlay.window("test.window").visible is False  # type: ignore[union-attr]


def test_pass113_gizmo_catalog_recommends_styles_for_existing_tools() -> None:
    plan = recommendations_for_tool("plan_tracer")
    translate = recommendations_for_tool("transform_translate")
    extrude = recommendations_for_tool("extrude")

    assert plan is not None and "minimal" in plan.point_styles and "target" in plan.point_styles
    assert translate is not None and "translate_arrow" in translate.point_styles
    assert extrude is not None and "translate_arrow" in extrude.point_styles
    assert set(all_recommended_point_styles()).issubset(DEFAULT_POINT_STYLES)

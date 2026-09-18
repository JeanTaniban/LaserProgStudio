# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tool_core.gizmos import GizmoManager
from laserprog_studio.tool_core.transform_gizmos import TransformGizmoManager


def test_pass1015_generic_creator_gizmo_contract_is_unchanged() -> None:
    ctx = ToolContext()
    manip = ctx.gizmos.translate(
        id="plan_trace.offset",
        owner_tool="plan_trace",
        origin=(10.0, 20.0, 30.0),
        axes=("x", "y"),
        radius_px=14,
    )

    assert isinstance(ctx.gizmos, GizmoManager)
    assert ctx.gizmos.handle("plan_trace.offset:x", owner_tool="plan_trace").position == (11.0, 20.0, 30.0)
    assert ctx.gizmos.handle("plan_trace.offset:y", owner_tool="plan_trace").position == (10.0, 21.0, 30.0)
    assert ctx.gizmos.handle("plan_trace.offset:center", owner_tool="plan_trace").selectable is True
    assert manip.metadata is None


def test_pass1015_transform_gizmos_have_a_separate_api_section() -> None:
    ctx = ToolContext()
    assert isinstance(ctx.transform_gizmos, TransformGizmoManager)
    assert ctx.transform_gizmos is not ctx.gizmos

    ctx.transform_gizmos.translate(
        id="app.transform.translate",
        owner_tool="app_transform_gizmo",
        origin=(10.0, 20.0, 30.0),
        axes=("x",),
        axis_vectors={"x": (0.0, 1.0, 0.0)},
        axis_length=5.0,
        include_center=False,
    )

    assert ctx.transform_gizmos.handle("app.transform.translate:x", owner_tool="app_transform_gizmo").position == (10.0, 25.0, 30.0)
    assert ctx.gizmos.handle("app.transform.translate:x", owner_tool="app_transform_gizmo") is None


def test_pass1015_generic_painter_keeps_the_historical_creator_contract() -> None:
    source = Path("src/laserprog_studio/application/_tool_core_diag_scene_painter.py").read_text(encoding="utf-8")
    assert "context_signature" not in source
    assert "_force_overlay_actor_foreground" not in source
    assert "TransformGizmo" not in source
    assert "ctx.transform_gizmos" not in source


def test_pass1015_transform_api_uses_only_transform_manager() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_api.py").read_text(encoding="utf-8")
    assert "ctx.transform_gizmos" in source
    assert "ctx.gizmos" not in source


def test_pass1015_translate_renderer_has_no_large_terminal_points() -> None:
    source = Path("src/laserprog_studio/application/transform_gizmo_renderer.py").read_text(encoding="utf-8")
    block = source[source.index("def _build_translate"):source.index("def _build_rotate")]
    assert "_point_mesh([tip])" not in block
    assert "arrowhead strokes" in block

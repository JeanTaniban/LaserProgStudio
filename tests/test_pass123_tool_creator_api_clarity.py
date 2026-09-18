# -*- coding: utf-8 -*-
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from laserprog_studio.tool_api import ToolContext, actors, inspector, snap
from laserprog_studio.tool_core.diagnostic.runner import CoreDiagRunner
from laserprog_studio.tool_core.snap import SnapSource


def _load(path: str):
    file_path = Path(path)
    spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_pass123_inspector_lowercase_dsl_accepts_lists_and_rejects_duplicate_ids() -> None:
    panel = inspector.panel(
        "Creator Friendly",
        id="creator.demo",
        sections=[
            inspector.section(
                "Geometry",
                [
                    inspector.float_field("length", "Length", default=25.0, min_value=1.0, unit="mm"),
                    inspector.bool_field("closed", "Closed", default=True),
                ],
            )
        ],
    )

    ctx = ToolContext()
    ctx.inspector.set_panel(panel)
    assert ctx.inspector.values() == {"length": 25.0, "closed": True}
    assert ctx.inspector.describe()["fields"] == ["length", "closed"]

    with pytest.raises(ValueError, match="duplicate field ids"):
        inspector.panel(
            "Broken",
            sections=[inspector.section("Bad", [inspector.text_field("name", "Name"), inspector.text_field("name", "Name 2")])],
        )


def test_pass123_scene_cache_summary_and_smart_snap_exclude_moved_actor() -> None:
    ctx = ToolContext()
    ctx.selection.register_actor(actors.point("keep", (0.0, 0.0, 0.0), interaction="grabbable"))
    ctx.selection.register_actor(actors.point("moving", (5.0, 0.0, 0.0), interaction="grabbable"))

    result = ctx.snap.smart((5.0, 0.0, 0.0), (5.0, 0.0), ctx, exclude_ids=("moving",))
    summary = ctx.scene_cache.summary()

    assert summary.valid
    assert summary.points == 2
    assert result.snapped is False or result.source_id != "moving"
    assert {point.id for point in ctx.scene_cache.points()} == {"keep", "moving"}


def test_pass123_ui_snap_target_can_be_screen_only_or_world_backed() -> None:
    ctx = ToolContext()

    screen_only = ctx.snap.smart(
        (42.0, 10.0, 0.0),
        (100.0, 120.0),
        ctx,
        extra_targets=[snap.ui_point("ui.crosshair", (100.0, 120.0), priority=1)],
    )
    assert screen_only.snapped
    assert screen_only.source == SnapSource.UI_POINT
    assert screen_only.source_id == "ui.crosshair"
    assert screen_only.position == (42.0, 10.0, 0.0)

    world_backed = ctx.snap.smart(
        (0.0, 0.0, 0.0),
        (200.0, 220.0),
        ctx,
        extra_targets=[snap.ui_point("ui.handle", (200.0, 220.0), world_pos=(9.0, 9.0, 0.0), priority=1)],
    )
    assert world_backed.position == (9.0, 9.0, 0.0)


def test_pass123_complete_creator_api_example_uses_public_blocks() -> None:
    ctx = ToolContext()
    tool = _load("examples/tool_creator/creator_api_demo_tool.py").create_tool()
    tool.on_open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.title == "Creator API Demo"
    assert {actor.id for actor in ctx.selection.actors(owner_tool=tool.id)} == {
        "creator_demo.origin",
        "creator_demo.a",
        "creator_demo.b",
        "creator_demo.edge",
    }

    result = tool.snap_cursor(ctx, (40.0, 10.0, 0.0), (40.0, 10.0))
    assert result.snapped
    assert result.source_id in {"creator_demo.midpoint", "creator_demo.overlay_crosshair"}

    tool.apply(ctx)
    assert ctx.commands.undo_count == 1
    assert tool.applied == ["apply"]
    ctx.commands.undo()
    assert tool.applied == []


def test_pass123_tool_core_diagnostic_has_creator_api_demo() -> None:
    runner = CoreDiagRunner()
    snapshot = runner.run_creator_api_demo()

    assert snapshot.previews >= 1
    assert snapshot.commands_done >= 1
    assert runner.ctx.inspector.panel is not None
    assert runner.ctx.inspector.panel.title == "Creator API Demo"
    assert any("Creator API demo" in entry for entry in runner.log)

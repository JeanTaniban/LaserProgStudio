# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from laserprog_studio.tool_api import CreatorTool, ToolContext, actors, interaction, inspector, snap
from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_core.snap import SnapSource


def _screen(point):
    return (float(point[0]), float(point[1]))


def test_pass124_actor_snap_sources_are_not_ui_sources() -> None:
    ctx = ToolContext()
    ctx.selection.register_actor(actors.point("p1", (0.0, 0.0, 0.0), interaction="grabbable"))
    ctx.selection.register_actor(actors.line("edge", (10.0, 0.0, 0.0), (20.0, 0.0, 0.0), interaction="selectable"))
    ctx.scene_cache.rebuild(ctx, scope="snap")

    sources = {target.id: target.source for target in ctx.scene_cache.snap_targets()}
    assert sources["p1"] == SnapSource.TOOL_ACTOR_POINT
    assert sources["edge:0"] == SnapSource.TOOL_ACTOR_EDGE

    result = ctx.snap.smart((0.0, 0.0, 0.0), (0.0, 0.0), ctx)
    assert result.snapped
    assert result.source == SnapSource.TOOL_ACTOR_POINT
    assert result.source != SnapSource.UI_POINT


def test_pass124_exclude_ids_filter_without_cache_rebuild() -> None:
    ctx = ToolContext()
    ctx.selection.register_actor(actors.point("keep", (0.0, 0.0, 0.0), interaction="grabbable"))
    ctx.selection.register_actor(actors.point("moving", (5.0, 0.0, 0.0), interaction="grabbable"))
    ctx.scene_cache.rebuild(ctx, scope="snap")
    version_before = ctx.scene_cache.version

    result = ctx.snap.smart((5.0, 0.0, 0.0), (5.0, 0.0), ctx, exclude_ids=("moving",))

    assert ctx.scene_cache.version == version_before
    assert {point.id for point in ctx.scene_cache.points()} == {"keep", "moving"}
    assert result.snapped is False or result.source_id != "moving"


def test_pass124_tool_temp_targets_survive_rebuild_and_can_be_cleared_by_owner() -> None:
    ctx = ToolContext()
    ctx.scene_cache.add_point("guide.p", (9.0, 0.0, 0.0), owner_tool="tool.a")
    ctx.scene_cache.add_segment("guide.s", (0.0, 5.0, 0.0), (10.0, 5.0, 0.0), owner_tool="tool.a")
    ctx.scene_cache.add_snap_target(snap.ui_point("guide.ui", (20.0, 20.0)), owner_tool="tool.a")

    ctx.scene_cache.rebuild(ctx, scope="snap")
    summary = ctx.scene_cache.summary()
    assert summary.tool_points == 1
    assert summary.tool_segments == 1
    assert summary.ui_targets == 1

    result = ctx.snap.smart((9.0, 0.0, 0.0), (9.0, 0.0), ctx)
    assert result.snapped
    assert result.source == SnapSource.TOOL_TEMP_POINT
    assert result.source_id == "guide.p"

    ctx.scene_cache.rebuild(ctx, scope="snap")
    assert "guide.p" in {point.id for point in ctx.scene_cache.points()}

    ctx.scene_cache.clear_tool_targets("tool.a")
    assert "guide.p" not in {point.id for point in ctx.scene_cache.points()}
    assert "guide.s" not in {segment.id for segment in ctx.scene_cache.segments()}
    assert all(target.id != "guide.ui" for target in ctx.scene_cache.snap_targets())


def test_pass124_creator_tool_close_runs_cleanup() -> None:
    class DemoTool(CreatorTool):
        id = "demo.cleanup"

        def on_open(self, ctx: ToolContext) -> None:
            ctx.inspector.set_panel(inspector.panel("Cleanup", id=self.id, owner_tool=self.id))
            ctx.selection.register_actor(actors.point("cleanup.p", (0, 0, 0), owner_tool=self.id))
            ctx.preview.show_line("cleanup.preview", self.id, (0, 0, 0), (1, 0, 0))
            ctx.scene_cache.add_point("cleanup.snap", (2, 0, 0), owner_tool=self.id)

    ctx = ToolContext()
    tool = DemoTool()
    tool.open(ctx)
    assert ctx.inspector.panel is not None
    assert ctx.selection.actors(owner_tool=tool.id)
    assert ctx.preview.items(owner_tool=tool.id)
    assert ctx.scene_cache.summary().tool_points == 1

    tool.close(ctx)

    assert ctx.inspector.panel is None
    assert not ctx.selection.actors(owner_tool=tool.id)
    assert not ctx.preview.items(owner_tool=tool.id)
    assert ctx.scene_cache.summary().tool_points == 0


def test_pass124_actor_factories_reject_ambiguous_geometry() -> None:
    with pytest.raises(ValueError, match="circle.*radius is zero"):
        actors.circle("bad.circle", (0, 0, 0), (0, 0, 0))
    with pytest.raises(ValueError, match="arc.*Expected at least 3"):
        actors.arc("bad.arc", [(0, 0, 0), (1, 0, 0)])
    with pytest.raises(ValueError, match="polyline.*Expected at least 2"):
        actors.polyline("bad.poly", [(0, 0, 0)])


def test_pass124_commands_do_and_transaction_are_creator_friendly() -> None:
    ctx = ToolContext()
    state: list[str] = []

    with ctx.commands.transaction("two edits"):
        ctx.commands.do("add a", do=lambda: state.append("a"), undo=lambda: state.remove("a"))
        ctx.commands.do("add b", do=lambda: state.append("b"), undo=lambda: state.remove("b"))

    assert state == ["a", "b"]
    assert ctx.commands.undo_count == 1
    ctx.commands.undo()
    assert state == []
    ctx.commands.redo()
    assert state == ["a", "b"]


def test_pass124_default_actor_interaction_helper_selects_and_moves() -> None:
    ctx = ToolContext()
    ctx.selection.register_actor(actors.point("handle", (0.0, 0.0, 0.0), interaction="grabbable", owner_tool="tool.move"))

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), world_pos=(0.0, 0.0, 0.0), button=MouseButton.LEFT)
    move = ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(10.0, 0.0), world_pos=(10.0, 0.0, 0.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(10.0, 0.0), world_pos=(10.0, 0.0, 0.0), button=MouseButton.LEFT)

    assert interaction.select_or_grab(press, ctx, owner_tool="tool.move", world_to_screen=_screen)
    assert ctx.selection.ids() == ("handle",)
    assert interaction.select_or_grab(move, ctx, owner_tool="tool.move", world_to_screen=_screen)
    assert ctx.selection.actor("handle").points[0] == (10.0, 0.0, 0.0)
    assert interaction.select_or_grab(release, ctx, owner_tool="tool.move", world_to_screen=_screen)

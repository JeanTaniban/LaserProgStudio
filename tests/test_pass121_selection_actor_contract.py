# -*- coding: utf-8 -*-
from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core import ActorInteraction, ActorKind, ToolActor, ToolContext
from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, SelectionDemoBuilder


def _screen(point):
    return (float(point[0]), float(point[1]))


def test_pass121_selection_manager_actor_contract_and_shift_additive() -> None:
    ctx = ToolContext()
    ctx.selection.register_actor(ToolActor("fixed", ActorKind.POINT, "demo", ((0.0, 0.0, 0.0),), ActorInteraction.FIXED, hit_radius_px=8))
    ctx.selection.register_actor(ToolActor("point", ActorKind.POINT, "demo", ((20.0, 0.0, 0.0),), ActorInteraction.SELECTABLE, hit_radius_px=8))
    ctx.selection.register_actor(ToolActor("line", ActorKind.LINE, "demo", ((0.0, 20.0, 0.0), (30.0, 20.0, 0.0)), ActorInteraction.GRABBABLE, hit_radius_px=6))

    assert ctx.selection.select_at((0.0, 0.0), _screen, owner_tool="demo") is None
    assert ctx.selection.ids() == ()

    point_hit = ctx.selection.select_at((20.0, 1.0), _screen, owner_tool="demo")
    assert point_hit is not None and point_hit.actor_id == "point"
    assert ctx.selection.ids() == ("point",)

    line_hit = ctx.selection.select_at((12.0, 23.0), _screen, owner_tool="demo", additive=True)
    assert line_hit is not None and line_hit.actor_id == "line"
    assert ctx.selection.ids() == ("point", "line")

    assert ctx.selection.begin_grab("point", (20.0, 1.0)) == ()
    assert ctx.selection.begin_grab("line", (12.0, 23.0)) == ("line",)
    assert ctx.selection.move_selected((3.0, 4.0, 0.0)) == 1
    assert ctx.selection.actor("line").points == ((3.0, 24.0, 0.0), (33.0, 24.0, 0.0))
    assert ctx.selection.actor("point").points == ((20.0, 0.0, 0.0),)


def test_pass121_selection_demo_is_exposed_and_uses_tool_actor_contract() -> None:
    runner = CoreDiagRunner()
    snapshot = runner.run_selection_demo()
    actors = runner.ctx.selection.actors(owner_tool="tool_core_diag")
    kinds = {actor.kind for actor in actors}
    interactions = {actor.interaction_mode for actor in actors}

    assert snapshot.selected == 0
    assert len(actors) >= 5
    assert ActorKind.POINT in kinds
    assert ActorKind.LINE in kinds
    assert ActorInteraction.FIXED in interactions
    assert ActorInteraction.SELECTABLE in interactions
    assert ActorInteraction.GRABBABLE in interactions

    builder = SelectionDemoBuilder(runner.ctx)
    assert builder.select_at((36.0, 0.0), _screen) == "selection_demo:point_grabbable"
    assert runner.ctx.selection.begin_grab("selection_demo:point_grabbable", (36.0, 0.0)) == ("selection_demo:point_grabbable",)


def test_pass121_ui_and_overlay_drag_corner_guard_are_present() -> None:
    panel = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    adapter = read_qt_overlay_runtime_source()

    assert "API Lab" in panel
    assert "api_lab_add_actor" in panel
    assert "clamped-anchor-reset" in adapter
    assert "press outside visible overlay frame" in adapter
    assert "_press_hits_visible_frame" in adapter

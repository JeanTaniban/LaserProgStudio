# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.gizmos import build_creator_ui_motifs, refresh_creator_ui_interaction
from laserprog_studio.tool_api.interaction import hover_select_grab_actors
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool


def _event(event_type, screen, world, *, button=MouseButton.LEFT):
    return ToolEvent(event_type, screen_pos=screen, world_pos=world, button=button)


def test_grabbable_tool_core_handles_are_real_creator_actors_and_drag_fast() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass175", families=("point_styles",))
    actor_id = "test.pass175:point_styles:solid:grab"
    actor = ctx.selection.actor(actor_id)
    assert actor is not None
    assert actor.grabbable
    assert actor.points[0] == (17.0, 72.0, 0.35)

    refreshes = 0

    def refresh() -> None:
        nonlocal refreshes
        refreshes += 1
        refresh_creator_ui_interaction(ctx, owner_tool="test.pass175")

    assert hover_select_grab_actors(_event(ToolEventType.MOUSE_PRESS, (17.0, 72.0), (17.0, 72.0, 0.35)), ctx, owner_tool="test.pass175", refresh_visuals=refresh).handled
    result = hover_select_grab_actors(_event(ToolEventType.MOUSE_MOVE, (22.0, 76.0), (22.0, 76.0, 0.35)), ctx, owner_tool="test.pass175", refresh_visuals=refresh)
    assert result.handled and result.moved == 1
    assert hover_select_grab_actors(_event(ToolEventType.MOUSE_RELEASE, (22.0, 76.0), (22.0, 76.0, 0.35)), ctx, owner_tool="test.pass175", refresh_visuals=refresh).handled

    assert ctx.selection.actor(actor_id).points[0] == (22.0, 76.0, 0.35)
    assert next(handle for handle in ctx.gizmos.handles(owner_tool="test.pass175") if handle.id == actor_id).position == (22.0, 76.0, 0.35)
    assert refreshes >= 3
    # The drag path must not call the destructive full motif rebuild.
    assert ctx.overlay.windows == {}


def test_grabbable_line_actor_moves_as_actor_not_only_point_handles() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass175.line", families=("actor_kinds",))
    actor_id = "test.pass175.line:actor_kinds:line_grabbable"
    actor = ctx.selection.actor(actor_id)
    assert actor is not None and actor.grabbable
    assert actor.points == ((45.0, 0.0, 0.42), (63.0, 7.0, 0.42))

    def refresh() -> None:
        refresh_creator_ui_interaction(ctx, owner_tool="test.pass175.line")

    assert hover_select_grab_actors(_event(ToolEventType.MOUSE_PRESS, (45.0, 0.0), (45.0, 0.0, 0.42)), ctx, owner_tool="test.pass175.line", refresh_visuals=refresh).handled
    result = hover_select_grab_actors(_event(ToolEventType.MOUSE_MOVE, (50.0, 5.0), (50.0, 5.0, 0.42)), ctx, owner_tool="test.pass175.line", refresh_visuals=refresh)
    assert result.handled and result.moved == 1
    moved_actor = ctx.selection.actor(actor_id)
    assert moved_actor.points == ((50.0, 5.0, 0.42), (68.0, 12.0, 0.42))
    preview = next(item for item in ctx.preview.items(owner_tool="test.pass175.line") if item.id == "test.pass175.line:actor_kinds:preview:line_grabbable")
    assert preview.points == moved_actor.points


def test_empty_click_clears_selection_but_empty_camera_drag_does_not() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass175.clear", families=("actor_kinds",))
    point_id = "test.pass175.clear:actor_kinds:point"

    def refresh() -> None:
        refresh_creator_ui_interaction(ctx, owner_tool="test.pass175.clear")

    assert hover_select_grab_actors(_event(ToolEventType.MOUSE_PRESS, (-28.0, 0.0), (-28.0, 0.0, 0.42)), ctx, owner_tool="test.pass175.clear", refresh_visuals=refresh).handled
    hover_select_grab_actors(_event(ToolEventType.MOUSE_RELEASE, (-28.0, 0.0), (-28.0, 0.0, 0.42)), ctx, owner_tool="test.pass175.clear", refresh_visuals=refresh)
    assert ctx.selection.is_selected(point_id)

    miss_press = hover_select_grab_actors(_event(ToolEventType.MOUSE_PRESS, (400.0, 400.0), (400.0, 400.0, 0.42)), ctx, owner_tool="test.pass175.clear", refresh_visuals=refresh)
    assert not miss_press.handled
    assert ctx.selection.is_selected(point_id)
    miss_release = hover_select_grab_actors(_event(ToolEventType.MOUSE_RELEASE, (430.0, 430.0), (430.0, 430.0, 0.42)), ctx, owner_tool="test.pass175.clear", refresh_visuals=refresh)
    assert not miss_release.selection_cleared
    assert ctx.selection.is_selected(point_id)

    hover_select_grab_actors(_event(ToolEventType.MOUSE_PRESS, (400.0, 400.0), (400.0, 400.0, 0.42)), ctx, owner_tool="test.pass175.clear", refresh_visuals=refresh)
    cleared = hover_select_grab_actors(_event(ToolEventType.MOUSE_RELEASE, (402.0, 402.0), (402.0, 402.0, 0.42)), ctx, owner_tool="test.pass175.clear", refresh_visuals=refresh)
    assert cleared.selection_cleared
    assert not ctx.selection.is_selected(point_id)



def test_catalog_uses_native_actor_interaction_without_private_refresh_calls() -> None:
    catalog_source = Path("src/laserprog_studio/tooling/gizmo_catalog_tool.py").read_text(encoding="utf-8")
    assert "refresh_creator_ui_motifs" not in catalog_source
    assert "refresh_creator_ui_interaction" not in catalog_source
    assert "refresh_creator_ui_drag" not in catalog_source
    assert "resolve_drag_positions" in catalog_source
    assert "on_native_interaction_result" in catalog_source

    runtime_source = Path("src/laserprog_studio/tooling/creator_runtime.py").read_text(encoding="utf-8")
    assert "handle_native_creator_ui_event" in runtime_source

    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)
    actors = ctx.selection.actors(owner_tool=tool.id)
    snapshot = ctx.projected_drawing.snapshot(tool.id)
    assert len(actors) == len(snapshot.primitives)
    assert any(actor.grabbable for actor in actors)
    assert (len(snapshot.points), len(snapshot.lines), len(snapshot.faces), len(snapshot.handles)) == (1, 2, 1, 3)

def test_docs_state_native_interaction_clear_and_performance_policy() -> None:
    texts = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "docs/tool_creator/00_creator_ui_direction.md",
            "docs/tool_creator/06_overlay_preview_gizmos.md",
            "docs/tool_creator/16_gizmo_catalog_tool.md",
        )
    )
    assert "refresh_creator_ui_interaction" in texts
    assert "empty click" in texts.lower()
    assert "persistent" in texts.lower()

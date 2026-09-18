# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.gizmos import build_creator_ui_motifs, refresh_creator_ui_interaction
from laserprog_studio.tool_api.interaction import hover_select_grab_actors
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool


def _event(event_type, screen, world, *, button=MouseButton.LEFT):
    return ToolEvent(event_type, screen_pos=screen, world_pos=world, button=button)



def test_projected_catalog_visibility_is_reversible_and_disables_hit_targets() -> None:
    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)
    before = ctx.projected_drawing.snapshot(tool.id)
    assert before.primitives
    actors_before = ctx.selection.actors(owner_tool=tool.id)
    assert len(actors_before) == len(before.primitives)

    tool._set_visible(ctx, False)
    hidden = ctx.projected_drawing.snapshot(tool.id)
    assert hidden.visible is False
    assert hidden.primitives == before.primitives
    assert ctx.selection.hit_test((17.0, 72.0), ctx.viewport.world_to_screen, owner_tool=tool.id, selectable_only=True) is None

    tool._set_visible(ctx, True)
    shown = ctx.projected_drawing.snapshot(tool.id)
    assert shown.visible is True
    assert shown.primitives == before.primitives
    assert len(ctx.selection.actors(owner_tool=tool.id)) == len(actors_before)

def test_interaction_refresh_does_not_rebuild_snap_cache_or_sweep_visibility() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass176", families=("point_styles",))
    version_before = ctx.scene_cache.version
    actor_id = "test.pass176:point_styles:solid:grab"

    refreshes = 0

    def refresh() -> None:
        nonlocal refreshes
        refreshes += 1
        refresh_creator_ui_interaction(ctx, owner_tool="test.pass176")

    assert hover_select_grab_actors(
        _event(ToolEventType.MOUSE_PRESS, (17.0, 72.0), (17.0, 72.0, 0.35)),
        ctx,
        owner_tool="test.pass176",
        refresh_visuals=refresh,
    ).handled
    assert hover_select_grab_actors(
        _event(ToolEventType.MOUSE_MOVE, (20.0, 75.0), (20.0, 75.0, 0.35)),
        ctx,
        owner_tool="test.pass176",
        refresh_visuals=refresh,
    ).moved == 1
    assert hover_select_grab_actors(
        _event(ToolEventType.MOUSE_RELEASE, (20.0, 75.0), (20.0, 75.0, 0.35)),
        ctx,
        owner_tool="test.pass176",
        refresh_visuals=refresh,
    ).handled

    assert ctx.selection.actor(actor_id).points[0] == (20.0, 75.0, 0.35)
    assert refreshes >= 3
    # ActorRegistry invalidation may bump the version when the actor moves, but
    # the expensive valid snap rebuild must not run during hover/grab refresh.
    assert ctx.scene_cache.valid is False
    assert ctx.scene_cache.version >= version_before


def test_interaction_family_line_is_a_real_grabbable_actor() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass176.line", families=("actor_interactions",))
    actor_id = "test.pass176.line:actor_interactions:grabbable"
    actor = ctx.selection.actor(actor_id)
    assert actor is not None and actor.grabbable

    def refresh() -> None:
        refresh_creator_ui_interaction(ctx, owner_tool="test.pass176.line")

    assert hover_select_grab_actors(
        _event(ToolEventType.MOUSE_PRESS, (47.0, 44.0), (47.0, 44.0, 0.42)),
        ctx,
        owner_tool="test.pass176.line",
        refresh_visuals=refresh,
    ).handled
    result = hover_select_grab_actors(
        _event(ToolEventType.MOUSE_MOVE, (50.0, 48.0), (50.0, 48.0, 0.42)),
        ctx,
        owner_tool="test.pass176.line",
        refresh_visuals=refresh,
    )
    assert result.moved == 1
    moved_actor = ctx.selection.actor(actor_id)
    assert moved_actor.points == ((50.0, 48.0, 0.42), (69.0, 54.0, 0.42))
    preview = next(item for item in ctx.preview.items(owner_tool="test.pass176.line") if item.id == "test.pass176.line:actor_interactions:preview:grabbable")
    assert preview.points == moved_actor.points



def test_docs_and_catalog_source_state_projected_batch_policy() -> None:
    catalog_source = Path("src/laserprog_studio/tooling/gizmo_catalog_tool.py").read_text(encoding="utf-8")
    assert "apply_creator_ui_motif_visibility" not in catalog_source
    assert "refresh_creator_ui_motifs" not in catalog_source
    assert "registry.set_visible" in catalog_source
    assert "registry.replace_all" in catalog_source

    renderer_source = Path("src/laserprog_studio/application/projected_drawing_2d.py").read_text(encoding="utf-8")
    assert "vtkActor2D" in renderer_source
    assert "SetPickable(False)" in renderer_source

    docs = Path("docs/tool_creator/16_gizmo_catalog_tool.md").read_text(encoding="utf-8")
    assert "persistent `vtkActor2D` batches" in docs
    assert "Show" in docs and "Hide" in docs
    assert "without rebuilding actors" in docs


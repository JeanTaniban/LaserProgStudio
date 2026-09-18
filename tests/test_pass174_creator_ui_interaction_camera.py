# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.tool_api.gizmos import build_creator_ui_motifs, refresh_creator_ui_camera, refresh_creator_ui_motifs
from laserprog_studio.tool_api.interaction import hover_select_grab_actors
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool
from laserprog_studio.tooling.ids import TOOL_GIZMO_CATALOG


class _Owner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.plotter = SimpleNamespace(height=lambda: 500)

    def _world_to_display(self, point):
        return (float(point[0]), 500.0 - float(point[1]), 0.5)

    def _display_to_world_at_depth(self, x, y, depth):
        return (float(x), 500.0 - float(y), float(depth))


def test_creator_actor_interaction_is_public_and_refresh_preserves_dragged_positions() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass174", families=("actor_kinds",))
    actor_id = "test.pass174:actor_kinds:point"
    actor = ctx.selection.actor(actor_id)
    assert actor is not None
    assert actor.points[0] == (-28.0, 0.0, 0.42)

    refreshed = 0

    def refresh() -> None:
        nonlocal refreshed
        refreshed += 1
        refresh_creator_ui_motifs(ctx, owner_tool="test.pass174", families=("actor_kinds",))

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(-28.0, 0.0), world_pos=(-28.0, 0.0, 0.42), button=MouseButton.LEFT)
    result = hover_select_grab_actors(press, ctx, owner_tool="test.pass174", refresh_visuals=refresh)
    assert result.handled
    assert ctx.selection.state.grab_active

    move = ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(-18.0, 5.0), world_pos=(-18.0, 5.0, 0.42), button=MouseButton.LEFT)
    result = hover_select_grab_actors(move, ctx, owner_tool="test.pass174", refresh_visuals=refresh)
    assert result.handled
    assert result.moved >= 1
    assert ctx.selection.actor(actor_id).points[0] == (-18.0, 5.0, 0.42)

    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(-18.0, 5.0), world_pos=(-18.0, 5.0, 0.42), button=MouseButton.LEFT)
    assert hover_select_grab_actors(release, ctx, owner_tool="test.pass174", refresh_visuals=refresh).handled
    assert ctx.selection.actor(actor_id).points[0] == (-18.0, 5.0, 0.42)
    assert refreshed >= 3
    assert any(handle.position == (-18.0, 5.0, 0.42) for handle in ctx.gizmos.handles(owner_tool="test.pass174"))



def test_gizmo_catalog_hide_show_preserves_projected_primitives() -> None:
    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)
    before = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert before.primitives

    tool._set_visible(ctx, False)
    hidden = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert hidden.visible is False
    assert hidden.primitives == before.primitives
    assert ctx.selection.hit_test((0.0, 0.0), ctx.viewport.world_to_screen, owner_tool=TOOL_GIZMO_CATALOG) is None

    tool._set_visible(ctx, True)
    shown = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert shown.visible is True
    assert shown.primitives == before.primitives

def test_creator_ui_camera_refresh_is_public_and_application_integrated(monkeypatch) -> None:
    owner = _Owner()
    ctx = ToolContext(owner=owner)
    build_creator_ui_motifs(ctx, owner_tool="test.pass174", families=("point_styles",))

    calls: list[tuple[object, object, str, bool]] = []

    def fake_render(owner_arg, ctx_arg, owner_tool_arg, *, render=True):
        calls.append((owner_arg, ctx_arg, owner_tool_arg, bool(render)))

    import laserprog_studio.application.creator_viewport_ui as viewport_ui

    monkeypatch.setattr(viewport_ui, "render_creator_viewport_ui", fake_render)
    assert refresh_creator_ui_camera(ctx, owner_tool="test.pass174", render=False) is True
    assert calls == [(owner, ctx, "test.pass174", False)]

    refresh_source = Path("src/laserprog_studio/controllers/interaction_gizmo_refresh.py").read_text(encoding="utf-8")
    interaction_source = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")
    assert "refresh_creator_ui_camera" in refresh_source
    assert "handle_creator_tool_pointer_event" in interaction_source
    assert "active_creator_tool_for_pointer" in interaction_source



def test_catalog_docs_explain_non_interaction_cleanup_and_camera_framing() -> None:
    catalog = Path("docs/tool_creator/16_gizmo_catalog_tool.md").read_text(encoding="utf-8")
    projected = Path("docs/tool_creator/21_projected_drawing_2d.md").read_text(encoding="utf-8")

    assert "non-pickable" in catalog
    assert "world **XY plane at `Z=0`**" in catalog
    assert "ResetCamera" in catalog
    assert "ctx.cleanup_tool" in projected
    assert "render-only" in projected


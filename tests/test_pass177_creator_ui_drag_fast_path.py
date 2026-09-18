# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.gizmos import build_creator_ui_motifs, refresh_creator_ui_drag
from laserprog_studio.tool_api.interaction import hover_select_grab_actors
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.base import ToolSpec
from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool


def _event(event_type, screen, world, *, button=MouseButton.LEFT):
    return ToolEvent(event_type, screen_pos=screen, world_pos=world, button=button)


def test_drag_refresh_updates_only_moved_handle_and_dependent_row_previews() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass177", families=("point_styles",))
    actor_id = "test.pass177:point_styles:solid:line_grab:a"

    assert hover_select_grab_actors(
        _event(ToolEventType.MOUSE_PRESS, (86.0, 72.0), (86.0, 72.0, 0.35)),
        ctx,
        owner_tool="test.pass177",
    ).handled
    result = hover_select_grab_actors(
        _event(ToolEventType.MOUSE_MOVE, (90.0, 75.0), (90.0, 75.0, 0.35)),
        ctx,
        owner_tool="test.pass177",
    )
    assert result.moved == 1

    refresh_creator_ui_drag(ctx, owner_tool="test.pass177", changed_actor_ids=(actor_id,), render=False)

    state = ctx.selection.state
    assert state.dirty_visual_handle_ids == (actor_id,)
    assert "test.pass177:point_styles:solid:line_grab" in state.dirty_visual_preview_ids
    assert "test.pass177:point_styles:ring:line_grab" not in state.dirty_visual_preview_ids
    preview = next(item for item in ctx.preview.items(owner_tool="test.pass177") if item.id == "test.pass177:point_styles:solid:line_grab")
    assert preview.points[0] == (90.0, 75.0, 0.35)



def test_native_runtime_keeps_drag_api_and_projected_catalog_uses_public_constraints() -> None:
    source = Path("src/laserprog_studio/tool_api/interaction.py").read_text(encoding="utf-8")
    native_block = source.split("def handle_native_creator_ui_event", 1)[1].split("def tool_event_uses_left_button", 1)[0]
    assert "refresh_creator_ui_drag" in native_block
    assert "refresh_creator_ui_motifs" not in native_block

    catalog_source = Path("src/laserprog_studio/tooling/gizmo_catalog_tool.py").read_text(encoding="utf-8")
    assert "refresh_creator_ui_drag" not in catalog_source
    assert "resolve_drag_positions" in catalog_source
    assert "on_native_interaction_result" in catalog_source
    assert "ctx.projected_drawing" in catalog_source

def test_docs_name_the_two_refresh_paths() -> None:
    docs = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "docs/tool_creator/00_creator_ui_direction.md",
            "docs/tool_creator/06_overlay_preview_gizmos.md",
            "docs/tool_creator/16_gizmo_catalog_tool.md",
            "docs/archive/passes/pass177_creator_ui_drag_fast_path.md",
        )
    )
    assert "refresh_creator_ui_interaction" in docs
    assert "refresh_creator_ui_drag" in docs
    assert "cached mesh ranges" in docs



def test_projected_catalog_events_use_native_runtime_and_sync_only_projected_content(monkeypatch) -> None:
    from types import SimpleNamespace
    import laserprog_studio.tool_api.gizmos as gizmos

    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)
    adapter = CreatorStudioToolAdapter(
        spec=ToolSpec(id=tool.id, label=tool.label, category="tool", panel_index=0),
        creator=tool,
    )
    context = SimpleNamespace(tool_context=ctx)
    calls = {"drag": 0, "interaction": 0}
    original_drag = gizmos.refresh_creator_ui_drag
    original_interaction = gizmos.refresh_creator_ui_interaction

    def drag_proxy(*args, **kwargs):
        calls["drag"] += 1
        return original_drag(*args, **kwargs)

    def interaction_proxy(*args, **kwargs):
        calls["interaction"] += 1
        return original_interaction(*args, **kwargs)

    monkeypatch.setattr(gizmos, "refresh_creator_ui_drag", drag_proxy)
    monkeypatch.setattr(gizmos, "refresh_creator_ui_interaction", interaction_proxy)

    handle = next(item for item in ctx.projected_drawing.snapshot(tool.id).handles if item.constraint.value == "axis_x")
    press = _event(ToolEventType.MOUSE_PRESS, (handle.position[0], handle.position[1]), handle.position)
    move_world = (handle.position[0] + 5.0, handle.position[1] + 7.0, handle.position[2])
    move = _event(ToolEventType.MOUSE_MOVE, (move_world[0], move_world[1]), move_world)
    release = _event(ToolEventType.MOUSE_RELEASE, (move_world[0], move_world[1]), move_world)

    assert adapter.on_event(press, context) is True
    assert adapter.on_event(move, context) is True
    assert adapter.on_event(release, context) is True
    moved = next(item for item in ctx.projected_drawing.snapshot(tool.id).handles if item.id == handle.id)
    assert moved.position[0] == handle.position[0] + 5.0
    assert moved.position[1] == handle.position[1]
    assert calls["interaction"] >= 1
    assert calls["drag"] >= 1


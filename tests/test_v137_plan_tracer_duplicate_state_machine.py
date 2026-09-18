from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_api.interaction import hover_select_grab_actors
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.duplicate import (
    DUPLICATE_ACTION_PREFIX,
    _DUPLICATE_PREVIEW_BATCH_ID,
    _DUPLICATE_PREVIEW_PIVOT_ID,
)
from laserprog_studio.tooling.plan_trace_2d.prefabs import PlanTracePrefab
from laserprog_studio.tooling.plan_trace_2d.selection_edit import SketchPayload
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Scene:
    def pick_face_at(self, screen_pos, **_kwargs):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 0.0), object_id="ground", object_index=0)


def _open() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    ctx.scene = _Scene()
    ctx.pick.bind_context(ctx)
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT), ctx)
    return tool, ctx


def _point(tool: PlanTrace2DCreatorTool, xy: tuple[float, float]):
    point_id = f"plan_trace:point:{tool._state.next_point_index:04d}"
    tool._state.next_point_index += 1
    return tool._state.sketch.add_point(xy, point_id=point_id)


def _prefab() -> PlanTracePrefab:
    return PlanTracePrefab(
        "user:cursor",
        "Cursor prefab",
        SketchPayload(
            points={"a": (-2.0, 0.0), "b": (2.0, 0.0), "c": (0.0, 3.0)},
            lines=[
                {"start": "a", "end": "b", "metadata": {}},
                {"start": "b", "end": "c", "metadata": {}},
                {"start": "c", "end": "a", "metadata": {}},
            ],
            pivot=(0.0, 0.0),
        ),
    )


def test_v137_duplicate_library_inherits_native_modify_selection(monkeypatch) -> None:
    tool, ctx = _open()
    p0, p1 = _point(tool, (0.0, 0.0)), _point(tool, (20.0, 0.0))
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (_prefab(),))
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)

    event = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 0.0), button=MouseButton.LEFT)
    assert tool.wants_native_actor_interaction(event, ctx)
    result = hover_select_grab_actors(event, ctx, owner_tool=tool.id, world_to_screen=ctx.viewport.world_to_screen)
    tool.on_native_interaction_result(event, ctx, result)

    line_actor_id = tool._services.sketch_sync._line_actor_id(line.id)
    assert result.action == "select"
    assert ctx.selection.is_selected(line_actor_id)
    assert "semantic element(s) selected" in tool._services.duplicate.status_text(ctx)


def test_v137_duplicate_library_safe_drag_keeps_smart_snap_resolver() -> None:
    tool, ctx = _open()
    p0, p1 = _point(tool, (0.0, 0.0)), _point(tool, (10.0, 0.0))
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(line.id))
    tool._services.selection_edit.select_support_points(ctx)
    assert ctx.selection.begin_grab(p0.id, (0.0, 0.0), world_pos=(0.0, 0.0, 0.0))
    grabbed = tuple(ctx.selection.state.grabbed_ids)
    tool.on_native_interaction_result(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT),
        ctx,
        SimpleNamespace(action="grab", grabbed_ids=grabbed, hit=None),
    )

    replacements = tool.resolve_drag_positions(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(35.0, 15.0)), ctx)
    assert replacements
    assert p0.id in replacements


def test_v137_free_place_preview_updates_repeatedly_and_stays_after_click(monkeypatch) -> None:
    tool, ctx = _open()
    prefab = _prefab()
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (prefab,))
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    service.selected_prefab_id = prefab.id
    service._last_screen_pos = (15.0, 12.0)

    assert service.handle_button(ctx, DUPLICATE_ACTION_PREFIX + "place_one")
    registry = ctx.projected_drawing.for_tool(tool.id)
    first = registry.get(_DUPLICATE_PREVIEW_BATCH_ID)
    assert first is not None
    assert registry.get(_DUPLICATE_PREVIEW_PIVOT_ID) is not None

    assert service.handle_event(ctx, ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(40.0, 22.0)))
    second = registry.get(_DUPLICATE_PREVIEW_BATCH_ID)
    assert second is not None and second.segments != first.segments

    # A second move used to raise internally because stable ids were re-added
    # without replacement, leaving the first green contour frozen forever.
    assert service.handle_event(ctx, ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(70.0, 35.0)))
    third = registry.get(_DUPLICATE_PREVIEW_BATCH_ID)
    assert third is not None and third.segments != second.segments

    assert service.handle_event(
        ctx,
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(70.0, 35.0), button=MouseButton.LEFT),
    )
    assert service.stage == "place"
    assert registry.get(_DUPLICATE_PREVIEW_BATCH_ID) is not None
    assert registry.get(_DUPLICATE_PREVIEW_PIVOT_ID) is not None
    assert any(line.metadata.get("generated_by") == "duplicate" for line in tool._state.sketch.lines.values())
    assert not ctx.selection.ids()


def test_v137_escape_backs_one_duplicate_step_then_exits(monkeypatch) -> None:
    tool, ctx = _open()
    prefab = _prefab()
    monkeypatch.setattr("laserprog_studio.tooling.plan_trace_2d.duplicate.load_prefabs", lambda: (prefab,))
    tool._set_active_tool(ctx, "duplicate", reason="test", render=False)
    service = tool._services.duplicate
    service.selected_prefab_id = prefab.id
    assert service.handle_button(ctx, DUPLICATE_ACTION_PREFIX + "place_one")
    assert service.stage == "place"

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="escape"), ctx)
    assert tool._state.active_tool == "duplicate"
    assert service.stage == "library"

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="escape"), ctx)
    assert tool._state.active_tool == "modify"

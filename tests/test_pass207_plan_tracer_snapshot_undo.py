from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool, PlanTrace2DTool
from laserprog_studio.tooling.registry import get_tool_spec


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 7.0),
            object_id="face_7",
            object_index=1,
        )


class _App:
    def __init__(self) -> None:
        self.tool_context = ToolContext()
        self.scene = _HitScene()
        self.tool_context.scene = self.scene
        self.tool_context.pick.bind_context(self.tool_context)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def _key(tool: PlanTrace2DCreatorTool, ctx: ToolContext, key: str, *modifiers: str) -> bool:
    return tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key=key, modifiers=frozenset(modifiers)), ctx)


def test_plan_tracer_point_undo_redo_restores_sketch_and_visual_actors() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)

    _click(tool, ctx, 100.0, 100.0)
    assert len(tool._state.sketch.points) == 1
    assert ctx.commands.undo_count == 1
    assert len([actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point"]) == 1

    assert _key(tool, ctx, "z", "ctrl") is True
    assert len(tool._state.sketch.points) == 0
    assert ctx.commands.redo_count == 1
    assert not [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point"]

    assert _key(tool, ctx, "y", "ctrl") is True
    assert len(tool._state.sketch.points) == 1
    assert ctx.commands.undo_count == 1
    assert len([actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point"]) == 1


def test_plan_tracer_delete_is_one_snapshot_command_and_undo_restores_face() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 200.0, 150.0)
    assert len(tool._state.sketch.faces) == 1
    face_actor = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "face")
    ctx.selection.select(face_actor.id)
    undo_count_before_delete = ctx.commands.undo_count

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="delete"), ctx) is True
    assert len(tool._state.sketch.faces) == 0
    assert ctx.commands.undo_count == undo_count_before_delete + 1

    assert _key(tool, ctx, "z", "ctrl") is True
    assert len(tool._state.sketch.faces) == 1
    assert any(actor.metadata.get("plan_trace_role") == "face" for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE))


def test_modify_drag_release_records_single_undo_entry() -> None:
    runtime = PlanTrace2DTool(get_tool_spec(TOOL_PLAN_TRACE))
    app = _App()
    runtime.on_open(app)
    runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), app)
    ctx = app.tool_context
    tool = runtime.creator
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(100.0, 100.0), button=MouseButton.LEFT), app)
    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(200.0, 100.0), button=MouseButton.LEFT), app)
    moved_id = next(point_id for point_id, point in tool._state.sketch.points.items() if point.position == (200.0, 100.0))
    moved_actor = ctx.selection.actor(moved_id)
    assert moved_actor is not None

    undo_count_before_drag = ctx.commands.undo_count
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    ctx.selection.select(moved_id)
    # Native runtime starts the grab on press, then moves via the Plan tracer resolver.
    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(200.0, 100.0), button=MouseButton.LEFT), app)
    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(220.0, 120.0), button=MouseButton.LEFT), app)
    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(220.0, 120.0), button=MouseButton.LEFT), app)

    assert tool._state.sketch.points[moved_id].position == (220.0, 120.0)
    # Switching away from a metric draft auto-validates that placement, then the
    # native Modify drag is still recorded as one additional undo action.
    assert ctx.commands.undo_count == undo_count_before_drag + 2

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="z", modifiers=frozenset({"ctrl"})), ctx) is True
    assert tool._state.sketch.points[moved_id].position == (200.0, 100.0)

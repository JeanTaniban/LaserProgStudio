from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DTool
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


def _runtime() -> tuple[PlanTrace2DTool, _App]:
    runtime = PlanTrace2DTool(get_tool_spec(TOOL_PLAN_TRACE))
    app = _App()
    runtime.on_open(app)
    runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), app)
    assert runtime.creator._state.display_plane is not None
    assert runtime.creator._state_invariant_issues() == ()
    return runtime, app


def _click(runtime: PlanTrace2DTool, app: _App, x: float, y: float) -> None:
    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), app) is True


def test_drawing_modes_bypass_native_actor_selection_so_existing_vertices_remain_clickable_inputs() -> None:
    runtime, app = _runtime()
    ctx = app.tool_context
    tool = runtime.creator
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(runtime, app, 100.0, 100.0)
    _click(runtime, app, 200.0, 100.0)
    assert len(tool._state.sketch.lines) == 1

    # This press is directly on an existing point actor.  In Line mode it must be
    # treated as a drawing input/snap, not consumed by the native Modify selector.
    _click(runtime, app, 200.0, 100.0)
    assert tool._state.pending_line_start_id is not None
    _click(runtime, app, 200.0, 180.0)

    assert len(tool._state.sketch.lines) == 2
    assert tool._state_invariant_issues() == ()
    assert not ctx.selection.ids()


def test_native_modify_release_recompiles_topology_after_dragged_point_lands_on_line() -> None:
    runtime, app = _runtime()
    ctx = app.tool_context
    tool = runtime.creator
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    _click(runtime, app, 100.0, 100.0)
    _click(runtime, app, 200.0, 100.0)

    tool._set_active_tool(ctx, "point", reason="test", render=False)
    _click(runtime, app, 150.0, 150.0)
    dragged_id = next(point_id for point_id, point in tool._state.sketch.points.items() if point.position == (150.0, 150.0))
    dragged_actor = ctx.selection.actor(dragged_id)
    assert dragged_actor is not None

    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    ctx.selection.select(dragged_id)
    ctx.selection.begin_grab(dragged_id, (150.0, 150.0), dragged_actor.points[0])
    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(150.0, 100.0), button=MouseButton.LEFT), app) is True
    # The fast drag path only moves actors/live sketch points.  The release hook is
    # responsible for the topological compile.
    runtime.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(150.0, 100.0), button=MouseButton.LEFT), app)

    assert tool._state.sketch.points[dragged_id].position == (150.0, 100.0)
    assert len(tool._state.sketch.lines) == 2
    assert {frozenset((line.start_point_id, line.end_point_id)) for line in tool._state.sketch.lines.values()} == {
        frozenset({dragged_id, next(point_id for point_id, point in tool._state.sketch.points.items() if point.position == (100.0, 100.0))}),
        frozenset({dragged_id, next(point_id for point_id, point in tool._state.sketch.points.items() if point.position == (200.0, 100.0))}),
    }
    assert len(tool._state.sketch.polylines) == 1
    assert tool._state_invariant_issues() == ()

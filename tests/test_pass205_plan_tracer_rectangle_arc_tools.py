from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedActorKind, ProjectedFace, ProjectedLine
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


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


def test_plan_tracer_rectangle_mode_creates_closed_polyline_and_face() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_rectangle_corner_id is not None
    _click(tool, ctx, 200.0, 150.0)

    assert tool._state.pending_rectangle_corner_id is None
    assert len(tool._state.sketch.points) == 4
    assert len(tool._state.sketch.lines) == 4
    assert len(tool._state.sketch.polylines) == 1
    polyline = next(iter(tool._state.sketch.polylines.values()))
    assert polyline.closed is True
    assert len(tool._state.sketch.faces) == 1
    edge_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "edge"]
    assert len(edge_actors) == 4
    assert any(isinstance(item, ProjectedFace) for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives)
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()


def test_plan_tracer_arc_mode_creates_selectable_arc_from_three_clicks() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "arc", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_arc_start_id is not None
    assert tool._state.pending_arc_end_id is None
    _click(tool, ctx, 200.0, 100.0)
    assert tool._state.pending_arc_start_id is not None
    assert tool._state.pending_arc_end_id is not None
    _click(tool, ctx, 150.0, 150.0)

    assert tool._state.pending_arc_start_id is None
    assert tool._state.pending_arc_end_id is None
    assert len(tool._state.sketch.arcs) == 1
    assert len(tool._state.sketch.polylines) == 1
    polyline = next(iter(tool._state.sketch.polylines.values()))
    assert polyline.recognized_shape == "arc"
    arc_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "arc"]
    assert len(arc_actors) == 1
    assert arc_actors[0].metadata.get("plan_trace_sketch_arc_id") in tool._state.sketch.arcs
    assert any(isinstance(item, ProjectedLine) and item.actor_kind == ProjectedActorKind.ARC for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives)
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()


def test_changing_mode_clears_rectangle_and_arc_pending_state() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)

    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_rectangle_corner_id is not None
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    assert tool._state.pending_rectangle_corner_id is None

    tool._set_active_tool(ctx, "arc", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 200.0, 100.0)
    assert tool._state.pending_arc_start_id is not None
    assert tool._state.pending_arc_end_id is not None
    tool._set_active_tool(ctx, "point", reason="test", render=False)
    assert tool._state.pending_arc_start_id is None
    assert tool._state.pending_arc_end_id is None
    assert tool._state_invariant_issues() == ()


def test_sketch_open_arc_rebuilds_arc_polyline_without_face() -> None:
    sketch = SketchDocument()
    start = sketch.add_point((0.0, 0.0), point_id="a")
    end = sketch.add_point((10.0, 0.0), point_id="b")
    control = sketch.add_point((5.0, 5.0), point_id="c")
    sketch.add_arc(start.id, end.id, control.id, arc_id="arc.a")

    sketch.compile(SketchCompileOptions(solve_faces=True))

    assert len(sketch.polylines) == 1
    polyline = next(iter(sketch.polylines.values()))
    assert polyline.closed is False
    assert polyline.recognized_shape == "arc"
    assert not sketch.faces

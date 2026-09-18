from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedActorKind, ProjectedLine
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.snap import SnapKind
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


def test_sketch_circle_rebuilds_closed_polyline_and_generated_face() -> None:
    sketch = SketchDocument()
    center = sketch.add_point((0.0, 0.0), point_id="c")
    radius = sketch.add_point((10.0, 0.0), point_id="r")
    circle = sketch.add_circle(center.id, radius.id, circle_id="circle.a")

    result = sketch.compile(SketchCompileOptions(solve_faces=True))

    assert circle.id in sketch.circles
    assert result.rebuilt_polylines == 1
    polyline = next(iter(sketch.polylines.values()))
    assert polyline.closed is True
    assert polyline.recognized_shape == "circle"
    assert polyline.edge_ids == ("circle.a",)
    assert len(sketch.faces) == 1
    face = next(iter(sketch.faces.values()))
    assert face.boundary_entity_ids == ("circle.a",)
    assert len(face.polygon_points) >= 32


def test_plan_tracer_circle_mode_creates_selectable_curve_face_and_snap_landmarks() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "circle", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_circle_center_id is not None
    _click(tool, ctx, 150.0, 100.0)

    assert tool._state.pending_circle_center_id is None
    assert len(tool._state.sketch.circles) == 1
    assert len(tool._state.sketch.faces) == 1
    circle_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "circle"]
    assert len(circle_actors) == 1
    assert circle_actors[0].metadata.get("plan_trace_sketch_circle_id") in tool._state.sketch.circles
    assert any(isinstance(item, ProjectedLine) and item.actor_kind == ProjectedActorKind.CIRCLE for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives)
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()

    # Cursor query near a quadrant must be styled by the API as a curve-derived
    # constraint, not as a generic edge/free cursor.  At the exact quadrant the
    # perpendicular candidate can legitimately tie with the quadrant landmark.
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(150.0, 100.0)), ctx)
    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["snap_kind"] in {
        SnapKind.VERTEX.value,
        SnapKind.QUADRANT.value,
        SnapKind.PERPENDICULAR.value,
    }


def test_deleting_selected_plan_tracer_circle_removes_curve_and_generated_face() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "circle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 150.0, 100.0)

    circle_actor = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "circle")
    ctx.selection.select(circle_actor.id)

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Delete"), ctx) is True

    assert not tool._state.sketch.circles
    assert not tool._state.sketch.faces
    assert not [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "circle"]

from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedActorKind, ProjectedLine
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


def test_sketch_half_circle_arc_and_diameter_create_closed_polyline_and_face() -> None:
    sketch = SketchDocument()
    start = sketch.add_point((0.0, 0.0), point_id="a")
    end = sketch.add_point((10.0, 0.0), point_id="b")
    apex = sketch.add_point((5.0, 5.0), point_id="top")
    arc = sketch.add_arc(start.id, end.id, apex.id, arc_id="arc.a")
    diameter = sketch.add_line(start.id, end.id, line_id="diameter.a")
    diameter.metadata.update({"generated_by": "half_circle_diameter", "half_circle_arc_id": arc.id})

    report = sketch.compile(SketchCompileOptions(solve_faces=True))

    assert report.rebuilt_polylines == 1
    polyline = next(iter(sketch.polylines.values()))
    assert polyline.closed is True
    assert polyline.recognized_shape == "half_circle"
    assert set(polyline.edge_ids) == {"arc.a", "diameter.a"}
    assert len(sketch.faces) == 1
    face = next(iter(sketch.faces.values()))
    assert set(face.boundary_entity_ids) == {"arc.a", "diameter.a"}
    assert len(face.polygon_points) > 8


def test_plan_tracer_half_circle_mode_creates_selectable_arc_diameter_and_face() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "half_circle", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_half_circle_start_id is not None
    _click(tool, ctx, 200.0, 100.0)

    assert tool._state.pending_half_circle_start_id is None
    assert len(tool._state.sketch.arcs) == 1
    assert len(tool._state.sketch.lines) == 1
    assert len(tool._state.sketch.faces) == 1
    arc_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "arc"]
    assert len(arc_actors) == 1
    assert arc_actors[0].metadata.get("plan_trace_sketch_arc_id") in tool._state.sketch.arcs
    assert any(isinstance(item, ProjectedLine) and item.actor_kind == ProjectedActorKind.ARC for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives)
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()


def test_deleting_selected_plan_tracer_arc_removes_half_circle_face_and_diameter() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "half_circle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 200.0, 100.0)

    arc_actor = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "arc")
    ctx.selection.select(arc_actor.id)

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Delete"), ctx) is True

    assert not tool._state.sketch.arcs
    assert not tool._state.sketch.lines
    assert not tool._state.sketch.faces
    assert not [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "arc"]

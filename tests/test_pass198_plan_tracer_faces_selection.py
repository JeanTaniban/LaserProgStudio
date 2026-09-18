from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedFace
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


def _line(tool: PlanTrace2DCreatorTool, ctx: ToolContext, a: tuple[float, float], b: tuple[float, float]) -> None:
    _click(tool, ctx, *a)
    _click(tool, ctx, *b)


def test_sketch_closed_polyline_creates_face_and_face_delete_keeps_edges() -> None:
    sketch = SketchDocument()
    for point_id, xy in {"a": (0.0, 0.0), "b": (10.0, 0.0), "c": (10.0, 10.0), "d": (0.0, 10.0)}.items():
        sketch.add_point(xy, point_id=point_id)
    for line_id, start, end in (("ab", "a", "b"), ("bc", "b", "c"), ("cd", "c", "d"), ("da", "d", "a")):
        sketch.add_line(start, end, line_id=line_id)

    sketch.compile(SketchCompileOptions(solve_faces=True))

    assert len(sketch.polylines) == 1
    assert next(iter(sketch.polylines.values())).closed is True
    assert len(sketch.faces) == 1
    face_id = next(iter(sketch.faces))

    sketch.delete_face_only(face_id)

    assert len(sketch.lines) == 4
    assert len(sketch.faces) == 0
    assert len(sketch.suppressed_face_signatures) == 1


def test_plan_tracer_closed_lines_create_selectable_face_actor_and_delete_only_fill() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _line(tool, ctx, (100.0, 100.0), (200.0, 100.0))
    _line(tool, ctx, (200.0, 100.0), (200.0, 180.0))
    _line(tool, ctx, (200.0, 180.0), (100.0, 180.0))
    _line(tool, ctx, (100.0, 180.0), (100.0, 100.0))

    assert len(tool._state.sketch.faces) == 1
    face_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "face"]
    assert len(face_actors) == 1
    assert face_actors[0].metadata.get("filled_polygon_hit") is True
    assert any(isinstance(item, ProjectedFace) for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives)
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()

    ctx.selection.select(face_actors[0].id)
    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Delete"), ctx) is True

    assert len(tool._state.sketch.lines) == 4
    assert len(tool._state.sketch.faces) == 0
    assert not [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "face"]
    assert not any(isinstance(item, ProjectedFace) for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives)
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()

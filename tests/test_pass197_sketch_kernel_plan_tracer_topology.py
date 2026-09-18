from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchCompiler, SketchDocument
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


def test_sketch_compiler_splits_line_when_point_lands_on_it() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b = sketch.add_point((10.0, 0.0), point_id="b")
    p = sketch.add_point((5.0, 0.0), point_id="p")
    original = sketch.add_line(a.id, b.id, line_id="ab")

    result = SketchCompiler(SketchCompileOptions(split_tolerance=1.0e-6, solve_faces=False)).compile(sketch)

    assert result.split_lines == 1
    assert original.id not in sketch.lines
    assert len(sketch.lines) == 2
    assert {frozenset((line.start_point_id, line.end_point_id)) for line in sketch.lines.values()} == {
        frozenset(("a", "p")),
        frozenset(("p", "b")),
    }
    assert len(sketch.polylines) == 1
    polyline = next(iter(sketch.polylines.values()))
    assert polyline.point_ids == ("a", "p", "b")


def test_sketch_compiler_merges_duplicate_chain_points_into_one_polyline() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b1 = sketch.add_point((10.0, 0.0), point_id="b1")
    b2 = sketch.add_point((10.0 + 1.0e-7, 0.0), point_id="b2")
    c = sketch.add_point((20.0, 0.0), point_id="c")
    sketch.add_line(a.id, b1.id, line_id="ab")
    sketch.add_line(b2.id, c.id, line_id="bc")

    result = SketchCompiler(SketchCompileOptions(merge_tolerance=1.0e-5, solve_faces=False)).compile(sketch)

    assert result.merged_points == 1
    assert len(sketch.points) == 3
    assert len(sketch.polylines) == 1
    polyline = next(iter(sketch.polylines.values()))
    assert polyline.point_ids == ("a", "b1", "c")


def test_sketch_delete_edge_rebuilds_two_polylines() -> None:
    sketch = SketchDocument()
    for point_id, x in (("a", 0.0), ("b", 10.0), ("c", 20.0), ("d", 30.0)):
        sketch.add_point((x, 0.0), point_id=point_id)
    sketch.add_line("a", "b", line_id="ab")
    sketch.add_line("b", "c", line_id="bc")
    sketch.add_line("c", "d", line_id="cd")
    sketch.compile(SketchCompileOptions(solve_faces=False))

    sketch.delete_line_cascade("bc")

    assert len(sketch.polylines) == 2
    assert {polyline.point_ids for polyline in sketch.polylines.values()} == {("a", "b"), ("c", "d")}


def test_plan_tracer_line_mode_creates_topology_and_point_on_line_splits_edge() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(100.0, 100.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(200.0, 100.0), button=MouseButton.LEFT), ctx)

    assert len(tool._state.sketch.lines) == 1
    assert len([actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "edge"]) == 1

    tool._set_active_tool(ctx, "point", reason="test", render=False)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(150.0, 100.0), button=MouseButton.LEFT), ctx)

    assert len(tool._state.sketch.points) == 3
    assert len(tool._state.sketch.lines) == 2
    assert len(tool._state.sketch.polylines) == 1
    assert len([actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "edge"]) == 2

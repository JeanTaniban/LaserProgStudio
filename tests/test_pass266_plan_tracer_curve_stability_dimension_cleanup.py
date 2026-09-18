from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedActorKind, ProjectedLine
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.constants import _PENDING_PREVIEW_PREFIX
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=1)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def test_plan_tracer_live_compile_preserves_user_circles_when_they_intersect() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    sketch = tool._state.sketch
    c1 = sketch.add_point((0.0, 0.0), point_id="c1")
    r1 = sketch.add_point((5.0, 0.0), point_id="r1")
    c2 = sketch.add_point((6.0, 0.0), point_id="c2")
    r2 = sketch.add_point((11.0, 0.0), point_id="r2")
    sketch.add_circle(c1.id, r1.id, circle_id="circle1")
    sketch.add_circle(c2.id, r2.id, circle_id="circle2")

    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)

    assert set(sketch.circles) == {"circle1", "circle2"}
    assert not sketch.arcs
    circle_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "circle"]
    assert len(circle_actors) == 2


def test_default_kernel_can_still_split_intersecting_circles_for_topology_tests() -> None:
    sketch = SketchDocument()
    c1 = sketch.add_point((0.0, 0.0), point_id="c1")
    r1 = sketch.add_point((5.0, 0.0), point_id="r1")
    c2 = sketch.add_point((6.0, 0.0), point_id="c2")
    r2 = sketch.add_point((11.0, 0.0), point_id="r2")
    sketch.add_circle(c1.id, r1.id, circle_id="circle1")
    sketch.add_circle(c2.id, r2.id, circle_id="circle2")

    result = sketch.compile(SketchCompileOptions(split_tolerance=1.0e-5, solve_faces=False))

    assert result.split_circles == 2
    assert not sketch.circles
    assert len(sketch.arcs) >= 4


def test_dimension_is_deleted_when_its_target_line_is_structurally_split() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b = sketch.add_point((10.0, 0.0), point_id="b")
    line = sketch.add_line(a.id, b.id, line_id="line")
    dim = sketch.add_edge_length_dimension(line.id, dimension_id="dim.line")
    assert dim.id in sketch.dimensions
    sketch.add_point((5.0, 0.0), point_id="mid")

    result = sketch.compile(SketchCompileOptions(split_tolerance=1.0e-5, solve_faces=False))

    assert result.split_lines == 1
    assert "line" not in sketch.lines
    assert "dim.line" not in sketch.dimensions


def test_curve_preview_updates_stable_item_instead_of_hiding_all_preview_primitives() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "circle", reason="test", render=False)
    center = tool._state.sketch.add_point((10.0, 10.0), point_id="center")
    tool._state.pending_circle_center_id = center.id
    first_revision = ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).revision

    world = tool._services.coordinates.sketch_xy_to_display_world((20.0, 10.0))
    tool._services.snap._update_pending_geometry_preview(ctx, world)
    after_first = ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).revision
    tool._services.snap._update_pending_geometry_preview(ctx, world)
    after_second = ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).revision

    item = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(f"{_PENDING_PREVIEW_PREFIX}:circle")
    assert isinstance(item, ProjectedLine)
    assert item.actor_kind == ProjectedActorKind.CIRCLE
    assert item.visible is True
    assert after_first > first_revision
    assert after_second == after_first
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()

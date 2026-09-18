from __future__ import annotations

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
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


def _line_length(tool: PlanTrace2DCreatorTool) -> float:
    line = next(iter(tool._state.sketch.lines.values()))
    a = tool._state.sketch.points[line.start_point_id].position
    b = tool._state.sketch.points[line.end_point_id].position
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5


def test_pass307_modify_existing_line_reopens_metric_bar_and_rebuilds_line() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    p1 = tool._state.sketch.add_point((0.0, 0.0), point_id="p1")
    p2 = tool._state.sketch.add_point((50.0, 0.0), point_id="p2")
    line = tool._state.sketch.add_line(p1.id, p2.id, line_id="l1")
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)

    actor_id = f"{TOOL_PLAN_TRACE}:line:{line.id}"
    assert tool._services.metrics.open_metric_edit_for_actor(ctx, actor_id) is True
    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.mode == "line"
    assert ctx.overlay.window("plan_trace_2d.metric_overlay").visible is True  # type: ignore[union-attr]

    assert tool.apply_metric_value(ctx, "length", "25 mm") is True
    tool.on_overlay_button_clicked("plan_trace_2d.metric.validate", ctx)

    assert tool._state.metric_draft is None
    assert len(tool._state.sketch.lines) == 1
    assert round(_line_length(tool), 6) == 25.0


def test_pass307_modify_existing_circle_reopens_radius_diameter_metrics() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    center = tool._state.sketch.add_point((10.0, 10.0), point_id="pc")
    radius_point = tool._state.sketch.add_point((20.0, 10.0), point_id="pr")
    circle = tool._state.sketch.add_circle(center.id, radius_point.id, circle_id="c1")
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)

    actor_id = f"{TOOL_PLAN_TRACE}:circle:{circle.id}"
    assert tool._services.metrics.open_metric_edit_for_actor(ctx, actor_id) is True
    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.mode == "circle"
    assert set(tool._state.metric_draft.session.fields) == {"radius", "diameter"}

    assert tool.apply_metric_value(ctx, "diameter", "40 mm") is True
    values = tool._state.metric_draft.session.as_values()  # type: ignore[union-attr]
    assert values["radius"] == 20.0
    assert values["diameter"] == 40.0
    tool.on_overlay_button_clicked("plan_trace_2d.metric.validate", ctx)

    circle = next(iter(tool._state.sketch.circles.values()))
    c = tool._state.sketch.points[circle.center_point_id].position
    r = tool._state.sketch.points[circle.radius_point_id].position
    assert round(((r[0] - c[0]) ** 2 + (r[1] - c[1]) ** 2) ** 0.5, 6) == 20.0


def test_pass307_modify_existing_rectangle_face_reopens_width_height_metrics() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    p1 = tool._state.sketch.add_point((0.0, 0.0), point_id="p1")
    p3 = tool._state.sketch.add_point((60.0, 30.0), point_id="p3")
    tool._services.drawing._add_axis_aligned_rectangle(p1.id, p3.id, p1.position, p3.position)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    assert len(tool._state.sketch.faces) == 1
    face = next(iter(tool._state.sketch.faces.values()))

    actor_id = f"{TOOL_PLAN_TRACE}:face:{face.id}"
    assert tool._services.metrics.open_metric_edit_for_actor(ctx, actor_id) is True
    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.mode == "rectangle"

    assert tool.apply_metric_value(ctx, "width", "20 mm") is True
    assert tool.apply_metric_value(ctx, "height", "10 mm") is True
    tool.on_overlay_button_clicked("plan_trace_2d.metric.validate", ctx)

    xs = [point.position[0] for point in tool._state.sketch.points.values()]
    ys = [point.position[1] for point in tool._state.sketch.points.values()]
    assert round(max(xs) - min(xs), 6) == 20.0
    assert round(max(ys) - min(ys), 6) == 10.0
    assert len(tool._state.sketch.lines) == 4

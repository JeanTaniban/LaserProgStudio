from __future__ import annotations

from laserprog_studio.tool_api import metrics as metric_api
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
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


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_metric_api_has_sessions_for_all_two_click_shapes_and_arc() -> None:
    rectangle = metric_api.rectangle_metric_session("metric.rect", width=80.0, height=40.0)
    half = metric_api.half_circle_metric_session("metric.half", radius=25.0, angle_degrees=0.0)
    arc = metric_api.arc_metric_session("metric.arc", radius=30.0, angle_degrees=90.0)

    assert set(rectangle.fields) == {"width", "height"}
    assert set(half.fields) == {"radius", "diameter", "angle"}
    assert set(arc.fields) == {"radius", "angle"}


def test_plan_tracer_rectangle_second_click_enters_metric_edit_and_rebuilds_from_values() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)

    _click(tool, ctx, 0.0, 0.0)
    undo_after_first = ctx.commands.undo_count
    _click(tool, ctx, 30.0, 20.0)

    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.mode == "rectangle"
    assert ctx.commands.undo_count == undo_after_first
    assert tool.apply_metric_value(ctx, "width", "10 mm") is True
    assert tool.apply_metric_value(ctx, "height", "5 mm") is True
    xs = [point.position[0] for point in tool._state.sketch.points.values()]
    ys = [point.position[1] for point in tool._state.sketch.points.values()]
    assert round(max(xs) - min(xs), 6) == 10.0
    assert round(max(ys) - min(ys), 6) == 5.0

    tool.on_overlay_button_clicked("plan_trace_2d.metric.validate", ctx)
    assert tool._state.metric_draft is None
    assert ctx.commands.undo_count == undo_after_first + 1


def test_metric_overlay_auto_validates_when_user_starts_another_viewport_action() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 20.0, 0.0)
    assert tool._state.metric_draft is not None
    undo_after_draft = ctx.commands.undo_count

    _click(tool, ctx, 50.0, 0.0)
    assert tool._state.metric_draft is None
    assert ctx.commands.undo_count == undo_after_draft + 2
    assert tool._state.pending_line_start_id is not None


def test_plan_tracer_half_circle_metric_rebuilds_radius_and_diameter_pair() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "half_circle", reason="test", render=False)

    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 20.0, 0.0)
    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.mode == "half_circle"

    assert tool.apply_metric_value(ctx, "radius", "15 mm") is True
    assert tool._state.metric_draft is not None
    values = tool._state.metric_draft.session.as_values()
    assert values["radius"] == 15.0
    assert values["diameter"] == 30.0
    diameter_lines = [line for line in tool._state.sketch.lines.values() if line.metadata.get("generated_by") == "half_circle_diameter"]
    assert len(diameter_lines) == 1
    line = diameter_lines[0]
    start = tool._state.sketch.points[line.start_point_id].position
    end = tool._state.sketch.points[line.end_point_id].position
    assert round(((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5, 6) == 30.0


def test_overlay_field_commit_entrypoint_strips_metric_prefix() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "circle", reason="test", render=False)
    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 20.0, 10.0)

    assert tool.on_overlay_field_changed("plan_trace_2d.metric_overlay", "plan_trace_2d.metric_overlay.metric.diameter", "40 mm", ctx) is True
    assert tool._state.metric_draft is not None
    values = tool._state.metric_draft.session.as_values()
    assert values["radius"] == 20.0
    assert values["diameter"] == 40.0

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


def test_metric_api_builds_top_center_validation_overlay() -> None:
    session = metric_api.line_metric_session("metric.demo", length=120.0, angle_degrees=45.0)
    window = metric_api.build_metric_edit_window(
        window_id="metric.demo",
        owner_tool="demo",
        session=session,
        validate_button_id="metric.validate",
        cancel_button_id="metric.cancel",
    )

    assert window.anchor == "viewport_bottom_center"
    assert window.overlay_kind == "toolbar"
    assert window.movable is False
    assert window.cursor_offset_px[1] < 72
    assert [button.label for button in window.buttons] == ["Validate", "Cancel"]
    assert window.buttons[0].style == "primary"
    assert any(field.label == "Length" and "120" in field.value for field in window.fields)
    assert any(field.label == "Angle" and "45" in field.value for field in window.fields)


def test_plan_tracer_line_second_click_opens_metric_transaction_overlay() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(tool, ctx, 0.0, 0.0)
    assert tool._state.pending_line_start_id is not None
    _click(tool, ctx, 30.0, 0.0)

    assert tool._state.pending_line_start_id is None
    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.mode == "line"
    window = ctx.overlay.window("plan_trace_2d.metric_overlay")
    assert window is not None and window.visible is True
    assert window.anchor == "viewport_bottom_center"
    assert any(field.label == "Length" and "29.1" in field.value for field in window.fields)


def test_plan_tracer_metric_validate_records_single_commit_for_second_click() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(tool, ctx, 0.0, 0.0)
    undo_after_start = ctx.commands.undo_count
    _click(tool, ctx, 30.0, 0.0)
    assert ctx.commands.undo_count == undo_after_start

    tool.on_overlay_button_clicked("plan_trace_2d.metric.validate", ctx)
    assert tool._state.metric_draft is None
    assert ctx.overlay.window("plan_trace_2d.metric_overlay").visible is False  # type: ignore[union-attr]
    assert ctx.commands.undo_count == undo_after_start + 1


def test_plan_tracer_metric_cancel_restores_snapshot() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "circle", reason="test", render=False)

    _click(tool, ctx, 10.0, 10.0)
    point_count_after_center = len(tool._state.sketch.points)
    _click(tool, ctx, 20.0, 10.0)
    assert tool._state.metric_draft is not None
    assert len(tool._state.sketch.circles) == 1

    tool.on_overlay_button_clicked("plan_trace_2d.metric.cancel", ctx)
    assert tool._state.metric_draft is None
    assert len(tool._state.sketch.circles) == 0
    assert len(tool._state.sketch.points) == point_count_after_center
    assert ctx.overlay.window("plan_trace_2d.metric_overlay").visible is False  # type: ignore[union-attr]


def test_plan_tracer_metric_value_hook_rebuilds_line_from_clean_snapshot() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 50.0, 0.0)

    assert tool.apply_metric_value(ctx, "length", "25 mm") is True
    assert tool._state.metric_draft is not None
    assert len(tool._state.sketch.lines) == 1
    line = next(iter(tool._state.sketch.lines.values()))
    start = tool._state.sketch.points[line.start_point_id].position
    end = tool._state.sketch.points[line.end_point_id].position
    assert round(((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5, 6) == 25.0

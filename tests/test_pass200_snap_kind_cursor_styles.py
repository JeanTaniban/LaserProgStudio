from __future__ import annotations

from laserprog_studio.tool_api import snap
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.snap import SnapKind, SnapSource
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


def test_snap_result_exposes_semantic_kind_and_midpoint_target() -> None:
    ctx = ToolContext()
    result = ctx.snap.smart(
        (5.0, 0.0, 0.0),
        (5.0, 0.0),
        ctx,
        extra_targets=[snap.segment("edge.a", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), source=SnapSource.CUSTOM_EDGE, priority=70)],
    )

    assert result.snapped is True
    assert result.kind == SnapKind.MIDPOINT
    assert result.label == "Midpoint"
    assert result.source_id == "edge.a:midpoint"
    assert result.position == (5.0, 0.0, 0.0)


def test_plan_tracer_cursor_style_is_api_owned_by_snap_kind() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(100.0, 100.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(200.0, 100.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(150.0, 100.0)), ctx)

    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["snap_kind"] == SnapKind.MIDPOINT.value
    assert cursor.metadata["snap_label"] == "Midpoint"
    assert cursor.metadata["point_style"] == "ring"
    assert cursor.metadata["snap_show_label"] is True
    assert tool._state.last_snap_kind == SnapKind.MIDPOINT.value
    assert tool._state.last_snap_label.startswith("tool_temp_edge")

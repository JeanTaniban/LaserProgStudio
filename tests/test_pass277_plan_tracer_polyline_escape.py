from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.constants import _MODE_LINE, _MODE_POLYLINE, _TOOLBOX_ID
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def __init__(self) -> None:
        self.meshes = []

    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=1)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    ctx.document.bind(ctx.scene)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_escape_cancels_current_line_placement_without_switching_to_modify() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, _MODE_LINE, reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_line_start_id is not None

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="escape"), ctx) is True

    assert tool._state.active_tool == _MODE_LINE
    assert tool._state.pending_line_start_id is None
    toolbox = ctx.overlay.window(_TOOLBOX_ID)
    assert toolbox is not None and toolbox.visible is True


def test_polyline_adds_chained_segments_until_escape() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, _MODE_POLYLINE, reason="test", render=False)

    _click(tool, ctx, 10.0, 10.0)
    assert tool._state.pending_polyline_last_id is not None
    assert len(tool._state.sketch.lines) == 0

    _click(tool, ctx, 50.0, 10.0)
    assert len(tool._state.sketch.lines) == 1
    first_pending = tool._state.pending_polyline_last_id

    _click(tool, ctx, 50.0, 40.0)
    assert len(tool._state.sketch.lines) == 2
    assert tool._state.pending_polyline_last_id != first_pending

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="escape"), ctx) is True
    assert tool._state.active_tool == _MODE_POLYLINE
    assert tool._state.pending_polyline_last_id is None
    assert len(tool._state.sketch.lines) == 2


def test_polyline_double_click_finishes_chain_without_adding_segment() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, _MODE_POLYLINE, reason="test", render=False)

    _click(tool, ctx, 10.0, 10.0)
    _click(tool, ctx, 50.0, 10.0)
    assert len(tool._state.sketch.lines) == 1
    assert tool._state.pending_polyline_last_id is not None

    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_DOUBLE_CLICK, screen_pos=(50.0, 10.0), button=MouseButton.LEFT), ctx) is True

    assert tool._state.active_tool == _MODE_POLYLINE
    assert tool._state.pending_polyline_last_id is None
    assert len(tool._state.sketch.lines) == 1


def test_qt_double_click_is_forwarded_to_creator_tool_instead_of_only_being_consumed() -> None:
    source = Path("src/laserprog_studio/application/creator_pointer_interaction.py").read_text(encoding="utf-8")
    controller = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")

    assert "QEvent.MouseButtonDblClick" in source
    assert "ToolEventType.MOUSE_DOUBLE_CLICK" in source
    double_click_branch = controller.split("QEvent.MouseButtonDblClick", 1)[0]
    assert "handle_creator_tool_pointer_event" in double_click_branch

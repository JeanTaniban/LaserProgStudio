from __future__ import annotations

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _SurfaceScene:
    def __init__(self, *, hit: bool = True, normal=(0.0, 1.0, 0.0)) -> None:
        self.hit = bool(hit)
        self.normal = normal

    def pick_face_at(self, screen_pos, **_filters):
        if not self.hit:
            return PickResult.none(screen_pos)
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), 5.0, float(y)),
            object_id="panel_face",
            object_index=2,
            element_index=9,
            normal=self.normal,
        )


class _Owner:
    def __init__(self) -> None:
        self.align_calls: list[dict[str, object]] = []
        self.fixed_view_calls: list[str] = []

    def _set_fixed_orthographic_view(self, view: str) -> None:
        self.fixed_view_calls.append(str(view))

    def align_camera_to_plan_surface(self, *, origin, normal, up_axis=None) -> None:
        self.align_calls.append({"origin": origin, "normal": normal, "up_axis": up_axis})


def _ctx(*, hit: bool = True, normal=(0.0, 1.0, 0.0)) -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _SurfaceScene(hit=hit, normal=normal)
    ctx.owner = _Owner()
    ctx.pick.bind_context(ctx)
    return ctx


def _left_press(x: float = 10.0, y: float = 20.0) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT)


def test_open_keeps_current_view_until_user_selects_surface() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()

    tool.on_open(ctx)

    assert tool._state.plane is None
    assert ctx.owner.fixed_view_calls == []
    assert ctx.owner.align_calls == []
    assert ctx.overlay.window("plan_trace_2d.anchor_prompt") is not None


def test_surface_click_locks_arbitrary_face_plane_and_aligns_camera() -> None:
    ctx = _ctx(normal=(0.0, 1.0, 0.0))
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)

    assert tool.on_event(_left_press(), ctx) is True

    assert tool._state.phase == "draw"
    assert tool._state.plane is not None
    assert tool._state.plane.normal == (0.0, 1.0, 0.0)
    assert tool._state.plane.depth == 5.0
    assert ctx.owner.fixed_view_calls == []
    assert len(ctx.owner.align_calls) == 1
    assert ctx.owner.align_calls[0]["normal"] == (0.0, 1.0, 0.0)
    assert ctx.overlay.window("plan_trace_2d.toolbox") is not None


def test_miss_locks_ground_origin_plane_and_aligns_top_camera() -> None:
    ctx = _ctx(hit=False)
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)

    assert tool.on_event(_left_press(), ctx) is True

    assert tool._state.phase == "draw"
    assert tool._state.plane is not None
    assert tool._state.plane.normal == (0.0, 0.0, 1.0)
    assert tool._state.plane.depth == 0.0
    assert tool._state.anchor_world == (0.0, 0.0, 0.0)
    assert len(ctx.owner.align_calls) == 1
    assert ctx.owner.align_calls[0]["origin"] == (0.0, 0.0, 0.0)
    assert ctx.owner.align_calls[0]["normal"] == (0.0, 0.0, 1.0)
    assert ctx.overlay.window("plan_trace_2d.toolbox") is not None
    assert "ground" in (ctx.status.latest().message or "").lower()


def test_escape_without_pending_drawing_switches_to_modify_not_close() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool.on_event(_left_press(), ctx)

    assert tool._state.active_tool == "point"
    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="escape"), ctx) is True

    assert tool._state.active_tool == "modify"
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.modify"
    assert ctx.overlay.window("plan_trace_2d.toolbox") is not None


def test_escape_with_pending_line_cancels_placement_and_keeps_line_mode() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool.on_event(_left_press(), ctx)
    tool._services.mode_state._set_active_tool(ctx, "line", reason="test", render=False)

    tool.on_event(_left_press(30.0, 40.0), ctx)
    assert tool._state.pending_line_start_id is not None
    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="escape"), ctx) is True

    assert tool._state.pending_line_start_id is None
    assert tool._state.active_tool == "line"
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.line"

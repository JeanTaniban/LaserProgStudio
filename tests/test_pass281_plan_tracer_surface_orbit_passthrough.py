from __future__ import annotations

from pathlib import Path

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _SurfaceScene:
    def __init__(self, *, hit: bool = True) -> None:
        self.hit = hit

    def pick_face_at(self, screen_pos, **_filters):
        if not self.hit:
            return PickResult.none(screen_pos)
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), 3.0, float(y)),
            object_id="candidate_face",
            object_index=1,
            element_index=4,
            normal=(0.0, 1.0, 0.0),
        )


class _Owner:
    def __init__(self) -> None:
        self.align_calls: list[dict[str, object]] = []
        self._qt_click_pos = (999.0, 999.0)
        self._qt_click_time = 42.0

    def align_camera_to_plan_surface(self, *, origin, normal, up_axis=None) -> None:
        self.align_calls.append({"origin": origin, "normal": normal, "up_axis": up_axis})


def _ctx(*, hit: bool = True) -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _SurfaceScene(hit=hit)
    ctx.owner = _Owner()
    ctx.pick.bind_context(ctx)
    return ctx


def _press(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT)


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), button=MouseButton.LEFT)


def test_initial_surface_press_is_passthrough_so_camera_can_orbit() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)

    assert tool.wants_pointer_press_passthrough(_press(10.0, 20.0), ctx) is True

    assert tool._state.plane is None
    assert tool._state.surface_pick_press_screen_pos == (10.0, 20.0)
    assert ctx.owner.align_calls == []


def test_click_like_release_after_passthrough_locks_surface() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert tool.wants_pointer_press_passthrough(_press(10.0, 20.0), ctx) is True

    assert tool.on_event(_release(13.0, 22.0), ctx) is True

    assert tool._state.phase == "draw"
    assert tool._state.plane is not None
    assert ctx.owner.align_calls
    assert ctx.owner._qt_click_pos is None
    assert ctx.owner._qt_click_time == 0.0


def test_drag_release_after_passthrough_is_not_consumed_or_picked() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert tool.wants_pointer_press_passthrough(_press(10.0, 20.0), ctx) is True

    assert tool.on_event(_release(80.0, 60.0), ctx) is False

    assert tool._state.phase == "pick_height"
    assert tool._state.plane is None
    assert ctx.owner.align_calls == []


def test_creator_pointer_bridge_has_press_passthrough_hook() -> None:
    source = Path("src/laserprog_studio/application/creator_pointer_interaction.py").read_text(encoding="utf-8")
    plan_tool = Path("src/laserprog_studio/tooling/plan_trace_2d_tool.py").read_text(encoding="utf-8")

    assert "def _creator_press_passthrough_requested" in source
    assert "wants_pointer_press_passthrough" in source
    assert "QEvent.MouseButtonPress and _creator_press_passthrough_requested" in source
    assert "def wants_pointer_press_passthrough" in plan_tool

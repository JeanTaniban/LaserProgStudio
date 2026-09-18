from __future__ import annotations

from types import SimpleNamespace

import pytest

from laserprog_studio.application.creator_pointer_interaction import (
    creator_camera_navigation_active,
    handle_creator_tool_pointer_event,
)
from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Scene:
    def pick_face_at(self, screen_pos, **_kwargs):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 0.0), object_id="ground", object_index=0)


def _open() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    ctx.scene = _Scene()
    ctx.pick.bind_context(ctx)
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT), ctx)
    return tool, ctx


def _add_point(tool: PlanTrace2DCreatorTool, xy: tuple[float, float]):
    point_id = f"plan_trace:point:{tool._state.next_point_index:04d}"
    tool._state.next_point_index += 1
    return tool._state.sketch.add_point(xy, point_id=point_id)


def _selected_line(tool: PlanTrace2DCreatorTool, ctx: ToolContext):
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (10.0, 0.0))
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(line.id))
    return p0, p1, line


def test_v138_native_press_on_promoted_support_point_preserves_group_selection() -> None:
    tool, ctx = _open()
    p0, p1, line = _selected_line(tool, ctx)
    press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(0.0, 0.0),
        world_pos=(0.0, 0.0, 0.0),
        button=MouseButton.LEFT,
    )

    assert tool.wants_native_actor_interaction(press, ctx)
    result = handle_native_creator_ui_event(
        press,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )

    assert result.action == "grab"
    assert set(result.grabbed_ids) == {p0.id, p1.id}
    assert tool._services.sketch_sync._line_actor_id(line.id) in ctx.selection.ids()


def test_v138_ctrl_drag_rotates_whole_selection_around_grabbed_point() -> None:
    tool, ctx = _open()
    p0, p1, _line = _selected_line(tool, ctx)
    press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(0.0, 0.0),
        world_pos=(0.0, 0.0, 0.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"ctrl"}),
    )
    assert tool.wants_native_actor_interaction(press, ctx)
    result = handle_native_creator_ui_event(
        press,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )
    tool.on_native_interaction_result(press, ctx, result)

    move = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(180.0, 0.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"ctrl"}),
    )
    drag = handle_native_creator_ui_event(
        move,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )

    assert drag.moved == 2
    assert tool._state.sketch.points[p0.id].position == pytest.approx((0.0, 0.0))
    assert tool._state.sketch.points[p1.id].position == pytest.approx((0.0, 10.0), abs=1.0e-8)


def test_v138_releasing_ctrl_resumes_translation_without_pivot_jump() -> None:
    tool, ctx = _open()
    p0, p1, _line = _selected_line(tool, ctx)
    press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(0.0, 0.0),
        world_pos=(0.0, 0.0, 0.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"ctrl"}),
    )
    assert tool.wants_native_actor_interaction(press, ctx)
    result = handle_native_creator_ui_event(
        press,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )
    tool.on_native_interaction_result(press, ctx, result)
    rotate = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(180.0, 0.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"ctrl"}),
    )
    handle_native_creator_ui_event(
        rotate,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )
    before = tool._state.sketch.points[p0.id].position, tool._state.sketch.points[p1.id].position

    release_ctrl = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(180.0, 0.0),
        button=MouseButton.LEFT,
    )
    handle_native_creator_ui_event(
        release_ctrl,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )
    after = tool._state.sketch.points[p0.id].position, tool._state.sketch.points[p1.id].position
    assert after[0] == pytest.approx(before[0])
    assert after[1] == pytest.approx(before[1])

    translate = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(230.0, 50.0),
        button=MouseButton.LEFT,
    )
    handle_native_creator_ui_event(
        translate,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )
    moved = tool._state.sketch.points[p0.id].position, tool._state.sketch.points[p1.id].position
    assert moved[0][0] == pytest.approx(before[0][0] + 50.0)
    assert moved[0][1] == pytest.approx(before[0][1] + 50.0)
    assert moved[1][0] == pytest.approx(before[1][0] + 50.0)
    assert moved[1][1] == pytest.approx(before[1][1] + 50.0)


class _Qt:
    NoButton = 0
    LeftButton = 1
    MiddleButton = 2
    RightButton = 4
    ShiftModifier = 8
    ControlModifier = 16
    AltModifier = 32


class _QEvent:
    MouseButtonPress = 1
    MouseMove = 2
    MouseButtonRelease = 3
    MouseButtonDblClick = 4


class _MouseEvent:
    def __init__(self, *, button=_Qt.NoButton, modifiers=0):
        self._button = button
        self._modifiers = modifiers

    def button(self):
        return self._button

    def modifiers(self):
        return self._modifiers


class _Plotter:
    def height(self):
        return 500


class _Owner:
    TOOL_NONE = "none"

    def __init__(self):
        self.context = SimpleNamespace()
        self.active_tool = "plan_trace"
        self.plotter = _Plotter()
        self._right_context_candidate = False
        self._right_pan_active = False

    def _display_to_world_at_depth(self, x, y, depth):
        return (float(x), float(y), float(depth))

    def _world_to_display(self, point):
        return (float(point[0]), float(point[1]), float(point[2]))


class _ToolWrapper:
    id = "plan_trace"

    def __init__(self, creator, ctx):
        self.creator = creator
        self._ctx = ctx

    def tool_context(self, _context):
        return self._ctx

    def on_event(self, event, _context):
        return self.creator.on_event(event, self._ctx)


def test_v138_shift_box_drag_is_not_stolen_by_camera_and_releases_immediately(monkeypatch) -> None:
    tool, ctx = _open()
    _selected_line(tool, ctx)
    owner = _Owner()
    wrapper = _ToolWrapper(tool, ctx)
    shown: list[tuple[float, float, float, float]] = []
    hidden: list[bool] = []

    import laserprog_studio.application.creator_box_selection_overlay as overlay_module

    monkeypatch.setattr(
        overlay_module,
        "sync_creator_selection_box_overlay",
        lambda _owner, _ctx: shown.append(_ctx.selection_box.state.rect.as_tuple()),
    )
    monkeypatch.setattr(
        overlay_module,
        "hide_creator_selection_box_overlay",
        lambda _owner: hidden.append(True),
    )

    assert handle_creator_tool_pointer_event(
        owner,
        wrapper,
        _QEvent.MouseButtonPress,
        _MouseEvent(button=_Qt.LeftButton, modifiers=_Qt.ShiftModifier),
        100.0,
        100.0,
        _Qt.LeftButton,
        Qt=_Qt,
        QEvent=_QEvent,
    )
    assert ctx.selection_box.pending

    assert handle_creator_tool_pointer_event(
        owner,
        wrapper,
        _QEvent.MouseMove,
        _MouseEvent(modifiers=_Qt.ShiftModifier),
        160.0,
        150.0,
        _Qt.LeftButton,
        Qt=_Qt,
        QEvent=_QEvent,
    )
    assert ctx.selection_box.active
    assert shown[-1] == (100.0, 100.0, 160.0, 150.0)
    assert not creator_camera_navigation_active(owner)

    assert handle_creator_tool_pointer_event(
        owner,
        wrapper,
        _QEvent.MouseButtonRelease,
        _MouseEvent(button=_Qt.LeftButton, modifiers=_Qt.ShiftModifier),
        160.0,
        150.0,
        _Qt.NoButton,
        Qt=_Qt,
        QEvent=_QEvent,
    )
    assert not ctx.selection_box.pending
    assert hidden
    assert not creator_camera_navigation_active(owner)

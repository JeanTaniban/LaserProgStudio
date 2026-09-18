from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.application.creator_pointer_interaction import (
    begin_creator_camera_navigation,
    creator_camera_navigation_active,
    finish_creator_camera_navigation,
    handle_creator_tool_pointer_event,
)
from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Qt:
    LeftButton = 1
    MiddleButton = 2
    RightButton = 4
    NoButton = 0
    ShiftModifier = 8
    ControlModifier = 16
    AltModifier = 32


class _QEvent:
    MouseButtonPress = 1
    MouseMove = 2
    MouseButtonRelease = 3
    MouseButtonDblClick = 4


class _MoveEvent:
    def buttons(self):
        return _Qt.NoButton

    def modifiers(self):
        return _Qt.NoButton


def _plane() -> LockedPlaneSpec:
    return LockedPlaneSpec(
        view=FixedPlanarView.TOP,
        normal=(0.0, 0.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        v_axis=(0.0, 1.0, 0.0),
        depth=0.0,
    )


def test_qvtk_nobutton_move_stays_in_camera_fast_path() -> None:
    ctx = ToolContext()
    calls = {"begin": 0, "tool_event": 0}

    class _Tool:
        def tool_context(self, _context):
            return ctx

        def on_camera_interaction_begin(self, _ctx, **_payload):
            calls["begin"] += 1

        def on_event(self, *_args, **_kwargs):
            calls["tool_event"] += 1
            raise AssertionError("camera-owned move must not reach Creator hover/snap")

    tool = _Tool()
    owner = SimpleNamespace(
        context=SimpleNamespace(),
        _viewport_pointer_buttons_down=True,
        _right_pan_active=True,
    )

    handled = handle_creator_tool_pointer_event(
        owner,
        tool,
        _QEvent.MouseMove,
        _MoveEvent(),
        410.0,
        260.0,
        _Qt.NoButton,
        Qt=_Qt,
        QEvent=_QEvent,
    )

    assert handled is False
    assert creator_camera_navigation_active(owner) is True
    assert owner._creator_camera_navigation_mode == "pan"
    assert calls == {"begin": 1, "tool_event": 0}



def test_pending_right_context_candidate_does_not_steal_plan_tracer_pan_threshold() -> None:
    ctx = ToolContext()
    calls = {"begin": 0, "tool_event": 0}

    class _Tool:
        id = "plan_trace"

        def tool_context(self, _context):
            return ctx

        def on_camera_interaction_begin(self, _ctx, **_payload):
            calls["begin"] += 1

        def on_event(self, *_args, **_kwargs):  # pragma: no cover - failure path
            calls["tool_event"] += 1
            raise AssertionError("pending right-click context must be resolved by the controller, not Creator")

    owner = SimpleNamespace(
        context=SimpleNamespace(),
        active_tool="plan_trace",
        _right_context_candidate=True,
        _right_pan_active=False,
    )

    handled = handle_creator_tool_pointer_event(
        owner,
        _Tool(),
        _QEvent.MouseMove,
        _MoveEvent(),
        416.0,
        268.0,
        _Qt.RightButton,
        Qt=_Qt,
        QEvent=_QEvent,
    )

    assert handled is False
    assert creator_camera_navigation_active(owner) is False
    assert calls == {"begin": 0, "tool_event": 0}

def test_camera_end_defers_plan_tracer_cursor_catchup_until_real_pointer_event() -> None:
    ctx = ToolContext()
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = _plane()
    calls: list[tuple[tuple[float, float] | None, bool]] = []

    def _update_cursor(_ctx, event, *, render):
        calls.append((event.screen_pos, bool(render)))

    tool._services.snap._update_cursor = _update_cursor
    tool.on_camera_interaction_begin(ctx, mode="pan", screen_pos=(10.0, 20.0))

    # Defensive direct-call gate: even a stray event must not trigger snap work.
    assert tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_MOVE,
            screen_pos=(40.0, 50.0),
            button=MouseButton.NONE,
        ),
        ctx,
    ) is False
    assert calls == []

    tool.on_camera_interaction_end(ctx, mode="pan", screen_pos=(80.0, 90.0))

    assert calls == []
    assert tool._state.camera_interaction_active is False


def test_zoom_debounce_only_latest_generation_can_resume_tool() -> None:
    ctx = ToolContext()
    calls = {"begin": 0, "end": 0}

    class _Tool:
        def tool_context(self, _context):
            return ctx

        def on_camera_interaction_begin(self, _ctx, **_payload):
            calls["begin"] += 1

        def on_camera_interaction_end(self, _ctx, **_payload):
            calls["end"] += 1

    tool = _Tool()
    owner = SimpleNamespace(context=SimpleNamespace())
    first = begin_creator_camera_navigation(owner, tool, mode="zoom", screen_pos=(1.0, 2.0), renew=True)
    second = begin_creator_camera_navigation(owner, tool, mode="zoom", screen_pos=(3.0, 4.0), renew=True)

    assert first != second
    assert finish_creator_camera_navigation(owner, tool, generation=first) is False
    assert creator_camera_navigation_active(owner) is True
    assert finish_creator_camera_navigation(owner, tool, generation=second) is True
    assert calls == {"begin": 1, "end": 1}


class _ButtonEvent:
    def __init__(self, button=_Qt.LeftButton, modifiers=_Qt.NoButton):
        self._button = button
        self._modifiers = modifiers

    def button(self):
        return self._button

    def modifiers(self):
        return self._modifiers


def test_stale_viewport_button_latch_does_not_start_camera_navigation() -> None:
    ctx = ToolContext()
    calls = {"tool_event": 0}

    class _Tool:
        def tool_context(self, _context):
            return ctx

        def on_event(self, *_args, **_kwargs):
            calls["tool_event"] += 1
            return True

    owner = SimpleNamespace(
        context=SimpleNamespace(),
        _viewport_pointer_buttons_down=True,
        _right_pan_active=False,
    )

    handled = handle_creator_tool_pointer_event(
        owner,
        _Tool(),
        _QEvent.MouseMove,
        _MoveEvent(),
        120.0,
        130.0,
        _Qt.NoButton,
        Qt=_Qt,
        QEvent=_QEvent,
    )

    assert handled is True
    assert calls == {"tool_event": 1}
    assert creator_camera_navigation_active(owner) is False


def test_camera_owned_release_can_finish_passthrough_click_immediately() -> None:
    ctx = ToolContext()
    calls = {"release": 0, "end": 0}

    class _Tool:
        def tool_context(self, _context):
            return ctx

        def wants_pointer_release_passthrough(self, event, _ctx):
            return event.button == MouseButton.LEFT

        def on_event(self, event, _context):
            assert event.type == ToolEventType.MOUSE_RELEASE
            calls["release"] += 1
            return True

        def on_camera_interaction_end(self, _ctx, **_payload):
            calls["end"] += 1

    tool = _Tool()
    owner = SimpleNamespace(context=SimpleNamespace())
    begin_creator_camera_navigation(owner, tool, mode="orbit", screen_pos=(10.0, 10.0))

    handled = handle_creator_tool_pointer_event(
        owner,
        tool,
        _QEvent.MouseButtonRelease,
        _ButtonEvent(_Qt.LeftButton),
        12.0,
        11.0,
        _Qt.LeftButton,
        Qt=_Qt,
        QEvent=_QEvent,
    )

    assert handled is True
    assert creator_camera_navigation_active(owner) is False
    assert calls == {"release": 1, "end": 1}


def test_plan_tracer_recovers_if_tool_state_outlives_owner_camera_state() -> None:
    ctx = ToolContext()
    owner = SimpleNamespace()
    ctx.owner = owner
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = _plane()
    tool._state.camera_interaction_active = True

    calls = []

    def _update_cursor(_ctx, event, *, render):
        calls.append((event.screen_pos, bool(render)))

    tool._services.snap._update_cursor = _update_cursor

    assert tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_MOVE,
            screen_pos=(33.0, 44.0),
            button=MouseButton.NONE,
        ),
        ctx,
    ) in {False, True}
    assert tool._state.camera_interaction_active is False
    assert calls == [((33.0, 44.0), True)]


def test_controller_release_clears_pointer_latch_from_released_button() -> None:
    source = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")

    assert "released_button = event.button()" in source
    assert "released_button in {Qt.LeftButton, Qt.MiddleButton, Qt.RightButton}" in source
    assert "subsequent plain hover moves look like camera drags" in source

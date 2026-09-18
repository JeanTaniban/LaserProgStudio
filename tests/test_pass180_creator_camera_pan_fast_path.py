# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.application.creator_pointer_interaction import handle_creator_tool_pointer_event
from laserprog_studio.tool_api.gizmos import build_creator_ui_motifs
from laserprog_studio.tool_core import ToolContext


class Qt:
    LeftButton = 1
    MiddleButton = 2
    RightButton = 4
    NoButton = 0
    ShiftModifier = 8
    ControlModifier = 16
    AltModifier = 32


class QEvent:
    MouseButtonPress = 1
    MouseMove = 2
    MouseButtonRelease = 3


class MoveEvent:
    def __init__(self, buttons: int) -> None:
        self._buttons = buttons

    def buttons(self):
        return self._buttons

    def modifiers(self):
        return Qt.NoButton


def _assert_camera_move_is_not_forwarded(buttons: int) -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="gizmo_catalog", families=("point_styles", "actor_interactions"))
    ctx.selection.state.grab_active = False

    def forbidden_hit_test(*_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("button-down camera navigation must not hit-test Creator actors")

    ctx.selection.hit_test = forbidden_hit_test  # type: ignore[method-assign]

    class Tool:
        def tool_context(self, _context):
            return ctx

        def on_event(self, *_args, **_kwargs):  # pragma: no cover - failure path
            raise AssertionError("button-down camera navigation must not be forwarded to Creator runtime")

    owner = SimpleNamespace(context=SimpleNamespace())
    handled = handle_creator_tool_pointer_event(
        owner,
        Tool(),
        QEvent.MouseMove,
        MoveEvent(buttons),
        240.0,
        120.0,
        buttons,
        Qt=Qt,
        QEvent=QEvent,
    )
    assert handled is False


def test_right_button_pan_skips_creator_hover_hit_test() -> None:
    _assert_camera_move_is_not_forwarded(Qt.RightButton)


def test_middle_button_pan_skips_creator_hover_hit_test() -> None:
    _assert_camera_move_is_not_forwarded(Qt.MiddleButton)


def test_multi_button_camera_navigation_skips_creator_hover_hit_test() -> None:
    _assert_camera_move_is_not_forwarded(Qt.RightButton | Qt.MiddleButton)

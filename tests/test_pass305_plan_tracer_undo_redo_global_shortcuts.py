from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.application.creator_global_shortcuts import (
    dispatch_creator_key_shortcut,
    handle_creator_redo_shortcut,
    handle_creator_undo_shortcut,
)
from laserprog_studio.tool_core import ToolEventType


class _Tool:
    def __init__(self, handled: bool = True) -> None:
        self.handled = handled
        self.events = []

    def tool_context(self, context):
        return context

    def on_event(self, event, context):
        self.events.append(event)
        return self.handled


def test_pass305_undo_redo_actions_route_to_active_creator_first(monkeypatch) -> None:
    tool = _Tool(True)
    monkeypatch.setattr("laserprog_studio.tooling.registry.get_studio_tool", lambda _active: tool)
    owner = SimpleNamespace(active_tool="plan_trace_2d", TOOL_NONE="none", context=object(), undo_scene=lambda: (_ for _ in ()).throw(AssertionError("scene undo should not run")), redo_scene=lambda: (_ for _ in ()).throw(AssertionError("scene redo should not run")))

    handle_creator_undo_shortcut(owner)
    handle_creator_redo_shortcut(owner)

    assert [event.type for event in tool.events] == [ToolEventType.KEY_PRESS, ToolEventType.KEY_PRESS]
    assert [(event.key, event.ctrl, event.shift) for event in tool.events] == [("z", True, False), ("y", True, False)]


def test_pass305_undo_redo_falls_back_to_scene_when_tool_does_not_handle(monkeypatch) -> None:
    tool = _Tool(False)
    calls = []
    monkeypatch.setattr("laserprog_studio.tooling.registry.get_studio_tool", lambda _active: tool)
    owner = SimpleNamespace(active_tool="box", TOOL_NONE="none", context=object(), undo_scene=lambda: calls.append("undo"), redo_scene=lambda: calls.append("redo"))

    handle_creator_undo_shortcut(owner)
    handle_creator_redo_shortcut(owner)

    assert calls == ["undo", "redo"]


def test_pass305_dispatch_preserves_ctrl_shift_z_redo(monkeypatch) -> None:
    tool = _Tool(True)
    monkeypatch.setattr("laserprog_studio.tooling.registry.get_studio_tool", lambda _active: tool)
    owner = SimpleNamespace(active_tool="plan_trace_2d", TOOL_NONE="none", context=object())

    assert dispatch_creator_key_shortcut(owner, "z", modifiers=frozenset({"ctrl", "shift"})) is True
    assert tool.events[-1].key == "z"
    assert tool.events[-1].ctrl is True
    assert tool.events[-1].shift is True


def test_pass305_actions_menu_uses_creator_aware_undo_redo_handlers() -> None:
    source = Path("src/laserprog_studio/ui/actions_menus.py").read_text(encoding="utf-8")
    assert "handle_creator_undo_shortcut" in source
    assert "handle_creator_redo_shortcut" in source
    assert "self.act_undo.triggered.connect(lambda _checked=False: handle_creator_undo_shortcut(self))" in source
    assert "self.act_redo.triggered.connect(lambda _checked=False: handle_creator_redo_shortcut(self))" in source


def test_pass305_undo_redo_qactions_remain_enabled_for_creator_tool_shortcuts() -> None:
    source = Path("src/laserprog_studio/ui/transform_controls.py").read_text(encoding="utf-8")
    assert "creator_tool_active" in source
    assert "action_undo = bool(can_undo or creator_tool_active)" in source
    assert "action_redo = bool(can_redo or creator_tool_active)" in source
    assert "btn_project_undo" in source

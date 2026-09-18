from __future__ import annotations

from pathlib import Path


def test_global_escape_action_routes_through_creator_api_before_closing_tool() -> None:
    actions = Path("src/laserprog_studio/ui/actions_menus.py").read_text(encoding="utf-8")
    router = Path("src/laserprog_studio/application/creator_global_shortcuts.py").read_text(encoding="utf-8")

    assert "handle_creator_escape_shortcut" in actions
    assert "self.act_escape.triggered.connect(lambda _checked=False: handle_creator_escape_shortcut(self))" in actions
    assert "self.act_escape.triggered.connect(self.close_active_tool)" not in actions
    assert "def dispatch_creator_key_shortcut" in router
    assert "ToolEvent(ToolEventType.KEY_PRESS, key=str(key_name)" in router
    assert 'dispatch_creator_key_shortcut(owner, "escape")' in router
    assert "owner.close_active_tool()" in router


def test_global_delete_action_uses_same_creator_delete_path_as_overlay_button() -> None:
    actions = Path("src/laserprog_studio/ui/actions_menus.py").read_text(encoding="utf-8")
    router = Path("src/laserprog_studio/application/creator_global_shortcuts.py").read_text(encoding="utf-8")
    plan_tool = Path("src/laserprog_studio/tooling/plan_trace_2d_tool.py").read_text(encoding="utf-8")

    assert "handle_creator_delete_shortcut" in actions
    assert "self.act_delete.triggered.connect(lambda _checked=False: handle_creator_delete_shortcut(self))" in actions
    assert "self.act_delete.triggered.connect(self.delete_selected)" not in actions
    assert 'dispatch_creator_key_shortcut(owner, "delete")' in router
    assert "owner.delete_selected()" in router
    assert "if event.is_delete:" in plan_tool
    assert "_delete_selected_points(ctx)" in plan_tool


def test_toolbar_buttons_use_fixed_slots_between_separators() -> None:
    source = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")

    assert "row.setSpacing(4 if kind == \"toolbar\" else 6)" in source
    assert "toolbar_slot_widths = _toolbar_button_slot_widths(spec)" in source
    assert "toolbar_slot_width = toolbar_slot_widths[index]" in source
    assert "button.setFixedSize(toolbar_slot_width, 66)" in source
    assert "separator.setMinimumHeight(42)" in source

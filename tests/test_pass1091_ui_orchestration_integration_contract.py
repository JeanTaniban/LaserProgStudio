# -*- coding: utf-8 -*-
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_main_window_installs_ui_orchestration_after_building_widgets():
    source = (ROOT / "src/laserprog_studio/window.py").read_text(encoding="utf-8")
    assert "self._build_main_ui()" in source
    assert "self.ui_orchestration.install()" in source
    assert source.index("self._build_main_ui()") < source.index("self.ui_orchestration.install()")


def test_tool_lifecycle_publishes_semantic_events_and_contextual_guidance():
    source = (ROOT / "src/laserprog_studio/application/tool_lifecycle_controller.py").read_text(encoding="utf-8")
    for event_name in (
        "tool.open.requested",
        "tool.opened",
        "tool.open.blocked_by_active_tool",
        "tool.applied",
        "tool.cancelled",
        "tool.closed",
    ):
        assert event_name in source
    assert "show_active_tool_conflict" in source
    assert "show_contextual_error" in source


def test_view_menu_exposes_layout_manager_and_user_presets():
    source = (ROOT / "src/laserprog_studio/ui/actions_menus.py").read_text(encoding="utf-8")
    assert "Dispositions de l’interface" in source
    assert "Enregistrer la disposition actuelle" in source
    assert "Gérer les dispositions" in source

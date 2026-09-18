from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tool_box_is_hidden_until_a_tool_is_active() -> None:
    panels = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    preview = (ROOT / "src" / "laserprog_studio" / "application" / "preview_controller.py").read_text(encoding="utf-8")
    help_controller = (ROOT / "src" / "laserprog_studio" / "application" / "tool_help_controller.py").read_text(encoding="utf-8")
    assert 'self.tool_idle_panel = QFrame()' in panels
    assert 'self.btn_scene_history = QPushButton("History")' in panels
    assert 'self.btn_tool_help.setEnabled(False); self.btn_tool_help.setVisible(False)' in panels
    assert 'self.tool_box.setVisible(False)' in panels
    assert 'w.preview_label.setText("")' in preview
    assert 'tool_box.setVisible(tool_active)' in preview
    assert 'idle_panel.setVisible(not tool_active)' in preview
    assert 'button.setVisible(bool(active))' in help_controller


def test_inline_history_wiring_was_removed_from_right_tool_stack() -> None:
    factory = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    transform = (ROOT / "src" / "laserprog_studio" / "ui" / "transform_controls.py").read_text(encoding="utf-8")
    preview = (ROOT / "src" / "laserprog_studio" / "application" / "preview_controller.py").read_text(encoding="utf-8")
    assert 'w = QGroupBox("History")' not in factory
    assert 'owner.scene_history_inline_list' not in factory
    assert 'refresh_scene_history_inline_panel' not in transform
    assert 'refresh_scene_history_inline_panel' not in preview

from __future__ import annotations

from pathlib import Path

from laserprog_studio.state import TransformState

ROOT = Path(__file__).resolve().parents[1]


def test_parts_list_keeps_ten_rows_visible() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    assert "visible_part_rows = 10" in source
    assert "parts_list_height = visible_part_rows * part_row_height + 14" in source
    assert "self.mesh_list.setMinimumHeight(parts_list_height)" in source


def test_no_tool_space_is_reserved_for_history_button_only() -> None:
    factory = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    panels = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    preview = (ROOT / "src" / "laserprog_studio" / "application" / "preview_controller.py").read_text(encoding="utf-8")
    assert 'w = QGroupBox("History")' not in factory
    assert "SceneHistoryInlineList" not in factory
    assert 'self.tool_idle_panel = QFrame()' in panels
    assert 'self.tool_box = QGroupBox("Tool")' in panels
    assert "tool_box.setVisible(tool_active)" in preview
    assert "idle_panel.setVisible(not tool_active)" in preview
    assert "refresh_scene_history_inline_panel" not in preview


def test_default_transform_mode_is_translate() -> None:
    assert TransformState().mode == "translate"


def test_toolbar_palette_is_a_real_toggle_not_modal_popup() -> None:
    layout = (ROOT / "src" / "laserprog_studio" / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    palette = (ROOT / "src" / "laserprog_studio" / "ui" / "toolbar_palette.py").read_text(encoding="utf-8")
    controller = (ROOT / "src" / "laserprog_studio" / "application" / "toolbar_controller.py").read_text(encoding="utf-8")
    assert "self.btn_toolbar_palette.setCheckable(True)" in layout
    assert "dialog.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)" in palette
    assert "dialog.show()" in controller
    assert "dialog.exec()" not in controller
    assert "existing is not None and existing.isVisible()" in controller
    assert "The toolbar is limited to {TOOLBAR_MAX_ITEMS} items" in palette

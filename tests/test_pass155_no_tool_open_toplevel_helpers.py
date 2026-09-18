from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_light_transform_overlay_is_embedded_not_qt_tool_window() -> None:
    frame = read("src/laserprog_studio/ui/light_transform/frame.py")
    construction = read("src/laserprog_studio/ui/light_transform/construction.py")

    assert "self.setWindowFlags(Qt.Widget)" in frame
    assert "self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)" not in frame
    assert "LightTransformOverlayFrame(parent, viewport=parent)" in construction
    assert "LightTransformOverlayFrame(self, viewport=parent)" not in construction


def test_creator_inspector_widgets_are_built_with_parents() -> None:
    source = read("src/laserprog_studio/ui/inspector_panel_adapter.py")

    assert "description = QLabel(panel.description, root)" in source
    assert "group = QGroupBox(section.title, root)" in source
    assert "parent: Any = None" in source
    assert "row = QWidget(parent)" in source
    assert "editor = QDoubleSpinBox(row)" in source
    assert "editor = QComboBox(row)" in source
    assert "file_edit = QLineEdit(str(value), editor)" in source
    assert "font_button = QPushButton(\"Font\", editor)" in source


def test_toolbar_dynamic_buttons_are_parented_before_layout_insert() -> None:
    source = read("src/laserprog_studio/application/toolbar_controller.py")

    assert "button = self._item_button(spec, parent=holder)" in source
    assert "def _item_button(self, spec: Any, *, parent: Any = None)" in source
    assert "button = QToolButton(parent)" in source


def test_tool_lifecycle_schedules_unexpected_top_level_guard() -> None:
    source = read("src/laserprog_studio/application/tool_lifecycle_controller.py")
    guard = read("src/laserprog_studio/ui/top_level_window_guard.py")

    assert "from ..ui.top_level_window_guard import schedule_tool_top_level_guard" in source
    assert "schedule_tool_top_level_guard(self.owner, reason=f\"open tool {tool_id}\")" in source
    assert "QApplication.instance()" in guard
    assert "app.topLevelWidgets()" in guard
    assert "widget.hide()" in guard
    assert "QTimer.singleShot(80" in guard

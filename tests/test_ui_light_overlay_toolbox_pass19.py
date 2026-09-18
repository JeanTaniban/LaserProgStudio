from pathlib import Path

from _light_transform_source import read_light_transform_source

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


def test_light_ui_can_be_exited_from_overlay_when_side_panels_are_hidden() -> None:
    source = read_light_transform_source(ROOT)
    assert "self.light_btn_exit_ui = QToolButton(overlay)" in source
    assert "self.light_btn_exit_ui.setObjectName(\"LightOverlayExitButton\")" in source
    assert "self.light_btn_exit_ui.clicked.connect(self._on_light_overlay_exit_ui_clicked)" in source
    assert "def _on_light_overlay_exit_ui_clicked" in source
    assert "self._set_inspector_light_mode(False, \"overlay Full UI button\")" in source
    assert "button.setVisible(full_light)" in source


def test_light_overlay_scale_lock_uses_reserved_slot_and_icon() -> None:
    source = read_light_transform_source(ROOT)
    inspector = (STUDIO / "controllers" / "transform_inspector.py").read_text(encoding="utf-8")
    styles = (STUDIO / "ui" / "actions_menus.py").read_text(encoding="utf-8")
    assert "self.light_scale_ratio_lock_slot = QFrame(overlay)" in source
    assert "setObjectName(\"LightOverlayLockSlot\")" in source
    assert "setFixedSize(48, 42)" in source
    assert "def _light_lock_icon" in source
    assert "def _refresh_light_scale_lock_button" in source
    assert "refresh(locked=locked, is_scale=is_scale, available=available)" in inspector
    assert "QFrame#LightOverlayLockSlot" in styles
    assert "QToolButton#LightOverlayLockButton:checked" in styles


def test_center_toolbox_is_centered_and_styled_as_a_capsule() -> None:
    layout = (STUDIO / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    styles = (STUDIO / "ui" / "actions_menus.py").read_text(encoding="utf-8")
    toolbar = (STUDIO / "application" / "toolbar_controller.py").read_text(encoding="utf-8")
    assert "top.setObjectName(\"ToolboxBar\")" in layout
    assert "self.top_toolbar_host = QWidget(panel)" in layout
    assert "host_l.addWidget(top, 0, Qt.AlignCenter)" in layout
    assert "self.top_toolbar_scroll.setWidgetResizable(True)" in layout
    assert "QFrame#ToolboxBar" in styles
    assert "QToolButton#ToolbarPaletteButton" in styles
    assert "QToolButton[toolbarItem=\"true\"]" in styles
    assert "button.setProperty(\"toolbarItem\", True)" in toolbar


def test_toolbar_palette_closes_on_click_away() -> None:
    source = (STUDIO / "ui" / "toolbar_palette.py").read_text(encoding="utf-8")
    clickaway = (STUDIO / "application" / "toolbar_palette_clickaway.py").read_text(encoding="utf-8")
    assert "class ToolbarPaletteClickAwayFilter" in clickaway
    assert "app.installEventFilter(click_away_filter)" in source
    assert "dialog.geometry().contains(point)" in clickaway
    assert "dialog.close()" in clickaway
    assert "app.removeEventFilter(click_away_filter)" in source

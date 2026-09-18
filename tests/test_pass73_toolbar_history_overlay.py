from __future__ import annotations

import json
from pathlib import Path

from _light_transform_source import read_light_transform_source

from laserprog_studio.services.toolbar_preferences import load_toolbar_preferences, save_toolbar_preferences

ROOT = Path(__file__).resolve().parents[1]


def test_toolbar_layout_is_saved_to_dedicated_json(tmp_path: Path) -> None:
    prefs = tmp_path / "studio_toolbar.json"
    ids = ["tool:primitive", "tool:vent_generator", "modifier:hollow"]
    save_toolbar_preferences(ids, registry_version=3, max_items=18, path=prefs)
    payload = json.loads(prefs.read_text(encoding="utf-8"))
    assert payload["toolbar_item_ids"] == ids
    assert payload["toolbar_registry_version"] == 3
    assert payload["toolbar_max_items"] == 18
    assert load_toolbar_preferences(prefs)["toolbar_item_ids"] == ids


def test_toolbar_controller_loads_and_flushes_json_preferences() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "application" / "toolbar_controller.py").read_text(encoding="utf-8")
    assert "load_toolbar_preferences()" in source
    assert "def save_toolbar_preferences_now" in source
    assert "save_toolbar_preferences(" in source
    assert "w._save_ui_layout_preferences_now()" in source


def test_close_event_flushes_toolbar_preferences() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "controllers" / "camera.py").read_text(encoding="utf-8")
    assert "toolbar_controller.save_toolbar_preferences_now()" in source
    assert "self._save_ui_layout_preferences_now()" in source


def test_idle_tool_corner_is_standalone_history_not_inline_list() -> None:
    panels = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    factory = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    styles = (ROOT / "src" / "laserprog_studio" / "ui" / "actions_menus.py").read_text(encoding="utf-8")
    assert 'self.btn_scene_history = QPushButton("History")' in panels
    assert 'self.btn_tool_help.setVisible(False)' in panels
    assert 'self.tool_box.setVisible(False)' in panels
    assert "SceneHistoryInlineList" not in factory
    assert "QListWidget#SceneHistoryInlineList::item" not in styles
    assert "QFrame#ToolIdlePanel" in styles


def test_light_overlay_uses_floating_composited_surface_instead_of_child_alpha_stacking() -> None:
    source = read_light_transform_source(ROOT)
    styles = (ROOT / "src" / "laserprog_studio" / "ui" / "actions_menus.py").read_text(encoding="utf-8")
    interaction = (ROOT / "src" / "laserprog_studio" / "controllers" / "interaction.py").read_text(encoding="utf-8")
    assert "class LightTransformOverlayFrame" in source
    assert "Qt.Tool | Qt.FramelessWindowHint" in source
    assert "Qt.WA_TranslucentBackground, True" in source
    assert "setAutoFillBackground(False)" in source
    assert "QPainter.CompositionMode_Source" in source
    assert "area.mapToGlobal" in source
    assert "if bool(overlay.isWindow())" in source
    assert "old_geometry.united(overlay.geometry())" in source
    assert "plotter_area" in interaction
    assert "QPainter.CompositionMode_SourceOver" in source
    assert "QColor(23, 26, 31, 242)" in source
    assert "drawRoundedRect" in source
    assert "background-color: transparent" in styles

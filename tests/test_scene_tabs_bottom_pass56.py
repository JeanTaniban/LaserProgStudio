# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401
from _scene_tabs_source import read_scene_tabs_source


ROOT = Path(__file__).resolve().parents[1]


def test_scene_tabs_are_in_bottom_footer_instead_of_camera_help_label() -> None:
    layout_source = (ROOT / "src" / "laserprog_studio" / "ui" / "layout_panels.py").read_text(encoding="utf-8")

    assert "Camera: free view left drag" not in layout_source
    assert "self.scene_tabs_footer = QFrame(panel)" in layout_source
    assert "self.scene_tab_bar = QTabBar(self.scene_tabs_footer)" in layout_source
    assert "self.scene_tabs_layout = QHBoxLayout()" in layout_source
    assert "footer_l.addLayout(self.scene_tabs_layout, 1)" in layout_source
    assert "self.scene_tabs_scroll = QScrollArea" not in layout_source
    assert "self.scene_tab_bar.setVisible(False)" in layout_source
    assert "layout.addWidget(self.plotter_area, 1)" in layout_source
    assert "layout.addWidget(self.scene_tabs_footer)" in layout_source
    assert layout_source.index("layout.addWidget(self.plotter_area, 1)") < layout_source.index("layout.addWidget(self.scene_tabs_footer)")


def test_scene_tabs_have_chrome_like_footer_style_and_new_button() -> None:
    style_source = (ROOT / "src" / "laserprog_studio" / "ui" / "actions_menus.py").read_text(encoding="utf-8")

    assert "QFrame#SceneTabsFooter" in style_source
    assert "QToolButton#SceneNewTabButton" in style_source
    assert "QFrame#SceneTabChrome" in style_source
    assert "QToolButton#SceneTabLabel" in style_source
    assert "border-top-left-radius: 10px" in style_source
    assert "border-top-right-radius: 10px" in style_source
    assert "qproperty-drawBase: 0" in style_source


def test_scene_tabs_visible_strip_is_synchronized_from_project_store() -> None:
    controller_source = read_scene_tabs_source(ROOT)

    assert "def _sync_visible_scene_tab_strip" in controller_source
    assert "SceneTabChrome" in controller_source
    assert "SceneTabLabel" in controller_source
    assert "SceneTabClose" in controller_source
    assert "SceneTabChromeTest" not in controller_source
    assert 'text="TEST"' not in controller_source
    assert "self._sync_visible_scene_tab_strip()" in controller_source
    assert "_clear_hidden_scene_tab_bar" in controller_source
    assert "bar.clear()" not in controller_source


def test_scene_tabs_switch_and_close_can_use_scene_ids_directly() -> None:
    controller_source = read_scene_tabs_source(ROOT)

    assert "def switch_scene_by_id" in controller_source
    assert "def close_scene_by_id" in controller_source
    assert "self.switch_scene_by_id(str(bar.tabData" in controller_source
    assert "self.close_scene_by_id(str(bar.tabData" in controller_source

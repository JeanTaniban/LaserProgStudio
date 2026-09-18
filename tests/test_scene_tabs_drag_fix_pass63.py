# -*- coding: utf-8 -*-
from pathlib import Path

from _scene_tabs_source import read_scene_tabs_source

ROOT = Path(__file__).resolve().parents[1]


def test_visible_scene_tab_label_passes_mouse_events_to_parent_for_drag() -> None:
    source = read_scene_tabs_source(ROOT)

    assert "WA_TransparentForMouseEvents" in source
    assert "Mouse events on that button do not automatically reach the parent" in source
    assert "def update_scene_tab_drag" in source
    assert "def scene_tab_insert_index_at_global_pos" in source
    assert "self._owner.switch_scene_by_id(self._scene_id)" in source
    assert "eventFilter" not in source


def test_scene_tab_drag_reorders_only_on_release_to_avoid_lost_cursor() -> None:
    source = read_scene_tabs_source(ROOT)

    assert "def update_scene_tab_drag_preview" in source
    assert "preview-only" in source
    assert "move_scene_tab_to_index(source_scene_id, int(target_index))" in source
    assert "deletes the source widget" in source
    assert "QApplication.setOverrideCursor" not in source
    assert "self.grabMouse()" in source
    assert "self.releaseMouse()" in source

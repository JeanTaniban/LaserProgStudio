# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from _scene_tabs_source import read_scene_tabs_source

ROOT = Path(__file__).resolve().parents[1]


def test_scene_tab_drag_has_ghost_and_noop_guard_to_prevent_disappearing_tabs() -> None:
    source = read_scene_tabs_source(ROOT)

    assert "def _scene_tab_live_index_is_noop" in source
    assert "return live_insert_index == source_index or live_insert_index == source_index + 1" in source
    assert "if self._scene_tab_live_index_is_noop(source_scene_id, int(target_index))" in source
    assert "return" in source
    assert "last remaining source of intermittent”main tab disappears”" not in source
    assert "main tab disappears" in source


def test_scene_tab_drag_uses_parented_non_interactive_ghost_not_reparenting_source() -> None:
    source = read_scene_tabs_source(ROOT)
    style = (ROOT / "src" / "laserprog_studio" / "ui" / "actions_menus.py").read_text(encoding="utf-8")

    assert "def _create_scene_tab_drag_ghost" in source
    assert "QFrame(footer)" in source
    assert "WA_TransparentForMouseEvents" in source
    assert "def _move_scene_tab_drag_ghost" in source
    assert "def _destroy_scene_tab_drag_ghost" in source
    assert "SceneTabDragGhost" in style

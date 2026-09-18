# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401
from _scene_tabs_source import read_scene_tabs_source


ROOT = Path(__file__).resolve().parents[1]


def test_scene_tab_sync_does_not_call_qtabbar_clear() -> None:
    source = read_scene_tabs_source(ROOT)

    assert "def _clear_hidden_scene_tab_bar" in source
    assert "removeTab(0)" in source
    assert ".clear()" not in source
    assert "sync_hidden_scene_tab_bar" in source


def test_visible_scene_tab_sync_runs_even_if_hidden_bar_fails() -> None:
    source = read_scene_tabs_source(ROOT)

    assert "The hidden synchronization QTabBar must never prevent" in source
    assert "self._sync_visible_scene_tab_strip()" in source
    hidden_error_at = source.index('log_exception("sync_hidden_scene_tab_bar")')
    later_visible_sync_at = source.index("self._sync_visible_scene_tab_strip()", hidden_error_at)
    assert hidden_error_at < later_visible_sync_at

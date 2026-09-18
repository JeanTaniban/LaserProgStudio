from pathlib import Path

from _scene_tabs_source import read_scene_tabs_source


def test_scene_tab_strip_clear_does_not_orphan_visible_widgets() -> None:
    source = read_scene_tabs_source()
    method = source.split("def _clear_visible_scene_tab_strip", 1)[1].split("def _make_scene_tab_widget", 1)[0]
    assert "widget.setParent(None)" not in method
    assert "widget.hide()" in method
    assert "widget.deleteLater()" in method


def test_project_dirty_still_refreshes_tabs_but_without_top_level_flash() -> None:
    source = Path("src/laserprog_studio/project/runtime_bridge.py").read_text(encoding="utf-8")
    assert "owner.sync_scene_tabs()" in source
    scene_tabs = read_scene_tabs_source()
    assert "tiny transient window" in scene_tabs

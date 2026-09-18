from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path


def test_overlay_drag_tracks_dirty_region_and_redraws_once_on_release() -> None:
    source = read_qt_overlay_runtime_source()
    assert "_remember_drag_dirty" in source
    assert "_finalize_drag_redraw" in source
    assert "_invalidate_overlay_backing" in source
    assert "_schedule_overlay_backing_cleanup" in source
    assert "temporarily expose the dirty union" in source
    assert "widget.hide()" in source
    assert "widget.repaint()" in source
    assert "parent.repaint(dirty)" in source


def test_overlay_release_redraw_is_not_on_mouse_move_hot_path() -> None:
    source = read_qt_overlay_runtime_source()
    move_body = source.split("def mouseMoveEvent", 1)[1].split("def mouseReleaseEvent", 1)[0]
    assert "_finalize_drag_redraw" not in move_body
    assert "parent.repaint" not in move_body
    assert "widget.repaint" not in move_body
    assert "qt-move fast-path" in move_body


def test_overlay_docs_explain_release_redraw_contract() -> None:
    overlay_doc = Path("docs/tool_creator/06_overlay_preview_gizmos.md").read_text(encoding="utf-8")
    checklist = Path("docs/tool_creator/09_creator_api_checklist.md").read_text(encoding="utf-8")
    pass_doc = Path("docs/archive/passes/pass187_overlay_release_redraw.md").read_text(encoding="utf-8")
    assert "release redraw" in overlay_doc
    assert "translucent-overlay traces" in overlay_doc
    assert "must not call Qt `repaint()`" in overlay_doc
    assert "single release redraw" in checklist
    assert "release redraw" in pass_doc

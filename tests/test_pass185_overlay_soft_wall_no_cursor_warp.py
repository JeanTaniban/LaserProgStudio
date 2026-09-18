from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path


def test_overlay_adapter_does_not_warp_or_explicitly_grab_cursor() -> None:
    source = read_qt_overlay_runtime_source()
    assert "QCursor" not in source
    assert "setPos" not in source
    assert "grabMouse()" not in source
    assert "soft-wall-rebase" in source
    assert "releaseMouse()" in source  # defensive cleanup of stale platform grabs


def test_overlay_docs_make_soft_wall_runtime_contract_explicit() -> None:
    overlay_doc = Path("docs/tool_creator/06_overlay_preview_gizmos.md").read_text(encoding="utf-8")
    direction_doc = Path("docs/tool_creator/00_creator_ui_direction.md").read_text(encoding="utf-8")
    pass_doc = Path("docs/archive/passes/pass185_overlay_soft_wall_no_cursor_warp.md").read_text(encoding="utf-8")
    assert "soft-wall" in overlay_doc
    assert "OS cursor is never warped" in overlay_doc
    assert "does not warp the OS cursor" in direction_doc
    assert "never call cursor warping" in pass_doc
    assert "must not move Qt widgets" in pass_doc

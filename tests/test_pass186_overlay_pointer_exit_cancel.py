from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.overlay.placement import OverlayRect, pointer_inside_overlay_rect


def test_pointer_inside_overlay_rect_is_strict_to_real_frame() -> None:
    rect = OverlayRect(100, 50, 80, 40)
    assert pointer_inside_overlay_rect(100, 50, rect)
    assert pointer_inside_overlay_rect(179, 89, rect)
    assert not pointer_inside_overlay_rect(180, 89, rect)
    assert not pointer_inside_overlay_rect(179, 90, rect)
    assert not pointer_inside_overlay_rect(99, 50, rect)


def test_qt_overlay_drag_cancels_when_constrained_pointer_leaves_rect() -> None:
    source = read_qt_overlay_runtime_source()
    assert "_pointer_inside_widget_global_rect" in source
    assert "pointer left constrained overlay rect" in source
    assert "_cancel_drag" in source
    assert "_drag_cancelled" in source
    assert "_finish_drag(self, commit=True)" in source
    assert "setPos" not in source
    assert "grabMouse()" not in source


def test_overlay_docs_explain_pointer_exit_cancel_contract() -> None:
    overlay_doc = Path("docs/tool_creator/06_overlay_preview_gizmos.md").read_text(encoding="utf-8")
    direction_doc = Path("docs/tool_creator/00_creator_ui_direction.md").read_text(encoding="utf-8")
    checklist = Path("docs/tool_creator/09_creator_api_checklist.md").read_text(encoding="utf-8")
    pass_doc = Path("docs/archive/passes/pass186_overlay_pointer_exit_cancel.md").read_text(encoding="utf-8")
    assert "pointer leave the real overlay rectangle" in overlay_doc
    assert "clears the pointer offset" in overlay_doc
    assert "pointer leaves the real rectangle" in direction_doc
    assert "pointer-exit cancellation" in checklist
    assert "stale pointer/anchor offset" in pass_doc

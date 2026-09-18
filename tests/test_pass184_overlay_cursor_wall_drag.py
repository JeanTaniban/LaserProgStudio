from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.overlay.placement import OverlayRect, constrain_overlay_drag_position


def test_pass184_live_drag_constraint_blocks_overlap_without_jump() -> None:
    pos = constrain_overlay_drag_position(
        90,
        50,
        20,
        50,
        (50, 40),
        [OverlayRect(80, 40, 90, 80)],
        (400, 260),
        gap=8,
    )
    candidate = OverlayRect(pos[0], pos[1], 50, 40)
    assert not candidate.intersects(OverlayRect(80, 40, 90, 80).expanded(8))
    assert pos == (20, 50)


def test_pass184_live_drag_constraint_slides_along_free_axis() -> None:
    # Diagonal request overlaps the blocker, but the vertical component is free.
    pos = constrain_overlay_drag_position(
        90,
        120,
        20,
        50,
        (50, 40),
        [OverlayRect(80, 40, 90, 80)],
        (400, 260),
        gap=8,
    )
    candidate = OverlayRect(pos[0], pos[1], 50, 40)
    assert not candidate.intersects(OverlayRect(80, 40, 90, 80).expanded(8))
    assert pos == (20, 120)


def test_pass184_qt_overlay_drag_has_soft_wall_fast_path() -> None:
    source = read_qt_overlay_runtime_source()
    assert "constrain_overlay_drag_position" in source
    assert "soft-wall-rebase" in source
    assert "QCursor.setPos" not in source
    assert "grabMouse()" not in source
    assert "Sample moves at about 25 Hz" in source
    assert "parent.update(old_geometry)" not in source
    assert "sync_qt_overlay_windows" not in source.split("def mouseMoveEvent", 1)[1].split("def mouseReleaseEvent", 1)[0]


def test_pass184_docs_explain_native_soft_wall_overlay_drag() -> None:
    overlay_doc = Path("docs/tool_creator/06_overlay_preview_gizmos.md").read_text(encoding="utf-8")
    direction_doc = Path("docs/tool_creator/00_creator_ui_direction.md").read_text(encoding="utf-8")
    checklist = Path("docs/tool_creator/09_creator_api_checklist.md").read_text(encoding="utf-8")
    assert "soft-wall" in overlay_doc
    assert "OS cursor is never warped" in overlay_doc
    assert "soft-wall" in direction_doc
    assert "soft-wall" in checklist

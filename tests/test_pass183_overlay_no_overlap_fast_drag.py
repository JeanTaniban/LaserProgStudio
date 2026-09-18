from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.overlay.placement import OverlayRect, avoid_overlay_overlap, clamp_overlay_position


def test_overlay_position_is_clamped_to_viewport() -> None:
    assert clamp_overlay_position(-100, 900, (120, 80), (400, 300), margin=12) == (12, 208)


def test_overlay_overlap_solver_moves_candidate_out_of_blocker() -> None:
    pos = avoid_overlay_overlap(
        70,
        70,
        (100, 80),
        [OverlayRect(50, 50, 140, 100)],
        (500, 400),
        gap=8,
    )
    candidate = OverlayRect(pos[0], pos[1], 100, 80)
    assert not candidate.intersects(OverlayRect(50, 50, 140, 100).expanded(8))


def test_qt_overlay_adapter_uses_move_fast_path_not_parent_repaint_loop() -> None:
    source = read_qt_overlay_runtime_source()
    assert "qt-move fast-path" in source
    assert "parent.update(old_geometry)" not in source
    assert "parent.update(self.geometry()" not in source
    assert "_avoid_overlap_pos" in source

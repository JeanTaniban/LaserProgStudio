# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path

from _light_transform_source import read_light_transform_source

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "src" / "laserprog_studio" / "ui"
CONTROLLERS = ROOT / "src" / "laserprog_studio" / "controllers"


class LightUIStaticTest(unittest.TestCase):
    def test_main_splitter_allows_left_and_right_collapse(self) -> None:
        source = (UI / "layout_panels.py").read_text(encoding="utf-8")
        self.assertIn("root.setCollapsible(0, True)", source)
        self.assertIn("root.setCollapsible(2, True)", source)
        self.assertNotIn("root.setCollapsible(0, False)", source)

    def test_light_mode_detects_both_side_panes_and_collapses_both(self) -> None:
        source = read_light_transform_source(ROOT)
        self.assertIn("def _sync_ui_layout_state_from_splitter", source)
        self.assertIn("left_size <= threshold and right_size <= threshold", source)
        self.assertIn("def _is_full_light_ui_mode", source)
        self.assertIn("target = [0, max(total, 420), 0]", source)
        self.assertIn("_set_side_panel_compact_minimums(True)", source)

    def test_transform_overlay_depends_on_right_inspector_only(self) -> None:
        source = read_light_transform_source(ROOT)
        self.assertIn("def _is_right_inspector_collapsed", source)
        self.assertIn("def _is_transform_overlay_mode", source)
        self.assertIn("return bool(self._is_right_inspector_collapsed())", source)
        self.assertIn("visible = bool(self._is_transform_overlay_mode())", source)
        self.assertIn("full_light = bool(self._is_full_light_ui_mode())", source)

    def test_tool_lifecycle_restores_previous_compact_layout(self) -> None:
        source = (ROOT / "src" / "laserprog_studio" / "application" / "layout_controller.py").read_text(encoding="utf-8")
        facade = (CONTROLLERS / "layout_restore.py").read_text(encoding="utf-8")
        self.assertIn("LayoutController", facade)
        self.assertIn("compact_overlay", source)
        self.assertIn("target = [int(saved[0]), max(int(saved[1]), 420), int(saved[2])]", source)
        self.assertIn("_set_side_panel_compact_minimums(False)", source)

    def test_splitter_resize_sync_is_debounced_and_does_not_refresh_fields_per_pixel(self) -> None:
        source = read_light_transform_source(ROOT)
        self.assertIn("def _schedule_light_transform_overlay_sync", source)
        self.assertIn("QTimer.singleShot(45, self._run_scheduled_light_transform_overlay_sync)", source)
        self.assertIn("def _run_scheduled_light_transform_overlay_sync", source)
        self.assertIn("sync_fields = bool(visible) and (force or visibility_changed)", source)
        moved_block = source[source.index("def _on_main_splitter_moved"):source.index("def _schedule_light_transform_overlay_sync")]
        self.assertIn("_schedule_light_transform_overlay_sync", moved_block)
        self.assertNotIn("_sync_light_transform_fields", moved_block)
        self.assertNotIn("_sync_light_transform_overlay()", moved_block)

    def test_overlay_position_uses_cached_geometry_not_adjust_size_every_time(self) -> None:
        source = read_light_transform_source(ROOT)
        block = source[source.index("def _position_light_transform_overlay"):source.index("def _set_light_transform_overlay_hover")]
        self.assertIn("_light_overlay_geometry_signature", block)
        self.assertNotIn("adjustSize()", block)


if __name__ == "__main__":
    unittest.main()

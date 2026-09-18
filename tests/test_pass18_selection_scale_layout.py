# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path

from _light_transform_source import read_light_transform_source

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


class Pass18SelectionScaleLayoutTest(unittest.TestCase):
    def test_ctrl_a_and_rectangle_selection_are_batched(self) -> None:
        scene = (STUDIO / "controllers" / "scene.py").read_text(encoding="utf-8")
        interaction = (STUDIO / "controllers" / "interaction.py").read_text(encoding="utf-8")
        box = (STUDIO / "controllers" / "selection_box.py").read_text(encoding="utf-8")
        actions = (STUDIO / "ui" / "actions_menus.py").read_text(encoding="utf-8")
        self.assertIn("def set_selection_indices", scene)
        self.assertIn("def select_all_parts", scene)
        self.assertIn("Ctrl+A", actions)
        self.assertIn("self.select_all_parts()", interaction)
        self.assertIn("class SelectionBoxLayer", box)
        self.assertIn("SelectionBoxOverlay", box)
        self.assertIn("_display_to_qt_xy", box)
        self.assertIn("_indices_intersecting_selection_box", box)
        self.assertIn("set_selection_indices(hits", box)

    def test_scale_ratio_lock_is_shared_by_inspector_overlay_and_gizmo(self) -> None:
        transform_state = (STUDIO / "state" / "transform_state.py").read_text(encoding="utf-8")
        bridge = (STUDIO / "controllers" / "state_bridge.py").read_text(encoding="utf-8")
        inspector = (STUDIO / "controllers" / "transform_inspector.py").read_text(encoding="utf-8")
        tool_panel = (STUDIO / "ui" / "tool_panels.py").read_text(encoding="utf-8")
        light = read_light_transform_source(ROOT)
        drag = (STUDIO / "controllers" / "transform_drag.py").read_text(encoding="utf-8")
        self.assertIn("scale_ratio_locked: bool", transform_state)
        self.assertIn("def scale_ratio_locked", bridge)
        self.assertIn("scale_ratio_lock_check", tool_panel)
        self.assertIn("light_scale_ratio_lock", light)
        self.assertIn("def _propagate_locked_scale_change_from_widgets", inspector)
        self.assertIn("_propagate_locked_scale_change_from_widgets([self.light_x, self.light_y, self.light_z])", light)
        self.assertIn('locked = bool(getattr(self, "scale_ratio_locked", False))', drag)
        self.assertIn('for logical in ("x", "y", "z")', drag)

    def test_layout_transitions_are_coalesced_for_light_ui_and_tool_open_close(self) -> None:
        light = read_light_transform_source(ROOT)
        layout_restore = (STUDIO / "controllers" / "layout_restore.py").read_text(encoding="utf-8")
        layout_controller = (STUDIO / "application" / "layout_controller.py").read_text(encoding="utf-8")
        preview = (STUDIO / "controllers" / "preview_controller.py").read_text(encoding="utf-8")
        lifecycle = (STUDIO / "application" / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
        self.assertIn("def _set_main_splitter_sizes_coalesced", light)
        self.assertIn("splitter.blockSignals(True)", light)
        self.assertIn("_layout_transition_in_progress", light)
        self.assertIn("LayoutController", layout_restore)
        self.assertIn("_set_main_splitter_sizes_coalesced", layout_controller)
        self.assertNotIn("main_splitter.setSizes", layout_controller)
        self.assertIn("_schedule_light_transform_overlay_sync", preview)
        self.assertIn("_schedule_light_transform_overlay_sync", lifecycle)


if __name__ == "__main__":
    unittest.main()

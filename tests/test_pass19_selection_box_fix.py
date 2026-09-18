# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


class Pass19SelectionBoxFixTest(unittest.TestCase):
    def test_selection_box_uses_transparent_overlay_not_native_rubberband(self) -> None:
        box = (STUDIO / "controllers" / "selection_box.py").read_text(encoding="utf-8")
        overlay = (STUDIO / "ui" / "selection_box_overlay.py").read_text(encoding="utf-8")
        self.assertIn("SelectionBoxOverlay", box)
        self.assertNotIn("QRubberBand", box)
        self.assertIn("WA_TransparentForMouseEvents", overlay)
        self.assertIn("WA_TranslucentBackground", overlay)
        self.assertIn("fillRect", overlay)
        self.assertIn("drawRect", overlay)

    def test_selection_box_converts_vtk_display_pixels_to_qt_coordinates(self) -> None:
        box = (STUDIO / "controllers" / "selection_box.py").read_text(encoding="utf-8")
        self.assertIn("def _render_window_pixel_size", box)
        self.assertIn("def _display_to_qt_xy", box)
        self.assertIn("rw.GetSize()", box)
        self.assertIn("qt_h - (float(display_y) * sy)", box)
        self.assertIn("self._display_to_qt_xy(dx, dy)", box)
        self.assertNotIn("height - float(dy)", box)


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

import _path_setup  # noqa: F401
from laserprog_studio.rendering.handles import (
    SPLIT_HANDLE_SHAFT_RADIUS_RATIO,
    SPLIT_HANDLE_TIP_RADIUS_RATIO,
    split_handle_dimensions_from_gizmo_length,
)


class RenderingHandlesTest(unittest.TestCase):
    def test_split_handle_ratio_is_readable_but_still_thin(self) -> None:
        self.assertEqual(SPLIT_HANDLE_SHAFT_RADIUS_RATIO, 0.0105)
        self.assertEqual(SPLIT_HANDLE_TIP_RADIUS_RATIO, 0.0360)
        self.assertGreater(SPLIT_HANDLE_SHAFT_RADIUS_RATIO, 0.0075)
        self.assertLess(SPLIT_HANDLE_SHAFT_RADIUS_RATIO, 0.0200)

    def test_split_handle_dimensions_scale_from_gizmo_length(self) -> None:
        dims = split_handle_dimensions_from_gizmo_length(100.0)
        self.assertEqual(dims.length, 100.0)
        self.assertAlmostEqual(dims.shaft_radius, 1.05)
        self.assertAlmostEqual(dims.tip_radius, 3.6)
        small = split_handle_dimensions_from_gizmo_length(0.0)
        self.assertGreater(small.length, 0.0)
        self.assertGreater(small.shaft_radius, 0.0)


if __name__ == "__main__":
    unittest.main()

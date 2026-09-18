# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPLIT_PLANE = ROOT / "src" / "laserprog_studio" / "controllers" / "split_plane_tool.py"


class SplitPlaneStaticTest(unittest.TestCase):
    def test_split_plane_arrow_uses_transform_gizmo_camera_scale(self) -> None:
        source = SPLIT_PLANE.read_text(encoding="utf-8")
        self.assertIn("def _split_plane_handle_dimensions", source)
        self.assertIn("_gizmo_length_at(origin", source)
        self.assertIn("split_handle_dimensions_from_gizmo_length(gizmo_len)", source)
        self.assertIn("make_arrow_handle_mesh(origin, forward, handle_dims)", source)
        self.assertNotIn("def _make_split_plane_handle_mesh", source)
        self.assertNotIn("pv.Arrow(start=origin, direction=forward, scale=handle_len", source)
        self.assertNotIn("handle_len = max(size * 0.26", source)
        self.assertNotIn("shaft_radius = max(float(size) * 0.0030", source)
        self.assertNotIn("tip_radius = max(float(size) * 0.0100", source)

    def test_split_plane_arrow_block_calls_dimension_helper(self) -> None:
        tree = ast.parse(SPLIT_PLANE.read_text(encoding="utf-8"), filename=str(SPLIT_PLANE))
        calls_helper = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "_split_plane_handle_dimensions":
                    calls_helper = True
                    break
        self.assertTrue(calls_helper, "split plane actor sync should call the camera-aware dimension helper")

    def test_camera_refresh_path_updates_split_handle(self) -> None:
        refresh = (ROOT / "src" / "laserprog_studio" / "controllers" / "interaction_gizmo_refresh.py").read_text(encoding="utf-8")
        camera = (ROOT / "src" / "laserprog_studio" / "controllers" / "camera.py").read_text(encoding="utf-8")
        interaction = (ROOT / "src" / "laserprog_studio" / "controllers" / "interaction.py").read_text(encoding="utf-8")
        self.assertIn("def _refresh_camera_scaled_overlays", refresh)
        self.assertIn("_sync_modifier_plane_actor(render=False)", refresh)
        self.assertIn("_refresh_camera_scaled_overlays(render=False)", camera)
        self.assertIn("_refresh_camera_scaled_overlays(render=True)", interaction)


if __name__ == "__main__":
    unittest.main()

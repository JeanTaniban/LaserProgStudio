from __future__ import annotations

import unittest

import _path_setup  # noqa: F401
from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.domain import MeshMaterial
from laserprog_studio.rendering.display_modes import get_display_mode
from laserprog_studio.rendering.materials import actor_style_for_mesh
from laserprog_studio.state import RenderState


class Mission6DisplayModesTest(unittest.TestCase):
    def test_render_state_tracks_mode_and_edge_toggle(self):
        state = RenderState()
        self.assertEqual(state.display_mode, "wireframe")
        self.assertTrue(state.show_edges_overlay)

    def test_solid_uses_engraving_color_but_material_mode_uses_material(self):
        mesh = WorkMesh(
            name="part",
            vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)],
            triangles=[(0, 1, 2)],
            color="#E53935",
            material=MeshMaterial(base_color="#336699", opacity=0.65, metallic=0.2, roughness=0.8),
        )
        solid = actor_style_for_mesh(mesh, "solid", show_edges=True)
        self.assertEqual(solid.color, (0xE5 / 255.0, 0x39 / 255.0, 0x35 / 255.0))
        self.assertEqual(solid.opacity, 1.0)
        self.assertTrue(solid.show_edges)

        material = actor_style_for_mesh(mesh, get_display_mode("material"), show_edges=False)
        self.assertEqual(material.color, (0x33 / 255.0, 0x66 / 255.0, 0x99 / 255.0))
        self.assertEqual(material.opacity, 0.65)
        self.assertEqual(material.metallic, 0.2)
        self.assertEqual(material.roughness, 0.8)
        self.assertFalse(material.show_edges)

    def test_wireframe_is_edged_surface_not_bare_lines(self):
        mesh = WorkMesh("part", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
        style = actor_style_for_mesh(mesh, "wireframe")
        self.assertEqual(style.representation, "surface")
        self.assertTrue(style.show_edges)


if __name__ == "__main__":
    unittest.main()

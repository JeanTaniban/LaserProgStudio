# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import unittest

import _path_setup  # noqa: F401
from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams, apply_texture_projection, clear_texture_projection, compute_projected_uvs


class TextureProjectionToolTest(unittest.TestCase):
    def _box_mesh(self) -> WorkMesh:
        return WorkMesh(
            name="quad",
            vertices=[(0, 0, 0), (10, 0, 0), (10, 5, 0), (0, 5, 0)],
            triangles=[(0, 1, 2), (0, 2, 3)],
        )

    def test_compute_projected_uvs_matches_vertex_count(self) -> None:
        mesh = self._box_mesh()
        uvs = compute_projected_uvs(mesh, projection_mode="planar")
        self.assertEqual(len(uvs), len(mesh.vertices))
        self.assertEqual(uvs[0], (0.0, 0.0))
        self.assertEqual(uvs[2], (1.0, 1.0))

    def test_apply_texture_projection_attaches_metadata_and_uvs(self) -> None:
        mesh = self._box_mesh()
        params = TextureProjectionParams(texture_id="tex_demo", texture_path=Path("demo.png"), projection_mode="planar", usage="engrave")
        out = apply_texture_projection([mesh], [0], params)
        self.assertIsNotNone(out[0].uvs)
        self.assertEqual(out[0].material.texture_id, "tex_demo")
        self.assertEqual(out[0].texture_projections[0].texture_id, "tex_demo")
        self.assertEqual(out[0].texture_projections[0].texture_path, "demo.png")
        cleared = clear_texture_projection(out, [0])
        self.assertIsNone(cleared[0].uvs)
        self.assertEqual(cleared[0].texture_projections, [])


class TextureProjectionAspectRatioTest(unittest.TestCase):
    def _rect_mesh(self) -> WorkMesh:
        return WorkMesh(
            name="rect",
            vertices=[(0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)],
            triangles=[(0, 1, 2), (0, 2, 3)],
        )

    def test_preserve_aspect_square_image_does_not_stretch_to_wide_face(self) -> None:
        uvs = compute_projected_uvs(
            self._rect_mesh(),
            projection_mode="planar",
            preserve_aspect=True,
            image_width=100,
            image_height=100,
        )
        u_span = max(u for u, _v in uvs) - min(u for u, _v in uvs)
        v_span = max(v for _u, v in uvs) - min(v for _u, v in uvs)
        # v40: ratio-preserving images start clamped inside the face bounds.
        # A square image on a 20x10 face therefore fits height, leaving horizontal
        # room rather than starting oversized/cropped.
        self.assertAlmostEqual(u_span, 2.0)
        self.assertAlmostEqual(v_span, 1.0)

    def test_preserve_aspect_wide_image_keeps_original_ratio(self) -> None:
        uvs = compute_projected_uvs(
            self._rect_mesh(),
            projection_mode="planar",
            preserve_aspect=True,
            image_width=400,
            image_height=100,
        )
        u_span = max(u for u, _v in uvs) - min(u for u, _v in uvs)
        v_span = max(v for _u, v in uvs) - min(v for _u, v in uvs)
        physical_texture_aspect = (20.0 / u_span) / (10.0 / v_span)
        self.assertAlmostEqual(physical_texture_aspect, 4.0)


if __name__ == "__main__":
    unittest.main()


class TextureProjectionPolyDataTest(unittest.TestCase):
    def test_workmesh_to_polydata_exposes_vtk_texture_coordinates(self) -> None:
        try:
            from laserprog_studio.mesh_ops import workmesh_to_polydata
        except Exception as exc:  # pragma: no cover - optional GUI stack
            self.skipTest(str(exc))
        mesh = WorkMesh(
            name="rect",
            vertices=[(0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)],
            triangles=[(0, 1, 2), (0, 2, 3)],
        )
        mesh.uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

        try:
            poly = workmesh_to_polydata(mesh)
        except ModuleNotFoundError as exc:  # pragma: no cover - optional PyVista stack
            self.skipTest(str(exc))
        tcoords = poly.GetPointData().GetTCoords()

        self.assertIsNotNone(tcoords)
        self.assertEqual(tcoords.GetNumberOfTuples(), len(mesh.vertices))


class TextureProjectionFaceDecalTest(unittest.TestCase):
    def _cube_mesh(self) -> WorkMesh:
        # Same triangle layout as the primitive cube style: 12 triangles, 8 vertices.
        v = [
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ]
        t = [
            (0, 1, 2), (0, 2, 3),  # bottom
            (4, 6, 5), (4, 7, 6),  # top
            (0, 4, 5), (0, 5, 1),
            (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3),
            (3, 7, 4), (3, 4, 0),
        ]
        return WorkMesh(name="cube", vertices=v, triangles=t)

    def test_face_click_creates_decal_instead_of_texturing_whole_cube(self) -> None:
        mesh = self._cube_mesh()
        params = TextureProjectionParams(
            texture_id="tex_demo",
            texture_path=Path("demo.png"),
            projection_mode="box",
            usage="engrave",
            coverage_angle_deg=5.0,
            seed_face_index=2,
            projection_origin=(0.0, 0.0, 1.0),
            projection_normal=(0.0, 0.0, -1.0),
            image_width=100,
            image_height=100,
        )
        out = apply_texture_projection([mesh], [0], params)
        self.assertEqual(len(out), 2)
        self.assertIsNone(out[0].uvs)
        decal = out[1]
        self.assertTrue(getattr(decal, "is_texture_decal", False))
        self.assertEqual(getattr(decal, "texture_decal_for"), "cube")
        # Only the two triangles of the clicked coplanar cube face are textured.
        self.assertEqual(len(decal.triangles), 2)
        self.assertIsNotNone(decal.uvs)
        self.assertEqual(len(decal.uvs), len(decal.vertices))

    def test_clear_base_mesh_removes_its_texture_decal(self) -> None:
        mesh = self._cube_mesh()
        params = TextureProjectionParams(
            texture_id="tex_demo",
            texture_path=Path("demo.png"),
            projection_mode="planar",
            usage="engrave",
            seed_face_index=2,
            projection_origin=(0.0, 0.0, 1.0),
            projection_normal=(0.0, 0.0, -1.0),
        )
        out = apply_texture_projection([mesh], [0], params)
        cleared = clear_texture_projection(out, [0])
        self.assertEqual(len(cleared), 1)
        self.assertFalse(getattr(cleared[0], "is_texture_decal", False))

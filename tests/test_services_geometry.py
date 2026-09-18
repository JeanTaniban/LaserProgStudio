# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest

import _path_setup  # noqa: F401
from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.services.geometry import bounds_axis_size, bounds_from_vertices_list, translated_mesh_copies


class GeometryServiceTest(unittest.TestCase):
    def test_bounds_from_vertices_list(self) -> None:
        bounds = bounds_from_vertices_list([(1, 2, 3), (-2, 5, 0), (4, -1, 7)])
        self.assertEqual(bounds, (-2.0, 4.0, -1.0, 5.0, 0.0, 7.0))

    def test_bounds_axis_size(self) -> None:
        bounds = (-2.0, 4.0, -1.0, 5.0, 0.0, 7.0)
        self.assertEqual(bounds_axis_size(bounds, "x"), 6.0)
        self.assertEqual(bounds_axis_size(bounds, "y"), 6.0)
        self.assertEqual(bounds_axis_size(bounds, "z"), 7.0)
        self.assertEqual(bounds_axis_size(bounds, "unknown"), 6.0)

    def test_translated_mesh_copies_do_not_mutate_source(self) -> None:
        source = WorkMesh(name="part", vertices=[(0, 0, 0), (1, 1, 1)], triangles=[(0, 1, 1)])
        copies = translated_mesh_copies([source], (10, -2, 3))
        self.assertEqual(source.vertices, [(0, 0, 0), (1, 1, 1)])
        self.assertEqual(copies[0].vertices, [(10.0, -2.0, 3.0), (11.0, -1.0, 4.0)])
        self.assertIsNot(copies[0], source)


if __name__ == "__main__":
    unittest.main()

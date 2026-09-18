# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from collections import Counter

import _path_setup  # noqa: F401
from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.extrude_down import extrude_mesh_down


def _cube_mesh() -> WorkMesh:
    vertices = [
        (0, 0, 0),
        (10, 0, 0),
        (10, 10, 0),
        (0, 10, 0),
        (0, 0, 10),
        (10, 0, 10),
        (10, 10, 10),
        (0, 10, 10),
    ]
    triangles = [
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    return WorkMesh(name="cube", vertices=vertices, triangles=triangles, color="#CCCCCC")


def _surface_component_count(mesh: WorkMesh) -> int:
    parent = list(range(len(mesh.triangles)))

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(a: int, b: int) -> None:
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[rb] = ra

    vertex_to_triangle: dict[int, int] = {}
    for tri_idx, tri in enumerate(mesh.triangles):
        for vertex_idx in tri:
            if vertex_idx in vertex_to_triangle:
                union(tri_idx, vertex_to_triangle[vertex_idx])
            else:
                vertex_to_triangle[vertex_idx] = tri_idx
    return len({find(i) for i in range(len(mesh.triangles))})


class ExtrudeDownCleanMeshTest(unittest.TestCase):
    def test_extrude_down_replaces_lower_geometry_with_one_welded_mesh(self) -> None:
        source = _cube_mesh()
        result, stats, warning = extrude_mesh_down(source, plane_z=5.0, ground_z=0.0, tolerance=1e-5)

        self.assertIsNone(warning)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(stats.supports, 1)
        self.assertEqual(_surface_component_count(result), 1)

    def test_extrude_down_has_no_duplicate_cut_or_bottom_vertices(self) -> None:
        result, _stats, warning = extrude_mesh_down(_cube_mesh(), plane_z=5.0, ground_z=0.0, tolerance=1e-5)

        self.assertIsNone(warning)
        assert result is not None
        coords = Counter((round(x, 6), round(y, 6), round(z, 6)) for x, y, z in result.vertices)
        duplicates = [coord for coord, count in coords.items() if count > 1]
        self.assertEqual(duplicates, [])

    def test_extrude_down_result_is_edge_manifold_on_simple_closed_mesh(self) -> None:
        result, _stats, warning = extrude_mesh_down(_cube_mesh(), plane_z=5.0, ground_z=0.0, tolerance=1e-5)

        self.assertIsNone(warning)
        assert result is not None
        edge_use = Counter()
        for tri in result.triangles:
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                edge_use[tuple(sorted((a, b)))] += 1
        non_manifold_edges = [edge for edge, count in edge_use.items() if count != 2]
        self.assertEqual(non_manifold_edges, [])


if __name__ == "__main__":
    unittest.main()


def _box_with_square_hole_mesh() -> WorkMesh:
    from shapely.geometry import Polygon
    from shapely.ops import triangulate

    footprint = Polygon(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        holes=[[(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)]],
    )
    vertices: list[tuple[float, float, float]] = []
    vertex_by_coord: dict[tuple[float, float, float], int] = {}
    triangles: list[tuple[int, int, int]] = []

    def vertex(x: float, y: float, z: float) -> int:
        key = (round(float(x), 8), round(float(y), 8), round(float(z), 8))
        if key not in vertex_by_coord:
            vertex_by_coord[key] = len(vertices)
            vertices.append((float(x), float(y), float(z)))
        return vertex_by_coord[key]

    for z, reverse in ((10.0, False), (0.0, True)):
        for tri in triangulate(footprint):
            if not footprint.covers(tri.representative_point()):
                continue
            ids = [vertex(x, y, z) for x, y in list(tri.exterior.coords)[:-1]]
            triangles.append(tuple(ids if not reverse else (ids[0], ids[2], ids[1])))

    def add_walls(coords, *, reverse: bool = False) -> None:
        ring = list(coords)[:-1]
        top = [vertex(x, y, 10.0) for x, y in ring]
        bottom = [vertex(x, y, 0.0) for x, y in ring]
        for i in range(len(ring)):
            j = (i + 1) % len(ring)
            if reverse:
                triangles.append((bottom[i], top[j], bottom[j]))
                triangles.append((bottom[i], top[i], top[j]))
            else:
                triangles.append((bottom[i], bottom[j], top[j]))
                triangles.append((bottom[i], top[j], top[i]))

    add_walls(footprint.exterior.coords)
    for interior in footprint.interiors:
        add_walls(interior.coords, reverse=True)
    return WorkMesh(name="box_with_hole", vertices=vertices, triangles=triangles, color="#CCCCCC")


def test_extrude_down_preserves_holes_in_cut_section_and_bottom_cap() -> None:
    from collections import Counter
    from shapely.geometry import Point, Polygon

    result, stats, warning = extrude_mesh_down(_box_with_square_hole_mesh(), plane_z=5.0, ground_z=-5.0, tolerance=1e-5)

    self = ExtrudeDownCleanMeshTest()
    self.assertIsNone(warning)
    self.assertIsNotNone(result)
    assert result is not None
    self.assertEqual(stats.supports, 1)

    outer_with_hole = Polygon(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        holes=[[(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)]],
    )
    hole = Polygon([(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)])
    bottom_triangles = 0
    triangles_inside_hole = 0
    triangles_inside_kept_footprint = 0
    for tri in result.triangles:
        zs = [result.vertices[i][2] for i in tri]
        if all(abs(z + 5.0) <= 1e-6 for z in zs):
            bottom_triangles += 1
            cx = sum(result.vertices[i][0] for i in tri) / 3.0
            cy = sum(result.vertices[i][1] for i in tri) / 3.0
            point = Point(cx, cy)
            if hole.contains(point):
                triangles_inside_hole += 1
            if outer_with_hole.contains(point):
                triangles_inside_kept_footprint += 1
    self.assertGreater(bottom_triangles, 0)
    self.assertGreater(triangles_inside_kept_footprint, 0)
    self.assertEqual(triangles_inside_hole, 0)

    edge_use = Counter()
    for tri in result.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge_use[tuple(sorted((a, b)))] += 1
    self.assertEqual([edge for edge, count in edge_use.items() if count != 2], [])


def _flat_face_with_square_hole_mesh() -> WorkMesh:
    from shapely.geometry import Polygon
    from shapely import constrained_delaunay_triangles

    footprint = Polygon(
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        holes=[[(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)]],
    )
    vertices: list[tuple[float, float, float]] = []
    vertex_by_coord: dict[tuple[float, float, float], int] = {}
    triangles: list[tuple[int, int, int]] = []

    def vertex(x: float, y: float, z: float) -> int:
        key = (round(float(x), 8), round(float(y), 8), round(float(z), 8))
        if key not in vertex_by_coord:
            vertex_by_coord[key] = len(vertices)
            vertices.append((float(x), float(y), float(z)))
        return vertex_by_coord[key]

    for tri in constrained_delaunay_triangles(footprint).geoms:
        if not footprint.covers(tri):
            continue
        ids = [vertex(x, y, 10.0) for x, y in list(tri.exterior.coords)[:-1]]
        triangles.append(tuple(ids))
    return WorkMesh(name="face_with_hole", vertices=vertices, triangles=triangles, color="#CCCCCC")


def test_extrude_down_flat_face_with_hole_builds_closed_solid_not_empty_shell() -> None:
    from collections import Counter
    from shapely.geometry import Point, Polygon

    result, stats, warning = extrude_mesh_down(_flat_face_with_square_hole_mesh(), plane_z=10.0, ground_z=0.0, tolerance=1e-5)

    assert warning is None
    assert result is not None
    assert stats.supports == 1

    hole = Polygon([(4.0, 4.0), (6.0, 4.0), (6.0, 6.0), (4.0, 6.0)])
    top_triangles = 0
    bottom_triangles = 0
    triangles_inside_hole = 0
    for tri in result.triangles:
        pts = [result.vertices[i] for i in tri]
        zs = [p[2] for p in pts]
        if all(abs(z - 10.0) <= 1e-6 for z in zs):
            top_triangles += 1
        if all(abs(z - 0.0) <= 1e-6 for z in zs):
            bottom_triangles += 1
        if all(abs(z - 10.0) <= 1e-6 or abs(z - 0.0) <= 1e-6 for z in zs):
            cx = sum(p[0] for p in pts) / 3.0
            cy = sum(p[1] for p in pts) / 3.0
            if hole.contains(Point(cx, cy)):
                triangles_inside_hole += 1
    assert top_triangles > 0
    assert bottom_triangles > 0
    assert triangles_inside_hole == 0

    edge_use = Counter()
    for tri in result.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edge_use[tuple(sorted((a, b)))] += 1
    assert [edge for edge, count in edge_use.items() if count != 2] == []

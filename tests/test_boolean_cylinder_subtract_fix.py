from __future__ import annotations

from collections import defaultdict
import copy

import _path_setup  # noqa: F401
import pytest

from laserprog_studio.boolean_ops import boolean_difference, is_closed_triangle_mesh
from laserprog_studio.primitives.base import PrimitiveBuildRequest
from laserprog_studio.primitives.generators import build_box, build_cone, build_cylinder


def _bad_oriented_edge_count(mesh) -> int:
    edges: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for a, b, c in mesh.triangles:
        for x, y in ((a, b), (b, c), (c, a)):
            key = (x, y) if x < y else (y, x)
            edges[key].append((x, y))
    return sum(1 for dirs in edges.values() if len(dirs) != 2 or dirs[0] == dirs[1])


def _box():
    return build_box(PrimitiveBuildRequest("box", {"size_x": 40, "size_y": 40, "size_z": 40}, 1))


def test_cylinder_and_cone_primitive_winding_is_boolean_ready() -> None:
    cyl = build_cylinder(
        PrimitiveBuildRequest("cylinder", {"size_x": 20, "size_y": 20, "size_z": 60, "segments": 32}, 1)
    )
    cone = build_cone(PrimitiveBuildRequest("cone", {"size_x": 20, "size_y": 20, "size_z": 60, "segments": 32}, 1))

    assert is_closed_triangle_mesh(cyl.vertices, cyl.triangles) == (True, 0, 0)
    assert is_closed_triangle_mesh(cone.vertices, cone.triangles) == (True, 0, 0)
    assert _bad_oriented_edge_count(cyl) == 0
    assert _bad_oriented_edge_count(cone) == 0


@pytest.mark.skipif(pytest.importorskip("manifold3d", reason="manifold3d optional") is None, reason="manifold3d optional")
def test_subtract_cylinder_from_box_produces_closed_non_empty_mesh() -> None:
    cyl = build_cylinder(
        PrimitiveBuildRequest("cylinder", {"size_x": 20, "size_y": 20, "size_z": 60, "segments": 32}, 1)
    )

    result = boolean_difference(_box(), cyl)

    assert len(result.vertices) > 0
    assert len(result.triangles) > 0
    assert is_closed_triangle_mesh(result.vertices, result.triangles) == (True, 0, 0)


@pytest.mark.skipif(pytest.importorskip("manifold3d", reason="manifold3d optional") is None, reason="manifold3d optional")
def test_boolean_difference_repairs_old_inverted_cylinder_side_faces() -> None:
    cyl = build_cylinder(
        PrimitiveBuildRequest("cylinder", {"size_x": 20, "size_y": 20, "size_z": 60, "segments": 32}, 1)
    )
    old_broken = copy.deepcopy(cyl)
    old_broken.triangles = [
        (a, c, b) if index % 4 in (0, 1) else (a, b, c)
        for index, (a, b, c) in enumerate(old_broken.triangles)
    ]

    assert _bad_oriented_edge_count(old_broken) > 0

    result = boolean_difference(_box(), old_broken)

    assert len(result.triangles) > 0
    assert is_closed_triangle_mesh(result.vertices, result.triangles) == (True, 0, 0)

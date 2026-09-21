# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import _path_setup  # noqa: F401

from PIL import Image

from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh
from laserprog_studio.geometry_ops.boolean_topology_contract import analyze_work_mesh_boolean_topology
from laserprog_studio.boolean_ops import _prepared_boolean_arrays, boolean_difference, is_closed_triangle_mesh
from laserprog_studio.geometry_ops.manifold_contract import construct_manifold, manifold_is_valid
from laserprog_studio.primitives.base import PrimitiveBuildRequest
from laserprog_studio.primitives.generators import build_box


def test_mask_relief_diagonal_components_need_no_private_merge_policy(tmp_path: Path) -> None:
    mask = tmp_path / "diagonal.png"
    img = Image.new("L", (2, 2), 255)
    img.putpixel((0, 0), 0)
    img.putpixel((1, 1), 0)
    img.save(mask)

    mesh = build_mask_relief_mesh(mask, max_height_mm=5.0, pixel_size_mm=2.0, binary=True).mesh
    assert getattr(mesh, "_lps_skip_boolean_merge", False) is False
    assert bool((mesh.metadata or {}).get("boolean_skip_merge", False)) is False
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles)[0] is True

    _vertices, _triangles, skip_merge = _prepared_boolean_arrays(mesh, label="mask")
    assert skip_merge is False

    reloaded_mesh = deepcopy(mesh)
    _vertices, _triangles, skip_merge = _prepared_boolean_arrays(reloaded_mesh, label="reloaded mask")
    assert skip_merge is False


def test_mask_relief_concave_hole_is_a_geometric_manifold(tmp_path: Path) -> None:
    mask = tmp_path / "notched-mask.png"
    img = Image.new("L", (5, 5), 0)
    # A one-pixel cavity plus an exterior notch exercises cap triangulation
    # across both a hole and a concave boundary.
    img.putpixel((2, 2), 255)
    img.putpixel((0, 0), 255)
    img.save(mask)

    mesh = build_mask_relief_mesh(mask, max_height_mm=3.0, pixel_size_mm=1.0, binary=True).mesh
    report = analyze_work_mesh_boolean_topology(mesh)
    assert report.indexed_closed is True
    assert report.geometrically_manifold is True

def _box(*, size_x: float, size_y: float, size_z: float, pos_x: float, pos_y: float, pos_z: float):
    return build_box(
        PrimitiveBuildRequest(
            primitive_id="box",
            values={
                "size_x": size_x,
                "size_y": size_y,
                "size_z": size_z,
                "pos_x": pos_x,
                "pos_y": pos_y,
                "pos_z": pos_z,
            },
            name_index=1,
        )
    )


def test_mask_relief_is_directly_manifold_certified(tmp_path: Path) -> None:
    import manifold3d as m3d
    import numpy as np

    mask = tmp_path / "circle.png"
    img = Image.new("L", (96, 96), 255)
    from PIL import ImageDraw
    ImageDraw.Draw(img).ellipse((14, 14, 82, 82), fill=0)
    img.save(mask)

    mesh = build_mask_relief_mesh(
        mask,
        max_height_mm=6.0,
        pixel_size_mm=1.0,
        binary=True,
        levels=50,
        smooth=35,
        max_grid_size=0,
    ).mesh

    construction = construct_manifold(
        m3d,
        vertices=np.asarray(mesh.vertices, dtype=np.float64),
        triangles=np.asarray(mesh.triangles, dtype=np.int32),
        merge=False,
        prefer_64bit=True,
    )
    assert manifold_is_valid(construction.manifold, m3d)
    assert str(construction.status) == "NoError"


def test_mask_relief_supports_chained_boolean_differences(tmp_path: Path) -> None:
    mask = tmp_path / "disc.png"
    img = Image.new("L", (120, 120), 255)
    from PIL import ImageDraw
    ImageDraw.Draw(img).ellipse((10, 10, 110, 110), fill=0)
    img.save(mask)

    source = build_mask_relief_mesh(
        mask,
        max_height_mm=8.0,
        pixel_size_mm=1.0,
        binary=True,
        levels=50,
        smooth=35,
        max_grid_size=0,
    ).mesh

    cutter_a = _box(
        size_x=12.0,
        size_y=12.0,
        size_z=12.0,
        pos_x=0.0,
        pos_y=0.0,
        pos_z=4.0,
    )
    once = boolean_difference(source, cutter_a, cutter_margin_mm=0.0)
    assert is_closed_triangle_mesh(once.vertices, once.triangles) == (True, 0, 0)

    cutter_b = _box(
        size_x=8.0,
        size_y=8.0,
        size_z=12.0,
        pos_x=25.0,
        pos_y=0.0,
        pos_z=4.0,
    )
    twice = boolean_difference(once, cutter_b, cutter_margin_mm=0.0)
    assert is_closed_triangle_mesh(twice.vertices, twice.triangles) == (True, 0, 0)
    assert len(twice.triangles) > 0


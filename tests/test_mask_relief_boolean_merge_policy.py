# -*- coding: utf-8 -*-
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import _path_setup  # noqa: F401

from PIL import Image

from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh
from laserprog_studio.geometry_ops.boolean_topology_contract import analyze_work_mesh_boolean_topology
from laserprog_studio.boolean_ops import _prepared_boolean_arrays, is_closed_triangle_mesh


def test_mask_relief_marks_boolean_merge_skip_for_diagonal_point_contacts(tmp_path: Path) -> None:
    mask = tmp_path / "diagonal.png"
    img = Image.new("L", (2, 2), 255)
    img.putpixel((0, 0), 0)
    img.putpixel((1, 1), 0)
    img.save(mask)

    mesh = build_mask_relief_mesh(mask, max_height_mm=5.0, pixel_size_mm=2.0, binary=True).mesh
    assert getattr(mesh, "_lps_skip_boolean_merge", False) is True
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles)[0] is True

    _vertices, _triangles, skip_merge = _prepared_boolean_arrays(mesh, label="mask")
    assert skip_merge is True

    reloaded_mesh = deepcopy(mesh)
    delattr(reloaded_mesh, "_lps_skip_boolean_merge")
    _vertices, _triangles, skip_merge = _prepared_boolean_arrays(reloaded_mesh, label="reloaded mask")
    assert skip_merge is True


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

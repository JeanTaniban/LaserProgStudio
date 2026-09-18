# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401

from PIL import Image

from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh
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

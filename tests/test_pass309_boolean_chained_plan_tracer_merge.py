# -*- coding: utf-8 -*-
from __future__ import annotations

import _path_setup  # noqa: F401

from laserprog_studio.boolean_ops import _copy_runtime_mesh_attrs, _prepared_boolean_arrays
from laserprog_studio.primitives.base import PrimitiveBuildRequest
from laserprog_studio.primitives.generators import build_box


def _box():
    return build_box(PrimitiveBuildRequest("box", {"size_x": 10, "size_y": 10, "size_z": 10}, 1))


def test_pass309_closed_generated_solids_are_merged_for_chained_booleans() -> None:
    mesh = _box()
    _vertices, _triangles, skip_merge = _prepared_boolean_arrays(mesh, label="closed-box")

    assert skip_merge is False


def test_pass309_boolean_result_does_not_inherit_mask_relief_skip_merge_flag() -> None:
    src = _box()
    setattr(src, "_lps_skip_boolean_merge", True)
    setattr(src, "_lps_custom_runtime", "keep-me")
    dst = _box()

    _copy_runtime_mesh_attrs(src, dst)

    assert getattr(dst, "_lps_custom_runtime") == "keep-me"
    assert getattr(dst, "_lps_skip_boolean_merge", False) is False

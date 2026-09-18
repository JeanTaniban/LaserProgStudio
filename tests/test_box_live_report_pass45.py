# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math

from laserprog_studio.fabrication.box_generator import (
    attach_box_metadata,
    box_metadata,
    compute_box_metrics,
    cuboid_triangles,
    cuboid_vertices,
    make_box_boards,
    WorkMesh,
)


def test_pass45_box_metadata_survives_deepcopy_for_live_inspector_reports() -> None:
    boards = make_box_boards(120.0, 80.0, 60.0, 3.0)
    mesh = WorkMesh(name="bottom", vertices=cuboid_vertices(boards[0]), triangles=cuboid_triangles(), color="#fff")
    attach_box_metadata(
        mesh,
        group_id="box-live",
        board_name="bottom",
        width=120.0,
        depth=80.0,
        height=60.0,
        thickness=3.0,
    )

    copied = copy.deepcopy(mesh)
    meta = box_metadata(copied)

    assert meta is not None
    assert meta["group_id"] == "box-live"
    assert meta["board_name"] == "bottom"
    assert meta["thickness_mm"] == 3.0


def test_pass45_box_metrics_recompute_from_updated_outer_dimensions() -> None:
    boards = make_box_boards(200.0, 90.0, 70.0, 3.0)
    metrics = compute_box_metrics(200.0, 90.0, 70.0, 3.0, boards)

    assert math.isclose(metrics.outer_volume_l, 1.26, rel_tol=1e-9)
    assert math.isclose(metrics.inner_volume_l, (194.0 * 84.0 * 64.0) / 1_000_000.0, rel_tol=1e-9)
    assert metrics.board_cut_area_m2 > 0.0

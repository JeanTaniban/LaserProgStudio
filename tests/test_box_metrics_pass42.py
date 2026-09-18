# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from laserprog_studio.fabrication.box_generator import board_cut_area_mm2, compute_box_metrics, make_box_boards


def test_pass42_box_metrics_report_inner_and_outer_litres() -> None:
    boards = make_box_boards(120.0, 80.0, 60.0, 3.0)
    metrics = compute_box_metrics(120.0, 80.0, 60.0, 3.0, boards)

    assert math.isclose(metrics.outer_volume_l, 0.576, rel_tol=1e-9)
    assert math.isclose(metrics.inner_volume_l, 0.455544, rel_tol=1e-9)
    assert metrics.inner_width_mm == 114.0
    assert metrics.inner_depth_mm == 74.0
    assert metrics.inner_height_mm == 54.0


def test_pass42_box_metrics_sum_real_generated_board_surface_m2() -> None:
    boards = make_box_boards(120.0, 80.0, 60.0, 3.0)
    metrics = compute_box_metrics(120.0, 80.0, 60.0, 3.0, boards)

    expected_mm2 = 2 * (120.0 * 80.0) + 2 * (120.0 * 54.0) + 2 * (74.0 * 54.0)
    assert math.isclose(metrics.board_cut_area_mm2, expected_mm2, rel_tol=1e-9)
    assert math.isclose(metrics.board_cut_area_m2, expected_mm2 / 1_000_000.0, rel_tol=1e-9)
    assert math.isclose(sum(board_cut_area_mm2(board) for board in boards), expected_mm2, rel_tol=1e-9)

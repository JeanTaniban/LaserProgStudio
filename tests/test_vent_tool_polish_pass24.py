# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from laserprog_studio.planar_tools import (
    VentPathDraft,
    VentSectionKind,
    make_locked_plane,
    smooth_path_points,
    validate_vent_waypoints_and_curve,
)


def _rect_draft() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 10.0
    draft.section.height = 5.0
    draft.section.area = 50.0
    draft.wall_thickness = 3.0
    draft.compact_wall_fusion = True
    return draft


def test_pass24_vent_metrics_report_target_length_delta() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (60.0, 0.0)]
    draft.target_length = 75.0

    metrics = draft.metrics()

    assert math.isclose(metrics.inner_width, 10.0)
    assert math.isclose(metrics.outer_width, 16.0)
    assert math.isclose(metrics.centerline_length, 60.0)
    assert math.isclose(metrics.target_delta, -15.0)
    assert metrics.snap_grid_step == 4.0
    assert metrics.fill_area is False


def test_pass24_smoothed_centerline_does_not_overshoot_clean_u_path() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0), (40.0, 13.0), (0.0, 13.0)]

    smooth = smooth_path_points(draft.waypoints, samples_per_segment=8)
    ys = [p[1] for p in smooth]

    assert min(ys) >= -1e-9
    assert max(ys) <= 13.0 + 1e-9
    assert draft.validation_result().ok is True


def test_pass24_combined_waypoint_and_curve_validation_rejects_self_crossing_only() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0), (40.0, 12.0), (0.0, 12.0)]

    result = validate_vent_waypoints_and_curve(draft.waypoints, draft.clearance_policy())

    assert result.ok is True


def test_pass24_only_walls_round_does_not_affect_metrics_or_shape_contract() -> None:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.ROUND
    draft.section.area = math.pi * 25.0
    draft.wall_thickness = 2.0
    draft.only_walls = True
    draft.waypoints = [(0.0, 0.0), (25.0, 0.0)]

    assert draft.uses_only_walls() is False
    assert math.isclose(draft.metrics().inner_width, 10.0, rel_tol=1e-6)

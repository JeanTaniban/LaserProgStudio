# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind, make_locked_plane


def _rect_draft() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    return draft


def test_pass40_flare_scale_is_anchored_to_real_first_and_last_waypoints_when_curved() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (50.0, 0.0), (100.0, 25.0)]
    draft.flare_side = VentFlareSide.BOTH
    draft.flare_factor = 1.8
    draft.segment_curve_radii = [30.0, 20.0]
    draft.segment_curve_strengths = [1.0, -1.0]
    draft._sync_curve_offsets()

    center, scales = draft.sampled_centerline_with_flare_scales(samples_per_segment=24)

    assert center[0] == draft.waypoints[0]
    assert center[-1] == draft.waypoints[-1]
    assert scales[0] == draft.flare_factor
    assert scales[-1] == draft.flare_factor
    assert scales[24] == 1.0  # exact first intermediate waypoint: start flare is finished here
    assert scales[-25] == 1.0  # exact penultimate waypoint: end flare starts after this


def test_pass40_changing_curve_radius_does_not_change_flare_endpoint_scale() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (60.0, 0.0), (90.0, 30.0)]
    draft.flare_side = VentFlareSide.END
    draft.flare_factor = 2.0

    draft.segment_curve_radii = [0.0, 0.0]
    draft.segment_curve_strengths = [0.0, 0.0]
    draft._sync_curve_offsets()
    center_a, scales_a = draft.sampled_centerline_with_flare_scales(samples_per_segment=18)

    draft.segment_curve_radii = [40.0, 35.0]
    draft.segment_curve_strengths = [1.0, -1.0]
    draft._sync_curve_offsets()
    center_b, scales_b = draft.sampled_centerline_with_flare_scales(samples_per_segment=18)

    assert center_a[-1] == center_b[-1] == draft.waypoints[-1]
    assert scales_a[-1] == scales_b[-1] == draft.flare_factor
    assert scales_a[0] == scales_b[0] == 1.0

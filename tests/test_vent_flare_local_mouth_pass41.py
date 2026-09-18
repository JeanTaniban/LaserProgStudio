# -*- coding: utf-8 -*-
from __future__ import annotations

from shapely.geometry import LineString

from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind, make_locked_plane
from laserprog_studio.planar_tools.vent_preview_snap import rectangular_vent_footprint_geometries


def _rect_draft() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    draft.waypoints = [(0.0, 0.0), (100.0, 0.0), (100.0, 50.0)]
    return draft


def _vertical_span(geom, x: float) -> float:
    cut = geom.intersection(LineString([(float(x), -1000.0), (float(x), 1000.0)]))
    bounds = cut.bounds
    return float(bounds[3] - bounds[1]) if bounds else 0.0


def test_pass41_flare_is_a_local_endpoint_mouth_not_a_segment_wide_scale() -> None:
    draft = _rect_draft()
    draft.flare_side = VentFlareSide.START
    draft.flare_factor = 2.0

    outer, inner = rectangular_vent_footprint_geometries(draft, draft.smoothed_centerline())

    # The mouth is no longer a hard rectangular pad. It starts fully flared at
    # the endpoint, then returns smoothly to the nominal duct section before the
    # first user segment can be consumed.
    assert round(_vertical_span(outer, 0.0), 6) == 44.0  # 20*2/2 + wall = 22 mm half width
    assert 24.0 < _vertical_span(outer, 2.0) < 44.0
    assert round(_vertical_span(outer, 30.0), 6) == 24.0  # normal 20/2 + wall = 12 mm half width
    assert round(_vertical_span(inner, 0.0), 6) == 40.0
    assert 20.0 < _vertical_span(inner, 2.0) < 40.0
    assert round(_vertical_span(inner, 30.0), 6) == 20.0


def test_pass41_curve_radius_does_not_move_the_endpoint_mouth_bounds() -> None:
    draft = _rect_draft()
    draft.flare_side = VentFlareSide.START
    draft.flare_factor = 1.8
    draft.segment_curve_radii = [0.0, 0.0]
    draft.segment_curve_strengths = [0.0, 0.0]
    draft._sync_curve_offsets()
    outer_a, _inner_a = rectangular_vent_footprint_geometries(draft, draft.smoothed_centerline(samples_per_segment=18))

    draft.segment_curve_radii = [45.0, 30.0]
    draft.segment_curve_strengths = [1.0, -1.0]
    draft._sync_curve_offsets()
    outer_b, _inner_b = rectangular_vent_footprint_geometries(draft, draft.smoothed_centerline(samples_per_segment=18))

    # The local mouth is oriented by the first two user waypoints and remains at
    # the same endpoint footprint even when the preview curve changes.
    no_flare = _rect_draft()
    no_flare.segment_curve_radii = [45.0, 30.0]
    no_flare.segment_curve_strengths = [1.0, -1.0]
    no_flare._sync_curve_offsets()
    outer_normal, _inner_normal = rectangular_vent_footprint_geometries(no_flare, no_flare.smoothed_centerline(samples_per_segment=18))

    assert round(_vertical_span(outer_a, 2.0), 6) == round(_vertical_span(outer_b, 2.0), 6)
    assert round(_vertical_span(outer_b, 30.0), 6) == round(_vertical_span(outer_normal, 30.0), 6)

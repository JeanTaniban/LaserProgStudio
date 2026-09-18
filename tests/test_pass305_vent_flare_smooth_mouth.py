# -*- coding: utf-8 -*-
from __future__ import annotations

from shapely.geometry import LineString

from _path_setup import ROOT  # noqa: F401
from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind, make_locked_plane
from laserprog_studio.planar_tools.vent_preview_snap import _endpoint_flare_depth, rectangular_vent_footprint_geometries


def _draft() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    draft.waypoints = [(0.0, 0.0), (100.0, 0.0)]
    draft.flare_side = VentFlareSide.START
    draft.flare_factor = 2.0
    return draft


def _span(geom, x: float) -> float:
    cut = geom.intersection(LineString([(float(x), -1000.0), (float(x), 1000.0)]))
    bounds = cut.bounds
    return float(bounds[3] - bounds[1]) if bounds else 0.0


def test_pass305_rectangular_flare_is_smooth_not_a_step() -> None:
    draft = _draft()
    outer, inner = rectangular_vent_footprint_geometries(draft, draft.smoothed_centerline())
    depth = _endpoint_flare_depth(draft, at_start=True)

    xs = [0.0, depth * 0.25, depth * 0.5, depth * 0.75, depth + 1.0]
    outer_spans = [_span(outer, x) for x in xs]
    inner_spans = [_span(inner, x) for x in xs]

    assert outer_spans[0] > outer_spans[1] > outer_spans[2] > outer_spans[3] > outer_spans[4]
    assert inner_spans[0] > inner_spans[1] > inner_spans[2] > inner_spans[3] > inner_spans[4]
    assert round(outer_spans[-1], 6) == 24.0
    assert round(inner_spans[-1], 6) == 20.0


def test_pass305_flare_transition_is_longer_than_legacy_step_pad() -> None:
    draft = _draft()
    assert _endpoint_flare_depth(draft, at_start=True) > draft.section.width * 0.5

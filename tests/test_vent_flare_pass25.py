# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from laserprog_studio.planar_tools import (
    VentFlareSide,
    VentPathDraft,
    VentSectionKind,
    make_locked_plane,
    make_vent_path_mesh,
)
from laserprog_studio.planar_tools.vent_preview_snap import rectangular_vent_footprint_geometries
from shapely.geometry import LineString


def _straight_rect_vent(*, only_walls: bool = False) -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    draft.only_walls = only_walls
    draft.waypoints = [(0.0, 0.0), (60.0, 0.0), (120.0, 0.0)]
    return draft


def _straight_round_vent() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.ROUND
    draft.section.area = math.pi * 25.0
    draft.wall_thickness = 2.0
    draft.waypoints = [(0.0, 0.0), (60.0, 0.0), (120.0, 0.0)]
    return draft


def _outer_y_span(mesh, *, row: int, ring_count: int) -> float:
    start = row * ring_count * 2
    ys = [mesh.vertices[i][1] for i in range(start, start + ring_count)]
    return max(ys) - min(ys)


def _y_span_at_x(mesh, x: float, *, tol: float = 1e-6) -> float:
    ys = [float(v[1]) for v in mesh.vertices if abs(float(v[0]) - float(x)) <= tol]
    assert ys, f"no vertices at x={x}"
    return max(ys) - min(ys)


def _footprint_span_at_x(draft: VentPathDraft, x: float) -> float:
    outer, _inner = rectangular_vent_footprint_geometries(draft, draft.smoothed_centerline())
    cut = outer.intersection(LineString([(float(x), -1000.0), (float(x), 1000.0)]))
    bounds = cut.bounds
    return float(bounds[3] - bounds[1]) if bounds else 0.0


def test_pass25_rectangular_flare_widens_selected_start_only() -> None:
    draft = _straight_rect_vent()
    draft.flare_side = VentFlareSide.START
    draft.flare_factor = 1.6

    mesh = make_vent_path_mesh(draft)
    assert mesh.vertices

    start_span = _footprint_span_at_x(draft, 2.0)
    middle_span = _footprint_span_at_x(draft, 60.0)
    end_span = _footprint_span_at_x(draft, 118.0)

    assert start_span > middle_span * 1.25
    assert abs(end_span - middle_span) < 1e-6


def test_pass25_round_flare_is_supported() -> None:
    draft = _straight_round_vent()
    draft.flare_side = VentFlareSide.BOTH
    draft.flare_factor = 1.5
    draft.mark_end_flare_finalized(True)

    mesh = make_vent_path_mesh(draft)
    ring_count = 16
    row_count = len(mesh.vertices) // (ring_count * 2)

    assert _outer_y_span(mesh, row=0, ring_count=ring_count) > _outer_y_span(mesh, row=row_count // 2, ring_count=ring_count)
    assert _outer_y_span(mesh, row=row_count - 1, ring_count=ring_count) > _outer_y_span(mesh, row=row_count // 2, ring_count=ring_count)


def test_pass25_flare_preserves_only_walls_contract() -> None:
    full = _straight_rect_vent(only_walls=False)
    walls = _straight_rect_vent(only_walls=True)
    for draft in (full, walls):
        draft.flare_side = VentFlareSide.BOTH
        draft.flare_factor = 1.4
        draft.mark_end_flare_finalized(True)

    full_mesh = make_vent_path_mesh(full)
    walls_mesh = make_vent_path_mesh(walls)

    # Only-walls is now a hidden legacy flag for rectangular EVT.  Both paths
    # intentionally use the same footprint-based generator.
    assert len(walls_mesh.vertices) == len(full_mesh.vertices)
    assert len(walls_mesh.triangles) == len(full_mesh.triangles)


def test_pass25_flare_keeps_base_clearance_policy_local() -> None:
    base = _straight_rect_vent()
    flared = _straight_rect_vent()
    flared.flare_side = VentFlareSide.BOTH
    flared.flare_factor = 1.5

    assert flared.clearance_policy().min_centerline_spacing == base.clearance_policy().min_centerline_spacing
    assert flared.effective_flare_side() is VentFlareSide.BOTH
    flared.mark_end_flare_finalized(True)
    assert flared.effective_flare_side() is VentFlareSide.BOTH

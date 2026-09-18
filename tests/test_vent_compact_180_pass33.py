# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter

from laserprog_studio.planar_tools import (
    FixedPlanarView,
    VentFlareSide,
    VentPathDraft,
    VentSectionKind,
    VentSectionSpec,
    make_vent_path_mesh,
    plane_from_first_hit,
    sample_vent_centerline,
)


def _rect_draft(*, only_walls: bool = False) -> VentPathDraft:
    draft = VentPathDraft(plane_from_first_hit(FixedPlanarView.TOP))
    draft.section = VentSectionSpec(kind=VentSectionKind.RECTANGLE, width=10.0, height=6.0, area=60.0)
    draft.wall_thickness = 3.0
    draft.only_walls = bool(only_walls)
    return draft


def _boundary_edge_count(mesh) -> int:
    counts: Counter[tuple[int, int]] = Counter()
    for tri in mesh.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return sum(1 for count in counts.values() if count == 1)


def test_pass33_clean_waypoints_do_not_create_hidden_180_arc() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (40.0, 6.5), (0.0, 13.0)]

    sampled = sample_vent_centerline(draft.waypoints, bend_radius=draft.minimum_bend_radius(), samples_per_corner=16)

    assert draft.validation_result().ok is True
    assert sampled == draft.waypoints
    assert max(x for x, _y in sampled) == 40.0


def test_pass33_curve_handle_creates_explicit_smooth_segment() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0)]
    draft.update_curve_handle_plane(0, (20.0, 8.0))

    sampled = draft.smoothed_centerline(samples_per_segment=16)

    assert draft.validation_result().ok is True
    assert len(sampled) > len(draft.waypoints)
    assert max(y for _x, y in sampled) > 3.5
    assert draft.segment_handle_points()[0] == (20.0, 8.0)


def test_pass33_flare_lives_only_on_first_and_last_user_segments() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (20.0, 0.0), (20.0, 40.0), (0.0, 40.0)]
    draft.flare_side = VentFlareSide.BOTH
    draft.flare_factor = 1.8
    draft.mark_end_flare_finalized(True)
    total = draft.estimated_centerline_length()

    assert draft.flare_scale_at_distance(0.0, total) > 1.7
    assert draft.flare_scale_at_distance(20.0, total) == 1.0
    assert draft.flare_scale_at_distance(total - 20.0, total) == 1.0
    assert draft.flare_scale_at_distance(total, total) > 1.7


def test_pass33_only_walls_straight_mesh_is_closed() -> None:
    draft = _rect_draft(only_walls=True)
    draft.waypoints = [(0.0, 0.0), (80.0, 0.0)]

    mesh = make_vent_path_mesh(draft)

    assert len(mesh.vertices) > 0
    assert _boundary_edge_count(mesh) == 0

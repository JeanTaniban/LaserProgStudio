# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter

from laserprog_studio.planar_tools import (
    VentPathDraft,
    VentSectionKind,
    make_locked_plane,
    make_vent_path_mesh,
    sample_vent_centerline,
)


def _rect_vent() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 10.0
    draft.section.height = 6.0
    draft.section.area = 60.0
    draft.wall_thickness = 3.0
    draft.compact_wall_fusion = True
    return draft


def _boundary_edge_count(mesh) -> int:
    counts: Counter[tuple[int, int]] = Counter()
    for tri in mesh.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return sum(1 for count in counts.values() if count == 1)


def test_pass30_clean_sampling_keeps_user_waypoints_when_no_curve_handle() -> None:
    draft = _rect_vent()
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0), (40.0, 13.0), (0.0, 13.0)]

    sampled = sample_vent_centerline(draft.waypoints, bend_radius=draft.minimum_bend_radius(), samples_per_corner=10)

    assert draft.validation_result().ok is True
    assert sampled == draft.waypoints


def test_pass30_single_point_hairpin_is_not_special_cased() -> None:
    draft = _rect_vent()
    draft.waypoints = [(0.0, 0.0), (30.0, 0.0), (0.0, 0.5)]

    result = draft.validation_result()

    assert result.ok is True


def test_pass30_add_candidate_checks_whole_future_centerline_crossing() -> None:
    draft = _rect_vent()
    draft.waypoints = [(0.0, 0.0), (70.0, 0.0), (70.0, 30.0), (0.0, 30.0)]

    result = draft.clamp_waypoint_candidate((35.0, -2.0), anchor=draft.waypoints[-1])

    assert not result.valid
    assert result.raw_point == (35.0, -2.0)
    assert "self-intersects" in result.message or "centerline" in result.message


def test_pass30_only_walls_generates_closed_wall_solids() -> None:
    draft = _rect_vent()
    draft.only_walls = True
    draft.waypoints = [(0.0, 0.0), (80.0, 0.0)]

    mesh = make_vent_path_mesh(draft)

    assert _boundary_edge_count(mesh) == 0

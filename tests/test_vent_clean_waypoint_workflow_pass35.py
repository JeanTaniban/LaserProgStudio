# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from laserprog_studio.planar_tools import VentPathDraft, VentSectionKind, make_locked_plane, make_vent_path_mesh
from laserprog_studio.planar_tools.contracts import PlanarToolConfig
from laserprog_studio.planar_tools.pointer import snap_plane_point


def _rect_draft() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 10.0
    draft.section.height = 5.0
    draft.section.area = 50.0
    draft.wall_thickness = 3.0
    return draft


def test_pass35_snap_grid_uses_outer_width_quarter_relative_to_first_waypoint() -> None:
    draft = _rect_draft()
    draft.waypoints = [(3.0, 2.0), (43.0, 2.0)]
    cfg = PlanarToolConfig(grid_snap_enabled=True, smart_snap_enabled=False, grid_step=draft.snap_grid_step(), grid_origin=draft.waypoints[0])

    snapped, label = snap_plane_point((6.9, 5.9), cfg)

    assert draft.snap_grid_step() == 4.0
    assert snapped == (7.0, 6.0)
    assert label == "grid 4"


def test_pass35_smart_snap_anchors_include_centerline_and_edges_without_visible_handles() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0)]
    anchors = draft.snap_anchor_points(samples_per_segment=8)

    assert any(abs(y - 8.0) < 1e-6 for _x, y in anchors)
    assert any(abs(y - 5.0) < 1e-6 for _x, y in anchors)
    assert (0.0, 0.0) in anchors
    assert (40.0, 0.0) in anchors

    draft.selected_index = 1
    draft.set_selected_segment_curve(radius=8.0, strength=1.0)
    curved = draft.snap_anchor_points(samples_per_segment=8)
    assert any(abs(x - 20.0) < 1e-6 and y > 3.5 for x, y in curved)


def test_pass35_fill_area_generates_global_stock_with_carved_airway() -> None:
    draft = _rect_draft()
    draft.fill_area = True
    draft.waypoints = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0)]

    mesh = make_vent_path_mesh(draft)

    assert len(mesh.vertices) > 0
    assert len(mesh.triangles) > 0
    zs = [z for _x, _y, z in mesh.vertices]
    assert max(zs) - min(zs) == 11.0


def test_pass36_preview_offsets_do_not_create_long_spikes_on_tight_turns() -> None:
    from laserprog_studio.planar_tools.vent_preview_snap import offset_paths

    center = [(0.0, 0.0), (40.0, 0.0), (0.0, 8.0)]
    left, right = offset_paths(center, 8.0)

    assert len(left) >= 3
    assert len(right) >= 3
    assert max(abs(y) for _x, y in left + right) < 40.0
    assert max(abs(x) for x, _y in left + right) < 55.0


def test_pass36_selected_segment_curve_keeps_radius_and_force_values() -> None:
    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0)]
    draft.selected_index = 1

    draft.set_selected_segment_curve(radius=12.0, strength=0.5)

    assert draft.segment_curve_radii == [12.0]
    assert draft.segment_curve_strengths == [0.5]
    assert draft.curve_offsets_for_sampling() == [6.0]
    assert max(y for _x, y in draft.smoothed_centerline(samples_per_segment=8)) > 2.5


def test_pass37_preview_edges_follow_the_curved_centerline_samples() -> None:
    from laserprog_studio.planar_tools.vent_preview_snap import offset_paths

    draft = _rect_draft()
    draft.waypoints = [(0.0, 0.0), (40.0, 0.0)]
    draft.selected_index = 1
    draft.set_selected_segment_curve(radius=14.0, strength=1.0)
    center = draft.smoothed_centerline(samples_per_segment=18)

    left, right = offset_paths(center, 8.0)

    assert len(left) == len(center)
    assert len(right) == len(center)
    for c, l, r in zip(center, left, right):
        assert math.isclose(math.dist(c, l), 8.0, rel_tol=1e-6, abs_tol=1e-6)
        assert math.isclose(math.dist(c, r), 8.0, rel_tol=1e-6, abs_tol=1e-6)
    assert any(y > 13.0 for _x, y in left)

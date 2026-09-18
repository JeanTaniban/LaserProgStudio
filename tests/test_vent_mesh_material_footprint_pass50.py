# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter

from shapely.geometry import LineString

from laserprog_studio.planar_tools import VentFlareSide, VentPathDraft, VentSectionKind, make_locked_plane, make_vent_path_mesh
from laserprog_studio.planar_tools.vent_preview_snap import rectangular_vent_material_footprint


def _rect_draft(*, fill_area: bool = False, flare: bool = False) -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 18.0
    draft.section.height = 8.0
    draft.section.area = 144.0
    draft.wall_thickness = 3.0
    draft.fill_area = fill_area
    draft.waypoints = [(0.0, 0.0), (48.0, 0.0), (48.0, 34.0), (8.0, 34.0)]
    draft.selected_index = 2
    draft.set_selected_segment_curve(radius=12.0, strength=0.65)
    if flare:
        draft.flare_side = VentFlareSide.BOTH
        draft.flare_factor = 1.7
        draft.end_flare_finalized = True
    return draft


def _bad_edge_count(mesh) -> int:
    counts: Counter[tuple[int, int]] = Counter()
    for tri in mesh.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return sum(1 for count in counts.values() if count != 2)


def test_pass50_rectangular_evt_wall_mesh_is_closed_with_curves_and_mouths() -> None:
    mesh = make_vent_path_mesh(_rect_draft(fill_area=False, flare=True))

    assert len(mesh.vertices) > 0
    assert len(mesh.triangles) > 0
    assert _bad_edge_count(mesh) == 0


def test_pass50_fill_area_evt_mesh_is_closed_and_airway_stays_open() -> None:
    draft = _rect_draft(fill_area=True, flare=True)
    material = rectangular_vent_material_footprint(draft, draft.smoothed_centerline(samples_per_segment=24), fill_area=True)

    assert material is not None
    assert not material.is_empty
    # The open airway cutter must remove the full centerline route from the
    # material, otherwise Fill area can cap or block a duct section.
    route = LineString(draft.smoothed_centerline(samples_per_segment=24)).buffer(0.5, cap_style=2, join_style=1)
    assert material.intersection(route).area < 1e-6

    mesh = make_vent_path_mesh(draft)
    assert len(mesh.vertices) > 0
    assert len(mesh.triangles) > 0
    assert _bad_edge_count(mesh) == 0

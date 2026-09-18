# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.planar_tools import (
    VentFlareSide,
    VentPathDraft,
    VentSectionKind,
    make_locked_plane,
    make_vent_path_mesh,
)


def _rect_vent() -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    draft.waypoints = [(0.0, 0.0), (120.0, 0.0), (120.0, 25.0), (40.0, 25.0)]
    return draft


def _outer_y_span(mesh, *, row: int, ring_count: int) -> float:
    start = row * ring_count * 2
    ys = [mesh.vertices[i][1] for i in range(start, start + ring_count)]
    return max(ys) - min(ys)


def _y_span_at_x(mesh, x: float, *, tol: float = 1e-6) -> float:
    ys = [float(v[1]) for v in mesh.vertices if abs(float(v[0]) - float(x)) <= tol]
    assert ys, f"no vertices at x={x}"
    return max(ys) - min(ys)


def test_pass26_end_flare_is_active_without_double_click_finalization() -> None:
    draft = _rect_vent()
    draft.flare_side = VentFlareSide.END
    draft.flare_factor = 1.8

    assert draft.effective_flare_side() is VentFlareSide.END
    assert draft.validation_result().ok is True
    assert "double-clique" not in draft.validation_result().message()

    mesh = make_vent_path_mesh(draft)
    assert _y_span_at_x(mesh, 40.0) > _y_span_at_x(mesh, 0.0)


def test_pass26_start_flare_does_not_globally_clamp_the_whole_pipe_width() -> None:
    draft = _rect_vent()
    draft.flare_side = VentFlareSide.START
    draft.flare_factor = 2.0

    # Compact rectangular vents are now the default workflow: the parallel run
    # is spaced for the normal compact duct (20 + 2 = 22 mm), but not for a
    # globally widened 40 mm inlet. It must remain valid because the flare
    # footprint is local to the inlet.
    assert draft.clearance_policy().min_centerline_spacing == 22.0
    assert draft.validation_result().ok is True


def test_pass26_adding_a_new_waypoint_keeps_outlet_flare_on_current_last_point() -> None:
    draft = _rect_vent()
    draft.flare_side = VentFlareSide.BOTH
    draft.flare_factor = 1.4
    draft.mark_end_flare_finalized(True)
    assert draft.effective_flare_side() is VentFlareSide.BOTH

    draft.add_waypoint_plane((20.0, 60.0))
    assert draft.end_flare_finalized is False
    assert draft.effective_flare_side() is VentFlareSide.BOTH
    assert draft.validation_result().ok is True

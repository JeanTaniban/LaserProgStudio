# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.planar_tools import PlanTraceAddKind, PlanarEditMode, PlanarPolygonDraft, make_locked_plane, sample_plan_trace_element


def test_pass95_plan_trace_line_arc_circle_elements_are_staged_and_selectable() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=4.0)
    assert draft.mode is PlanarEditMode.MOD

    draft.set_add_kind(PlanTraceAddKind.LINE)
    assert draft.mode is PlanarEditMode.ADD
    assert draft.add_trace_point_plane((0.0, 0.0)) is False
    assert draft.add_trace_point_plane((10.0, 0.0)) is True
    assert len(draft.elements) == 1
    assert draft.elements[0].kind is PlanTraceAddKind.LINE

    assert draft.select_nearest_plane((10.1, 0.0), max_distance=1.0) == 1
    assert draft.has_selection()
    draft.update_selected_plane((12.0, 0.0))
    assert draft.elements[0].points[1] == (12.0, 0.0)
    assert draft.delete_selected() is True
    assert len(draft.elements) == 0


def test_pass95_plan_trace_sampling_supports_semicircle_and_circle() -> None:
    arc = sample_plan_trace_element(PlanTraceAddKind.SEMICIRCLE, [(0.0, 0.0), (10.0, 0.0), (5.0, 5.0)], samples=24)
    circle = sample_plan_trace_element(PlanTraceAddKind.CIRCLE, [(0.0, 0.0), (0.0, 5.0)], samples=32)

    assert len(arc) > 8
    assert arc[0] == (0.0, 0.0)
    assert abs(arc[-1][0] - 10.0) < 1e-6
    assert len(circle) == 32
    assert max(abs((x * x + y * y) ** 0.5 - 5.0) for x, y in circle) < 1e-6

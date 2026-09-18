# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.planar_tools import (
    PlanTraceAddKind,
    PlanarPolygonDraft,
    PlanarToolConfig,
    collect_plan_trace_snap_points,
    make_locked_plane,
    nearest_plan_trace_snap,
    snap_plane_point,
)
from laserprog_studio.state.planar_tool_state import PlanarToolState


def test_pass96_plan_trace_snap_reuses_existing_line_endpoint_for_new_junction() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=4.0)
    draft.set_add_kind(PlanTraceAddKind.LINE)
    assert draft.add_trace_point_plane((0.0, 0.0)) is False
    assert draft.add_trace_point_plane((20.0, 0.0)) is True

    anchors = collect_plan_trace_snap_points(draft, samples_per_segment=10)
    assert (20.0, 0.0) in anchors

    snapped, label = snap_plane_point(
        (20.9, 0.7),
        PlanarToolConfig(grid_snap_enabled=False, smart_snap_enabled=True, smart_snap_tolerance=4.0),
        anchor_points=anchors,
    )
    assert snapped == (20.0, 0.0)
    assert label == "smart point"

    hit = nearest_plan_trace_snap((21.0, 0.25), draft, tolerance=4.0)
    assert hit is not None
    assert hit.point == (20.0, 0.0)


def test_pass96_plan_trace_snap_includes_arc_and_active_construction_points() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=4.0)
    draft.set_add_kind(PlanTraceAddKind.SEMICIRCLE)
    draft.active_element_points.append((5.0, 5.0))
    draft.elements.append(
        __import__("laserprog_studio.planar_tools", fromlist=["PlanTraceElement"]).PlanTraceElement(
            kind=PlanTraceAddKind.SEMICIRCLE,
            points=[(0.0, 0.0), (10.0, 0.0), (5.0, 5.0)],
        )
    )

    anchors = collect_plan_trace_snap_points(draft, samples_per_segment=12)
    assert (5.0, 5.0) in anchors
    assert len(anchors) > 8  # sampled arc points are available to snap to, not only endpoints


def test_pass96_planar_state_clears_snap_preview_fields_on_lifecycle() -> None:
    state = PlanarToolState()
    plane = make_locked_plane("top")
    state.begin(tool_id="plan_trace", view=plane.view, plane=plane, previous_camera_view_mode="free")
    state.snap_preview_plane_point = (1.0, 2.0)
    state.snap_preview_raw_plane = (1.2, 2.3)
    state.snap_preview_label = "smart point"
    state.end()

    assert state.snap_preview_plane_point is None
    assert state.snap_preview_raw_plane is None
    assert state.snap_preview_label == ""


def test_pass96_preview_uses_visible_old_style_point_gizmos_and_snap_hint_actor_names() -> None:
    source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")
    assert "render_points_as_spheres=True" in source
    assert "cloud.glyph" in source
    assert "_cached_point_sphere" in source
    assert "planar_tool_preview_snap_hint" in source
    assert "_point_world_radius" in source

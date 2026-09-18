# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.planar_tools import (
    PlanTraceAddKind,
    PlanTraceElement,
    PlanarPolygonDraft,
    PlanarToolConfig,
    make_extruded_polygon_mesh,
    make_locked_plane,
    plan_trace_closed_regions,
    snap_plane_point,
)


def test_plan_trace_smart_snap_targets_projected_edges() -> None:
    snapped, label = snap_plane_point(
        (5.2, 0.8),
        PlanarToolConfig(grid_snap_enabled=False, smart_snap_enabled=True, smart_snap_tolerance=1.0),
        anchor_points=[],
        edge_segments=[((0.0, 0.0), (10.0, 0.0))],
    )
    assert snapped == (5.2, 0.0)
    assert label == "smart edge"


def test_plan_trace_grid_snap_is_explicit_and_independent() -> None:
    snapped, label = snap_plane_point(
        (4.2, 7.6),
        PlanarToolConfig(grid_snap_enabled=True, smart_snap_enabled=False, grid_step=5.0),
        anchor_points=[(4.2, 7.6)],
    )
    assert snapped == (5.0, 10.0)
    assert label == "grid 5"


def test_plan_trace_joined_lines_make_closed_face_and_extrude() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=10.0)
    draft.elements.extend(
        [
            PlanTraceElement(PlanTraceAddKind.LINE, [(0.0, 0.0), (20.0, 0.0)]),
            PlanTraceElement(PlanTraceAddKind.LINE, [(20.0, 0.0), (20.0, 10.0)]),
            PlanTraceElement(PlanTraceAddKind.LINE, [(20.0, 10.0), (0.0, 10.0)]),
            PlanTraceElement(PlanTraceAddKind.LINE, [(0.0, 10.0), (0.0, 0.0)]),
        ]
    )

    regions = plan_trace_closed_regions(draft)
    assert len(regions) == 1
    assert round(regions[0].area, 6) == 200.0
    assert draft.is_ready_for_extrusion()

    mesh = make_extruded_polygon_mesh(draft)
    assert len(mesh.vertices) == 8
    assert len(mesh.triangles) == 12


def test_plan_trace_circle_is_a_real_face_for_extrusion() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=10.0)
    draft.elements.append(PlanTraceElement(PlanTraceAddKind.CIRCLE, [(0.0, 0.0), (5.0, 0.0)]))

    regions = plan_trace_closed_regions(draft)
    assert len(regions) == 1
    assert regions[0].area > 70.0
    assert draft.is_ready_for_extrusion()

    mesh = make_extruded_polygon_mesh(draft)
    assert len(mesh.vertices) >= 32
    assert len(mesh.triangles) >= 60


def test_plan_trace_controller_uses_snap_caches_during_drag() -> None:
    source = __import__("inspect").getsource(__import__("laserprog_studio.application.planar_tool_controller", fromlist=["PlanarToolController"]).PlanarToolController)
    assert "rebuild_plan_trace_scene_snap_cache" in source
    assert "drag_snap_anchor_cache" in source
    assert "_draw_planar_preview_interactive" in source

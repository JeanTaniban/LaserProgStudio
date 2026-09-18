# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.planar_tools import PlanarPolygonDraft, PlanarToolConfig, make_locked_plane, make_extruded_polygon_mesh, snap_plane_point
from laserprog_studio.snapping import find_smart_translation_snap


@dataclass
class DummyMesh:
    vertices: list[tuple[float, float, float]]


def test_pln_segment_curve_is_sampled_in_preview_and_mesh() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=5.0)
    for point in ((0.0, 0.0), (40.0, 0.0), (40.0, 20.0), (0.0, 20.0)):
        draft.add_point_plane(point)
    assert draft.close_polygon()
    draft.selected_index = 1
    assert draft.set_selected_segment_curve(radius=8.0, strength=0.75) == 0

    sampled = draft.sampled_boundary_points(samples_per_segment=24)
    assert len(sampled) > len(draft.points)
    assert draft.validation_result().ok

    mesh = make_extruded_polygon_mesh(draft)
    assert len(mesh.vertices) == len(sampled) * 2
    assert len(mesh.triangles) >= len(sampled)


def test_pln_smart_snap_can_run_without_grid_snap() -> None:
    cfg = PlanarToolConfig(grid_snap_enabled=False, smart_snap_enabled=True, grid_step=10.0, smart_snap_tolerance=1.0)
    snapped, label = snap_plane_point((9.7, 4.3), cfg, anchor_points=[(10.0, 30.0)])
    assert snapped == (10.0, 4.3)
    assert label == "smart U"


def test_translation_smart_snap_uses_internal_mesh_feature_coordinates() -> None:
    # Target has an internal feature at X=12 that is not a bounds min/max/center.
    moving = DummyMesh(vertices=[(5.8, 0.0, 0.0), (6.1, 0.0, 0.0)])
    target = DummyMesh(vertices=[(0.0, 0.0, 0.0), (6.0, 0.0, 0.0), (30.0, 0.0, 0.0)])

    snap = find_smart_translation_snap(
        meshes=[moving, target],
        moving_index=0,
        moving_indices={0},
        proposed_vertices=moving.vertices,
        axis="x",
        tolerance=0.25,
    )

    assert snap.mode == "smart"
    assert snap.candidate is not None
    assert snap.candidate.kind == "feature"
    assert abs(snap.correction + 0.1) < 1e-9

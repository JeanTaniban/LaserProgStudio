# -*- coding: utf-8 -*-
from __future__ import annotations

import math

import pytest

from laserprog_studio.tool_api import tracing
from laserprog_studio.tool_core.tracing import TraceDraftMachine, TraceDraftStatus, TraceMode, normalize_trace_mode
from laserprog_studio.tooling.cloth.flattening import flatten_cloth_document
from laserprog_studio.tooling.cloth.mesh_builder import build_cloth_surface_mesh, triangulate_simple_polygon
from laserprog_studio.tooling.cloth.models import ClothDocument, ClothFoldKind, ClothWorkflowPhase
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan
from laserprog_studio.tooling.cloth.serialization import cloth_document_from_dict, cloth_document_to_dict, restore_cloth_source
from laserprog_studio.tooling.cloth.state_machine import (
    ClothFoldDraftPhase,
    ClothTransitionError,
    ClothWorkflowMachine,
)
from laserprog_studio.tooling.cloth.topology import order_curve_loop, patch_area, sample_patch_boundary
from laserprog_studio.tooling.cloth.validation import validate_cloth_document
from laserprog_studio.tooling.plan_trace_2d.mode_state import PlanTrace2DModeStateService


def _two_panel_document() -> ClothDocument:
    doc = ClothDocument()
    p0 = doc.add_point((0.0, 0.0, 0.0), point_id="p0")
    p1 = doc.add_point((10.0, 0.0, 0.0), point_id="p1")
    p2 = doc.add_point((10.0, 10.0, 0.0), point_id="p2")
    p3 = doc.add_point((0.0, 10.0, 0.0), point_id="p3")
    p4 = doc.add_point((10.0, 10.0, 8.0), point_id="p4")
    p5 = doc.add_point((10.0, 0.0, 8.0), point_id="p5")
    c0 = doc.add_line(p0.id, p1.id, curve_id="c0")
    shared = doc.add_line(p1.id, p2.id, curve_id="shared")
    c2 = doc.add_line(p2.id, p3.id, curve_id="c2")
    c3 = doc.add_line(p3.id, p0.id, curve_id="c3")
    c4 = doc.add_line(p2.id, p4.id, curve_id="c4")
    c5 = doc.add_line(p4.id, p5.id, curve_id="c5")
    c6 = doc.add_line(p5.id, p1.id, curve_id="c6")
    a = doc.add_patch((c0.id, shared.id, c2.id, c3.id), patch_id="panel_a", name="Base")
    b = doc.add_patch((shared.id, c4.id, c5.id, c6.id), patch_id="panel_b", name="Flap")
    doc.add_fold(shared.id, a.id, b.id, fold_id="fold_ab", kind=ClothFoldKind.VALLEY, angle_degrees=90.0)
    return doc


def _distance2(a, b) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def test_shared_tracing_api_is_public_and_plan_tracer_uses_the_same_normalizer() -> None:
    assert tracing.TraceMode.LINE.value == "line"
    assert normalize_trace_mode("polyligne") == "polyline"
    assert PlanTrace2DModeStateService._normalize_tool_mode("polyligne") == "polyline"
    assert PlanTrace2DModeStateService._normalize_tool_mode("demi-cercle") == "half_circle"
    assert PlanTrace2DModeStateService._normalize_tool_mode("cote") == "dimension"


def test_trace_draft_machine_has_deterministic_click_sequences() -> None:
    machine = TraceDraftMachine()
    machine.begin(TraceMode.ARC)
    assert machine.add_point("a").draft.status is TraceDraftStatus.ACTIVE
    assert machine.add_point("b").ready_to_commit is False
    update = machine.add_point("c")
    assert update.ready_to_commit is True
    committed = machine.commit()
    assert committed.committed is True
    assert committed.draft.point_ids == ("a", "b", "c")

    machine.begin(TraceMode.POLYLINE)
    machine.add_point("p0")
    machine.add_point("p1")
    machine.add_point("p2")
    update = machine.finish(closed=True)
    assert update.committed and update.draft.closed


def test_circular_arc_sampler_supports_arbitrary_3d_planes() -> None:
    points = tracing.sample_circular_arc_3d((0.0, 0.0, 0.0), (0.0, 10.0, 0.0), (0.0, 5.0, 5.0), segments=16)
    assert len(points) == 17
    assert points[0] == pytest.approx((0.0, 0.0, 0.0))
    assert points[-1] == pytest.approx((0.0, 10.0, 0.0))
    assert max(abs(point[0]) for point in points) < 1.0e-9


def test_cloth_document_orders_panel_loops_and_measures_surface_area() -> None:
    doc = _two_panel_document()
    assert order_curve_loop(doc, doc.patches["panel_a"].outer_curve_ids) is not None
    assert order_curve_loop(doc, doc.patches["panel_b"].outer_curve_ids) is not None
    assert patch_area(doc, "panel_a") == pytest.approx(100.0)
    assert patch_area(doc, "panel_b") == pytest.approx(80.0)
    assert len(sample_patch_boundary(doc, "panel_a")) == 4


def test_cloth_validation_accepts_two_manifold_planar_panels_and_one_hinge() -> None:
    report = validate_cloth_document(_two_panel_document())
    assert report.can_apply, [issue.message for issue in report.issues]
    assert not report.errors


def test_cloth_validation_rejects_non_planar_panel() -> None:
    doc = _two_panel_document()
    doc.move_point("p3", (0.0, 10.0, 1.0))
    report = validate_cloth_document(doc)
    assert not report.can_apply
    assert "cloth.patch.non_planar" in {issue.code for issue in report.errors}


def test_rigid_flattening_preserves_all_boundary_lengths_and_places_panels_opposite_the_hinge() -> None:
    doc = _two_panel_document()
    flat = flatten_cloth_document(doc)
    assert flat.success, [issue.message for issue in flat.issues]
    a = flat.placements["panel_a"]
    b = flat.placements["panel_b"]
    for first_id, second_id in (("p0", "p1"), ("p1", "p2"), ("p2", "p3"), ("p2", "p4"), ("p4", "p5"), ("p5", "p1")):
        world_a = doc.points[first_id].position
        world_b = doc.points[second_id].position
        placement = a if {first_id, second_id} <= {"p0", "p1", "p2", "p3"} else b
        assert _distance2(placement.map_world(world_a), placement.map_world(world_b)) == pytest.approx(
            math.dist(world_a, world_b), abs=1.0e-8
        )
    hinge_a = a.map_world(doc.points["p1"].position)
    hinge_b = a.map_world(doc.points["p2"].position)
    edge = (hinge_b[0] - hinge_a[0], hinge_b[1] - hinge_a[1])
    centroid_a = tuple(sum(a.map_world(point)[i] for point in sample_patch_boundary(doc, "panel_a")) / 4 for i in (0, 1))
    centroid_b = tuple(sum(b.map_world(point)[i] for point in sample_patch_boundary(doc, "panel_b")) / 4 for i in (0, 1))
    side_a = edge[0] * (centroid_a[1] - hinge_a[1]) - edge[1] * (centroid_a[0] - hinge_a[0])
    side_b = edge[0] * (centroid_b[1] - hinge_a[1]) - edge[1] * (centroid_b[0] - hinge_a[0])
    assert side_a * side_b < 0.0


def test_surface_mesh_builder_creates_faces_only_for_folded_and_flat_outputs() -> None:
    doc = _two_panel_document()
    flat = flatten_cloth_document(doc)
    folded_mesh = build_cloth_surface_mesh(doc, name="Folded")
    flat_mesh = build_cloth_surface_mesh(doc, name="Flat", flattened=flat)
    assert folded_mesh.success and flat_mesh.success
    assert len(folded_mesh.mesh.triangles) == 4
    assert len(flat_mesh.mesh.triangles) == 4
    assert all(abs(vertex[2]) < 1.0e-9 for vertex in flat_mesh.mesh.vertices)
    assert folded_mesh.mesh.metadata["cloth_surface_only"] is True
    assert flat_mesh.mesh.metadata["cloth_flattened"] is True


def test_concave_panel_triangulation_does_not_fall_back_to_an_invalid_fan() -> None:
    polygon = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (2.0, 2.0), (0.0, 4.0)]
    triangles = triangulate_simple_polygon(polygon)
    assert len(triangles) == 3
    assert {index for triangle in triangles for index in triangle} == set(range(5))


def test_serialization_round_trip_preserves_ids_topology_and_fold_parameters() -> None:
    doc = _two_panel_document()
    restored = cloth_document_from_dict(cloth_document_to_dict(doc))
    assert tuple(restored.points) == tuple(doc.points)
    assert tuple(restored.curves) == tuple(doc.curves)
    assert tuple(restored.patches) == tuple(doc.patches)
    assert restored.folds["fold_ab"].angle_degrees == pytest.approx(90.0)
    assert validate_cloth_document(restored).can_apply


def test_apply_plan_contains_editable_folded_and_flat_surface_meshes() -> None:
    doc = _two_panel_document()
    plan = build_cloth_apply_plan(doc, name="Sleeve")
    assert plan.ready, plan.issues
    assert plan.flat_scene_name == "Sleeve · Flat pattern"
    assert plan.folded_mesh is not None and plan.flat_mesh is not None
    restored_folded = restore_cloth_source(plan.folded_mesh)
    restored_flat = restore_cloth_source(plan.flat_mesh)
    assert restored_folded is not None and restored_folded[1] == "folded"
    assert restored_flat is not None and restored_flat[1] == "flat"
    assert tuple(restored_folded[0].patches) == ("panel_a", "panel_b")


def test_workflow_machine_keeps_opening_edit_preview_apply_and_cancel_explicit() -> None:
    machine = ClothWorkflowMachine()
    assert machine.session.phase is ClothWorkflowPhase.OPENING
    machine.start_new()
    assert machine.session.phase is ClothWorkflowPhase.EDITING
    machine.session.document = _two_panel_document()
    machine.session.dirty = True
    machine.request_flat_preview()
    assert machine.session.phase is ClothWorkflowPhase.FLAT_PREVIEW
    plan = machine.prepare_apply(name="Cloth test")
    assert plan.ready
    assert machine.session.phase is ClothWorkflowPhase.APPLY_READY
    machine.mark_applied()
    assert machine.session.phase is ClothWorkflowPhase.APPLIED
    assert not machine.invariant_issues()

    second = ClothWorkflowMachine()
    second.edit_existing(_two_panel_document(), source_mesh_id="mesh-cloth")
    second.session.document.move_point("p0", (-5.0, 0.0, 0.0))
    second.cancel()
    assert second.session.phase is ClothWorkflowPhase.CANCELLED
    assert second.session.document.points["p0"].position == pytest.approx((0.0, 0.0, 0.0))


def test_workflow_machine_blocks_illegal_transitions_instead_of_silently_mutating_state() -> None:
    machine = ClothWorkflowMachine()
    with pytest.raises(ClothTransitionError):
        machine.begin_trace(TraceMode.LINE)
    machine.start_new()
    with pytest.raises(ClothTransitionError):
        machine.mark_applied()


def test_fold_draft_machine_requires_edge_second_panel_then_angle() -> None:
    machine = ClothWorkflowMachine()
    machine.start_new()
    machine.session.document = _two_panel_document()
    draft = machine.begin_fold()
    assert draft.phase is ClothFoldDraftPhase.SELECT_EDGE
    machine.fold.select_edge("shared", "panel_a")
    machine.fold.select_second_panel("panel_b")
    machine.fold.adjust(angle_degrees=45.0, kind=ClothFoldKind.MOUNTAIN)
    assert machine.fold.draft.phase is ClothFoldDraftPhase.READY
    # Existing document already contains a fold on this edge; remove it to test commit.
    machine.session.document.folds.clear()
    fold = machine.commit_fold()
    assert fold.angle_degrees == pytest.approx(45.0)
    assert fold.kind is ClothFoldKind.MOUNTAIN

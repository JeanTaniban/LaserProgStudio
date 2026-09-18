from __future__ import annotations

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.flattening import flatten_cloth_document
from laserprog_studio.tooling.cloth.geometry_overlay import (
    CLOTH_GEOMETRY_ACTION_PREFIX,
    CLOTH_GEOMETRY_WINDOW_ID,
    ClothGeometryTraceOverlay,
)
from laserprog_studio.tooling.cloth.geometry_trace import (
    ClothGeometryTraceController,
    SourceEdgeSelection,
    SourceMeshSnapshot,
    ordered_boundary_loops,
    structural_mesh_edges,
)
from laserprog_studio.tooling.cloth.mesh_builder import build_cloth_surface_mesh
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.validation import validate_cloth_document


def _cube_snapshot() -> SourceMeshSnapshot:
    vertices = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0),
        (10.0, 0.0, 10.0),
        (10.0, 10.0, 10.0),
        (0.0, 10.0, 10.0),
    )
    triangles = (
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    )
    return SourceMeshSnapshot("cube", 0, "Cube", vertices, triangles)


def test_connected_twice_uses_semantic_cube_edges_not_triangle_diagonals() -> None:
    snapshot = _cube_snapshot()
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    controller.selected_edges = (
        SourceEdgeSelection(snapshot.object_id, (0, 1)),
        SourceEdgeSelection(snapshot.object_id, (1, 2)),
    )

    assert controller.apply_prediction("connected") == 5
    assert controller.apply_prediction("connected") == 5

    selected = {item.edge for item in controller.selected_edges}
    assert selected == set(structural_mesh_edges(snapshot))
    assert len(selected) == 12
    assert len(snapshot.edges) == 18
    assert (0, 2) not in selected
    assert (4, 6) not in selected


def test_connected_twice_then_trace_reconstructs_six_cube_faces_transactionally() -> None:
    snapshot = _cube_snapshot()
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    controller.selected_edges = (
        SourceEdgeSelection(snapshot.object_id, (0, 1)),
        SourceEdgeSelection(snapshot.object_id, (1, 2)),
    )
    controller.apply_prediction("connected")
    controller.apply_prediction("connected")
    document = ClothDocument()

    outcome = controller.create(document, ClothDrawingController(document))

    assert outcome.committed, outcome.message
    assert len(document.points) == 8
    assert len(document.curves) == 12
    assert len(document.patches) == 6
    assert all(len(patch.outer_curve_ids) == 4 for patch in document.patches.values())
    # A closed cube has many adjacency cycles. Mesh trace keeps a fold spanning
    # tree and converts the other shared edges into automatic pattern cuts.
    assert len(document.folds) == 5
    assert sum(bool(curve.metadata.get("cloth_auto_cut")) for curve in document.curves.values()) == 7
    assert not validate_cloth_document(document).errors

    folded = build_cloth_surface_mesh(document)
    assert folded.success, folded.issues
    assert folded.mesh is not None and len(folded.mesh.triangles) == 12
    flattened = flatten_cloth_document(document)
    assert flattened.success, flattened.issues
    flat_mesh = build_cloth_surface_mesh(document, flattened=flattened)
    assert flat_mesh.success, flat_mesh.issues
    assert flat_mesh.mesh is not None and len(flat_mesh.mesh.triangles) == 12


def test_close_face_prediction_adds_one_small_hidden_cube_edge() -> None:
    snapshot = _cube_snapshot()
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    controller.selected_edges = tuple(
        SourceEdgeSelection(snapshot.object_id, edge)
        for edge in ((0, 1), (1, 2), (2, 3))
    )

    predictions = controller.predictions()

    assert tuple(item.edge for item in predictions.closure_edges) == ((0, 3),)
    assert any(not plan.complete and plan.coverage == 0.75 for plan in predictions.closable_faces)
    assert controller.apply_prediction("close_face") == 1
    completed = controller.predictions()
    assert not completed.closure_edges
    assert any(plan.complete for plan in completed.closable_faces)


def test_close_face_overlay_is_contextual_and_explains_near_closure() -> None:
    snapshot = _cube_snapshot()
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    overlay = ClothGeometryTraceOverlay("cloth", controller)
    ctx = ToolContext()

    overlay.sync(ctx)
    initial = {button.id: button for button in ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID).buttons}
    assert not initial[f"{CLOTH_GEOMETRY_ACTION_PREFIX}close_source_face"].enabled

    controller.selected_edges = tuple(
        SourceEdgeSelection(snapshot.object_id, edge)
        for edge in ((0, 1), (1, 2), (2, 3))
    )
    controller.revision += 1
    overlay.sync(ctx)
    window = ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID)
    buttons = {button.id: button for button in window.buttons}
    assert buttons[f"{CLOTH_GEOMETRY_ACTION_PREFIX}close_source_face"].enabled
    status = next(field.value for field in window.fields if field.id == "cloth.geometry.status")
    assert "Face nearly closed" in status
    assert "1 small/hidden" in status


def test_residual_mesh_edges_are_batched_without_automatic_face_search(monkeypatch) -> None:
    snapshot = _cube_snapshot()
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    # Three disjoint semantic edges do not form a source face, a closed loop,
    # or the special two-rail Cover case.
    controller.selected_edges = (
        SourceEdgeSelection(snapshot.object_id, (0, 1)),
        SourceEdgeSelection(snapshot.object_id, (4, 5)),
        SourceEdgeSelection(snapshot.object_id, (2, 3)),
    )
    document = ClothDocument()
    drawing = ClothDrawingController(document)

    def forbidden(_self, _curve_ids):
        raise AssertionError("Mesh trace must not run automatic face discovery per residual edge")

    monkeypatch.setattr(ClothDrawingController, "_auto_create_faces", forbidden)
    outcome = controller.create(document, drawing)

    assert outcome.committed, outcome.message
    assert len(document.curves) == 3
    assert not document.patches


def test_open_or_branched_edge_sets_are_never_reported_as_closed_loops() -> None:
    assert ordered_boundary_loops(((0, 1), (1, 2), (2, 3))) == ()
    assert ordered_boundary_loops(((0, 1), (1, 2), (2, 0), (1, 3))) == ()
    assert ordered_boundary_loops(((0, 1), (1, 2), (2, 3), (0, 3))) == ((0, 1, 2, 3),)


def test_trace_selection_budget_fails_before_mutating_the_document() -> None:
    snapshot = _cube_snapshot()
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    controller.selected_edges = tuple(
        SourceEdgeSelection(snapshot.object_id, (0, 1))
        for _ in range(5001)
    )
    document = ClothDocument()

    outcome = controller.create(document, ClothDrawingController(document))

    assert not outcome.committed
    assert "limited to 5000" in outcome.message
    assert not document.points and not document.curves and not document.patches

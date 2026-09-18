from __future__ import annotations

from copy import deepcopy

import pytest

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tooling.cloth.boolean_bridge import (
    attach_boolean_operation_to_cloth_result,
    prepare_cloth_mesh_for_boolean,
)
from laserprog_studio.tooling.cloth.boolean_pattern import append_cloth_boolean_modifier, cloth_boolean_modifiers
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.flattening import flatten_cloth_document
from laserprog_studio.tooling.cloth.geometry_trace import (
    ClothGeometryTraceController,
    SourceEdgeSelection,
    structural_mesh_edges,
)
from laserprog_studio.tooling.cloth.mesh_builder import build_cloth_surface_mesh
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan
from laserprog_studio.tooling.cloth.serialization import attach_cloth_source, restore_cloth_source
from laserprog_studio.tooling.cloth.stitching import heal_cloth_stitches



def _cube_snapshot():
    from laserprog_studio.tooling.cloth.geometry_trace import SourceMeshSnapshot

    vertices = (
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
        (0.0, 0.0, 10.0), (10.0, 0.0, 10.0), (10.0, 10.0, 10.0), (0.0, 10.0, 10.0),
    )
    triangles = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    )
    return SourceMeshSnapshot("cube", 0, "Cube", vertices, triangles)

def _box(name: str, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> WorkMesh:
    vertices = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    return WorkMesh(name, vertices, triangles)


def _square_document(size: float = 20.0) -> ClothDocument:
    document = ClothDocument(metadata={"cloth_thickness_mm": 0.4, "cloth_stitch_tolerance_mm": 0.05})
    for point_id, position in {
        "p0": (0.0, 0.0, 0.0),
        "p1": (size, 0.0, 0.0),
        "p2": (size, size, 0.0),
        "p3": (0.0, size, 0.0),
    }.items():
        document.add_point(position, point_id=point_id)
    for curve_id, first, second in (
        ("c0", "p0", "p1"), ("c1", "p1", "p2"),
        ("c2", "p2", "p3"), ("c3", "p3", "p0"),
    ):
        document.add_line(first, second, curve_id=curve_id)
    document.add_patch(("c0", "c1", "c2", "c3"), patch_id="panel", name="Panel")
    return document



def _right_angle_document() -> ClothDocument:
    document = ClothDocument(metadata={"cloth_thickness_mm": 0.3, "cloth_stitch_tolerance_mm": 0.05})
    for point_id, position in {
        "p0": (0.0, 0.0, 0.0), "p1": (10.0, 0.0, 0.0),
        "p2": (10.0, 10.0, 0.0), "p3": (0.0, 10.0, 0.0),
        "p4": (0.0, 0.0, 10.0), "p5": (0.0, 10.0, 10.0),
    }.items():
        document.add_point(position, point_id=point_id)
    for curve_id, first, second in (
        ("a0", "p0", "p1"), ("a1", "p1", "p2"), ("a2", "p2", "p3"),
        ("shared", "p3", "p0"), ("b0", "p0", "p4"),
        ("b1", "p4", "p5"), ("b2", "p5", "p3"),
    ):
        document.add_line(first, second, curve_id=curve_id)
    document.add_patch(("a0", "a1", "a2", "shared"), patch_id="a", name="Horizontal")
    document.add_patch(("b0", "b1", "b2", "shared"), patch_id="b", name="Vertical")
    document.add_fold("shared", "a", "b", fold_id="fold")
    return document

def _flat_area(mesh: WorkMesh) -> float:
    area = 0.0
    for first, second, third in mesh.triangles:
        a, b, c = mesh.vertices[first], mesh.vertices[second], mesh.vertices[third]
        area += abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) * 0.5
    return area


def _micro_gap_document(*, explicit_cut: bool = False) -> ClothDocument:
    document = ClothDocument(metadata={"cloth_stitch_tolerance_mm": 0.05})
    points = {
        "a0": (0.0, 0.0, 0.0), "a1": (10.0, 0.0, 0.0),
        "a2": (10.0, 10.0, 0.0), "a3": (0.0, 10.0, 0.0),
        "b0": (10.02, 0.0, 0.0), "b1": (20.0, 0.0, 0.0),
        "b2": (20.0, 10.0, 0.0), "b3": (10.02, 10.0, 0.0),
    }
    for point_id, position in points.items():
        document.add_point(position, point_id=point_id)
    for curve_id, first, second in (
        ("a0c", "a0", "a1"), ("aseam", "a1", "a2"),
        ("a2c", "a2", "a3"), ("a3c", "a3", "a0"),
        ("b0c", "b0", "b1"), ("b1c", "b1", "b2"),
        ("b2c", "b2", "b3"), ("bseam", "b3", "b0"),
    ):
        metadata = {"cloth_user_cut": True} if explicit_cut and curve_id in {"aseam", "bseam"} else None
        document.add_line(first, second, curve_id=curve_id, metadata=metadata)
    document.add_patch(("a0c", "aseam", "a2c", "a3c"), patch_id="a")
    document.add_patch(("b0c", "b1c", "b2c", "bseam"), patch_id="b")
    return document


def test_apply_generates_boolean_ready_closed_thin_solid() -> None:
    plan = build_cloth_apply_plan(_square_document(), name="Sheet")

    assert plan.ready, plan.issues
    assert plan.folded_mesh is not None
    assert is_closed_triangle_mesh(plan.folded_mesh.vertices, plan.folded_mesh.triangles) == (True, 0, 0)
    assert plan.folded_mesh.metadata["cloth_boolean_ready"] is True
    assert plan.folded_mesh.metadata["cloth_surface_only"] is False
    assert plan.folded_mesh.metadata["cloth_thickness_mm"] == pytest.approx(0.4)
    assert len(plan.folded_mesh.vertices) == 8
    assert len(plan.folded_mesh.triangles) == 12


def test_legacy_open_cloth_is_regenerated_from_source_before_boolean() -> None:
    document = _square_document()
    legacy = build_cloth_surface_mesh(document, name="Legacy", solid=False).mesh
    assert legacy is not None
    legacy = attach_cloth_source(legacy, document=document, output_kind="folded")
    assert not is_closed_triangle_mesh(legacy.vertices, legacy.triangles)[0]

    prepared = prepare_cloth_mesh_for_boolean(legacy)

    assert is_closed_triangle_mesh(prepared.vertices, prepared.triangles) == (True, 0, 0)
    assert prepared.metadata["cloth_boolean_ready"] is True
    assert restore_cloth_source(prepared) is not None


def test_boolean_hole_is_regenerated_in_folded_and_flat_outputs() -> None:
    document = _square_document()
    append_cloth_boolean_modifier(
        document,
        _box("pin", 8.0, 12.0, 8.0, 12.0, -2.0, 2.0),
        operation="difference",
    )

    plan = build_cloth_apply_plan(document, name="Sheet with pin hole")

    assert plan.ready, plan.issues
    assert plan.flat_mesh is not None and plan.folded_mesh is not None
    assert _flat_area(plan.flat_mesh) == pytest.approx(400.0 - 16.0, abs=1.0e-6)
    assert is_closed_triangle_mesh(plan.folded_mesh.vertices, plan.folded_mesh.triangles) == (True, 0, 0)
    # Outer loop plus one inner loop are both represented as flat boundary edges.
    _closed, boundary_edges, nonmanifold_edges = is_closed_triangle_mesh(plan.flat_mesh.vertices, plan.flat_mesh.triangles)
    assert boundary_edges >= 8
    assert nonmanifold_edges == 0


def test_boolean_edge_notch_is_preserved_when_flattened() -> None:
    document = _square_document()
    append_cloth_boolean_modifier(
        document,
        _box("notch", -2.0, 5.0, 8.0, 12.0, -2.0, 2.0),
        operation="difference",
    )

    plan = build_cloth_apply_plan(document)

    assert plan.ready, plan.issues
    assert plan.flat_mesh is not None
    assert _flat_area(plan.flat_mesh) == pytest.approx(400.0 - 20.0, abs=1.0e-6)


def test_notch_crossing_a_fold_is_projected_to_both_flat_panels() -> None:
    document = _right_angle_document()
    append_cloth_boolean_modifier(
        document,
        _box("fold-notch", -2.0, 2.0, 4.0, 6.0, -2.0, 2.0),
        operation="difference",
    )

    plan = build_cloth_apply_plan(document)

    assert plan.ready, plan.issues
    assert plan.flat_mesh is not None and plan.folded_mesh is not None
    assert _flat_area(plan.flat_mesh) == pytest.approx(192.0, abs=1.0e-6)
    assert is_closed_triangle_mesh(plan.folded_mesh.vertices, plan.folded_mesh.triangles) == (True, 0, 0)


def test_boolean_result_keeps_editable_source_and_supports_chained_modifiers() -> None:
    initial = build_cloth_apply_plan(_square_document()).folded_mesh
    assert initial is not None
    initial.metadata["cloth_linked_flat_scene_id"] = "flat-scene"
    first_cutter = _box("pin-a", 3.0, 5.0, 3.0, 5.0, -2.0, 2.0)
    first_result = attach_boolean_operation_to_cloth_result(
        initial, first_cutter, deepcopy(initial), operation="difference"
    )
    second_cutter = _box("pin-b", 15.0, 17.0, 15.0, 17.0, -2.0, 2.0)
    second_result = attach_boolean_operation_to_cloth_result(
        first_result, second_cutter, deepcopy(first_result), operation="difference"
    )

    restored = restore_cloth_source(second_result)
    assert restored is not None
    document, output_kind = restored
    assert output_kind == "folded"
    assert len(cloth_boolean_modifiers(document)) == 2
    assert second_result.metadata["cloth_linked_flat_scene_id"] == "flat-scene"
    rebuilt = build_cloth_apply_plan(document)
    assert rebuilt.ready, rebuilt.issues
    assert rebuilt.flat_mesh is not None
    assert _flat_area(rebuilt.flat_mesh) == pytest.approx(392.0, abs=1.0e-6)


def test_cube_pattern_cuts_do_not_create_nonmanifold_boolean_input() -> None:
    snapshot = _cube_snapshot()
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    controller.selected_edges = tuple(
        SourceEdgeSelection(snapshot.object_id, edge) for edge in structural_mesh_edges(snapshot)
    )
    document = ClothDocument(metadata={"cloth_thickness_mm": 0.2})
    outcome = controller.create(document, ClothDrawingController(document))
    assert outcome.committed
    assert sum(bool(curve.metadata.get("cloth_auto_cut")) for curve in document.curves.values()) == 7

    plan = build_cloth_apply_plan(document, name="Cube cloth")

    assert plan.ready, plan.issues
    assert plan.folded_mesh is not None
    assert is_closed_triangle_mesh(plan.folded_mesh.vertices, plan.folded_mesh.triangles) == (True, 0, 0)
    assert plan.folded_mesh.metadata["cloth_closed_mid_surface"] is True


def test_stitch_tolerance_heals_a_microscopic_gap_into_one_pattern_piece() -> None:
    document = _micro_gap_document()

    report = heal_cloth_stitches(document)
    flattened = flatten_cloth_document(document)

    assert report.healed_curve_pairs == 1
    assert report.created_folds == 1
    assert report.snapped_points == 2
    assert flattened.success
    assert len({placement.component_index for placement in flattened.placements.values()}) == 1
    plan = build_cloth_apply_plan(document)
    assert plan.ready, plan.issues
    assert plan.folded_mesh is not None
    assert is_closed_triangle_mesh(plan.folded_mesh.vertices, plan.folded_mesh.triangles) == (True, 0, 0)


def test_stitch_tolerance_never_reconnects_an_explicit_cut() -> None:
    document = _micro_gap_document(explicit_cut=True)

    report = heal_cloth_stitches(document)
    flattened = flatten_cloth_document(document)

    assert report.healed_curve_pairs == 0
    assert not document.folds
    assert flattened.success
    assert len({placement.component_index for placement in flattened.placements.values()}) == 2


def test_flat_pattern_output_is_rejected_as_boolean_target() -> None:
    plan = build_cloth_apply_plan(_square_document())
    assert plan.ready and plan.flat_mesh is not None
    with pytest.raises(ValueError, match="3D Cloth output"):
        prepare_cloth_mesh_for_boolean(plan.flat_mesh)

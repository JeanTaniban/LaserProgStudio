from __future__ import annotations

from copy import deepcopy
import math

import pytest

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tooling.cloth import boolean_modifiers as modifier_module
from laserprog_studio.tooling.cloth.boolean_modifiers import (
    CLOTH_BOOLEAN_MODIFIERS_KEY,
    append_cloth_boolean_modifier,
)
from laserprog_studio.tooling.cloth.mesh_builder import build_cloth_surface_mesh
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan
from laserprog_studio.tooling.cloth.stitching import heal_cloth_stitches


def _box(name: str, x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> WorkMesh:
    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    triangles = [
        (0, 2, 1),
        (0, 3, 2),
        (4, 5, 6),
        (4, 6, 7),
        (0, 1, 5),
        (0, 5, 4),
        (1, 2, 6),
        (1, 6, 5),
        (2, 3, 7),
        (2, 7, 6),
        (3, 0, 4),
        (3, 4, 7),
    ]
    return WorkMesh(name, vertices, triangles)


def _two_panel_document(*, gap_mm: float = 0.0, add_seam: bool = False) -> ClothDocument:
    document = ClothDocument(
        metadata={
            "cloth_thickness_mm": 0.3,
            "cloth_stitch_tolerance_mm": 0.05,
        }
    )
    points = {
        "a0": (0.0, 0.0, 0.0),
        "a1": (10.0, 0.0, 0.0),
        "a2": (10.0, 10.0, 0.0),
        "a3": (0.0, 10.0, 0.0),
        "b0": (10.0 + gap_mm, 0.0, 0.0),
        "b1": (20.0, 0.0, 0.0),
        "b2": (20.0, 10.0, 0.0),
        "b3": (10.0 + gap_mm, 10.0, 0.0),
    }
    for point_id, position in points.items():
        document.add_point(position, point_id=point_id)
    for curve_id, first, second in (
        ("a_bottom", "a0", "a1"),
        ("a_join", "a1", "a2"),
        ("a_top", "a2", "a3"),
        ("a_left", "a3", "a0"),
        ("b_bottom", "b0", "b1"),
        ("b_right", "b1", "b2"),
        ("b_top", "b2", "b3"),
        ("b_join", "b3", "b0"),
    ):
        document.add_line(first, second, curve_id=curve_id)
    document.add_patch(
        ("a_bottom", "a_join", "a_top", "a_left"),
        patch_id="panel_a",
        name="A",
    )
    document.add_patch(
        ("b_bottom", "b_right", "b_top", "b_join"),
        patch_id="panel_b",
        name="B",
    )
    if add_seam:
        document.add_seam(("a_join",), ("b_join",), seam_id="authored_seam")
    return document


def test_modifier_append_is_atomic_for_invalid_non_finite_mesh() -> None:
    document = _two_panel_document()
    before_metadata = deepcopy(document.metadata)
    before_revision = document.revision
    invalid = WorkMesh(
        "invalid",
        [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (math.nan, 1.0, 0.0)],
        [(0, 1, 2)],
    )

    with pytest.raises(ValueError, match="finite coordinates"):
        append_cloth_boolean_modifier(document, invalid, operation="difference")

    assert document.metadata == before_metadata
    assert document.revision == before_revision


def test_malformed_persisted_modifier_fails_closed_with_clear_issue() -> None:
    document = _two_panel_document()
    document.metadata[CLOTH_BOOLEAN_MODIFIERS_KEY] = [
        {
            "version": 1,
            "operation": "difference",
            "mesh": {
                "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                "triangles": [[0, 1, 99]],
            },
        }
    ]

    result = build_cloth_surface_mesh(document)

    assert result.mesh is None
    assert any("outside the cutter mesh" in issue for issue in result.issues)


def test_modifier_payload_is_parsed_once_for_all_panels(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _two_panel_document()
    append_cloth_boolean_modifier(
        document,
        _box("far cutter", 100.0, 101.0, 100.0, 101.0, -1.0, 1.0),
        operation="difference",
    )
    calls = 0
    original = modifier_module.modifier_from_payload

    def counted(payload):
        nonlocal calls
        calls += 1
        return original(payload)

    monkeypatch.setattr(modifier_module, "modifier_from_payload", counted)

    result = build_cloth_surface_mesh(document)

    assert result.success, result.issues
    assert calls == 1


def test_authored_seam_is_never_converted_to_a_fold_by_tolerance_healing() -> None:
    document = _two_panel_document(gap_mm=0.02, add_seam=True)

    report = heal_cloth_stitches(document)

    assert report.healed_curve_pairs == 0
    assert report.created_folds == 0
    assert not document.folds
    assert "a_join" in document.curves
    assert "b_join" in document.curves
    assert document.seams["authored_seam"].first_curve_ids == ("a_join",)
    assert document.seams["authored_seam"].second_curve_ids == ("b_join",)


def test_apply_preflight_heals_only_its_clone_and_does_not_mutate_source() -> None:
    document = _two_panel_document(gap_mm=0.02)
    before = deepcopy(document)

    plan = build_cloth_apply_plan(document, name="Healed clone")

    assert plan.ready, plan.issues
    assert document == before
    assert not document.folds
    assert len(document.curves) == 8


def test_boolean_result_drops_stale_generated_topology_metadata() -> None:
    from laserprog_studio.tooling.cloth.boolean_bridge import (
        attach_boolean_operation_to_cloth_result,
    )

    initial = build_cloth_apply_plan(_two_panel_document()).folded_mesh
    assert initial is not None
    assert "cloth_mid_surface_vertices" in initial.metadata
    cutter = _box("pin", 2.0, 3.0, 2.0, 3.0, -1.0, 1.0)

    result = attach_boolean_operation_to_cloth_result(
        initial,
        cutter,
        deepcopy(initial),
        operation="difference",
    )

    assert "cloth_mid_surface_vertices" not in result.metadata
    assert "cloth_patch_triangle_ranges" not in result.metadata
    assert result.metadata["cloth_boolean_modifier_count"] == 1
    assert result.metadata["cloth_boolean_last_operation"] == "difference"


def test_internal_source_attachment_reuses_fresh_geometry_buffers() -> None:
    from laserprog_studio.tooling.cloth.serialization import attach_cloth_source_in_place

    document = _two_panel_document()
    mesh = _box("fresh", 0.0, 1.0, 0.0, 1.0, 0.0, 1.0)
    vertices = mesh.vertices
    triangles = mesh.triangles

    attached = attach_cloth_source_in_place(mesh, document=document, output_kind="folded")

    assert attached is mesh
    assert attached.vertices is vertices
    assert attached.triangles is triangles

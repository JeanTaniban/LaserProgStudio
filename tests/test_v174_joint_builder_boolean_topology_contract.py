# -*- coding: utf-8 -*-
from __future__ import annotations

import copy

import pytest

from laserprog_studio.boolean_ops import _finalize_canonical_boolean_mesh, is_closed_triangle_mesh
from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.fabrication.joint_builder_core import _validate_joint_boolean_outputs


def _box(name: str = "box") -> WorkMesh:
    vertices = [
        (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
        (0.0, 0.0, 3.0), (10.0, 0.0, 3.0), (10.0, 10.0, 3.0), (0.0, 10.0, 3.0),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    return WorkMesh(name=name, vertices=vertices, triangles=triangles, color="#CCC")


def test_v174_canonical_boolean_result_is_preserved_exactly() -> None:
    mesh = _box("canonical")
    original_vertices = copy.deepcopy(mesh.vertices)
    original_triangles = copy.deepcopy(mesh.triangles)

    result = _finalize_canonical_boolean_mesh(mesh)

    assert result is mesh
    assert result.vertices == original_vertices
    assert result.triangles == original_triangles
    assert result.metadata["boolean_ready"] is True
    assert result.metadata["boolean_topology_contract"] == "manifold3d_canonical_v1"
    assert is_closed_triangle_mesh(result.vertices, result.triangles) == (True, 0, 0)


def test_v174_joint_builder_marks_both_closed_results_boolean_ready() -> None:
    male = _box("male")
    female = _box("female")

    stats = _validate_joint_boolean_outputs(male, female)

    assert stats["male"]["closed"] is True
    assert stats["female"]["closed"] is True
    assert male.metadata["boolean_ready"] is True
    assert female.metadata["boolean_ready"] is True
    assert male.metadata["joint_builder_topology_contract"] == "closed_solid_v1"
    assert female.metadata["joint_builder_topology_contract"] == "closed_solid_v1"


def test_v174_joint_builder_refuses_open_output_before_preview_commit() -> None:
    male = _box("male")
    female = _box("female-open")
    female.triangles = female.triangles[:-1]
    assert is_closed_triangle_mesh(female.vertices, female.triangles)[0] is False

    with pytest.raises(ValueError, match="refused an invalid solid result") as exc:
        _validate_joint_boolean_outputs(male, female)

    assert "boundary_edges=" in str(exc.value)
    assert "boolean_ready" not in female.metadata


def test_v174_joint_builder_diagnostics_report_topology_only_when_callback_is_present() -> None:
    events: list[tuple[str, dict]] = []
    male = _box("male")
    female = _box("female")

    _validate_joint_boolean_outputs(male, female, debug=lambda tag, payload: events.append((tag, payload)))

    assert events
    assert events[-1][0] == "joint_output_topology_validated"
    assert events[-1][1]["results"]["male"]["boundary_edges"] == 0


def test_v174_regression_generic_cleanup_can_open_a_topologically_closed_canonical_mesh() -> None:
    # This models the exact class of failure seen after Joint Builder: a boolean
    # backend may return a valid indexed solid containing an extremely thin
    # tessellation cell. Generic tolerance welding/removal can collapse that cell
    # and turn the next boolean input into an open surface.
    from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh

    mesh = WorkMesh(
        name="canonical-sliver",
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0e-10, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ],
        triangles=[(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
        color="#CCC",
    )
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)

    repaired, report = repair_work_mesh(
        mesh,
        tolerance_mm=0.002,
        fill_holes=False,
        remove_tiny_faces=True,
        optional_backends=False,
    )

    assert report.removed_degenerate > 0
    assert is_closed_triangle_mesh(repaired.vertices, repaired.triangles)[0] is False

    preserved = _finalize_canonical_boolean_mesh(mesh)
    assert preserved.triangles == mesh.triangles
    assert is_closed_triangle_mesh(preserved.vertices, preserved.triangles) == (True, 0, 0)

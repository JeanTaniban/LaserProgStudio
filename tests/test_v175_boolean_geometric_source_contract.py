# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.fabrication.cube_boolean import make_cube_mesh
from laserprog_studio.fabrication.joint_builder_core import (
    _validate_joint_boolean_outputs,
    apply_tab_slot_simple,
    apply_tab_slot_to_scene,
)
from laserprog_studio.geometry_ops.boolean_topology_contract import (
    analyze_work_mesh_boolean_topology,
    require_geometric_boolean_manifold,
)
from laserprog_studio.planar_tools import make_locked_plane
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _box(name: str = "box") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0),
            (0.0, 0.0, 3.0), (10.0, 0.0, 3.0), (10.0, 10.0, 3.0), (0.0, 10.0, 3.0),
        ],
        triangles=[
            (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
            (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
        ],
        color="#CCC",
    )


def _closed_but_geometrically_collapsed() -> WorkMesh:
    # Closed by triangle indices (tetrahedron), but v0/v1 are geometrically the
    # same at boolean precision.  Welding that edge collapses two faces and
    # exposes boundaries: this is the same failure signature as the user's
    # indexed_closed=True -> merge_changed=True -> NotManifold report.
    return WorkMesh(
        name="zero-length-seam",
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0e-10, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ],
        triangles=[(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
        color="#CCC",
    )


def _rectangle_sketch() -> SketchDocument:
    sketch = SketchDocument()
    ids = [
        sketch.add_point((0.0, 0.0)).id,
        sketch.add_point((30.0, 0.0)).id,
        sketch.add_point((30.0, 20.0)).id,
        sketch.add_point((0.0, 20.0)).id,
    ]
    for first, second in zip(ids, ids[1:] + ids[:1]):
        sketch.add_line(first, second)
    sketch.compile(SketchCompileOptions(solve_faces=True))
    return sketch


def test_v175_geometry_contract_detects_index_closed_but_weld_invalid_mesh() -> None:
    mesh = _closed_but_geometrically_collapsed()
    report = analyze_work_mesh_boolean_topology(mesh)

    assert report.indexed_closed is True
    assert report.geometrically_manifold is False
    assert report.welded_vertices < report.vertices
    assert report.collapsed_triangles_after_weld > 0
    assert report.welded_boundary_edges > 0

    with pytest.raises(ValueError, match="not a valid geometric manifold"):
        require_geometric_boolean_manifold(mesh, label="regression input")


def test_v175_joint_builder_rejects_index_closed_output_that_will_fail_next_boolean() -> None:
    good = _box("male")
    bad = _closed_but_geometrically_collapsed()

    with pytest.raises(ValueError, match="later Union/Subtract") as exc:
        _validate_joint_boolean_outputs(good, bad)

    text = str(exc.value)
    assert "collapsed_triangles=" in text
    assert "original parts were left unchanged" in text
    assert "boolean_ready" not in bad.metadata


def test_v175_joint_builder_marks_geometry_valid_outputs_with_v2_contract() -> None:
    male = _box("male")
    female = _box("female")

    result = _validate_joint_boolean_outputs(male, female)

    assert result["male"]["geometrically_manifold"] is True
    assert result["female"]["geometrically_manifold"] is True
    assert male.metadata["joint_builder_topology_contract"] == "closed_solid_v1"
    assert female.metadata["joint_builder_topology_contract"] == "closed_solid_v1"
    assert male.metadata["joint_builder_geometry_contract"] == "geometric_manifold_v2"
    assert female.metadata["joint_builder_geometry_contract"] == "geometric_manifold_v2"
    assert male.metadata["boolean_geometric_manifold"] is True


def test_v175_joint_builder_avoids_coplanar_tab_seam_on_an_exterior_wall() -> None:
    """A tab spanning a board thickness must not end coplanar with its sides."""

    wall = make_cube_mesh(
        name="outside wall",
        pos=(0.0, 0.0, 10.0),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(3.0, 20.0, 20.0),
        color="#CCC",
    )
    base = make_cube_mesh(
        name="base",
        pos=(0.0, 0.0, -1.5),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(40.0, 40.0, 3.0),
        color="#CCC",
    )

    events: list[tuple[str, dict]] = []
    male, female = apply_tab_slot_simple(
        wall,
        base,
        touch_tolerance=0.05,
        clearance=0.15,
        joint_size=10.0,
        joint_count=1,
        joint_edge_margin=2.0,
        debug=lambda tag, data: events.append((tag, data)),
    )

    assert analyze_work_mesh_boolean_topology(male).geometrically_manifold is True
    assert analyze_work_mesh_boolean_topology(female).geometrically_manifold is True
    dimensions = next(data for tag, data in events if tag == "pin_dimensions")
    assert dimensions["male_tab_anchor_depth"] == pytest.approx(0.25)
    assert dimensions["male_tab_projection_depth"] == pytest.approx(3.0)
    assert dimensions["male_size_xyz"][1] == pytest.approx(3.25)


def test_v175_joint_builder_rejects_overlapping_multi_pin_layout_before_boolean() -> None:
    wall = make_cube_mesh(
        name="outside wall",
        pos=(0.0, 0.0, 10.0),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(3.0, 20.0, 20.0),
        color="#CCC",
    )
    base = make_cube_mesh(
        name="base",
        pos=(0.0, 0.0, -1.5),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(40.0, 40.0, 3.0),
        color="#CCC",
    )

    with pytest.raises(ValueError, match="prevent pin overlap"):
        apply_tab_slot_simple(
            wall,
            base,
            touch_tolerance=0.05,
            clearance=0.15,
            joint_size=10.0,
            joint_count=2,
            joint_edge_margin=2.0,
        )


def test_v175_joint_builder_subtract_all_cuts_intersecting_scene_meshes_only() -> None:
    wall = make_cube_mesh(
        name="male wall",
        pos=(0.0, 0.0, 10.0),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(3.0, 20.0, 20.0),
        color="#CCC",
    )
    base = make_cube_mesh(
        name="female base",
        pos=(0.0, 0.0, -1.5),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(40.0, 40.0, 3.0),
        color="#CCC",
    )
    blocker = make_cube_mesh(
        name="intersecting blocker",
        pos=(0.0, 0.0, -1.5),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(40.0, 40.0, 3.0),
        color="#CCC",
    )
    distant = make_cube_mesh(
        name="distant",
        pos=(100.0, 0.0, 0.0),
        rot_deg=(0.0, 0.0, 0.0),
        scale_mm=(10.0, 10.0, 10.0),
        color="#CCC",
    )

    out, changed = apply_tab_slot_to_scene(
        [wall, base, blocker, distant],
        index_a=0,
        index_b=1,
        touch_tolerance=0.05,
        clearance=0.15,
        joint_size=10.0,
        joint_count=1,
        joint_edge_margin=2.0,
        subtract_all=True,
    )

    assert changed == (0, 1, 2)
    assert out[0].name == "male wall"  # A receives its tab; it is never globally cut.
    assert out[2].name == "intersecting blocker"
    assert out[2].metadata["joint_builder_global_subtract"] is True
    assert out[2].triangles != blocker.triangles
    assert out[3] is distant
    assert analyze_work_mesh_boolean_topology(out[2]).geometrically_manifold is True


def test_v175_plan_tracer_document_boundary_rechecks_geometric_manifold_contract() -> None:
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = make_locked_plane("top")
    tool._state.sketch = _rectangle_sketch()
    tool._state.extrusion_depth = 3.0

    mesh = tool._build_apply_mesh()
    report = require_geometric_boolean_manifold(mesh, label="Plan Tracer")

    assert report.geometrically_manifold is True
    assert mesh.metadata["boolean_geometry_contract"] == "geometric_manifold_v2"
    assert mesh.metadata["boolean_geometric_manifold"] is True
    assert mesh.metadata["boolean_geometry_welded_vertices"] == len(mesh.vertices)


def test_v175_joint_builder_never_swallows_shared_boolean_validation_failure(monkeypatch) -> None:
    import laserprog_studio.boolean_ops as shared
    from laserprog_studio.fabrication import cube_boolean

    def reject(*_args, **_kwargs):
        raise ValueError("shared-topology-rejection")

    monkeypatch.setattr(shared, "boolean_mesh_3d", reject)

    with pytest.raises(ValueError, match="shared-topology-rejection"):
        cube_boolean._bool_mesh_3d_manifold(_box("a"), _box("b"), op="union")

from __future__ import annotations

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.geometry_ops.boolean_topology_contract import require_geometric_boolean_manifold
from laserprog_studio.planar_tools import make_locked_plane
from laserprog_studio.tool_api.sketch import SketchCompileOptions
from laserprog_studio.tool_core.sketch.document import SketchDocument
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


_COMPILE = SketchCompileOptions(
    merge_tolerance=1.0e-5,
    split_tolerance=1.0e-5,
    solve_faces=True,
    split_curve_intersections=False,
    split_curves_at_vertices=False,
)


def _rectangle(sketch: SketchDocument, x0: float, y0: float, x1: float, y1: float):
    points = [
        sketch.add_point((x0, y0)).id,
        sketch.add_point((x1, y0)).id,
        sketch.add_point((x1, y1)).id,
        sketch.add_point((x0, y1)).id,
    ]
    lines = []
    for first, second in zip(points, points[1:] + points[:1]):
        lines.append(sketch.add_line(first, second).id)
    return points, lines


def _apply_mesh(sketch: SketchDocument):
    tool = PlanTrace2DCreatorTool()
    tool._state.plane = make_locked_plane("top")
    tool._state.sketch = sketch
    tool._state.extrusion_depth = 3.0
    return tool._build_apply_mesh()


def _assert_boolean_ready(mesh) -> None:
    assert is_closed_triangle_mesh(mesh.vertices, mesh.triangles) == (True, 0, 0)
    report = require_geometric_boolean_manifold(mesh, label="Plan Tracer performance safety regression")
    assert report.indexed_boundary_edges == 0
    assert report.indexed_nonmanifold_edges == 0
    assert report.welded_boundary_edges == 0
    assert report.welded_nonmanifold_edges == 0
    assert report.welded_nonmanifold_vertices == 0
    assert report.collapsed_triangles_after_weld == 0
    assert report.duplicate_triangles_after_weld == 0


def test_face_fast_delete_then_immediate_apply_keeps_boolean_ready_solid() -> None:
    sketch = SketchDocument()
    _rectangle(sketch, 0.0, 0.0, 20.0, 20.0)
    _rectangle(sketch, 40.0, 0.0, 60.0, 20.0)
    sketch.compile(_COMPILE)
    assert len(sketch.faces) == 2

    faces = sorted(sketch.faces.values(), key=lambda face: min(point[0] for point in face.polygon_points))
    sketch.delete_face_only(faces[0].id, compile_after=False)

    # This is the v178 fast path invariant: the generated face is gone without a
    # topology rebuild, its boundary authoring geometry is untouched, and Apply
    # consumes only the remaining visible face.
    assert len(sketch.faces) == 1
    assert sketch.suppressed_face_signatures
    assert len(sketch.lines) == 8

    _assert_boolean_ready(_apply_mesh(sketch))


def test_structural_edge_delete_preserves_remote_geometry_and_boolean_ready_apply() -> None:
    sketch = SketchDocument()
    _left_points, left_lines = _rectangle(sketch, 0.0, 0.0, 20.0, 20.0)
    right_points, _right_lines = _rectangle(sketch, 40.0, 0.0, 60.0, 20.0)
    sketch.compile(_COMPILE)
    assert len(sketch.faces) == 2

    remote_before = {point_id: sketch.points[point_id].position for point_id in right_points}
    sketch.delete_line_cascade(left_lines[0], compile_after=False)
    sketch.compile(_COMPILE)
    remote_after = {point_id: sketch.points[point_id].position for point_id in right_points}

    assert remote_after == remote_before
    assert len(sketch.faces) == 1
    _assert_boolean_ready(_apply_mesh(sketch))


def test_optimized_clone_does_not_alias_face_or_dimension_style_state() -> None:
    sketch = SketchDocument()
    points, lines = _rectangle(sketch, 0.0, 0.0, 20.0, 20.0)
    sketch.compile(_COMPILE)
    dimension = sketch.add_edge_length_dimension(lines[0])
    dimension.style.text_size_px = 17
    face = next(iter(sketch.faces.values()))
    face.metadata["nested"] = {"values": [1, 2]}

    clone = sketch.clone()
    clone.faces[face.id].metadata["nested"]["values"].append(3)
    clone.dimensions[dimension.id].style.text_size_px = 99
    clone.move_point(points[0], (5.0, 6.0))

    assert sketch.faces[face.id].metadata["nested"]["values"] == [1, 2]
    assert sketch.dimensions[dimension.id].style.text_size_px == 17
    assert sketch.points[points[0]].position == (0.0, 0.0)

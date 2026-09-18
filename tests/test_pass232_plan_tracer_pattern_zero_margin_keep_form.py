from __future__ import annotations

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _plane() -> LockedPlaneSpec:
    return LockedPlaneSpec(
        view=FixedPlanarView.TOP,
        normal=(0.0, 0.0, 1.0),
        u_axis=(1.0, 0.0, 0.0),
        v_axis=(0.0, 1.0, 0.0),
        depth=0.0,
    )


def _rectangle_sketch(width: float = 100.0, height: float = 60.0) -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((width, 0.0)).id
    p3 = sketch.add_point((width, height)).id
    p4 = sketch.add_point((0.0, height)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )
    return sketch


def _touches_rectangle_boundary(hole: tuple[tuple[float, float], ...], *, width: float, height: float) -> bool:
    xs = [point[0] for point in hole]
    ys = [point[1] for point in hole]
    return (
        min(xs) == 0.0
        or max(xs) == width
        or min(ys) == 0.0
        or max(ys) == height
    )


def test_zero_edge_margin_keeps_face_owned_holes_strictly_inside_contour() -> None:
    tool = PlanTrace2DCreatorTool()
    sketch = _rectangle_sketch()
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))

    holes = tool._services.patterns._valid_hole_polygons_for_face(
        face,
        kind="square",
        cell_size=30.0,
        wall=4.0,
        margin=0.0,
        max_segments=5000,
        ignore_existing_pattern_holes=True,
    )

    assert holes
    assert not any(_touches_rectangle_boundary(hole, width=100.0, height=60.0) for hole in holes)


def test_keep_form_false_is_legacy_compatible_but_never_materializes_pattern_linework() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _rectangle_sketch()
    original_face_ids = tuple(tool._state.sketch.faces)
    original_line_ids = set(tool._state.sketch.lines)
    original_point_ids = set(tool._state.sketch.points)

    ok = tool._services.patterns.apply_as_union_face_holes(
        ctx,
        original_face_ids,
        kind="square",
        cell_size=30.0,
        wall=4.0,
        margin=0.0,
        keep_form=False,
        max_segments=5000,
        persistent=True,
        render=False,
    )

    assert ok is True
    assert tuple(tool._state.sketch.faces) == original_face_ids
    assert set(tool._state.sketch.lines) == original_line_ids
    assert set(tool._state.sketch.points) == original_point_ids
    assert not any(
        line.metadata.get("plan_trace_2d.pattern.material_boundary")
        for line in tool._state.sketch.lines.values()
    )
    face = tool._state.sketch.faces[original_face_ids[0]]
    assert face.metadata.get("plan_trace_2d.pattern.direct_holes") is True
    assert face.hole_polygons
    assert len(tool._state.motif_assignments_by_outer_signature) == 1
    assignment = next(iter(tool._state.motif_assignments_by_outer_signature.values()))
    assert assignment["kind"] == "square"
    assert assignment["keep_form"] is True

    # A normal Plan Tracer compile must restore the derived holes without ever
    # expanding the motif into authored point/line entities.
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
    assert set(tool._state.sketch.lines) == original_line_ids
    assert set(tool._state.sketch.points) == original_point_ids
    face = next(iter(tool._state.sketch.faces.values()))
    assert face.hole_polygons
    mesh = tool._build_apply_mesh()
    assert len(mesh.vertices) > 0
    assert len(mesh.triangles) > 0


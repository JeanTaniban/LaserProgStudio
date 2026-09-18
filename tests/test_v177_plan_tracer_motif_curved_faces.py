from __future__ import annotations

from laserprog_studio.geometry_ops.boolean_topology_contract import require_geometric_boolean_manifold
from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument, face_signature_from_points
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


def _compile(sketch: SketchDocument) -> None:
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )


def _circle_sketch(radius: float = 50.0) -> tuple[SketchDocument, str]:
    sketch = SketchDocument()
    center = sketch.add_point((0.0, 0.0)).id
    radius_point = sketch.add_point((radius, 0.0)).id
    circle_id = sketch.add_circle(center, radius_point).id
    _compile(sketch)
    return sketch, circle_id


def _shared_arc_sketch() -> tuple[SketchDocument, str]:
    """Rectangle split into two selectable faces by one shared circular arc."""

    sketch = SketchDocument()
    p00 = sketch.add_point((0.0, 0.0)).id
    p100 = sketch.add_point((100.0, 0.0)).id
    p100_50 = sketch.add_point((100.0, 50.0)).id
    p100_100 = sketch.add_point((100.0, 100.0)).id
    p0_100 = sketch.add_point((0.0, 100.0)).id
    p0_50 = sketch.add_point((0.0, 50.0)).id
    control = sketch.add_point((50.0, 78.0)).id

    for start, end in (
        (p00, p100),
        (p100, p100_50),
        (p100_50, p100_100),
        (p100_100, p0_100),
        (p0_100, p0_50),
        (p0_50, p00),
    ):
        sketch.add_line(start, end)
    arc_id = sketch.add_arc(p0_50, p100_50, control).id
    _compile(sketch)
    return sketch, arc_id


def _annulus_sketch(outer_radius: float = 60.0, inner_radius: float = 20.0) -> tuple[SketchDocument, str, str]:
    sketch = SketchDocument()
    center = sketch.add_point((0.0, 0.0)).id
    outer_radius_point = sketch.add_point((outer_radius, 0.0)).id
    inner_radius_point = sketch.add_point((inner_radius, 0.0)).id
    outer_circle = sketch.add_circle(center, outer_radius_point).id
    inner_circle = sketch.add_circle(center, inner_radius_point).id
    _compile(sketch)
    return sketch, outer_circle, inner_circle


def test_v177_pattern_on_circle_face_stays_parametric_and_preserves_circle_entity() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    sketch, circle_id = _circle_sketch()
    tool._state.plane = _plane()
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))

    counts_before = (len(sketch.points), len(sketch.lines), len(sketch.arcs), len(sketch.circles))
    assert circle_id in face.boundary_entity_ids

    ok = tool._services.patterns.apply_as_face_holes(
        ctx,
        face.id,
        kind="honeycomb",
        cell_size=15.0,
        wall=2.0,
        margin=0.0,
        persistent=True,
        render=False,
        max_segments=10000,
    )

    assert ok is True
    assert face.hole_polygons
    assert (len(sketch.points), len(sketch.lines), len(sketch.arcs), len(sketch.circles)) == counts_before
    assert circle_id in sketch.circles
    assert len(tool._state.motif_assignments_by_outer_signature) == 1

    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
    rebuilt = next(iter(sketch.faces.values()))
    assert circle_id in rebuilt.boundary_entity_ids
    assert rebuilt.hole_polygons
    assert (len(sketch.points), len(sketch.lines), len(sketch.arcs), len(sketch.circles)) == counts_before

    mesh = tool._build_apply_mesh()
    require_geometric_boolean_manifold(mesh, label="circle motif")


def test_v177_pattern_on_face_sharing_arc_never_mutates_shared_arc_or_neighbor_face() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    sketch, arc_id = _shared_arc_sketch()
    tool._state.plane = _plane()
    tool._state.sketch = sketch

    faces = tuple(sketch.faces.values())
    assert len(faces) == 2
    assert all(arc_id in face.boundary_entity_ids for face in faces)
    target, neighbor = faces
    counts_before = (len(sketch.points), len(sketch.lines), len(sketch.arcs), len(sketch.circles))
    arc_before = (
        sketch.arcs[arc_id].start_point_id,
        sketch.arcs[arc_id].end_point_id,
        sketch.arcs[arc_id].control_point_id,
    )

    ok = tool._services.patterns.apply_as_face_holes(
        ctx,
        target.id,
        kind="circle",
        cell_size=15.0,
        wall=2.0,
        margin=0.0,
        persistent=True,
        render=False,
        max_segments=10000,
    )

    assert ok is True
    assert target.hole_polygons
    assert neighbor.hole_polygons == ()
    assert arc_id in target.boundary_entity_ids
    assert arc_id in neighbor.boundary_entity_ids
    assert (
        sketch.arcs[arc_id].start_point_id,
        sketch.arcs[arc_id].end_point_id,
        sketch.arcs[arc_id].control_point_id,
    ) == arc_before
    assert (len(sketch.points), len(sketch.lines), len(sketch.arcs), len(sketch.circles)) == counts_before

    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
    rebuilt = tuple(sketch.faces.values())
    assert len(rebuilt) == 2
    assert all(arc_id in face.boundary_entity_ids for face in rebuilt)
    patterned = [face for face in rebuilt if face.metadata.get("plan_trace_2d.pattern.direct_holes")]
    untouched = [face for face in rebuilt if not face.metadata.get("plan_trace_2d.pattern.direct_holes")]
    assert len(patterned) == 1
    assert len(untouched) == 1
    assert patterned[0].hole_polygons
    assert untouched[0].hole_polygons == ()


def test_v177_pattern_preserves_native_circle_hole_in_annulus_before_and_after_compile() -> None:
    """A motif must add perforations; it must never fill an authored hole."""

    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    sketch, outer_circle_id, inner_circle_id = _annulus_sketch()
    tool._state.plane = _plane()
    tool._state.sketch = sketch

    annulus = next(face for face in sketch.faces.values() if len(face.hole_polygons) == 1)
    assert outer_circle_id in annulus.boundary_entity_ids
    assert annulus.hole_boundary_entity_ids == ((inner_circle_id,),)
    native_hole = annulus.hole_polygons[0]
    native_signature = face_signature_from_points(native_hole)

    ok = tool._services.patterns.apply_as_face_holes(
        ctx,
        annulus.id,
        kind="honeycomb",
        cell_size=15.0,
        wall=2.0,
        margin=2.0,
        persistent=True,
        render=False,
        max_segments=50000,
    )

    assert ok is True
    assert len(annulus.hole_polygons) > 1
    assert any(face_signature_from_points(hole) == native_signature for hole in annulus.hole_polygons)
    native_index = next(
        index for index, hole in enumerate(annulus.hole_polygons)
        if face_signature_from_points(hole) == native_signature
    )
    assert annulus.hole_boundary_entity_ids[native_index] == (inner_circle_id,)
    assert annulus.metadata["plan_trace_2d.pattern.native_hole_count"] == 1

    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
    rebuilt_annulus = next(face for face in sketch.faces.values() if face.metadata.get("plan_trace_2d.pattern.direct_holes"))
    assert any(face_signature_from_points(hole) == native_signature for hole in rebuilt_annulus.hole_polygons)
    native_index = next(
        index for index, hole in enumerate(rebuilt_annulus.hole_polygons)
        if face_signature_from_points(hole) == native_signature
    )
    assert rebuilt_annulus.hole_boundary_entity_ids[native_index] == (inner_circle_id,)
    assert rebuilt_annulus.metadata["plan_trace_2d.pattern.native_hole_count"] == 1

    mesh = tool._build_apply_mesh()
    require_geometric_boolean_manifold(mesh, label="annulus motif")


def test_v177_editable_source_serializes_compact_motif_not_generated_linework() -> None:
    from laserprog_studio.tooling.plan_trace_2d.editable_source import (
        build_editable_source,
        deserialize_sketch,
        motif_assignments_from_source,
    )

    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    sketch, circle_id = _circle_sketch()
    tool._state.plane = _plane()
    tool._state.sketch = sketch
    face = next(iter(sketch.faces.values()))

    assert tool._services.patterns.apply_as_face_holes(
        ctx,
        face.id,
        kind="square",
        cell_size=14.0,
        wall=2.0,
        margin=1.0,
        persistent=True,
        render=False,
        max_segments=10000,
    )

    source = build_editable_source(
        sketch=sketch,
        plane=tool._state.plane,
        display_plane=tool._state.display_plane,
        anchor_world=tool._state.anchor_world,
        extrusion_depth_mm=3.0,
        motif_assignments=tool._state.motif_assignments_by_outer_signature,
    )

    sketch_payload = source["sketch"]
    assert len(sketch_payload["points"]) == 2
    assert sketch_payload["lines"] == []
    assert sketch_payload["arcs"] == []
    assert len(sketch_payload["circles"]) == 1
    assert sketch_payload["circles"][0]["id"] == circle_id
    assignments = motif_assignments_from_source(source)
    assert len(assignments) == 1
    assignment = next(iter(assignments.values()))
    assert assignment["kind"] == "square"
    assert assignment["cell_size"] == 14.0

    reopened = deserialize_sketch(sketch_payload)
    assert len(reopened.points) == 2
    assert len(reopened.lines) == 0
    assert len(reopened.arcs) == 0
    assert len(reopened.circles) == 1

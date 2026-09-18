from __future__ import annotations

from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.projected_drawing import ProjectedFace
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _rectangle(sketch: SketchDocument, prefix: str, x0: float, y0: float, x1: float, y1: float) -> None:
    ids = [f"{prefix}a", f"{prefix}b", f"{prefix}c", f"{prefix}d"]
    for point_id, xy in zip(ids, ((x0, y0), (x1, y0), (x1, y1), (x0, y1))):
        sketch.add_point(xy, point_id=point_id)
    for line_id, start, end in (
        (f"{prefix}ab", ids[0], ids[1]),
        (f"{prefix}bc", ids[1], ids[2]),
        (f"{prefix}cd", ids[2], ids[3]),
        (f"{prefix}da", ids[3], ids[0]),
    ):
        sketch.add_line(start, end, line_id=line_id)


def test_face_solver_classifies_inner_loop_as_hole() -> None:
    sketch = SketchDocument()
    _rectangle(sketch, "outer", 0.0, 0.0, 100.0, 80.0)
    _rectangle(sketch, "inner", 25.0, 20.0, 75.0, 60.0)

    result = sketch.compile(SketchCompileOptions(solve_faces=True))

    assert result.rebuilt_faces == 2
    assert len(sketch.faces) == 2
    ring = next(face for face in sketch.faces.values() if face.hole_polygons)
    inner = next(face for face in sketch.faces.values() if not face.hole_polygons)
    assert ring.metadata["contains_holes"] is True
    assert ring.metadata["hole_count"] == 1
    assert len(ring.hole_polygons) == 1
    assert len(ring.hole_boundary_entity_ids) == 1
    assert set(ring.boundary_entity_ids) == {"outerab", "outerbc", "outercd", "outerda"}
    assert set(ring.hole_boundary_entity_ids[0]) == {"innerab", "innerbc", "innercd", "innerda"}
    assert set(inner.boundary_entity_ids) == {"innerab", "innerbc", "innercd", "innerda"}
    assert inner.metadata.get("generated_from_hole") is True


def test_nested_loops_create_hole_and_inner_island_face() -> None:
    sketch = SketchDocument()
    _rectangle(sketch, "outer", 0.0, 0.0, 100.0, 100.0)
    _rectangle(sketch, "hole", 20.0, 20.0, 80.0, 80.0)
    _rectangle(sketch, "island", 40.0, 40.0, 60.0, 60.0)

    sketch.compile(SketchCompileOptions(solve_faces=True))

    assert len(sketch.faces) == 3
    faces_with_holes = [face for face in sketch.faces.values() if face.hole_polygons]
    island_faces = [face for face in sketch.faces.values() if not face.hole_polygons]
    assert len(faces_with_holes) == 2
    assert len(island_faces) == 1
    assert any(set(face.hole_boundary_entity_ids[0]) == {"holeab", "holebc", "holecd", "holeda"} for face in faces_with_holes)
    assert any(set(face.hole_boundary_entity_ids[0]) == {"islandab", "islandbc", "islandcd", "islandda"} for face in faces_with_holes)
    assert set(island_faces[0].boundary_entity_ids) == {"islandab", "islandbc", "islandcd", "islandda"}


def test_plan_face_actor_hit_testing_respects_holes() -> None:
    ctx = ToolContext()
    actor = plan2d.register_plan_face(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        face_id=f"{TOOL_PLAN_TRACE}:face:test",
        polygon_world_points=((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0), (0.0, 100.0, 0.0)),
        hole_world_polygons=(((25.0, 25.0, 0.0), (75.0, 25.0, 0.0), (75.0, 75.0, 0.0), (25.0, 75.0, 0.0)),),
        selectable=True,
        sketch_face_id="f1",
    )

    world_to_screen = lambda point: (point[0], point[1])
    assert actor.metadata["has_holes"] is True
    assert ctx.selection.hit_test((10.0, 10.0), world_to_screen, owner_tool=TOOL_PLAN_TRACE, selectable_only=True) is not None
    assert ctx.selection.hit_test((50.0, 50.0), world_to_screen, owner_tool=TOOL_PLAN_TRACE, selectable_only=True) is None


def test_plan_tracer_sync_registers_face_holes_as_api_metadata() -> None:
    ctx = ToolContext()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool._state.display_plane = tool._state.plane
    _rectangle(tool._state.sketch, "outer", 0.0, 0.0, 100.0, 100.0)
    _rectangle(tool._state.sketch, "inner", 30.0, 30.0, 70.0, 70.0)

    tool._compile_and_sync_sketch(ctx, render=False)

    faces = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "face"]
    assert len(faces) == 2
    ring = next(actor for actor in faces if actor.metadata["hole_count"] == 1)
    inner = next(actor for actor in faces if actor.metadata["hole_count"] == 0)
    assert len(ring.metadata["filled_polygon_holes"]) == 1
    assert inner.metadata.get("has_holes") is False
    projected_faces = [item for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives if isinstance(item, ProjectedFace)]
    assert len(projected_faces) == 2
    assert any(len(item.holes) == 1 for item in projected_faces)
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()

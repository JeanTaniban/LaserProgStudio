from __future__ import annotations

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.constants import _RESTORE_FACES_BUTTON_ID
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


def _two_nested_rectangles() -> SketchDocument:
    sketch = SketchDocument()
    _rectangle(sketch, "outer", 0.0, 0.0, 100.0, 100.0)
    _rectangle(sketch, "inner", 30.0, 30.0, 60.0, 60.0)
    sketch.compile(SketchCompileOptions(split_curve_intersections=False, split_curves_at_vertices=False, solve_faces=True))
    return sketch


def test_nested_rectangles_compile_into_adjacent_selectable_regions_without_stacking() -> None:
    sketch = _two_nested_rectangles()

    assert len(sketch.faces) == 2
    ring = next(face for face in sketch.faces.values() if face.hole_polygons)
    island = next(face for face in sketch.faces.values() if not face.hole_polygons)

    assert set(ring.boundary_entity_ids) == {"outerab", "outerbc", "outercd", "outerda"}
    assert set(ring.hole_boundary_entity_ids[0]) == {"innerab", "innerbc", "innercd", "innerda"}
    assert set(island.boundary_entity_ids) == {"innerab", "innerbc", "innercd", "innerda"}
    assert island.metadata.get("generated_from_hole") is True


def test_deleted_inner_region_can_be_rebuilt_from_existing_boundaries() -> None:
    sketch = _two_nested_rectangles()
    island = next(face for face in sketch.faces.values() if not face.hole_polygons)

    sketch.delete_face_only(island.id, compile_after=True)

    assert len(sketch.faces) == 1
    assert sketch.suppressed_face_signatures

    sketch.restore_generated_faces(compile_after=True)

    assert len(sketch.faces) == 2
    assert not sketch.suppressed_face_signatures


def test_rebuild_faces_toolbar_action_restores_deleted_fill_and_actor() -> None:
    ctx = ToolContext()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool._state.plane = tool._state.display_plane
    tool._state.sketch = _two_nested_rectangles()
    inner = next(face for face in tool._state.sketch.faces.values() if not face.hole_polygons)
    tool._state.sketch.delete_face_only(inner.id, compile_after=True)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)

    assert len(tool._state.sketch.faces) == 1
    tool.on_overlay_button_clicked(_RESTORE_FACES_BUTTON_ID, ctx)

    face_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "face"]
    assert len(tool._state.sketch.faces) == 2
    assert len(face_actors) == 2

from __future__ import annotations

from types import MethodType

import pytest

from laserprog_studio.application.projected_drawing_2d import ProjectedDrawingOverlay2D
from laserprog_studio.application.projected_face_triangulation import triangulate_polygon_with_holes_cells
from laserprog_studio.boolean_ops import is_closed_triangle_mesh
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


def _two_adjacent_rectangles() -> SketchDocument:
    sketch = SketchDocument()
    points = {
        name: sketch.add_point(position).id
        for name, position in (
            ("a", (0.0, 0.0)),
            ("b", (100.0, 0.0)),
            ("c", (200.0, 0.0)),
            ("d", (200.0, 100.0)),
            ("e", (100.0, 100.0)),
            ("f", (0.0, 100.0)),
        )
    }
    for start, end in (
        ("a", "b"),
        ("b", "c"),
        ("c", "d"),
        ("d", "e"),
        ("e", "f"),
        ("f", "a"),
        ("b", "e"),
    ):
        sketch.add_line(points[start], points[end])
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )
    assert len(sketch.faces) == 2
    return sketch


def _select_faces(ctx: ToolContext, face_ids: tuple[str, ...]) -> None:
    actors = {
        f"face_actor_{index}": type(
            "_FaceActor",
            (),
            {
                "metadata": {
                    "plan_trace_role": "face",
                    "plan_trace_sketch_face_id": face_id,
                },
                "owner_tool": "plan_trace_2d",
            },
        )()
        for index, face_id in enumerate(face_ids)
    }
    original_actor_lookup = ctx.selection.actor
    ctx.selection.ids = lambda: tuple(actors)
    ctx.selection.actor = lambda actor_id, _actors=actors, _orig=original_actor_lookup: (
        _actors.get(str(actor_id)) or _orig(str(actor_id))
    )


def test_motif_uses_union_of_shift_selected_faces() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _two_adjacent_rectangles()
    face_ids = tuple(tool._state.sketch.faces)
    _select_faces(ctx, face_ids)
    tool._services.overlay._last_ctx = ctx
    tool._state.motif_kind = "square"
    tool._state.motif_cell_size = 60.0
    tool._state.motif_wall = 10.0
    tool._state.motif_margin = 0.0

    tool._services.motif_overlay.open(ctx)

    assert tool._state.motif_preview_face_ids == face_ids
    assert tool._state.pattern_face_ids == face_ids
    assert "Union de 2 faces" in tool._services.patterns.selected_face_text()
    assert tool._state.pattern_generated_count > 0
    assert all(tool._state.sketch.faces[face_id].hole_polygons for face_id in face_ids)

    left = min(tool._state.sketch.faces.values(), key=lambda face: min(x for x, _ in face.polygon_points))
    right = max(tool._state.sketch.faces.values(), key=lambda face: max(x for x, _ in face.polygon_points))
    assert any(max(x for x, _ in hole) == pytest.approx(100.0) for hole in left.hole_polygons)
    assert any(min(x for x, _ in hole) == pytest.approx(100.0) for hole in right.hole_polygons)

    # Boundary-crossing union openings are represented as GEOS-repaired notches
    # and must still produce visible indexed fill triangles on both source faces.
    for face in (left, right):
        outer = tuple((x, y, 0.0) for x, y in face.polygon_points)
        holes = tuple(tuple((x, y, 0.0) for x, y in hole) for hole in face.hole_polygons)
        assert triangulate_polygon_with_holes_cells(outer, holes)


def test_projected_static_sync_skips_snapshot_and_primitive_rescan() -> None:
    class _Manager:
        def state_token(self, _owner_tool: str) -> tuple[int, bool]:
            return (7, True)

        def snapshot(self, _owner_tool: str):
            raise AssertionError("static sync must not build a primitive snapshot")

    renderer = ProjectedDrawingOverlay2D.__new__(ProjectedDrawingOverlay2D)
    renderer.owner = object()
    renderer.manager = _Manager()
    renderer.owner_tool = "plan_trace_2d"
    renderer._revision = 7
    renderer._visible = True
    renderer._last_projection_signature = ("camera", 1)
    renderer._last_camera_state = None
    renderer._last_sync_camera_mode = "static"
    renderer._diagnostic_metrics = {
        "sync_count": 0,
        "compile_count": 0,
        "projection_count": 0,
        "cache_hit_count": 0,
    }
    renderer._ensure_renderer = MethodType(lambda self: object(), renderer)
    renderer._projection_signature = MethodType(lambda self: ("camera", 1), renderer)
    renderer._request_render = MethodType(lambda self, _reason: None, renderer)
    renderer._record_sync_audit = MethodType(
        lambda self, *, compile_ms, rebuild_ms, projection_ms, path="full": None,
        renderer,
    )

    changed = renderer.sync_from_manager(force=False, render=False)

    assert changed is False
    assert renderer._diagnostic_metrics["fast_noop_count"] == 1
    assert renderer._diagnostic_metrics["cache_hit_count"] == 1
    assert renderer._diagnostic_metrics["last_projected_points"] == 0


def test_union_motif_builds_closed_apply_mesh() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _two_adjacent_rectangles()
    face_ids = tuple(tool._state.sketch.faces)

    ok = tool._services.patterns.apply_as_union_face_holes(
        ctx,
        face_ids,
        kind="square",
        cell_size=60.0,
        wall=10.0,
        margin=0.0,
        max_segments=5000,
        persistent=True,
        render=False,
    )

    assert ok is True
    mesh = tool._build_apply_mesh()
    closed, boundary, nonmanifold = is_closed_triangle_mesh(mesh.vertices, mesh.triangles)
    assert closed, (boundary, nonmanifold, len(mesh.vertices), len(mesh.triangles))


def test_union_footprint_cache_reuses_same_selected_geometry() -> None:
    tool = PlanTrace2DCreatorTool()
    tool._state.sketch = _two_adjacent_rectangles()
    faces = tuple(tool._state.sketch.faces.values())
    service = tool._services.patterns

    first = service._union_face_footprint(faces, ignore_existing_pattern_holes=True)
    second = service._union_face_footprint(tuple(reversed(faces)), ignore_existing_pattern_holes=True)

    assert first is not None
    assert second is first
    assert len(service._union_footprint_cache) == 1


def test_union_motif_reuses_preview_result_for_final_apply() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _two_adjacent_rectangles()
    face_ids = tuple(tool._state.sketch.faces)
    service = tool._services.patterns

    kwargs = dict(
        kind="square",
        cell_size=60.0,
        wall=10.0,
        margin=0.0,
        max_segments=5000,
        persistent=True,
        render=False,
    )
    assert service.apply_as_union_face_holes(ctx, face_ids, **kwargs) is True

    def _must_not_regenerate(*_args, **_kwargs):
        raise AssertionError("final Apply must reuse the validated union preview")

    service._valid_hole_polygons_for_faces = _must_not_regenerate
    service._split_union_holes_by_face = _must_not_regenerate

    assert service.apply_as_union_face_holes(ctx, face_ids, **kwargs) is True
    assert len(service._union_pattern_cache) == 1
    assert all(tool._state.sketch.faces[face_id].hole_polygons for face_id in face_ids)


def test_motif_overlay_apply_reuses_lower_budget_union_preview() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    tool._state.plane = _plane()
    tool._state.sketch = _two_adjacent_rectangles()
    face_ids = tuple(tool._state.sketch.faces)
    _select_faces(ctx, face_ids)
    tool._services.overlay._last_ctx = ctx
    tool._state.motif_kind = "square"
    tool._state.motif_cell_size = 60.0
    tool._state.motif_wall = 10.0
    tool._state.motif_margin = 0.0

    tool._services.motif_overlay.open(ctx)
    assert len(tool._services.patterns._union_pattern_cache) == 1

    def _must_not_regenerate(*_args, **_kwargs):
        raise AssertionError("Apply must reuse the lower-budget preview when it was complete")

    tool._services.patterns._valid_hole_polygons_for_faces = _must_not_regenerate
    tool._services.patterns._split_union_holes_by_face = _must_not_regenerate
    tool._services.motif_overlay.apply(ctx)

    assert tool._state.motif_overlay_visible is False
    assert all(tool._state.sketch.faces[face_id].hole_polygons for face_id in face_ids)

from __future__ import annotations

from laserprog_studio.boolean_ops import is_closed_triangle_mesh
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core import ToolEvent, ToolEventType
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.planar_tools import VentPathDraft, VentSectionKind, make_locked_plane, make_vent_path_mesh


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 0.0), object_id="face", object_index=0)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _tool_with_plane() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT), ctx)
    assert tool._state.plane is not None
    return tool, ctx


def _rectangle_sketch() -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((40.0, 0.0)).id
    p3 = sketch.add_point((40.0, 20.0)).id
    p4 = sketch.add_point((0.0, 20.0)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    sketch.compile(SketchCompileOptions(split_curve_intersections=True, split_curves_at_vertices=True, solve_faces=True))
    return sketch


def _split_rectangle_sketch() -> SketchDocument:
    sketch = _rectangle_sketch()
    p5 = sketch.add_point((20.0, 0.0)).id
    p6 = sketch.add_point((20.0, 20.0)).id
    sketch.add_line(p5, p6)
    sketch.compile(SketchCompileOptions(split_curve_intersections=True, split_curves_at_vertices=True, solve_faces=True))
    return sketch


def _rectangle_with_hole_sketch() -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((40.0, 0.0)).id
    p3 = sketch.add_point((40.0, 40.0)).id
    p4 = sketch.add_point((0.0, 40.0)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    c = sketch.add_point((20.0, 20.0)).id
    r = sketch.add_point((28.0, 20.0)).id
    sketch.add_circle(c, r)
    sketch.compile(SketchCompileOptions(split_curve_intersections=False, split_curves_at_vertices=False, solve_faces=True))
    inner = next(face for face in sketch.faces.values() if not face.hole_polygons and len(face.boundary_entity_ids) == 1)
    sketch.delete_face_only(inner.id, compile_after=True)
    return sketch


def _assert_closed(mesh) -> None:
    closed, boundary, nonmanifold = is_closed_triangle_mesh(mesh.vertices, mesh.triangles)
    assert closed, (boundary, nonmanifold, len(mesh.vertices), len(mesh.triangles))


def test_plan_tracer_apply_rectangle_is_closed_by_index_for_booleans() -> None:
    tool, _ctx = _tool_with_plane()
    tool._state.sketch = _rectangle_sketch()

    mesh = tool._build_apply_mesh()

    _assert_closed(mesh)


def test_plan_tracer_apply_dissolves_internal_split_line_before_extrusion() -> None:
    tool, _ctx = _tool_with_plane()
    tool._state.sketch = _split_rectangle_sketch()
    assert len(tool._state.sketch.faces) == 2

    mesh = tool._build_apply_mesh()

    _assert_closed(mesh)
    # The vertical construction/split line at x=20 must not become an internal
    # extrusion wall. Such a wall is exactly the visual parasite reported by the
    # user and it also produces overlapping/non-boolean-friendly solids.
    internal_wall_triangles = 0
    for tri in mesh.triangles:
        pts = [mesh.vertices[i] for i in tri]
        if all(abs(float(p[0]) - 20.0) <= 1.0e-6 for p in pts):
            if max(float(p[2]) for p in pts) - min(float(p[2]) for p in pts) > 1.0e-6:
                internal_wall_triangles += 1
    assert internal_wall_triangles == 0


def test_plan_tracer_apply_deleted_inner_face_is_closed_ring() -> None:
    tool, _ctx = _tool_with_plane()
    tool._state.sketch = _rectangle_with_hole_sketch()

    mesh = tool._build_apply_mesh()

    _assert_closed(mesh)
    for ia, ib, ic in mesh.triangles:
        tri = [mesh.vertices[ia], mesh.vertices[ib], mesh.vertices[ic]]
        if max(p[2] for p in tri) - min(p[2] for p in tri) > 1.0e-6:
            continue
        cx = sum(p[0] for p in tri) / 3.0
        cy = sum(p[1] for p in tri) / 3.0
        assert ((cx - 20.0) ** 2 + (cy - 20.0) ** 2) ** 0.5 >= 7.95


def test_vent_generator_rectangular_mesh_is_boolean_ready_closed() -> None:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 18.0
    draft.section.height = 8.0
    draft.section.area = 144.0
    draft.wall_thickness = 3.0
    draft.waypoints = [(0.0, 0.0), (48.0, 0.0), (48.0, 34.0), (8.0, 34.0)]

    mesh = make_vent_path_mesh(draft)

    _assert_closed(mesh)

from __future__ import annotations

from pathlib import Path
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.constants import _METRIC_OVERLAY_ID, _METRIC_VALIDATE_BUTTON_ID
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=1)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.plane is not None


def _rectangle_with_inner_circle() -> SketchDocument:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0)).id
    p2 = sketch.add_point((40.0, 0.0)).id
    p3 = sketch.add_point((40.0, 40.0)).id
    p4 = sketch.add_point((0.0, 40.0)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    center = sketch.add_point((20.0, 20.0)).id
    radius = sketch.add_point((28.0, 20.0)).id
    sketch.add_circle(center, radius)
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )
    return sketch


def test_metric_validate_commits_current_overlay_value_without_prior_field_callback() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT), ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(40.0, 0.0), button=MouseButton.LEFT), ctx)

    # Mirrors the real first-click path: the Qt adapter has flushed the QLineEdit
    # text into the declarative overlay manager, but the tool must not require a
    # separate field callback to make Validate actually change geometry.
    ctx.overlay.update_field(_METRIC_OVERLAY_ID, f"{_METRIC_OVERLAY_ID}.metric.length", "18 mm")
    tool.on_overlay_button_clicked(_METRIC_VALIDATE_BUTTON_ID, ctx)

    assert tool._state.metric_draft is None
    line = next(iter(tool._state.sketch.lines.values()))
    a = tool._state.sketch.points[line.start_point_id].position
    b = tool._state.sketch.points[line.end_point_id].position
    assert round(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5, 6) == 18.0
    window = ctx.overlay.window(_METRIC_OVERLAY_ID)
    assert window is not None and window.visible is False


def test_rectangle_with_inner_circle_exposes_two_selectable_regions() -> None:
    sketch = _rectangle_with_inner_circle()
    faces = tuple(sketch.faces.values())
    assert len(faces) == 2
    ring = next(face for face in faces if face.hole_polygons)
    inner = next(face for face in faces if not face.hole_polygons and len(face.boundary_entity_ids) == 1)
    assert ring.metadata.get("contains_holes") is True
    assert inner.metadata.get("generated_from_hole") is True

    sketch.delete_face_only(inner.id, compile_after=True)
    faces_after_delete = tuple(sketch.faces.values())
    assert len(faces_after_delete) == 1
    assert faces_after_delete[0].hole_polygons


def test_apply_mesh_respects_deleted_inner_face_hole_caps() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._state.sketch = _rectangle_with_inner_circle()
    inner = next(face for face in tool._state.sketch.faces.values() if not face.hole_polygons and len(face.boundary_entity_ids) == 1)
    tool._state.sketch.delete_face_only(inner.id, compile_after=True)

    mesh = tool._build_apply_mesh()
    # No horizontal cap triangle may cover the center of the deleted circular face.
    # Side walls are ignored here because their vertices have different depths.
    for ia, ib, ic in mesh.triangles:
        tri = [mesh.vertices[ia], mesh.vertices[ib], mesh.vertices[ic]]
        if max(p[2] for p in tri) - min(p[2] for p in tri) > 1.0e-6:
            continue
        cx = sum(p[0] for p in tri) / 3.0
        cy = sum(p[1] for p in tri) / 3.0
        assert ((cx - 20.0) ** 2 + (cy - 20.0) ** 2) ** 0.5 >= 7.95


def test_creator_double_click_is_consumed_before_scene_mesh_picking() -> None:
    source = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")
    dblclick = source[source.index("MouseButtonDblClick") :]
    creator_guard = dblclick.index("creator_tool = active_creator_tool_for_pointer(self)")
    mesh_pick = dblclick.index("picked = self._pick_from_qt_pos(qx, qy)")
    assert creator_guard < mesh_pick

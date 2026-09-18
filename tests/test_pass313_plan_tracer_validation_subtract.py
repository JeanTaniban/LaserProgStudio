from __future__ import annotations

import copy


from laserprog_studio.primitives.base import PrimitiveBuildRequest
from laserprog_studio.primitives.generators import build_box
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tooling.plan_trace_2d.editable_source import (
    PLAN_TRACE_SUBTRACT_SOURCE_KIND,
    editable_source_from_mesh,
)
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.tool_api.sketch import SketchCompileOptions, SketchDocument


class _Scene:
    def __init__(self, meshes=None) -> None:
        self.meshes = list(meshes or [])

    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        object_id = getattr(self.meshes[0], "mesh_id", "target") if self.meshes else "target"
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 0.0),
            object_id=object_id,
            object_index=0,
            normal=(0.0, 0.0, 1.0),
        )


class _Owner:
    TOOL_NONE = "none"

    def __init__(self, *, decision: str | None = None) -> None:
        self.decision = decision
        self.rebuild_calls = 0
        self.close_calls = 0
        self.active_tool = "plan_trace"

    def align_camera_to_plan_surface(self, **_kwargs) -> None:
        pass

    def rebuild_scene(self, *_, **__) -> None:
        self.rebuild_calls += 1

    def close_active_tool(self, *_, **__) -> None:
        self.close_calls += 1
        self.active_tool = self.TOOL_NONE

    def ask_plan_trace_edit_or_new(self, *_args):
        return self.decision or "edit"



def _stub_boolean_difference(monkeypatch):
    def fake_boolean_difference(target, cutter):
        result = copy.deepcopy(target)
        metadata = dict(getattr(result, "metadata", {}) or {})
        zs = [float(p[2]) for p in getattr(cutter, "vertices", []) or [(0.0, 0.0, 0.0)]]
        metadata["test_cutter_depth_span"] = max(zs) - min(zs) if zs else 0.0
        result.metadata = metadata
        return result

    import laserprog_studio.boolean_ops as boolean_ops

    monkeypatch.setattr(boolean_ops, "boolean_difference", fake_boolean_difference)

def _ctx(meshes=None, *, decision: str | None = None) -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _Scene(meshes)
    ctx.owner = _Owner(decision=decision)
    ctx.pick.bind_context(ctx)
    ctx.document.bind(ctx.scene)
    return ctx


def _press(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> bool:
    return bool(tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx))


def _box(size_z=20.0):
    return build_box(PrimitiveBuildRequest("box", {"size_x": 80, "size_y": 80, "size_z": size_z, "color": "#B8B8B8"}, 1))


def _rectangle_sketch(a=(-10.0, -10.0), b=(10.0, 10.0)) -> SketchDocument:
    sketch = SketchDocument()
    x0, y0 = a
    x1, y1 = b
    p1 = sketch.add_point((x0, y0)).id
    p2 = sketch.add_point((x1, y0)).id
    p3 = sketch.add_point((x1, y1)).id
    p4 = sketch.add_point((x0, y1)).id
    sketch.add_line(p1, p2)
    sketch.add_line(p2, p3)
    sketch.add_line(p3, p4)
    sketch.add_line(p4, p1)
    sketch.compile(SketchCompileOptions(split_curve_intersections=True, split_curves_at_vertices=True, solve_faces=True))
    return sketch


def _draw_rectangle(tool: PlanTrace2DCreatorTool, ctx: ToolContext, a=(-10.0, -10.0), b=(10.0, 10.0)) -> None:
    tool._state.sketch = _rectangle_sketch(a, b)
    tool._state.next_point_index = int(getattr(tool._state.sketch, "_next_id", 1) or 1)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
    assert tool._state.sketch.faces


def test_pass313_validation_section_exposes_add_and_subtract_buttons() -> None:
    tool = PlanTrace2DCreatorTool()
    ctx = _ctx([_box()])
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    _draw_rectangle(tool, ctx)

    sections = tool._services.overlay._toolbar_sections(ctx)
    validation = next(section for section in sections if section.id == "validation")
    labels = [action.label for action in validation.actions]

    assert labels == ["Add", "Subtract"]
    assert all(action.enabled for action in validation.actions)
    assert ctx.overlay.buttons["plan_trace_2d.validation.add"].enabled is True
    assert ctx.overlay.buttons["plan_trace_2d.validation.subtract"].enabled is True


def test_pass313_subtract_uses_target_full_thickness_and_stores_intact_mesh(monkeypatch) -> None:
    _stub_boolean_difference(monkeypatch)
    target = _box(size_z=50.0)
    original_vertices = [list(v) for v in target.vertices]
    ctx = _ctx([target])
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    _draw_rectangle(tool, ctx, (-12.0, -12.0), (12.0, 12.0))

    assert tool._apply_subtract(ctx) is True

    assert len(ctx.scene.meshes) == 1
    result = ctx.scene.meshes[0]
    source = editable_source_from_mesh(result)
    assert source is not None
    assert source["kind"] == PLAN_TRACE_SUBTRACT_SOURCE_KIND
    assert source["metadata"]["operation"] == "subtract"
    assert source["extrusion_depth_mm"] > 50.0
    assert source["metadata"]["validation_marker_color"] == "#8BC34A"
    assert source["metadata"]["intact_target_mesh"]["vertices"] == original_vertices


def test_pass313_reopened_subtraction_reapplies_from_stored_intact_mesh(monkeypatch) -> None:
    _stub_boolean_difference(monkeypatch)
    ctx = _ctx([_box(size_z=30.0)])
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    _draw_rectangle(tool, ctx, (-8.0, -8.0), (8.0, 8.0))
    assert tool._apply_subtract(ctx) is True
    first = ctx.scene.meshes[0]
    first_source = editable_source_from_mesh(first)
    assert first_source is not None
    stored_vertices = [list(v) for v in first_source["metadata"]["intact_target_mesh"]["vertices"]]

    reopened = PlanTrace2DCreatorTool()
    reopened.on_open(ctx)
    assert _press(reopened, ctx, 0.0, 0.0)
    assert reopened._state.editing_source_kind == PLAN_TRACE_SUBTRACT_SOURCE_KIND
    _draw_rectangle(reopened, ctx, (-14.0, -14.0), (14.0, 14.0))
    assert reopened._apply_subtract(ctx) is True

    reapplied = ctx.scene.meshes[0]
    reapplied_source = editable_source_from_mesh(reapplied)
    assert reapplied_source is not None
    assert reapplied_source["kind"] == PLAN_TRACE_SUBTRACT_SOURCE_KIND
    assert [list(v) for v in reapplied_source["metadata"]["intact_target_mesh"]["vertices"]] == stored_vertices


def test_pass313_editing_subtraction_shows_intact_target_and_add_restores_original(monkeypatch) -> None:
    _stub_boolean_difference(monkeypatch)
    ctx = _ctx([_box(size_z=30.0)])
    original_vertices = [list(v) for v in ctx.scene.meshes[0].vertices]
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    _draw_rectangle(tool, ctx, (-8.0, -8.0), (8.0, 8.0))
    assert tool._apply_subtract(ctx) is True
    cut_source = editable_source_from_mesh(ctx.scene.meshes[0])
    assert cut_source is not None and cut_source["kind"] == PLAN_TRACE_SUBTRACT_SOURCE_KIND

    reopened = PlanTrace2DCreatorTool()
    reopened.on_open(ctx)
    assert _press(reopened, ctx, 0.0, 0.0)

    # The editable cut result is kept in state for cancel/reapply, but the scene
    # shown to the user is the stored intact target so the drawing has context.
    assert reopened._state.editing_source_kind == PLAN_TRACE_SUBTRACT_SOURCE_KIND
    assert len(ctx.scene.meshes) == 1
    assert editable_source_from_mesh(ctx.scene.meshes[0]) is None
    assert [list(v) for v in ctx.scene.meshes[0].vertices] == original_vertices

    _draw_rectangle(reopened, ctx, (-4.0, -4.0), (4.0, 4.0))
    assert reopened.on_apply(ctx) is True

    assert len(ctx.scene.meshes) == 2
    assert editable_source_from_mesh(ctx.scene.meshes[0]) is None
    assert [list(v) for v in ctx.scene.meshes[0].vertices] == original_vertices
    added_source = editable_source_from_mesh(ctx.scene.meshes[1])
    assert added_source is not None
    assert added_source["kind"] != PLAN_TRACE_SUBTRACT_SOURCE_KIND


def test_pass313_clicking_old_plan_tracer_source_can_start_new_drawing_instead_of_editing() -> None:
    ctx = _ctx([])
    first = PlanTrace2DCreatorTool()
    first.on_open(ctx)
    assert _press(first, ctx, 0.0, 0.0)
    _draw_rectangle(first, ctx, (0.0, 0.0), (20.0, 20.0))
    assert first.on_apply(ctx) is True
    assert len(ctx.scene.meshes) == 1
    original_source = copy.deepcopy(editable_source_from_mesh(ctx.scene.meshes[0]))
    assert original_source is not None

    ctx.owner.decision = "new"
    second = PlanTrace2DCreatorTool()
    second.on_open(ctx)
    assert _press(second, ctx, 5.0, 5.0)

    assert second._state.plane is not None
    assert second._state.editing_source_object_id is None
    assert len(ctx.scene.meshes) == 1, "the old Plan Tracer mesh must not be hidden when choosing New sketch"
    assert editable_source_from_mesh(ctx.scene.meshes[0]) == original_source

    _draw_rectangle(second, ctx, (2.0, 2.0), (8.0, 8.0))
    assert second.on_apply(ctx) is True
    assert len(ctx.scene.meshes) == 2
    assert editable_source_from_mesh(ctx.scene.meshes[0]) == original_source
    assert editable_source_from_mesh(ctx.scene.meshes[1]) is not None


def test_pass313_new_sketch_hides_editable_hover_preview_after_plane_lock() -> None:
    ctx = _ctx([])
    first = PlanTrace2DCreatorTool()
    first.on_open(ctx)
    assert _press(first, ctx, 0.0, 0.0)
    _draw_rectangle(first, ctx, (0.0, 0.0), (20.0, 20.0))
    assert first.on_apply(ctx) is True

    ctx.owner.decision = "new"
    second = PlanTrace2DCreatorTool()
    second.on_open(ctx)
    support = ctx.document.objects(include_preview=False)[0]
    second._services.snap._show_editable_hover_preview(ctx, support.mesh, support.id)
    preview = ctx.projected_drawing.for_tool(second.id).get("plan_trace_2d.editable_hover")
    assert preview is not None and preview.visible is True
    second._state.editable_hover_object_id = support.id
    second._state.editable_hover_label = support.name

    assert _press(second, ctx, 5.0, 5.0)

    preview = ctx.projected_drawing.for_tool(second.id).get("plan_trace_2d.editable_hover")
    assert preview is not None and preview.visible is False
    assert second._state.editable_hover_object_id is None
    assert second._state.editable_hover_label == ""


def test_pass313_new_drawing_on_old_subtraction_uses_current_cut_as_new_origin(monkeypatch) -> None:
    _stub_boolean_difference(monkeypatch)
    ctx = _ctx([_box(size_z=30.0)])
    first = PlanTrace2DCreatorTool()
    first.on_open(ctx)
    assert _press(first, ctx, 0.0, 0.0)
    _draw_rectangle(first, ctx, (-8.0, -8.0), (8.0, 8.0))
    assert first._apply_subtract(ctx) is True
    assert editable_source_from_mesh(ctx.scene.meshes[0]) is not None

    # Simulate a real boolean side-effect that exists only on the current cut
    # piece, not on the originally stored intact target.
    ctx.scene.meshes[0].metadata["current_cut_marker"] = "keep_this_as_new_origin"

    ctx.owner.decision = "new"
    second = PlanTrace2DCreatorTool()
    second.on_open(ctx)
    assert _press(second, ctx, 0.0, 0.0)
    assert second._state.editing_source_object_id is None
    assert editable_source_from_mesh(ctx.scene.meshes[0]) is not None

    _draw_rectangle(second, ctx, (-4.0, -4.0), (4.0, 4.0))
    assert second._apply_subtract(ctx) is True
    reapplied_source = editable_source_from_mesh(ctx.scene.meshes[0])
    assert reapplied_source is not None
    stored_metadata = reapplied_source["metadata"]["intact_target_mesh"]["metadata"]
    assert stored_metadata["current_cut_marker"] == "keep_this_as_new_origin"

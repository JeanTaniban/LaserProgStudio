from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.projected_drawing import ProjectedTriangleMesh
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.editable_source import PLAN_TRACE_DRAFT_SOURCE_KIND, editable_source_from_mesh
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _EditableScene:
    def __init__(self) -> None:
        self.meshes = []
        self.normal = (0.0, 0.0, 1.0)

    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        if self.meshes:
            mesh = self.meshes[0]
            return PickResult(
                "face",
                screen_pos=screen_pos,
                world_pos=(float(x), float(y), 0.0),
                object_id=getattr(mesh, "mesh_id", ""),
                object_index=0,
                normal=self.normal,
            )
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 0.0),
            object_id="seed_face",
            object_index=0,
            normal=self.normal,
        )


class _Owner:
    def __init__(self) -> None:
        self.align_calls = []
        self.rebuild_calls = 0

    def align_camera_to_plan_surface(self, *, origin, normal, up_axis=None) -> None:
        self.align_calls.append({"origin": origin, "normal": normal, "up_axis": up_axis})

    def rebuild_scene(self, *_, **__) -> None:
        self.rebuild_calls += 1


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _EditableScene()
    ctx.owner = _Owner()
    ctx.pick.bind_context(ctx)
    ctx.document.bind(ctx.scene)
    return ctx


def _press(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> bool:
    return bool(tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx))


def _move(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(x, y)), ctx)


def _draw_rectangle_volume(ctx: ToolContext) -> object:
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    tool._services.mode_state._set_active_tool(ctx, "rectangle", reason="test", render=False)
    assert _press(tool, ctx, 10.0, 10.0)
    assert _press(tool, ctx, 60.0, 40.0)
    assert tool._state.sketch.faces
    assert tool.on_apply(ctx) is True
    assert len(ctx.scene.meshes) == 1
    return ctx.scene.meshes[0]


def test_pass305_apply_stores_editable_plan_tracer_source() -> None:
    ctx = _ctx()
    mesh = _draw_rectangle_volume(ctx)

    source = editable_source_from_mesh(mesh)
    assert source is not None
    assert source["tool_id"] == TOOL_PLAN_TRACE
    assert source["extrusion_depth_mm"] == 3.0
    assert source["sketch"]["points"]
    assert source["sketch"]["lines"]


def test_pass305_hover_editable_volume_updates_status_and_preview() -> None:
    ctx = _ctx()
    mesh = _draw_rectangle_volume(ctx)

    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    _move(tool, ctx, 4.0, 5.0)

    assert tool._state.editable_hover_object_id == getattr(mesh, "mesh_id")
    assert "editable" in str(ctx.inspector.value("plan_trace_2d.snap", "")).lower()
    preview = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get("plan_trace_2d.editable_hover")
    assert isinstance(preview, ProjectedTriangleMesh)
    metadata = dict(preview.metadata)
    assert metadata["plan_trace_role"] == "editable_hover"
    assert metadata["source_object_id"] == getattr(mesh, "mesh_id")
    assert preview.style.outline_color == "#FFD54F"
    assert preview.style.outline_width_px == 5.0
    assert not ctx.preview.items(owner_tool=TOOL_PLAN_TRACE)


def test_pass305_click_editable_volume_restores_sketch_and_replace_on_apply() -> None:
    ctx = _ctx()
    original = _draw_rectangle_volume(ctx)
    original_id = getattr(original, "mesh_id")

    edit_tool = PlanTrace2DCreatorTool()
    edit_tool.on_open(ctx)
    assert _press(edit_tool, ctx, 3.0, 3.0)

    assert edit_tool._state.phase == "draw"
    assert edit_tool._state.editing_source_object_id == original_id
    assert edit_tool._state.active_tool == "modify"
    assert edit_tool._state.sketch.lines
    assert edit_tool._state.extrusion_depth == 3.0
    assert ctx.owner.align_calls, "opening an editable volume must align the camera to its stored normal"
    assert len(ctx.scene.meshes) == 0, "the source volume must be hidden/removed while editing so it cannot pollute snapping"

    # Add another rectangle to make the replacement visibly different.
    edit_tool._services.mode_state._set_active_tool(ctx, "rectangle", reason="test", render=False)
    assert _press(edit_tool, ctx, 80.0, 80.0)
    assert _press(edit_tool, ctx, 100.0, 100.0)
    assert edit_tool.on_apply(ctx) is True

    assert len(ctx.scene.meshes) == 1
    replacement = ctx.scene.meshes[0]
    assert getattr(replacement, "mesh_id") == original_id
    assert editable_source_from_mesh(replacement) is not None
    assert editable_source_from_mesh(replacement)["extrusion_depth_mm"] == 3.0


def test_pass305_cancel_saves_recoverable_red_draft_placeholder() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    tool._services.mode_state._set_active_tool(ctx, "rectangle", reason="test", render=False)
    assert _press(tool, ctx, 10.0, 10.0)
    assert _press(tool, ctx, 60.0, 40.0)
    assert tool._state.sketch.lines

    if tool._state.metric_draft is not None:
        tool._services.metrics._validate_metric_draft(ctx)
    assert tool._save_current_sketch_as_draft_and_return_to_pick(ctx) is True

    assert len(ctx.scene.meshes) == 1
    draft = ctx.scene.meshes[0]
    source = editable_source_from_mesh(draft)
    assert source is not None
    assert source["kind"] == PLAN_TRACE_DRAFT_SOURCE_KIND
    assert draft.color == "#F44336"
    assert draft.metadata["plan_trace_placeholder"] is True
    assert tool._state.plane is None


def test_pass305_click_draft_restores_then_apply_promotes_placeholder() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    tool._services.mode_state._set_active_tool(ctx, "rectangle", reason="test", render=False)
    assert _press(tool, ctx, 10.0, 10.0)
    assert _press(tool, ctx, 60.0, 40.0)
    if tool._state.metric_draft is not None:
        tool._services.metrics._validate_metric_draft(ctx)
    assert tool._save_current_sketch_as_draft_and_return_to_pick(ctx) is True
    draft_id = getattr(ctx.scene.meshes[0], "mesh_id")
    assert editable_source_from_mesh(ctx.scene.meshes[0])["kind"] == PLAN_TRACE_DRAFT_SOURCE_KIND

    resumed = PlanTrace2DCreatorTool()
    resumed.on_open(ctx)
    assert _press(resumed, ctx, 5.0, 5.0)

    assert resumed._state.editing_source_object_id == draft_id
    assert resumed._state.editing_source_kind == PLAN_TRACE_DRAFT_SOURCE_KIND
    assert resumed._state.sketch.lines
    assert resumed.on_apply(ctx) is True

    assert len(ctx.scene.meshes) == 1
    promoted = ctx.scene.meshes[0]
    assert getattr(promoted, "mesh_id") == draft_id
    promoted_source = editable_source_from_mesh(promoted)
    assert promoted_source is not None
    assert promoted_source["kind"] != PLAN_TRACE_DRAFT_SOURCE_KIND
    assert promoted.color != "#F44336"



def test_pass305_cancel_to_draft_saves_line_only_sketch_without_face() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    ctx.snap.set_smart_snap(False)
    ctx.snap.set_grid_snap(False)
    ctx.snap.grid_provider.enabled = False
    assert _press(tool, ctx, 0.0, 0.0)
    tool._services.mode_state._set_active_tool(ctx, "line", reason="test", render=False)
    assert _press(tool, ctx, 10.0, 10.0)
    assert _press(tool, ctx, 60.0, 10.0)
    assert tool._state.sketch.lines
    assert not tool._state.sketch.faces

    assert tool.cancel(ctx) is True

    assert len(ctx.scene.meshes) == 1
    draft = ctx.scene.meshes[0]
    source = editable_source_from_mesh(draft)
    assert source is not None
    assert source["kind"] == PLAN_TRACE_DRAFT_SOURCE_KIND
    assert draft.color == "#F44336"
    assert draft.metadata["plan_trace_placeholder"] is True
    assert draft.metadata["placeholder_bounds_2d"][0] <= 10.0
    assert draft.metadata["placeholder_bounds_2d"][2] >= 60.0
    assert tool._state.plane is None


def test_pass305_save_draft_action_saves_open_polyline_without_face() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    ctx.snap.set_smart_snap(False)
    ctx.snap.set_grid_snap(False)
    ctx.snap.grid_provider.enabled = False
    assert _press(tool, ctx, 0.0, 0.0)
    tool._services.mode_state._set_active_tool(ctx, "polyline", reason="test", render=False)
    assert _press(tool, ctx, 10.0, 10.0)
    assert _press(tool, ctx, 60.0, 10.0)
    assert _press(tool, ctx, 60.0, 40.0)
    assert tool._state.sketch.lines
    assert not tool._state.sketch.faces
    assert tool._state.pending_polyline_last_id is not None

    assert tool._save_current_sketch_as_draft_and_return_to_pick(ctx) is True

    assert len(ctx.scene.meshes) == 1
    draft = ctx.scene.meshes[0]
    source = editable_source_from_mesh(draft)
    assert source is not None
    assert source["kind"] == PLAN_TRACE_DRAFT_SOURCE_KIND
    assert draft.color == "#F44336"
    assert tuple(round(v, 3) for v in draft.metadata["placeholder_bounds_2d"]) == (10.0, 10.0, 60.0, 40.0)


def test_pass305_host_tool_close_saves_open_line_draft_even_when_cancel_bypasses_creator_cancel() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert _press(tool, ctx, 0.0, 0.0)
    tool._services.mode_state._set_active_tool(ctx, "line", reason="test", render=False)
    assert _press(tool, ctx, 10.0, 10.0)
    assert _press(tool, ctx, 60.0, 10.0)
    assert tool._state.sketch.lines
    assert not tool._state.sketch.faces

    tool.on_close(ctx)

    assert len(ctx.scene.meshes) == 1
    draft = ctx.scene.meshes[0]
    source = editable_source_from_mesh(draft)
    assert source is not None
    assert source["kind"] == PLAN_TRACE_DRAFT_SOURCE_KIND
    assert draft.color == "#F44336"


def test_pass305_cancel_edit_existing_volume_replaces_hidden_source_with_red_draft() -> None:
    ctx = _ctx()
    original = _draw_rectangle_volume(ctx)
    original_id = getattr(original, "mesh_id")

    edit_tool = PlanTrace2DCreatorTool()
    edit_tool.on_open(ctx)
    assert _press(edit_tool, ctx, 3.0, 3.0)
    assert len(ctx.scene.meshes) == 0

    assert edit_tool.cancel(ctx) is True

    assert len(ctx.scene.meshes) == 1
    draft = ctx.scene.meshes[0]
    assert getattr(draft, "mesh_id") == original_id
    source = editable_source_from_mesh(draft)
    assert source is not None
    assert source["kind"] == PLAN_TRACE_DRAFT_SOURCE_KIND
    assert draft.color == "#F44336"
    assert edit_tool._state.plane is None


def test_pass305_creator_renderer_supports_mesh_preview_highlight() -> None:
    painter = Path("src/laserprog_studio/application/_tool_core_diag_scene_painter.py").read_text(encoding="utf-8")
    fallback = Path("src/laserprog_studio/application/creator_viewport_ui.py").read_text(encoding="utf-8")
    assert "PreviewKind.MESH" in painter
    assert "workmesh_to_polydata(preview_payload)" in painter
    assert "workmesh_to_polydata(payload)" in fallback

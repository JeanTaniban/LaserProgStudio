from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedFace, ProjectedLine
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.constants import _PENDING_PREVIEW_PREFIX
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def __init__(self) -> None:
        self.meshes = []

    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=1)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    ctx.document.bind(ctx.scene)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_plan_tracer_apply_extrudes_current_closed_face_into_document() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 180.0, 160.0)
    assert tool._state.sketch.faces

    assert tool.on_apply(ctx) is True
    assert len(ctx.scene.meshes) == 1
    mesh = ctx.scene.meshes[0]
    assert mesh.name == "Plan trace 2D extrusion"
    assert len(mesh.vertices) >= 8
    assert len(mesh.triangles) >= 12


def test_plan_tracer_pending_line_preview_follows_snapped_cursor_before_second_click() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_line_start_id is not None
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(140.0, 130.0)), ctx)

    item = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(f"{_PENDING_PREVIEW_PREFIX}:line")
    assert isinstance(item, ProjectedLine)
    assert item.visible is True
    assert dict(item.metadata)["style_id"] == "preview"
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()


def test_plan_tracer_selected_face_redraws_as_yellow_orange_fill_and_outline() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 160.0, 140.0)

    face_actor = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "face")
    ctx.selection.select(face_actor.id)
    ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).sync_interaction_state(render=False)

    selected_face = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(face_actor.id)
    assert isinstance(selected_face, ProjectedFace)
    assert selected_face.style.fill_color == "#f0a805"
    assert selected_face.style.outline_color == "#f0a805"
    assert ctx.preview.items(owner_tool=TOOL_PLAN_TRACE) == ()


def test_qt_overlay_layout_source_recursively_destroys_nested_rows() -> None:
    source = __import__("pathlib").Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")
    assert "def _clear_layout_tree" in source
    assert "item.layout()" in source
    assert "setParent(None)" not in source
    assert "toolCoreButtonId" in source

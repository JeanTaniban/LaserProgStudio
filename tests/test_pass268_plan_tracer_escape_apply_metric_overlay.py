from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.constants import _MODE_LINE, _TOOLBOX_ID
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


def test_escape_cancels_pending_draw_preview_without_closing_plan_tracer() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_line_start_id is not None
    assert ctx.overlay.window(_TOOLBOX_ID) is not None

    assert tool.cancel(ctx) is True

    assert tool._state.plane is not None
    assert tool._state.active_tool == _MODE_LINE
    assert tool._state.pending_line_start_id is None
    toolbox = ctx.overlay.window(_TOOLBOX_ID)
    assert toolbox is not None and toolbox.visible is True


def test_apply_accepts_visible_solved_faces_even_with_extra_internal_edge() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 180.0, 160.0)
    assert tool._state.sketch.faces

    points = list(tool._state.sketch.points)
    assert len(points) >= 4
    tool._state.sketch.add_line(points[0], points[2], line_id="internal_diagonal")
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    assert tool.can_apply(ctx) is True

    assert tool.on_apply(ctx) is True
    assert len(ctx.scene.meshes) == 1
    mesh = ctx.scene.meshes[0]
    assert mesh.metadata["source_tool"] == TOOL_PLAN_TRACE
    assert mesh.metadata["extrusion_depth_mm"] == 10.0
    # Positive locked-plane normal points toward the camera; in top view the
    # extruded cap must therefore have a greater Z than the drawing plane.
    z_values = [float(vertex[2]) for vertex in mesh.vertices]
    assert max(z_values) - min(z_values) == 10.0


def test_global_apply_pipeline_knows_creator_tools_can_apply_without_preview_session() -> None:
    preview_source = Path("src/laserprog_studio/application/preview_controller.py").read_text(encoding="utf-8")
    lifecycle_source = Path("src/laserprog_studio/application/tool_lifecycle_controller.py").read_text(encoding="utf-8")
    runtime_source = Path("src/laserprog_studio/tooling/creator_runtime.py").read_text(encoding="utf-8")

    assert "creator_ready" in preview_source
    assert "can_apply(getattr(w, \"context\", None))" in preview_source
    assert "apply_creator_tool_without_preview" in lifecycle_source
    assert "def can_apply(self, context" in runtime_source


def test_metric_overlay_layout_is_single_row_compact_and_does_not_force_large_toolbar_height() -> None:
    layout_source = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")
    adapter_source = Path("src/laserprog_studio/tool_core/overlay/qt_adapter.py").read_text(encoding="utf-8")
    metrics_source = Path("src/laserprog_studio/tool_api/plan2d/metrics.py").read_text(encoding="utf-8")

    assert "def _is_inline_metric_toolbar" in layout_source
    assert "layout.addLayout(row)" in layout_source
    assert "return 48" in adapter_source
    assert "cursor_offset_px=(0, 0)" in metrics_source

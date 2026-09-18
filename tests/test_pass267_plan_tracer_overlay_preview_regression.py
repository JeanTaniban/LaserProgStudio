from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import plan2d
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
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
    assert tool._state.display_plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_qt_overlay_rebuild_reuses_installed_layout_so_toolbar_cannot_become_empty() -> None:
    source = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")

    assert "layout = old" in source
    assert "layout = QVBoxLayout(widget)" in source
    rebuild_body = source.split("def rebuild_overlay_widget", 1)[1]
    before_kind = rebuild_body.split("kind = str(spec.overlay_kind)", 1)[0]
    assert "old.deleteLater()" not in before_kind


def test_plan_tracer_free_mouse_motion_forces_preview_visual_sync(monkeypatch) -> None:
    """A pending line preview must redraw even when no snap target is detected.

    The cursor actor can stay in the same ``free`` snap style while the mouse is
    moving.  That path used to take the cursor-only fast update and skip the
    newly changed pending preview until a snap event forced a full redraw.
    """

    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    assert tool._state.pending_line_start_id is not None

    sync_calls: list[bool] = []
    real_sync = plan2d.sync_plan_actor_visuals

    def capture_sync(*args, **kwargs):
        sync_calls.append(bool(kwargs.get("position_only", False)))
        return real_sync(*args, **kwargs)

    monkeypatch.setattr(plan2d, "sync_plan_actor_visuals", capture_sync)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(140.0, 130.0)), ctx)

    assert sync_calls, "cursor/preview move should request a visual sync"
    assert sync_calls[-1] is False

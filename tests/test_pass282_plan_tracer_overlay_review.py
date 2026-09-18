from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.constants import _TOOLBOX_ID
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


def _toolbox():
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    toolbox = ctx.overlay.window(_TOOLBOX_ID)
    assert toolbox is not None
    return toolbox


def test_plan_tracer_toolbox_is_true_top_center_without_cursor_offset() -> None:
    toolbox = _toolbox()

    assert toolbox.anchor == "viewport_top_left"
    assert toolbox.cursor_offset_px == (0, 0)


def test_plan_tracer_toolbar_uses_sectioned_hud_groups() -> None:
    toolbox = _toolbox()

    assert [section.id for section in toolbox.toolbar_sections] == ["select", "draw", "shapes", "measure", "build"]
    assert [section.label for section in toolbox.toolbar_sections] == ["Select", "Draw", "Shapes", "Measure", "Build"]
    assert [button.section for button in toolbox.buttons] == [
        "select",
        "draw",
        "draw",
        "draw",
        "shapes",
        "shapes",
        "shapes",
        "shapes",
        "measure",
        "build",
        "build",
    ]
    assert toolbox.buttons[8].label == "Dimension"
    assert toolbox.buttons[9].label == "Rebuild"

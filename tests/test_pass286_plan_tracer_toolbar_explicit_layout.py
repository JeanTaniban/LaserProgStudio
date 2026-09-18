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


from laserprog_studio.tool_core.overlay.qt_layout import _toolbar_button_slot_widths, _toolbar_content_width, _toolbar_separator_count
from laserprog_studio.tool_core.overlay.specs import command_deck_auto_width_px


def test_plan_tracer_toolbar_uses_declarative_sections_not_tool_pixel_tables() -> None:
    toolbox = _toolbox()

    assert [button.section for button in toolbox.buttons] == [
        "select",
        "draw",
        "draw",
        "draw",
        "shapes",
        "shapes",
        "shapes",
        "shapes",
        "shapes",
        "measure",
        "build",
        "build",
        "build",
        "build",
        "validation",
        "validation",
    ]
    assert _toolbar_separator_count(toolbox) == 5
    assert toolbox.width_px == command_deck_auto_width_px(toolbox.buttons, toolbox.toolbar_sections, badge=True)
    assert toolbox.width_px <= 1240


def test_plan_tracer_toolbar_auto_slots_keep_all_full_labels_readable() -> None:
    toolbox = _toolbox()
    widths = dict(zip((button.label for button in toolbox.buttons), _toolbar_button_slot_widths(toolbox), strict=True))

    assert widths == {
        "Modify": 72,
        "Point": 68,
        "Line": 64,
        "Polyline": 78,
        "Rectangle": 86,
        "Circle": 70,
        "Half-circle": 86,
        "Arc": 55,
        "Curve": 54,
        "Dimension": 86,
        "Mesh trace": 86,
        "Rebuild": 74,
        "Pattern": 70,
        "Delete": 70,
        "Add": 78,
        "Subtract": 92,
    }
    assert min(widths.values()) >= 54
    assert max(widths.values()) <= 124

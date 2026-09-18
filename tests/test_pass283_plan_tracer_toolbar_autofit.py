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


from laserprog_studio.tool_core.overlay.qt_layout import _toolbar_button_slot_widths, _toolbar_content_width
from laserprog_studio.tool_core.overlay.specs import command_deck_auto_width_px


def test_plan_tracer_toolbar_uses_sectioned_autofit_instead_of_fixed_ribbon() -> None:
    toolbox = _toolbox()

    assert toolbox.width_px == command_deck_auto_width_px(toolbox.buttons, toolbox.toolbar_sections, badge=True)
    assert 720 <= toolbox.width_px <= 1240
    assert toolbox.width_px <= 1240


def test_plan_tracer_toolbar_slots_are_readable_full_caption_slots() -> None:
    toolbox = _toolbox()
    widths = dict(zip((button.label for button in toolbox.buttons), _toolbar_button_slot_widths(toolbox), strict=True))

    display_labels = {button.label: button.display_label or button.label for button in toolbox.buttons}
    assert display_labels["Dimension"] == "Dimension"
    assert display_labels["Rectangle"] == "Rectangle"
    assert display_labels["Half-circle"] == "Half-circle"
    assert widths["Dimension"] >= widths["Arc"]
    assert min(widths.values()) >= 54
    assert max(widths.values()) <= 132

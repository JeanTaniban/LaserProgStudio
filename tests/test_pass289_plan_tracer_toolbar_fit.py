from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.overlay.qt_layout import (
    _COMMAND_DECK_BUTTON_HEIGHT,
    _COMMAND_DECK_MARGIN_X,
    _COMMAND_DECK_SECTION_GAP,
    _command_deck_responsive_slot_widths,
    _command_deck_section_width,
)
from laserprog_studio.tooling.plan_trace_2d.constants import _TOOLBOX_ID
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=1)


def _toolbox():
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    toolbox = ctx.overlay.window(_TOOLBOX_ID)
    assert toolbox is not None
    return toolbox


def test_plan_tracer_command_deck_uses_one_readable_command_row() -> None:
    toolbox = _toolbox()
    sections = tuple(toolbox.toolbar_sections)
    responsive = _command_deck_responsive_slot_widths(toolbox, sections)
    widths = [
        _command_deck_section_width(
            tuple(button for button in toolbox.buttons if button.section == section.id),
            responsive,
        )
        for section in sections
    ]
    command_row = sum(widths) + _COMMAND_DECK_SECTION_GAP * max(0, len(widths) - 1)

    assert toolbox.width_px - (_COMMAND_DECK_MARGIN_X * 2) >= command_row
    assert command_row >= 940
    assert toolbox.width_px <= 1240
    assert responsive["plan_trace_2d.tool.bezier"] >= 50


def test_plan_tracer_command_deck_buttons_are_compact_readable_targets() -> None:
    assert 60 <= _COMMAND_DECK_BUTTON_HEIGHT <= 68

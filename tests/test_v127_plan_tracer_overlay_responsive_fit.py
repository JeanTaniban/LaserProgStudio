from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.overlay.qt_layout import (
    _COMMAND_DECK_MARGIN_X,
    _COMMAND_DECK_SECTION_GAP,
    _command_deck_min_slot_width,
    _command_deck_responsive_slot_widths,
    _command_deck_section_width,
    _section_buttons,
    _toolbar_sections,
)
from laserprog_studio.tooling.plan_trace_2d.constants import _TOOLBOX_ID
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 7.0),
            object_id="face_7",
            object_index=1,
        )


def _toolbox():
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT),
        ctx,
    )
    toolbox = ctx.overlay.window(_TOOLBOX_ID)
    assert toolbox is not None
    return toolbox


def test_v127_curve_and_measure_sections_fit_without_overlap() -> None:
    toolbox = _toolbox()
    sections = tuple(
        section
        for section in _toolbar_sections(toolbox)
        if _section_buttons(toolbox, str(section.id))
    )
    natural_row = sum(
        _command_deck_section_width(_section_buttons(toolbox, str(section.id)))
        for section in sections
    ) + _COMMAND_DECK_SECTION_GAP * max(0, len(sections) - 1)
    available = toolbox.width_px - (_COMMAND_DECK_MARGIN_X * 2)

    # Reproduces the v126 bug: natural fixed cards are wider than the shell.
    assert natural_row > available

    responsive = _command_deck_responsive_slot_widths(toolbox, sections)
    responsive_row = sum(
        _command_deck_section_width(_section_buttons(toolbox, str(section.id)), responsive)
        for section in sections
    ) + _COMMAND_DECK_SECTION_GAP * max(0, len(sections) - 1)

    assert responsive_row <= available
    assert [section.id for section in sections] == [
        "select",
        "draw",
        "shapes",
        "measure",
        "build",
        "validation",
    ]
    assert "plan_trace_2d.tool.bezier" in responsive
    assert "plan_trace_2d.tool.dimension" in responsive

    buttons = {str(button.id): button for button in toolbox.buttons}
    assert all(
        width >= _command_deck_min_slot_width(buttons[button_id])
        for button_id, width in responsive.items()
    )


def test_v127_renderer_uses_responsive_width_for_buttons_and_section_frames() -> None:
    from pathlib import Path

    source = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")

    assert "responsive_slot_widths = _command_deck_responsive_slot_widths(spec, visible_sections)" in source
    assert "section_w = _command_deck_section_width(buttons, responsive_slot_widths)" in source
    assert "button.setFixedSize(int(slot_width), _COMMAND_DECK_BUTTON_HEIGHT)" in source

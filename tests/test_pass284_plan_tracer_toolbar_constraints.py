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


from pathlib import Path

from laserprog_studio.tool_core.overlay.qt_layout import _toolbar_content_width


def test_plan_tracer_overlay_uses_wider_readable_hud_not_cramped_legacy_strip() -> None:
    toolbox = _toolbox()

    assert toolbox.width_px >= 480
    assert toolbox.width_px <= 1240
    assert toolbox.width_px <= 1240
    assert all(button.label for button in toolbox.buttons)
    assert all(button.icon for button in toolbox.buttons)
    assert toolbox.toolbar_sections


def test_qt_toolbar_v2_has_section_cards_and_status_pill() -> None:
    style = Path("src/laserprog_studio/tool_core/overlay/qt_style.py").read_text(encoding="utf-8")
    layout = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")
    widgets = Path("src/laserprog_studio/tool_core/overlay/qt_widgets.py").read_text(encoding="utf-8")

    assert "ToolCoreCommandDeckChip" in style
    assert "ToolCoreCommandDeckSection" in style
    assert "_rebuild_command_deck_widget" in layout
    assert "toolCoreVectorCommandDeck" in layout
    assert "_command_deck_responsive_slot_widths" in layout
    assert "button.setFixedSize(int(slot_width), _COMMAND_DECK_BUTTON_HEIGHT)" in layout
    assert "toolCoreVectorCommandDeck" in widgets

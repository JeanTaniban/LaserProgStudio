from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.overlay.qt_layout import (
    _SECTIONED_TOOLBAR_BUTTON_HEIGHT,
    _SECTIONED_TOOLBAR_PILL_HEIGHT,
    _sectioned_toolbar_allocations,
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


def test_sectioned_toolbar_uses_compact_command_rail_targets() -> None:
    toolbox = _toolbox()
    _frames, buttons = _sectioned_toolbar_allocations(toolbox, tuple(toolbox.toolbar_sections), True)

    assert 54 <= _SECTIONED_TOOLBAR_BUTTON_HEIGHT <= 64
    assert 64 <= _SECTIONED_TOOLBAR_PILL_HEIGHT <= 78
    assert min(buttons.values()) >= 54


def test_vector_button_renderer_paints_compact_cells_and_bottom_labels() -> None:
    widgets = Path("src/laserprog_studio/tool_core/overlay/qt_widgets.py").read_text(encoding="utf-8")

    assert "toolCoreVectorCommandDeck" in widgets
    assert "painter.drawRoundedRect(rect, 8, 8)" in widgets
    assert "text_rect = QRectF(rect.left() + 4.0, rect.bottom() - 19.0" in widgets
    assert "icon_side = max(28.0" in widgets

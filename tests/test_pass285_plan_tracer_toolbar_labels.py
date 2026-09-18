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


def test_plan_tracer_toolbar_restores_full_visible_labels_in_sectioned_hud() -> None:
    toolbox = _toolbox()
    labels = [button.label for button in toolbox.buttons]
    widths = dict(zip(labels, _toolbar_button_slot_widths(toolbox), strict=True))

    assert labels == [
        'Modify',
        'Point',
        'Line',
        'Polyline',
        'Rectangle',
        'Circle',
        'Half-circle',
        'Arc',
        'Curve',
        'Dimension',
        'Mesh trace',
        'Rebuild',
        'Pattern',
        'Delete',
        'Add',
        'Subtract',
    ]
    assert [button.display_label or button.label for button in toolbox.buttons] == labels
    assert toolbox.width_px == command_deck_auto_width_px(toolbox.buttons, toolbox.toolbar_sections, badge=True)
    assert toolbox.width_px >= 960
    assert toolbox.width_px <= 1240
    assert widths["Half-circle"] >= 54
    assert widths["Dimension"] >= 54
    assert widths["Arc"] <= widths["Rectangle"]


def test_plan_tracer_toolbar_buttons_keep_real_text_for_qt_painting_and_accessibility() -> None:
    layout_source = __import__("pathlib").Path("src/laserprog_studio/tool_core/overlay/qt_layout.py").read_text(encoding="utf-8")
    widget_source = __import__("pathlib").Path("src/laserprog_studio/tool_core/overlay/qt_widgets.py").read_text(encoding="utf-8")

    assert "button = QPushButton(display_label if vector_icon else label)" in layout_source
    assert 'button.setProperty("toolCoreVectorLabel", display_label)' in layout_source
    assert 'button.setAccessibleName(label)' in layout_source
    assert 'button.setProperty("toolCoreVectorNoElide", True)' in layout_source
    assert "painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignVCenter, label_to_paint)" in widget_source

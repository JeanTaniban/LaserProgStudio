from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
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


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def test_plan_tracer_toolbox_uses_professional_icon_toolbar_spec() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)

    window = ctx.overlay.window("plan_trace_2d.toolbox")
    assert window is not None
    assert window.overlay_kind == "command_deck"
    assert window.anchor == "viewport_top_left"
    assert 720 <= window.width_px <= 1240
    assert [section.label for section in window.toolbar_sections] == ["Select", "Draw", "Shapes", "Measure", "Build", "Validation"]
    assert [field.id for field in window.fields] == ["plan_trace_2d.mode_badge", "plan_trace_2d.command_status"]
    assert window.fields[0].label == "Mode"
    assert window.fields[0].value == "Point"

    labels = [button.label for button in window.buttons]
    assert labels == [
        "Modify", "Point", "Line", "Polyline", "Rectangle", "Circle", "Half-circle", "Arc", "Curve",
        "Dimension", "Mesh trace", "Rebuild", "Pattern", "Delete", "Add", "Subtract",
    ]
    icons = [button.icon for button in window.buttons]
    assert icons[:10] == [
        "sketch.modify",
        "sketch.point",
        "sketch.line",
        "sketch.line",
        "sketch.rectangle",
        "sketch.circle",
        "sketch.half_circle",
        "sketch.arc",
        "sketch.arc",
        "sketch.dimension",
    ]
    assert window.buttons[2].group == "plan_trace_2d.tool"
    by_id = {button.id: button for button in window.buttons}
    assert by_id["plan_trace_2d.action.restore_faces"].checkable is False
    assert by_id["plan_trace_2d.action.delete"].checkable is False
    assert by_id["plan_trace_2d.validation.subtract"].checkable is False


def test_plan_tracer_mode_badge_updates_with_active_mode() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)

    tool._set_active_tool(ctx, "line", reason="test", render=False)
    window = ctx.overlay.window("plan_trace_2d.toolbox")
    assert window is not None
    assert window.fields[0].value == "Line"
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.line"


def test_overlay_api_builds_sectioned_mode_toolbar_without_tool_specific_button_logic() -> None:
    from laserprog_studio.tool_core.overlay import OverlayActionSpec, OverlayModeSpec, OverlayToolbarSectionSpec, build_sectioned_toolbar_window

    window = build_sectioned_toolbar_window(
        window_id="demo.toolbar",
        owner_tool="demo",
        group_id="demo.mode",
        sections=(
            OverlayToolbarSectionSpec(
                "edit",
                "Edit",
                modes=(
                    OverlayModeSpec("demo.mode.modify", "Modify", icon="sketch.modify"),
                    OverlayModeSpec("demo.mode.line", "Line", icon="sketch.line", shortcut="L"),
                ),
            ),
            OverlayToolbarSectionSpec("build", "Build", actions=(OverlayActionSpec("demo.delete", "Delete", icon="sketch.delete", style="danger"),)),
        ),
        active_mode_id="demo.mode.line",
        badge_id="demo.mode_badge",
        badge_value="Line",
        width_px=0,
    )

    assert window.overlay_kind == "toolbar"
    assert window.anchor == "viewport_top_center"
    assert [section.id for section in window.toolbar_sections] == ["edit", "build"]
    assert window.fields[0].id == "demo.mode_badge"
    assert window.fields[0].value == "Line"
    assert [button.checked for button in window.buttons[:2]] == [False, True]
    assert all(button.group == "demo.mode" and button.style == "mode" for button in window.buttons[:2])
    assert window.buttons[-1].checkable is False
    assert window.buttons[-1].group is None
    assert window.buttons[-1].style == "danger"
    assert window.buttons[-1].section == "build"

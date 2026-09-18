from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR
from laserprog_studio.tooling.vent_generator.feedback import VENT_STATUS_ID, VENT_TOOLBAR_ID
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _ctx_and_tool() -> tuple[ToolContext, VentGeneratorCreatorTool]:
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    return ctx, tool


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(float(x), float(y), 0.0), button=MouseButton.LEFT)


def test_vent_generator_publishes_creator_preview_and_overlay_feedback() -> None:
    ctx, tool = _ctx_and_tool()

    assert VENT_TOOLBAR_ID in ctx.overlay.windows
    assert VENT_STATUS_ID in ctx.overlay.windows
    assert ctx.inspector.value("viewport_feedback").startswith("Add")

    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(80, 0), ctx) is True

    projected_ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items()}
    assert "vent.generator.preview.centerline" in projected_ids
    assert "vent.generator.preview.waypoint.00" in projected_ids
    assert "vent.generator.preview.waypoint.01" in projected_ids
    assert "vent.generator.preview.label.00" in projected_ids
    assert "vent.generator.preview.label.01" in projected_ids

    toolbar = ctx.overlay.windows[VENT_TOOLBAR_ID]
    assert toolbar.anchor == "viewport_top_left"
    assert toolbar.overlay_kind == "command_deck"
    assert not ctx.overlay.windows[VENT_STATUS_ID].visible
    assert any(button.id == "vent.generator.action.apply_mesh" for button in toolbar.buttons)
    assert ctx.overlay.group_active["vent.generator.mode"] == "vent.generator.mode.ADD"
    assert "2 waypoint" in ctx.inspector.value("viewport_feedback")


def test_vent_generator_overlay_buttons_drive_modes_and_actions() -> None:
    ctx, tool = _ctx_and_tool()
    tool.on_event(_release(0, 0), ctx)
    tool.on_event(_release(70, 0), ctx)

    tool.on_overlay_button_clicked("vent.generator.mode.MOD", ctx)
    assert ctx.inspector.value("mode") == "MOD"
    assert ctx.overlay.group_active["vent.generator.mode"] == "vent.generator.mode.MOD"

    tool.on_event(_release(70, 0), ctx)
    assert "Waypoint 2" in ctx.inspector.value("selected_point")
    projected_ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items()}
    assert "vent.generator.preview.selection" in projected_ids
    assert "vent.generator.route.waypoint.01" in projected_ids

    tool.on_overlay_button_clicked("vent.generator.action.reset_path", ctx)
    payload = ctx.owner.planar_tool_state.payload
    assert payload.waypoints == []
    assert ctx.inspector.value("mode") == "ADD"
    assert ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items() == ()
    assert ctx.overlay.group_active["vent.generator.mode"] == "vent.generator.mode.ADD"


def test_vent_generator_native_drag_moves_payload_route_not_only_dot() -> None:
    ctx, tool = _ctx_and_tool()
    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(80, 0), ctx) is True
    payload = ctx.owner.planar_tool_state.payload

    tool.on_overlay_button_clicked("vent.generator.mode.MOD", ctx)
    actor_id = "vent.generator.route.waypoint.01"
    assert ctx.selection.actor(actor_id) is not None
    ctx.selection.select(actor_id, replace=True)
    ctx.selection.begin_grab(actor_id, (80.0, 0.0), (80.0, 0.0, 0.0))

    event = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(120.0, 24.0),
        world_pos=(120.0, 24.0, 0.0),
        button=MouseButton.LEFT,
    )
    replacements = tool.resolve_drag_positions(event, ctx)

    assert replacements is not None
    assert actor_id in replacements
    assert payload.waypoints[1] == (120.0, 24.0)
    assert replacements[actor_id].points[0][:2] == (120.0, 24.0)
    # Segment actors are still present for the official Plan2D route grammar;
    # the release hook will rebuild their exact final UI state once.
    assert ctx.selection.actor("vent.generator.route.segment.00") is not None

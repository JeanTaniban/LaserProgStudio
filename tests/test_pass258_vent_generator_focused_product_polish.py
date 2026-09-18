from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import PlanarEditMode, VentPathDraft
from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR
from laserprog_studio.tooling.vent_generator.settings import MODE_CHOICES
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(float(x), float(y), 0.0), button=MouseButton.LEFT)


def _ctx_and_tool_with_planar_state() -> tuple[ToolContext, VentGeneratorCreatorTool]:
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    return ctx, tool


def test_pass258_reset_mode_is_a_momentary_ui_action_that_returns_to_add() -> None:
    ctx, tool = _ctx_and_tool_with_planar_state()
    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(80, 0), ctx) is True
    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)
    assert payload.waypoints

    ctx.inspector.update_value("mode", "RST")

    assert payload.waypoints == []
    assert payload.mode is PlanarEditMode.ADD
    assert ctx.inspector.value("mode") == "ADD"
    assert ctx.modes.active(TOOL_VENT_GENERATOR).id == "ADD"
    assert ctx.overlay.group_active["vent.generator.mode"] == "vent.generator.mode.ADD"
    assert "0 waypoint" in ctx.inspector.value("route_summary")


def test_pass258_reset_mode_label_says_it_is_immediate_not_a_sticky_mode() -> None:
    labels = dict(MODE_CHOICES)
    assert labels["RST"] == "Reset route now"


def test_pass258_creator_context_without_host_owner_keeps_a_functional_route_payload() -> None:
    ctx = ToolContext()
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)

    assert isinstance(tool._payload(ctx), VentPathDraft)  # intentional focused product guard
    assert "0 waypoint" in ctx.inspector.value("route_summary")

    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(80, 0), ctx) is True

    payload = tool._payload(ctx)
    assert isinstance(payload, VentPathDraft)
    assert payload.waypoints == [(0.0, 0.0), (80.0, 0.0)]
    assert "2 waypoints" in ctx.inspector.value("route_summary")
    assert ctx.inspector.value("apply_check").startswith("Ready to apply")
    assert "vent.generator.preview.centerline" in {item.id for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items()}
    assert tool.on_apply(ctx) is True
    assert "vertices" in ctx.inspector.value("apply_check")

    tool.close(ctx)
    assert tool._payload(ctx) is None

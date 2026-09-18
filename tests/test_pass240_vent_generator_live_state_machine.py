from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import PlanarEditMode, VentPathDraft
from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.vent_generator import VentRouteMachine, vent_route_summary, vent_selected_point_text
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _ctx_and_tool() -> tuple[ToolContext, VentGeneratorCreatorTool]:
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    return ctx, tool


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(float(x), float(y), 0.0), button=MouseButton.LEFT)


def _move(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_MOVE, world_pos=(float(x), float(y), 0.0), button=MouseButton.NONE)


def test_vent_generator_headless_events_cover_add_modify_delete_and_reset() -> None:
    ctx, tool = _ctx_and_tool()

    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(80, 0), ctx) is True
    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)
    assert payload.waypoints == [(0.0, 0.0), (80.0, 0.0)]
    assert "2 waypoints" in ctx.inspector.value("route_summary")

    ctx.inspector.update_value("mode", "MOD")
    assert payload.mode is PlanarEditMode.MOD
    assert tool.on_event(_release(80, 0), ctx) is True
    assert payload.selected_index == 1
    assert ctx.inspector.field_state("curve_radius").visible is True
    assert ctx.inspector.value("selected_point").startswith("Waypoint 2")

    assert tool.on_event(_move(90, 12), ctx) is True
    assert payload.waypoints[1] == (90.0, 12.0)
    assert "90.0, 12.0" in ctx.inspector.value("selected_point")

    ctx.inspector.update_value("curve_radius", 12.5)
    ctx.inspector.update_value("curve_strength", -0.4)
    assert payload.selected_segment_index() == 0
    assert payload.segment_curve_radii[0] == 12.5
    assert payload.segment_curve_strengths[0] == -0.4

    ctx.inspector.update_value("mode", "SUPP")
    assert tool.on_event(_release(90, 12), ctx) is True
    assert payload.waypoints == [(0.0, 0.0)]

    ctx.inspector.trigger("reset_path")
    assert payload.waypoints == []
    assert payload.mode is PlanarEditMode.ADD
    assert ctx.inspector.value("mode") == "ADD"


def test_vent_route_machine_is_the_canonical_route_edit_unit() -> None:
    ctx, _tool = _ctx_and_tool()
    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)

    machine = VentRouteMachine(payload, tolerance=4.0)
    assert machine.set_mode("draw").message == "Mode: ADD"
    assert machine.click_plane((0.0, 0.0)).changed is True
    assert machine.click_plane((60.0, 0.0)).changed is True
    assert "2 waypoints" in vent_route_summary(payload)

    machine.set_mode("move")
    assert machine.click_plane((60.0, 0.0)).selected_index == 1
    assert machine.move_selected((70.0, 10.0)).changed is True
    assert vent_selected_point_text(payload) == "Waypoint 2: 70.0, 10.0 mm"

    machine.set_mode("delete")
    assert machine.click_plane((70.0, 10.0)).changed is True
    assert len(payload.waypoints) == 1
    assert machine.set_mode("clear").changed is True
    assert payload.waypoints == []

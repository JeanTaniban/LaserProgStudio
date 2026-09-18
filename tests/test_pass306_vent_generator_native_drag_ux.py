from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import VentPathDraft, make_locked_plane
from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR
from laserprog_studio.tooling.vent_generator.feedback import sync_vent_route_visuals
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _ctx_tool_payload() -> tuple[ToolContext, VentGeneratorCreatorTool, VentPathDraft]:
    payload = VentPathDraft(make_locked_plane("top"))
    payload.add_waypoint_plane((0.0, 0.0))
    payload.add_waypoint_plane((80.0, 0.0))
    payload.add_waypoint_plane((120.0, 40.0))
    payload.mode = "MOD"
    payload.selected_index = 1
    state = PlanarToolState()
    state.payload = payload
    owner = SimpleNamespace(planar_tool_state=state)
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    state.payload = payload
    sync_vent_route_visuals(ctx, payload, state=state, render=False, full=True)
    return ctx, tool, payload


def _point_position(ctx: ToolContext, actor_id: str) -> tuple[float, float]:
    primitive = next(item for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items() if item.id == actor_id)
    pos = getattr(primitive, "position", None)
    assert pos is not None
    return (round(float(pos[0]), 6), round(float(pos[1]), 6))


def _line_points(ctx: ToolContext, actor_id: str) -> tuple[tuple[float, float], ...]:
    primitive = next(item for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items() if item.id == actor_id)
    points = tuple(getattr(primitive, "points", ()) or ())
    return tuple((round(float(point[0]), 6), round(float(point[1]), 6)) for point in points)


def test_pass306_native_drag_renders_live_even_when_resolver_presyncs_projected_registry() -> None:
    ctx, tool, payload = _ctx_tool_payload()
    actor_id = "vent.generator.route.waypoint.01"
    ctx.selection.select(actor_id, replace=True)
    ctx.selection.begin_grab(actor_id, (80.0, 0.0), (80.0, 0.0, 0.0))

    result = handle_native_creator_ui_event(
        ToolEvent(
            ToolEventType.MOUSE_MOVE,
            screen_pos=(110.0, 30.0),
            world_pos=(110.0, 30.0, 0.0),
            button=MouseButton.LEFT,
        ),
        ctx,
        owner_tool=TOOL_VENT_GENERATOR,
        drag_position_resolver=tool.resolve_drag_positions,
        render=False,
    )

    assert result.action == "drag"
    assert result.handled is True
    assert result.visual_changed is True
    assert payload.waypoints[1] == (110.0, 30.0)
    assert _point_position(ctx, actor_id) == (110.0, 30.0)
    assert _line_points(ctx, "vent.generator.route.segment.00")[-1] == (110.0, 30.0)
    assert _line_points(ctx, "vent.generator.route.segment.01")[0] == (110.0, 30.0)

    dirty_handles = set(ctx.selection.state.dirty_visual_handle_ids)
    assert actor_id in dirty_handles
    assert "vent.generator.route.segment.00" in dirty_handles
    assert "vent.generator.route.segment.01" in dirty_handles
    assert ctx.profiler.snapshot()["plan2d.actor_visuals.dirty_bridge"] >= 3


def test_pass306_plan2d_dirty_bridge_is_native_and_not_vent_specific() -> None:
    ctx, _tool, payload = _ctx_tool_payload()
    payload.waypoints[1] = (96.0, 12.0)

    sync_vent_route_visuals(ctx, payload, state=ctx.owner.planar_tool_state, render=False, full=False, changed_indices=(1,), position_only=True)

    dirty_handles = set(ctx.selection.state.dirty_visual_handle_ids)
    assert "vent.generator.route.waypoint.01" in dirty_handles
    assert "vent.generator.route.segment.00" in dirty_handles
    assert "vent.generator.route.segment.01" in dirty_handles

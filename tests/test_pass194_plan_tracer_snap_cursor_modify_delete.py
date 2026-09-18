from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedHandle
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
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


def _place(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float):
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)
    return next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.id.endswith(f":{len(tool._state.points):04d}"))


def test_plan_cursor_is_always_visible_and_follows_projected_world_mouse_without_snap() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)

    def _camera_projection(screen_pos, plane_or_depth=0.0):
        depth = float(getattr(plane_or_depth, "depth", plane_or_depth))
        return (1000.0 + float(screen_pos[0]), 2000.0 + float(screen_pos[1]), depth)

    ctx.viewport.screen_to_world_on_plane = _camera_projection

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(250.0, 260.0)), ctx)
    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["api_ui_visible"] is True
    assert cursor.points[0] == (1250.0, 2260.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert tool._state.last_snap_label == "none"



def test_plan_point_placement_uses_camera_projection_not_event_world_position() -> None:
    ctx = _ctx()

    def _camera_projection(screen_pos, plane_or_depth=0.0):
        depth = float(getattr(plane_or_depth, "depth", plane_or_depth))
        return (1000.0 + float(screen_pos[0]), 2000.0 + float(screen_pos[1]), depth)

    ctx.viewport.screen_to_world_on_plane = _camera_projection
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)

    tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_PRESS,
            screen_pos=(30.0, 40.0),
            world_pos=(-5.0, -6.0, -7.0),
            button=MouseButton.LEFT,
        ),
        ctx,
    )

    point = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point")
    assert point.points[0] == (1030.0, 2040.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert point.metadata["plan_trace_semantic_world_pos"] == (1030.0, 2040.0, 7.0)


def test_modify_drag_uses_smart_snap_and_updates_semantic_point_state() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    first = _place(tool, ctx, 30.0, 40.0)
    second = _place(tool, ctx, 80.0, 90.0)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    ctx.selection.select(first.id)
    ctx.selection.begin_grab(first.id, (30.0, 40.0), first.points[0])
    result = handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(80.0, 90.0), button=MouseButton.LEFT),
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        drag_position_resolver=tool.resolve_drag_positions,
        render=False,
    )

    moved = ctx.selection.actor(first.id)
    assert result.handled is True
    assert result.moved == 1
    assert moved is not None
    assert moved.points[0] == second.points[0]
    assert moved.metadata["plan_trace_semantic_world_pos"] == second.metadata["plan_trace_semantic_world_pos"]
    assert dict(tool._state.points)[first.id] == second.metadata["plan_trace_semantic_world_pos"]
    assert tool._state.last_snap_label.startswith("tool_temp_point")
    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["api_ui_visible"] is True
    assert cursor.points[0] == second.points[0]


def test_modify_mode_hover_keeps_diamond_visible_on_projected_plane() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    _place(tool, ctx, 30.0, 40.0)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(250.0, 260.0)), ctx)

    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["api_ui_visible"] is True
    assert cursor.points[0] == (250.0, 260.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert tool._state.last_snap_label == "none"


def test_multi_point_modify_drag_snaps_last_selected_point_and_moves_group() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    first = _place(tool, ctx, 30.0, 30.0)
    second = _place(tool, ctx, 50.0, 30.0)
    target = _place(tool, ctx, 120.0, 130.0)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    ctx.selection.select(first.id, replace=True)
    ctx.selection.select(second.id, replace=False)
    ctx.selection.begin_grab(first.id, (10.0, 10.0), first.points[0])
    result = handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(120.0, 130.0), button=MouseButton.LEFT),
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        drag_position_resolver=tool.resolve_drag_positions,
        render=False,
    )

    moved_first = ctx.selection.actor(first.id)
    moved_second = ctx.selection.actor(second.id)
    assert result.handled is True
    assert result.moved == 2
    assert moved_first is not None and moved_second is not None
    assert moved_second.points[0] == target.points[0]
    assert moved_first.points[0] == (100.0, 130.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert dict(tool._state.points)[second.id] == target.metadata["plan_trace_semantic_world_pos"]
    assert tool._state.last_snap_label.startswith("tool_temp_point")
    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["api_ui_visible"] is True
    assert cursor.points[0] == target.points[0]



def test_modify_drag_refresh_includes_snap_cursor_dirty_visual() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    point = _place(tool, ctx, 30.0, 40.0)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    ctx.selection.select(point.id)
    ctx.selection.begin_grab(point.id, (30.0, 40.0), point.points[0])
    result = handle_native_creator_ui_event(
        ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(45.0, 55.0), button=MouseButton.LEFT),
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        drag_position_resolver=tool.resolve_drag_positions,
        render=False,
    )

    cursor_id = f"{TOOL_PLAN_TRACE}:cursor"
    cursor = ctx.selection.actor(cursor_id)
    assert result.handled is True
    assert result.action == "drag"
    assert result.visual_changed is True
    assert cursor is not None
    assert cursor.points[0] == (45.0, 55.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    # The projected registry is now the viewport source of truth.  The cursor
    # primitive must move immediately without relying on the legacy dirty-id batch.
    cursor_primitive = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(cursor_id)
    assert isinstance(cursor_primitive, ProjectedHandle)
    assert cursor_primitive.position == cursor.points[0]
    assert not ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE)


def test_delete_key_removes_selected_plan_points_only() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    point = _place(tool, ctx, 30.0, 40.0)
    anchor_id = f"{TOOL_PLAN_TRACE}:height_anchor"
    ctx.selection.select(point.id)

    handled = tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="delete"), ctx)

    assert handled is True
    assert ctx.selection.actor(point.id) is None
    assert ctx.selection.actor(anchor_id) is not None
    assert tool._state.points == []
    assert not ctx.selection.ids()

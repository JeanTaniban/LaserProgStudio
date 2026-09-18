from __future__ import annotations

from time import perf_counter

from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Scene:
    def pick_face_at(self, screen_pos, **_kwargs):
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 0.0),
            object_id="ground",
            object_index=0,
        )


def _open() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    tool = PlanTrace2DCreatorTool()
    ctx = ToolContext()
    ctx.scene = _Scene()
    ctx.pick.bind_context(ctx)
    tool.on_open(ctx)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    return tool, ctx


def _add_point(tool: PlanTrace2DCreatorTool, xy: tuple[float, float]):
    point_id = f"plan_trace:point:{tool._state.next_point_index:04d}"
    tool._state.next_point_index += 1
    return tool._state.sketch.add_point(xy, point_id=point_id)


def _native(tool, ctx, event):
    assert tool.wants_native_actor_interaction(event, ctx)
    result = handle_native_creator_ui_event(
        event,
        ctx,
        owner_tool=tool.id,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
        drag_position_resolver=tool.resolve_drag_positions,
    )
    tool.on_native_interaction_result(event, ctx, result)
    return result


def test_v144_point_selection_survives_press_release_without_duplicate() -> None:
    tool, ctx = _open()
    point = _add_point(tool, (20.0, 15.0))
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    before_ids = tuple(tool._state.sketch.points)

    press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(20.0, 15.0),
        world_pos=(20.0, 15.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert _native(tool, ctx, press).action == "grab"
    release = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(20.0, 15.0),
        world_pos=(20.0, 15.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert _native(tool, ctx, release).action == "release"

    assert tuple(tool._state.sketch.points) == before_ids
    assert ctx.selection.is_selected(point.id)
    assert tuple(ctx.selection.ids()) == (point.id,)


def test_v144_box_drag_moves_do_not_rebuild_plan_tracer_overlay_or_renderer(monkeypatch) -> None:
    tool, ctx = _open()
    tool._services.selection._configure_modify_selection_api(ctx)
    report_calls: list[int] = []
    render_calls: list[int] = []
    monkeypatch.setattr(tool._services.overlay, "_sync_reports", lambda _ctx: report_calls.append(1))
    monkeypatch.setattr(
        tool._services.rendering,
        "_render",
        lambda _ctx, **_kwargs: render_calls.append(1),
    )

    press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(100.0, 100.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"shift"}),
    )
    assert tool._services.selection._handle_modify_selection_api_event(ctx, press)

    started = perf_counter()
    for index in range(1000):
        move = ToolEvent(
            ToolEventType.MOUSE_MOVE,
            screen_pos=(110.0 + float(index % 250), 120.0 + float(index % 180)),
            button=MouseButton.LEFT,
            modifiers=frozenset({"shift"}),
        )
        assert tool._services.selection._handle_modify_selection_api_event(ctx, move)
    elapsed = perf_counter() - started

    assert report_calls == []
    assert render_calls == []
    # Headless semantic updates are O(1) and should remain far below a UI frame
    # per event.  The generous bound catches accidental full-sketch work without
    # being sensitive to shared CI load.
    assert elapsed < 0.25

    release = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(300.0, 280.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"shift"}),
    )
    assert tool._services.selection._handle_modify_selection_api_event(ctx, release)
    assert len(report_calls) == 1
    assert len(render_calls) == 1


def test_v144_stale_drag_snap_cache_self_heals_when_grab_is_inactive() -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (10.0, 10.0))
    p1 = _add_point(tool, (40.0, 10.0))
    tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    service = tool._services.snap_targets

    service._begin_drag_snap_cache(ctx, exclude_ids=(p0.id,))
    assert service._drag_targets_cache is not None
    assert not any(target.id == p0.id for target in service._drag_targets_cache)

    # Simulate a release consumed by another UI layer. The cache must not remain
    # frozen after the generic selection runtime says no grab is active.
    ctx.selection.state.grab_active = False
    full, near = service._live_snap_targets_and_near(ctx, (10.0, 10.0))

    assert service._drag_targets_cache is None
    assert any(target.id == p0.id for target in full)
    assert any(target.id == p0.id for target in near)


def test_v144_exact_vertex_snap_remains_available_after_noop_point_click() -> None:
    tool, ctx = _open()
    point = _add_point(tool, (25.0, 30.0))
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)

    press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(25.0, 30.0),
        world_pos=(25.0, 30.0, 0.0),
        button=MouseButton.LEFT,
    )
    _native(tool, ctx, press)
    release = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(25.0, 30.0),
        world_pos=(25.0, 30.0, 0.0),
        button=MouseButton.LEFT,
    )
    _native(tool, ctx, release)

    world = tool._services.snap._update_cursor(
        ctx,
        ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(25.2, 30.1), button=MouseButton.NONE),
        render=False,
    )
    assert world is not None
    assert abs(world[0] - 25.0) < 1.0e-6
    assert abs(world[1] - 30.0) < 1.0e-6
    assert tool._state.last_snap_kind == "vertex"
    assert ctx.selection.is_selected(point.id)




def test_v144_live_geometry_invalidation_does_not_rebuild_frozen_drag_index(monkeypatch) -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (10.0, 10.0))
    p1 = _add_point(tool, (40.0, 10.0))
    tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    service = tool._services.snap_targets

    builds: list[int] = []
    real_build = service._build_screen_index

    def counted_build(*args, **kwargs):
        builds.append(1)
        return real_build(*args, **kwargs)

    monkeypatch.setattr(service, "_build_screen_index", counted_build)
    service._begin_drag_snap_cache(ctx, exclude_ids=(p0.id,))
    assert service._drag_targets_cache is not None

    service._near_targets_from_pool(ctx, service._drag_targets_cache, (30.0, 10.0))
    # Point-only sketch synchronization invalidates the future live pool while
    # dragging. The frozen drag geometry itself did not change.
    service.invalidate_geometry_cache()
    service._near_targets_from_pool(ctx, service._drag_targets_cache, (31.0, 10.0))

    assert len(builds) == 1

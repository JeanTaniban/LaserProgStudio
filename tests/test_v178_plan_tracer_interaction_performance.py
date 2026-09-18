from __future__ import annotations

from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind, SelectionManager, ToolActor
from laserprog_studio.tool_core.projected_drawing import ProjectedFace
from laserprog_studio.tool_core.sketch.document import SketchDocument
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
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT),
        ctx,
    )
    assert tool._state.plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT),
        ctx,
    )


def _draw_rectangle(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 180.0, 160.0)
    assert tool._state.sketch.faces
    tool._set_active_tool(ctx, "modify", reason="test", render=False)


def _native_click_face(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(140.0, 130.0), button=MouseButton.LEFT)
    result = handle_native_creator_ui_event(
        press,
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
    )
    assert result.handled is True
    tool.on_native_interaction_result(press, ctx, result)

    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(140.0, 130.0), button=MouseButton.LEFT)
    result = handle_native_creator_ui_event(
        release,
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
    )
    tool.on_native_interaction_result(release, ctx, result)
    if not result.handled:
        tool.on_event(release, ctx)


def test_screen_hit_index_reuses_projection_until_geometry_changes() -> None:
    selection = SelectionManager()
    owner = "dense-plan"
    for index in range(600):
        x = float((index % 30) * 12)
        y = float((index // 30) * 12)
        selection.register_actor(
            ToolActor(
                id=f"face:{index}",
                kind=ActorKind.POLYLINE,
                owner_tool=owner,
                points=((x, y, 0.0), (x + 10.0, y, 0.0), (x + 10.0, y + 10.0, 0.0), (x, y + 10.0, 0.0)),
                interaction=ActorInteraction.SELECTABLE,
                hit_radius_px=72.0,
                metadata={"filled_polygon_hit": True, "plan_trace_role": "face"},
            )
        )

    projection_calls = 0

    def projector(point):
        nonlocal projection_calls
        projection_calls += 1
        return (float(point[0]), float(point[1]))

    key = ("camera", 1)
    hit = selection.hit_test((5.0, 5.0), projector, owner_tool=owner, selectable_only=True, projection_key=key)
    assert hit is not None and hit.actor_id == "face:0"
    first_projection_calls = projection_calls
    assert first_projection_calls >= 600 * 4

    # Same camera + same actor geometry: ordinary hover must not reproject the
    # whole scene.  Only the local screen-grid candidates are tested.
    assert selection.hit_test((17.0, 5.0), projector, owner_tool=owner, selectable_only=True, projection_key=key) is not None
    assert projection_calls == first_projection_calls

    selection.set_hover("face:1")
    assert selection.hit_test((29.0, 5.0), projector, owner_tool=owner, selectable_only=True, projection_key=key) is not None
    assert projection_calls == first_projection_calls

    # Fixed helper actors (Plan Tracer cursor/preview handles) are not hit-test
    # geometry and therefore must not invalidate the selection index.
    selection.register_actor(
        ToolActor(
            id="cursor",
            kind=ActorKind.POINT,
            owner_tool=owner,
            points=((99.0, 99.0, 0.0),),
            interaction=ActorInteraction.FIXED,
        )
    )
    selection.hit_test((29.0, 5.0), projector, owner_tool=owner, selectable_only=True, projection_key=key)
    assert projection_calls == first_projection_calls

    # A real selectable geometry mutation invalidates and rebuilds exactly when
    # required for correctness.
    selection.register_actor(
        ToolActor(
            id="new-face",
            kind=ActorKind.POLYLINE,
            owner_tool=owner,
            points=((500.0, 500.0, 0.0), (510.0, 500.0, 0.0), (510.0, 510.0, 0.0), (500.0, 510.0, 0.0)),
            interaction=ActorInteraction.SELECTABLE,
            metadata={"filled_polygon_hit": True, "plan_trace_role": "face"},
        )
    )
    selection.hit_test((5.0, 5.0), projector, owner_tool=owner, selectable_only=True, projection_key=key)
    assert projection_calls > first_projection_calls



def test_projected_hover_visual_sync_is_local(monkeypatch) -> None:
    ctx = ToolContext()
    manager = ctx.projected_drawing
    owner = TOOL_PLAN_TRACE
    manager._items[owner] = {
        f"face:{index}": ProjectedFace(
            id=f"face:{index}",
            vertices=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)),
        )
        for index in range(2000)
    }
    ctx.selection.state.hover_id = "face:1000"

    selected_checks = 0
    original_is_selected = ctx.selection.is_selected

    def counted_is_selected(actor_id):
        nonlocal selected_checks
        selected_checks += 1
        return original_is_selected(actor_id)

    monkeypatch.setattr(ctx.selection, "is_selected", counted_is_selected)
    manager.sync_interaction_state(
        owner,
        render=False,
        actor_ids=("face:999", "face:1000"),
    )
    # The hovered actor short-circuits before selection lookup and only the old
    # hover needs one selection-state check.  A global pass would perform about
    # 1,999 checks here.
    assert selected_checks <= 2

def test_patterned_face_holes_are_indexed_in_screen_space() -> None:
    selection = SelectionManager()
    owner = "patterned-plan"
    holes = tuple(
        (
            (float((index % 50) * 3), float((index // 50) * 3), 0.0),
            (float((index % 50) * 3 + 1), float((index // 50) * 3), 0.0),
            (float((index % 50) * 3 + 1), float((index // 50) * 3 + 1), 0.0),
            (float((index % 50) * 3), float((index // 50) * 3 + 1), 0.0),
        )
        for index in range(2000)
    )
    selection.register_actor(
        ToolActor(
            id="face",
            kind=ActorKind.POLYLINE,
            owner_tool=owner,
            points=((0.0, 0.0, 0.0), (200.0, 0.0, 0.0), (200.0, 200.0, 0.0), (0.0, 200.0, 0.0)),
            interaction=ActorInteraction.SELECTABLE,
            hit_radius_px=72.0,
            metadata={
                "filled_polygon_hit": True,
                "filled_polygon_holes": holes,
                "plan_trace_role": "face",
            },
        )
    )
    projection_calls = 0

    def projector(point):
        nonlocal projection_calls
        projection_calls += 1
        return (float(point[0]), float(point[1]))

    key = ("camera", 9)
    # Build once.  This point is away from the dense motif area and lies in the
    # containing face.
    assert selection.hit_test((190.0, 190.0), projector, owner_tool=owner, selectable_only=True, projection_key=key) is not None
    built_calls = projection_calls
    assert built_calls >= 4 + len(holes) * 4

    # Warm hover performs no new world-to-screen projection, and an actual hole
    # still correctly excludes the containing face.
    assert selection.hit_test((190.0, 180.0), projector, owner_tool=owner, selectable_only=True, projection_key=key) is not None
    assert projection_calls == built_calls
    assert selection.hit_test((0.5, 0.5), projector, owner_tool=owner, selectable_only=True, projection_key=key) is None
    assert projection_calls == built_calls


def test_modify_idle_mouse_move_keeps_cursor_but_skips_heavy_snap_targets(monkeypatch) -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    _draw_rectangle(tool, ctx)

    calls = 0

    def forbidden_targets(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AssertionError("idle Modify hover must not rebuild/query drawing Smart Snap targets")

    monkeypatch.setattr(tool._services.snap_targets, "_live_snap_targets_and_near", forbidden_targets)
    handled = tool.on_event(
        ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(140.0, 130.0), button=MouseButton.NONE),
        ctx,
    )
    assert handled is False
    assert calls == 0
    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata.get("api_ui_visible") is True


def test_face_only_delete_skips_topology_compile_and_uses_two_history_clones(monkeypatch) -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    _draw_rectangle(tool, ctx)
    _native_click_face(tool, ctx)

    compile_calls = 0

    def forbidden_compile(*_args, **_kwargs):
        nonlocal compile_calls
        compile_calls += 1
        raise AssertionError("generated face deletion must not rebuild topology")

    monkeypatch.setattr(tool._services.sketch_sync, "_compile_and_sync_sketch", forbidden_compile)

    clone_calls = 0
    original_clone = SketchDocument.clone

    def counted_clone(self):
        nonlocal clone_calls
        clone_calls += 1
        return original_clone(self)

    monkeypatch.setattr(SketchDocument, "clone", counted_clone)
    assert tool._services.selection._delete_selected_points(ctx) is True
    assert compile_calls == 0
    # One detached BEFORE snapshot + one detached AFTER snapshot.  v177 took
    # four full sketch clones for the same history command.
    assert clone_calls == 2
    assert not tool._state.sketch.faces
    assert tool._state.sketch.suppressed_face_signatures


def test_sketch_clone_is_detached_without_generic_deepcopy_semantics() -> None:
    sketch = SketchDocument()
    p1 = sketch.add_point((0.0, 0.0), point_id="p1")
    p2 = sketch.add_point((10.0, 0.0), point_id="p2")
    p1.metadata["nested"] = {"value": [1, 2]}
    line = sketch.add_line("p1", "p2", line_id="l1")
    line.metadata["nested"] = {"value": [3, 4]}
    sketch.compile()

    clone = sketch.clone()
    assert clone == sketch
    assert clone is not sketch
    assert clone.points["p1"] is not sketch.points["p1"]
    assert clone.lines["l1"] is not sketch.lines["l1"]

    clone.move_point("p1", (7.0, 8.0))
    clone.points["p1"].metadata["nested"]["value"].append(99)
    clone.lines["l1"].metadata["nested"]["value"].append(88)
    assert sketch.points["p1"].position == (0.0, 0.0)
    assert sketch.points["p1"].metadata["nested"]["value"] == [1, 2]
    assert sketch.lines["l1"].metadata["nested"]["value"] == [3, 4]

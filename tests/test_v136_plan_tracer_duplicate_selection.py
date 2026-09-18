from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.prefabs import PlanTracePrefab, load_prefabs, save_prefab
from laserprog_studio.tooling.plan_trace_2d.selection_edit import SketchPayload
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _Scene:
    def pick_face_at(self, screen_pos, **_kwargs):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 0.0), object_id="ground", object_index=0)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _Scene()
    ctx.pick.bind_context(ctx)
    return ctx


def _open() -> tuple[PlanTrace2DCreatorTool, ToolContext]:
    tool = PlanTrace2DCreatorTool()
    ctx = _ctx()
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT), ctx)
    return tool, ctx


def _add_point(tool: PlanTrace2DCreatorTool, xy: tuple[float, float]):
    point_id = f"plan_trace:point:{tool._state.next_point_index:04d}"
    tool._state.next_point_index += 1
    return tool._state.sketch.add_point(xy, point_id=point_id)


def test_v136_safe_group_drag_detaches_unselected_incident_edge() -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (10.0, 0.0))
    p2 = _add_point(tool, (20.0, 0.0))
    selected_line = tool._state.sketch.add_line(p0.id, p1.id)
    untouched_line = tool._state.sketch.add_line(p1.id, p2.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    ctx.selection.select(tool._services.sketch_sync._line_actor_id(selected_line.id))
    tool._services.selection_edit.select_support_points(ctx)
    assert ctx.selection.begin_grab(p1.id, (10.0, 0.0), world_pos=(10.0, 0.0, 0.0))
    tool.on_native_interaction_result(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 0.0), button=MouseButton.LEFT),
        ctx,
        SimpleNamespace(action="grab", grabbed_ids=ctx.selection.state.grabbed_ids, hit=None),
    )

    detached_id = tool._state.sketch.lines[untouched_line.id].start_point_id
    assert detached_id != p1.id
    assert tool._state.sketch.points[detached_id].position == (10.0, 0.0)

    replacements = tool.resolve_drag_positions(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(80.0, 50.0)), ctx)
    assert replacements
    ctx.selection.move_actors_to(replacements)
    tool.on_native_interaction_result(
        ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(80.0, 50.0), button=MouseButton.LEFT),
        ctx,
        SimpleNamespace(action="release", grabbed_ids=ctx.selection.state.grabbed_ids, hit=None),
    )

    assert tool._state.sketch.points[p1.id].position != (10.0, 0.0)
    assert tool._state.sketch.points[detached_id].position == (10.0, 0.0)
    assert tool._state.sketch.lines[untouched_line.id].start_point_id == detached_id


def test_v136_copy_paste_face_recreates_closed_topology_and_selects_copy() -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (20.0, 0.0))
    p2 = _add_point(tool, (20.0, 10.0))
    p3 = _add_point(tool, (0.0, 10.0))
    tool._state.sketch.add_line(p0.id, p1.id)
    tool._state.sketch.add_line(p1.id, p2.id)
    tool._state.sketch.add_line(p2.id, p3.id)
    tool._state.sketch.add_line(p3.id, p0.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    assert len(tool._state.sketch.faces) == 1
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    face_actor = next(actor for actor in ctx.selection.actors(owner_tool=tool.id) if actor.metadata.get("plan_trace_role") == "face")
    ctx.selection.select(face_actor.id)

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="c", modifiers=frozenset({"ctrl"})), ctx)
    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="v", modifiers=frozenset({"ctrl"})), ctx)

    assert len(tool._state.sketch.faces) == 2
    selected_roles = [ctx.selection.actor(actor_id).metadata.get("plan_trace_role") for actor_id in ctx.selection.ids() if ctx.selection.actor(actor_id)]
    assert "point" in selected_roles
    assert "edge" in selected_roles


def test_v136_prefab_store_is_independent_json_library(tmp_path) -> None:
    path = tmp_path / "prefabs.json"
    payload = SketchPayload(
        points={"a": (-1.0, 0.0), "b": (1.0, 0.0)},
        lines=[{"start": "a", "end": "b", "metadata": {}}],
        pivot=(5.0, 7.0),
    )
    saved = save_prefab("My rail", payload, path=path)
    loaded = load_prefabs(path)

    assert saved.id == "user:my rail"
    assert len(loaded) == 1
    assert loaded[0].name == "My rail"
    assert loaded[0].payload.points == payload.points
    assert loaded[0].payload.pivot == (5.0, 7.0)


def test_v136_duplicate_places_prefab_along_selected_curve(monkeypatch) -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (100.0, 0.0))
    guide = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    prefab_payload = SketchPayload(
        points={"a": (0.0, -2.0), "b": (0.0, 2.0)},
        lines=[{"start": "a", "end": "b", "metadata": {}}],
        pivot=(0.0, 0.0),
    )
    prefab = PlanTracePrefab("user:tick", "Tick", prefab_payload)
    import laserprog_studio.tooling.plan_trace_2d.duplicate as duplicate_module
    monkeypatch.setattr(duplicate_module, "load_prefabs", lambda: (prefab,))

    service = tool._services.duplicate
    service.selected_prefab_id = prefab.id
    service.copy_count = 3
    service.follow_rotation = True
    service.stage = "edge"
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(guide.id))

    assert service._build_along_selected(ctx)
    duplicate_lines = [(line_id, line) for line_id, line in tool._state.sketch.lines.items() if line.metadata.get("generated_by") == "duplicate"]
    # The sketch compiler nodes each placed tick at its intersection with the
    # guide, so three logical prefab lines become six topological segments.
    assert len(duplicate_lines) == 6
    centers = []
    for line_id, line in duplicate_lines:
        a = tool._state.sketch.points[line.start_point_id].position
        b = tool._state.sketch.points[line.end_point_id].position
        centers.append(((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5))
    assert sorted(set(round(value[0], 3) for value in centers)) == [0.0, 50.0, 100.0]


def test_v136_face_drag_preserves_unselected_adjacent_face() -> None:
    tool, ctx = _open()
    points = [_add_point(tool, xy) for xy in ((0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (0.0, 10.0), (10.0, 10.0), (20.0, 10.0))]
    for start, end in ((0, 1), (1, 2), (3, 4), (4, 5), (0, 3), (1, 4), (2, 5)):
        tool._state.sketch.add_line(points[start].id, points[end].id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    assert len(tool._state.sketch.faces) == 2
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    left_face = min(tool._state.sketch.faces.values(), key=lambda face: sum(point[0] for point in face.polygon_points))
    actor = next(actor for actor in ctx.selection.actors(owner_tool=tool.id) if actor.metadata.get("plan_trace_sketch_face_id") == left_face.id)
    ctx.selection.select(actor.id)
    tool._services.selection_edit.select_support_points(ctx)
    assert ctx.selection.begin_grab(points[0].id, (0.0, 0.0), world_pos=(0.0, 0.0, 0.0))
    tool.on_native_interaction_result(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT),
        ctx,
        SimpleNamespace(action="grab", grabbed_ids=ctx.selection.state.grabbed_ids, hit=None),
    )
    assert tool._state.active_drag_detached_count == 2
    replacements = tool.resolve_drag_positions(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(50.0, 50.0)), ctx)
    ctx.selection.move_actors_to(replacements)
    tool.on_native_interaction_result(
        ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(50.0, 50.0), button=MouseButton.LEFT),
        ctx,
        SimpleNamespace(action="release", grabbed_ids=ctx.selection.state.grabbed_ids, hit=None),
    )
    assert len(tool._state.sketch.faces) == 2
    assert any(max(point[0] for point in face.polygon_points) <= 20.0 for face in tool._state.sketch.faces.values())
    assert any(min(point[0] for point in face.polygon_points) >= 40.0 for face in tool._state.sketch.faces.values())


def test_v136_duplicate_stitches_selected_curve_chain_independent_of_click_order(monkeypatch) -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (10.0, 0.0))
    p2 = _add_point(tool, (20.0, 0.0))
    first = tool._state.sketch.add_line(p0.id, p1.id)
    second = tool._state.sketch.add_line(p1.id, p2.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    # Reverse click order intentionally.
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(second.id))
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(first.id), replace=False)
    paths = tool._services.duplicate._curve_polylines(ctx)
    assert len(paths) == 1
    assert {paths[0][0], paths[0][-1]} == {(0.0, 0.0), (20.0, 0.0)}
    assert (10.0, 0.0) in paths[0]


def test_v136_face_fill_keeps_complete_prefab_inside_boundary(monkeypatch) -> None:
    tool, ctx = _open()
    points = [_add_point(tool, xy) for xy in ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))]
    for start, end in ((0, 1), (1, 2), (2, 3), (3, 0)):
        tool._state.sketch.add_line(points[start].id, points[end].id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    face_actor = next(actor for actor in ctx.selection.actors(owner_tool=tool.id) if actor.metadata.get("plan_trace_role") == "face")
    prefab_payload = SketchPayload(
        points={"a": (-4.0, 0.0), "b": (4.0, 0.0)},
        lines=[{"start": "a", "end": "b", "metadata": {}}],
        pivot=(0.0, 0.0),
    )
    prefab = PlanTracePrefab("user:wide", "Wide", prefab_payload)
    import laserprog_studio.tooling.plan_trace_2d.duplicate as duplicate_module
    monkeypatch.setattr(duplicate_module, "load_prefabs", lambda: (prefab,))
    service = tool._services.duplicate
    service.selected_prefab_id = prefab.id
    service.face_spacing = 20.0
    service.stage = "face"
    ctx.selection.select(face_actor.id)
    assert service._build_face_fill(ctx)
    generated = [line for line in tool._state.sketch.lines.values() if line.metadata.get("generated_by") == "duplicate"]
    assert generated
    for line in generated:
        for point_id in (line.start_point_id, line.end_point_id):
            x, y = tool._state.sketch.points[point_id].position
            assert -1.0e-8 <= x <= 10.0 + 1.0e-8
            assert -1.0e-8 <= y <= 10.0 + 1.0e-8


def test_v136_selected_edge_promotes_support_points_only_on_drag_press() -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (10.0, 0.0))
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    line_actor_id = tool._services.sketch_sync._line_actor_id(line.id)
    ctx.selection.select(line_actor_id)
    assert tuple(ctx.selection.ids()) == (line_actor_id,)
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT)
    assert tool.wants_native_actor_interaction(press, ctx)
    selected = set(ctx.selection.ids())
    assert line_actor_id in selected
    assert {p0.id, p1.id}.issubset(selected)


def test_v140_dragging_single_connected_point_deforms_incident_edges_without_cloning() -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (10.0, 0.0))
    p2 = _add_point(tool, (10.0, 10.0))
    line_a = tool._state.sketch.add_line(p0.id, p1.id)
    line_b = tool._state.sketch.add_line(p1.id, p2.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    original_point_ids = set(tool._state.sketch.points)
    ctx.selection.select(p1.id)
    assert ctx.selection.begin_grab(p1.id, (10.0, 0.0), world_pos=(10.0, 0.0, 0.0))
    tool.on_native_interaction_result(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 0.0), button=MouseButton.LEFT),
        ctx,
        SimpleNamespace(action="grab", grabbed_ids=ctx.selection.state.grabbed_ids, hit=None),
    )

    # A single selected point is a direct vertex edit. Its identity remains the
    # endpoint of every incident curve and no stationary clone is introduced.
    assert set(tool._state.sketch.points) == original_point_ids
    assert tool._state.sketch.lines[line_a.id].end_point_id == p1.id
    assert tool._state.sketch.lines[line_b.id].start_point_id == p1.id
    assert tool._state.active_drag_detached_count == 0

    replacements = tool.resolve_drag_positions(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(30.0, 20.0)), ctx)
    ctx.selection.move_actors_to(replacements)
    tool.on_native_interaction_result(
        ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(30.0, 20.0), button=MouseButton.LEFT),
        ctx,
        SimpleNamespace(action="release", grabbed_ids=ctx.selection.state.grabbed_ids, hit=None),
    )
    assert tool._state.sketch.points[p1.id].position != (10.0, 0.0)
    assert tool._state.sketch.lines[line_a.id].end_point_id == p1.id
    assert tool._state.sketch.lines[line_b.id].start_point_id == p1.id


def test_v136_group_drag_uses_physically_grabbed_point_as_smart_snap_pivot() -> None:
    tool, ctx = _open()
    p0 = _add_point(tool, (0.0, 0.0))
    p1 = _add_point(tool, (10.0, 0.0))
    line = tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(line.id))
    tool._services.selection_edit.select_support_points(ctx)
    assert ctx.selection.begin_grab(p0.id, (0.0, 0.0), world_pos=(0.0, 0.0, 0.0))
    grabbed = tuple(ctx.selection.state.grabbed_ids)
    assert tool._services.snap._drag_reference_point_id(ctx, grabbed) == p0.id

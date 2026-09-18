# -*- coding: utf-8 -*-
from __future__ import annotations

from math import pi

import pytest

from laserprog_studio.tool_api import ToolContext
from laserprog_studio.tool_api.plan2d.actors import register_plan_arc, register_plan_circle, register_plan_line
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_core.sketch import SketchDocument
from laserprog_studio.tool_core.sketch.compiler import SketchCompileOptions
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.selection_measure import measure_selected_path
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=0)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_selected_end_to_end_line_and_arc_report_exact_total() -> None:
    ctx = ToolContext()
    sketch = SketchDocument()
    p0 = sketch.add_point((0.0, 0.0))
    p1 = sketch.add_point((10.0, 0.0))
    p2 = sketch.add_point((20.0, 0.0))
    pc = sketch.add_point((15.0, 5.0))
    line = sketch.add_line(p0.id, p1.id)
    arc = sketch.add_arc(p1.id, p2.id, pc.id)
    line_actor = f"{TOOL_PLAN_TRACE}:line:{line.id}"
    arc_actor = f"{TOOL_PLAN_TRACE}:arc:{arc.id}"
    register_plan_line(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        line_id=line_actor,
        start_world_pos=(0.0, 0.0, 0.0),
        end_world_pos=(10.0, 0.0, 0.0),
        sketch_line_id=line.id,
    )
    register_plan_arc(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        arc_id=arc_actor,
        start_world_pos=(10.0, 0.0, 0.0),
        end_world_pos=(20.0, 0.0, 0.0),
        control_world_pos=(15.0, 5.0, 0.0),
        sketch_arc_id=arc.id,
    )
    ctx.selection.select(line_actor)
    ctx.selection.select(arc_actor, replace=False)

    measurement = measure_selected_path(ctx, sketch, owner_tool=TOOL_PLAN_TRACE)

    assert measurement is not None
    assert measurement.contiguous is True
    assert measurement.component_count == 1
    assert measurement.total_length == pytest.approx(10.0 + 5.0 * pi)
    assert "contiguous" in measurement.display_text()


def test_selected_circle_reports_exact_circumference_as_closed_path() -> None:
    ctx = ToolContext()
    sketch = SketchDocument()
    center = sketch.add_point((0.0, 0.0))
    radius_point = sketch.add_point((4.0, 0.0))
    circle = sketch.add_circle(center.id, radius_point.id)
    actor_id = f"{TOOL_PLAN_TRACE}:circle:{circle.id}"
    register_plan_circle(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        circle_id=actor_id,
        center_world_pos=(0.0, 0.0, 0.0),
        radius_world_pos=(4.0, 0.0, 0.0),
        sketch_circle_id=circle.id,
    )
    ctx.selection.select(actor_id)

    measurement = measure_selected_path(ctx, sketch, owner_tool=TOOL_PLAN_TRACE)

    assert measurement is not None
    assert measurement.total_length == pytest.approx(8.0 * pi)
    assert measurement.closed_components == 1
    assert "closed" in measurement.display_text()


def test_generated_face_id_stays_stable_across_unrelated_recompile() -> None:
    sketch = SketchDocument()
    p0 = sketch.add_point((0.0, 0.0))
    p1 = sketch.add_point((20.0, 0.0))
    p2 = sketch.add_point((20.0, 10.0))
    p3 = sketch.add_point((0.0, 10.0))
    for a, b in ((p0, p1), (p1, p2), (p2, p3), (p3, p0)):
        sketch.add_line(a.id, b.id)
    options = SketchCompileOptions(split_curve_intersections=False, split_curves_at_vertices=False)
    sketch.compile(options)
    first = {face.metadata["signature"]: face.id for face in sketch.faces.values()}
    assert first

    # A disconnected open line does not change the rectangle face signature.
    a = sketch.add_point((50.0, 50.0))
    b = sketch.add_point((60.0, 50.0))
    sketch.add_line(a.id, b.id)
    sketch.compile(options)
    second = {face.metadata["signature"]: face.id for face in sketch.faces.values()}

    for signature, face_id in first.items():
        assert second[signature] == face_id


def test_point_placement_does_not_run_topology_face_compiler() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "point", reason="test", render=False)
    ctx.profiler.reset()

    tool._services.sketch_sync._place_point(ctx, (10.0, 10.0, 7.75))
    tool._services.sketch_sync._place_point(ctx, (20.0, 10.0, 7.75))
    tool._services.sketch_sync._place_point(ctx, (30.0, 10.0, 7.75))

    assert len(tool._state.sketch.points) == 3
    assert ctx.profiler.values.get("plan_trace.sketch.compile_cache_misses", 0) == 0
    assert ctx.profiler.values.get("plan_trace.sketch.compile_cache_hits", 0) == 0


def test_completed_line_requests_exactly_one_compile() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    tool._services.drawing._handle_line_press(ctx, (10.0, 10.0, 7.75), base_snapshot=None)
    ctx.profiler.reset()

    tool._services.drawing._handle_line_press(ctx, (30.0, 10.0, 7.75), base_snapshot=None)

    assert len(tool._state.sketch.lines) == 1
    assert ctx.profiler.values.get("plan_trace.sketch.compile_cache_misses", 0) == 1
    assert ctx.profiler.values.get("plan_trace.sketch.compile_cache_hits", 0) == 0


def test_inspector_shows_total_selected_contiguous_length() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    sketch = tool._state.sketch
    p0 = sketch.add_point((0.0, 0.0), point_id="p0")
    p1 = sketch.add_point((10.0, 0.0), point_id="p1")
    p2 = sketch.add_point((10.0, 10.0), point_id="p2")
    sketch.add_line(p0.id, p1.id, line_id="l0")
    sketch.add_line(p1.id, p2.id, line_id="l1")
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    line_actor_ids = [
        actor.id
        for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE)
        if actor.metadata.get("plan_trace_role") == "edge"
    ]
    assert len(line_actor_ids) == 2
    ctx.selection.select(line_actor_ids[0])
    ctx.selection.select(line_actor_ids[1], replace=False)

    tool._services.overlay._sync_reports(ctx)

    assert ctx.inspector.value("plan_trace_2d.selection") == "2 edge(s)"
    measurement = measure_selected_path(ctx, tool._state.sketch, owner_tool=TOOL_PLAN_TRACE)
    assert measurement is not None
    assert ctx.inspector.value("plan_trace_2d.selection_length") == measurement.display_text()
    assert ctx.inspector.value("plan_trace_2d.selection_length") != "—"


def test_point_on_existing_line_still_runs_compile_and_splits_edge() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    sketch = tool._state.sketch
    p0 = sketch.add_point((0.0, 0.0), point_id="a")
    p1 = sketch.add_point((20.0, 0.0), point_id="b")
    sketch.add_line(p0.id, p1.id, line_id="base")
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    ctx.profiler.reset()

    tool._services.sketch_sync._place_point(ctx, (10.0, 0.0, 7.75))

    assert ctx.profiler.values.get("plan_trace.sketch.compile_cache_misses", 0) == 1
    assert len(sketch.lines) == 2


def test_unrelated_compile_keeps_unchanged_projected_face_primitive() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    sketch = tool._state.sketch
    p0 = sketch.add_point((0.0, 0.0), point_id="r0")
    p1 = sketch.add_point((20.0, 0.0), point_id="r1")
    p2 = sketch.add_point((20.0, 10.0), point_id="r2")
    p3 = sketch.add_point((0.0, 10.0), point_id="r3")
    for index, (a, b) in enumerate(((p0, p1), (p1, p2), (p2, p3), (p3, p0))):
        sketch.add_line(a.id, b.id, line_id=f"rect_{index}")
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    face = next(iter(sketch.faces.values()))
    actor_id = tool._services.sketch_sync._face_actor_id(face.id)
    registry = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE)
    primitive_before = registry.get(actor_id)
    assert primitive_before is not None

    a = sketch.add_point((50.0, 50.0), point_id="open_a")
    b = sketch.add_point((60.0, 50.0), point_id="open_b")
    sketch.add_line(a.id, b.id, line_id="open_line")
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)

    assert registry.get(actor_id) is primitive_before


def test_second_completed_line_dirties_only_new_point_and_edge() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    tool._services.drawing._handle_line_press(ctx, (10.0, 10.0, 7.75), base_snapshot=None)
    tool._services.drawing._handle_line_press(ctx, (30.0, 10.0, 7.75), base_snapshot=None)
    tool._services.drawing._handle_line_press(ctx, (30.0, 10.0, 7.75), base_snapshot=None)
    ctx.profiler.reset()
    tool._services.drawing._handle_line_press(ctx, (50.0, 10.0, 7.75), base_snapshot=None)

    assert len(tool._state.sketch.lines) == 2
    assert ctx.profiler.values.get("plan_trace.sketch.changed_actors", 0) == 2


def test_shift_click_polyline_segments_selects_edges_and_updates_length() -> None:
    """Regression: nearby endpoint handles must not steal exact edge clicks."""

    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "polyline", reason="test", render=False)
    for x, y in ((10.0, 10.0), (20.0, 10.0), (20.0, 20.0)):
        _click(tool, ctx, x, y)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    edge_actors = [
        actor
        for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE)
        if actor.metadata.get("plan_trace_role") == "edge"
    ]
    assert len(edge_actors) == 2
    for actor in edge_actors:
        start, end = actor.points[:2]
        screen_pos = (
            (float(start[0]) + float(end[0])) * 0.5,
            (float(start[1]) + float(end[1])) * 0.5,
        )
        assert tool.on_event(
            ToolEvent(
                ToolEventType.MOUSE_PRESS,
                screen_pos=screen_pos,
                button=MouseButton.LEFT,
                modifiers=frozenset({"shift"}),
            ),
            ctx,
        )

    selected = tuple(ctx.selection.actor(actor_id) for actor_id in ctx.selection.ids())
    assert all(actor is not None for actor in selected)
    assert [actor.metadata.get("plan_trace_role") for actor in selected] == ["edge", "edge"]
    assert ctx.inspector.value("plan_trace_2d.selection") == "2 edge(s)"
    measurement = measure_selected_path(ctx, tool._state.sketch, owner_tool=TOOL_PLAN_TRACE)
    assert measurement is not None
    assert ctx.inspector.value("plan_trace_2d.selection_length") == measurement.display_text()
    assert ctx.inspector.value("plan_trace_2d.selection_length") != "—"

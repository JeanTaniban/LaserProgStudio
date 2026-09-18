from __future__ import annotations

import math

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.mirror import MIRROR_WINDOW_ID
from laserprog_studio.tooling.plan_trace_2d.mirror_geometry import (
    ArcPrimitive,
    BezierPrimitive,
    CirclePrimitive,
    LinePrimitive,
    MirrorAxis,
    PointPrimitive,
    build_mirror_plan,
    sample_primitive,
)
from laserprog_studio.tooling.plan_trace_2d.mirror_state import MirrorStage
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
    return tool, ctx


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, xy: tuple[float, float]) -> bool:
    return tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_PRESS,
            screen_pos=xy,
            world_pos=(xy[0], xy[1], 0.0),
            button=MouseButton.LEFT,
        ),
        ctx,
    )


def _axis() -> MirrorAxis:
    return MirrorAxis((0.0, -100.0), (0.0, 100.0))


def _point_on_segment(point: tuple[float, float], a: tuple[float, float], b: tuple[float, float], tolerance: float = 1.0e-6) -> bool:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1.0e-20:
        return math.dist(point, a) <= tolerance
    t = ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq
    if t < -tolerance or t > 1.0 + tolerance:
        return False
    projection = (a[0] + t * dx, a[1] + t * dy)
    return math.dist(point, projection) <= tolerance


def test_v145_line_crossing_axis_is_split_and_each_half_is_reflected() -> None:
    source = LinePrimitive("line", (-4.0, -1.0), (2.0, 5.0))
    plan = build_mirror_plan((source,), _axis(), existing=(source,))

    assert plan.split_source_count == 1
    assert len(plan.additions) == 2
    assert all(isinstance(item, LinePrimitive) for item in plan.additions)
    # Both reflected pieces touch the exact original/axis intersection.
    assert all(any(abs(point[0]) <= 1.0e-8 for point in (item.start, item.end)) for item in plan.additions)
    # The resulting additions occupy both sides, making each side contain the
    # union of the original left/right shapes.
    mid_x = [0.5 * (item.start[0] + item.end[0]) for item in plan.additions]
    assert any(value < 0.0 for value in mid_x)
    assert any(value > 0.0 for value in mid_x)


def test_v145_arc_crossing_axis_is_split_into_exact_circular_subarcs() -> None:
    # Non-symmetric circular arc crossing the vertical axis.
    source = ArcPrimitive("arc", (-10.0, -2.0), (7.0, 6.0), (1.0, 13.0))
    plan = build_mirror_plan((source,), _axis(), existing=(source,))

    assert plan.split_source_count == 1
    assert len(plan.additions) == 2
    assert all(isinstance(item, ArcPrimitive) for item in plan.additions)
    for item in plan.additions:
        samples = sample_primitive(item, segments=24)
        # Recover the circle center from the three authored arc points.
        sx, sy = item.start
        ex, ey = item.end
        cx, cy = item.control
        det = 2.0 * (sx * (cy - ey) + cx * (ey - sy) + ex * (sy - cy))
        assert abs(det) > 1.0e-9
        s2 = sx * sx + sy * sy
        c2 = cx * cx + cy * cy
        e2 = ex * ex + ey * ey
        ox = (s2 * (cy - ey) + c2 * (ey - sy) + e2 * (sy - cy)) / det
        oy = (s2 * (ex - cx) + c2 * (sx - ex) + e2 * (cx - sx)) / det
        radii = [math.hypot(x - ox, y - oy) for x, y in samples]
        assert max(radii) - min(radii) < 1.0e-6



def test_v145_already_symmetric_arc_is_detected_without_duplicate_additions() -> None:
    source = ArcPrimitive("arc", (-10.0, 0.0), (10.0, 0.0), (0.0, 10.0))
    plan = build_mirror_plan((source,), _axis(), existing=(source,))

    assert plan.split_source_count == 1
    assert not plan.additions
    assert plan.skipped_duplicate_count == 2

def test_v145_bezier_can_be_split_at_multiple_axis_crossings() -> None:
    source = BezierPrimitive(
        "bezier",
        (-6.0, 0.0),
        (8.0, 5.0),
        (-8.0, 10.0),
        (6.0, 15.0),
    )
    plan = build_mirror_plan((source,), _axis(), existing=(source,))

    assert plan.split_source_count == 1
    assert len(plan.additions) >= 3
    assert all(isinstance(item, BezierPrimitive) for item in plan.additions)


def test_v145_self_symmetric_geometry_is_not_duplicated() -> None:
    axis = _axis()
    sources = (
        LinePrimitive("axis_line", (0.0, -5.0), (0.0, 5.0)),
        CirclePrimitive("centered_circle", (0.0, 0.0), (5.0, 0.0)),
        PointPrimitive("axis_point", (0.0, 3.0)),
    )
    plan = build_mirror_plan(sources, axis, existing=sources)

    assert not plan.additions
    assert plan.skipped_on_axis_count == 3


def test_v145_whole_sketch_mode_completes_both_sides_without_duplicate_existing_counterparts() -> None:
    axis = _axis()
    right = LinePrimitive("right", (4.0, 1.0), (8.0, 3.0))
    left_counterpart = LinePrimitive("left", (-4.0, 1.0), (-8.0, 3.0))
    unmatched_left = PointPrimitive("point", (-12.0, 7.0))
    sources = (right, left_counterpart, unmatched_left)
    plan = build_mirror_plan(sources, axis, existing=sources)

    assert len(plan.additions) == 1
    assert isinstance(plan.additions[0], PointPrimitive)
    assert plan.additions[0].point == (12.0, 7.0)
    assert plan.skipped_duplicate_count == 2


def test_v145_toolbar_mode_locks_selection_scope_and_shows_compact_overlay() -> None:
    tool, ctx = _open()
    p0 = tool._state.sketch.add_point((10.0, 0.0), point_id="p0")
    p1 = tool._state.sketch.add_point((20.0, 0.0), point_id="p1")
    line = tool._state.sketch.add_line(p0.id, p1.id)
    p2 = tool._state.sketch.add_point((30.0, 0.0), point_id="p2")
    p3 = tool._state.sketch.add_point((40.0, 0.0), point_id="p3")
    tool._state.sketch.add_line(p2.id, p3.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(line.id))

    tool._set_active_tool(ctx, "mirror", reason="test", render=False)

    service = tool._services.mirror
    assert service.uses_selection
    assert service.scope_selection is not None
    assert service.scope_selection.line_ids == frozenset((line.id,))
    window = ctx.overlay.window(MIRROR_WINDOW_ID)
    assert window is not None
    assert window.width_px <= 310
    assert window.fields[0].label == "Selected geometry"


def test_v145_two_axis_clicks_produce_preview_then_apply_adds_only_selected_geometry() -> None:
    tool, ctx = _open()
    a0 = tool._state.sketch.add_point((10.0, 0.0), point_id="a0")
    a1 = tool._state.sketch.add_point((20.0, 0.0), point_id="a1")
    selected_line = tool._state.sketch.add_line(a0.id, a1.id)
    b0 = tool._state.sketch.add_point((30.0, 10.0), point_id="b0")
    b1 = tool._state.sketch.add_point((40.0, 10.0), point_id="b1")
    tool._state.sketch.add_line(b0.id, b1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    ctx.selection.select(tool._services.sketch_sync._line_actor_id(selected_line.id))
    original_line_ids = set(tool._state.sketch.lines)
    original_positions = {key: value.position for key, value in tool._state.sketch.points.items()}

    tool._set_active_tool(ctx, "mirror", reason="test", render=False)
    assert _click(tool, ctx, (0.0, -50.0))
    assert tool._services.mirror.workflow.stage is MirrorStage.AXIS_END
    assert _click(tool, ctx, (0.0, 50.0))
    assert tool._services.mirror.workflow.stage is MirrorStage.PREVIEW
    assert tool._services.mirror.plan is not None
    assert tool._services.mirror.plan.addition_count == 1

    assert tool._services.mirror.apply(ctx)
    assert tool._state.active_tool == "modify"
    assert original_line_ids.issubset(tool._state.sketch.lines)
    assert all(tool._state.sketch.points[key].position == value for key, value in original_positions.items())
    assert len(tool._state.sketch.lines) == 3
    mirrored_line = next(value for key, value in tool._state.sketch.lines.items() if key not in original_line_ids)
    mirrored_positions = {
        tool._state.sketch.points[mirrored_line.start_point_id].position,
        tool._state.sketch.points[mirrored_line.end_point_id].position,
    }
    assert mirrored_positions == {(-10.0, 0.0), (-20.0, 0.0)}


def test_v145_no_selection_uses_whole_sketch_and_crossing_rectangle_regenerates_faces() -> None:
    tool, ctx = _open()
    points = [
        tool._state.sketch.add_point((-10.0, -5.0), point_id="r0"),
        tool._state.sketch.add_point((4.0, -5.0), point_id="r1"),
        tool._state.sketch.add_point((4.0, 5.0), point_id="r2"),
        tool._state.sketch.add_point((-10.0, 5.0), point_id="r3"),
    ]
    for start, end in zip(points, points[1:] + points[:1]):
        tool._state.sketch.add_line(start.id, end.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    assert len(tool._state.sketch.faces) == 1
    original_lines = set(tool._state.sketch.lines)

    tool._set_active_tool(ctx, "mirror", reason="test", render=False)
    assert not tool._services.mirror.uses_selection
    _click(tool, ctx, (0.0, -50.0))
    _click(tool, ctx, (0.0, 50.0))
    plan = tool._services.mirror.plan
    assert plan is not None
    assert plan.split_source_count == 2
    assert plan.addition_count >= 4
    assert tool._services.mirror.apply(ctx)

    # The topology compiler may subdivide an original edge at the newly added
    # axis vertex, but every source segment remains geometrically covered; the
    # Mirror command itself never removes or moves source geometry.
    current_segments = []
    for line in tool._state.sketch.lines.values():
        current_segments.append((
            tool._state.sketch.points[line.start_point_id].position,
            tool._state.sketch.points[line.end_point_id].position,
        ))
    for expected_a, expected_b in [
        ((-10.0, -5.0), (4.0, -5.0)),
        ((4.0, -5.0), (4.0, 5.0)),
        ((4.0, 5.0), (-10.0, 5.0)),
        ((-10.0, 5.0), (-10.0, -5.0)),
    ]:
        # Sample the source edge and ensure each point lies on at least one
        # current segment after normalization.
        for index in range(11):
            t = index / 10.0
            point = (
                expected_a[0] + (expected_b[0] - expected_a[0]) * t,
                expected_a[1] + (expected_b[1] - expected_a[1]) * t,
            )
            assert any(_point_on_segment(point, a, b) for a, b in current_segments)
    assert len(tool._state.sketch.faces) >= 2


def test_v145_failed_compile_rolls_back_the_entire_add_only_transaction(monkeypatch) -> None:
    tool, ctx = _open()
    p0 = tool._state.sketch.add_point((10.0, 0.0), point_id="p0")
    p1 = tool._state.sketch.add_point((20.0, 0.0), point_id="p1")
    tool._state.sketch.add_line(p0.id, p1.id)
    tool._services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
    before = tool._services.history._snapshot_state()

    tool._set_active_tool(ctx, "mirror", reason="test", render=False)
    _click(tool, ctx, (0.0, -50.0))
    _click(tool, ctx, (0.0, 50.0))
    assert tool._services.mirror.plan is not None

    original_compile = tool._services.sketch_sync._compile_and_sync_sketch
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic compiler rejection")
        return original_compile(*args, **kwargs)

    monkeypatch.setattr(tool._services.sketch_sync, "_compile_and_sync_sketch", fail_once)

    assert not tool._services.mirror.apply(ctx)
    assert tool._state.sketch == before.sketch
    assert tool._state.next_point_index == before.next_point_index
    assert tool._state.active_tool == "mirror"
    assert tool._services.mirror.workflow.stage is MirrorStage.PREVIEW


def test_v145_line_duplicate_lookup_is_indexed_not_quadratic(monkeypatch) -> None:
    from laserprog_studio.tooling.plan_trace_2d import mirror_geometry as kernel

    axis = _axis()
    sources = tuple(
        LinePrimitive(f"line_{index}", (10.0 + index * 3.0, 0.0), (11.0 + index * 3.0, 1.0))
        for index in range(400)
    )
    original = kernel._primitive_covers
    comparisons = 0

    def counted(existing, candidate, tolerance):
        nonlocal comparisons
        comparisons += 1
        return original(existing, candidate, tolerance)

    monkeypatch.setattr(kernel, "_primitive_covers", counted)
    plan = kernel.build_mirror_plan(sources, axis, existing=sources)

    assert len(plan.additions) == len(sources)
    # A full scan would perform roughly 160,000 comparisons. The analytic
    # supporting-line index should keep this near zero for disjoint mirrors.
    assert comparisons < 2_000

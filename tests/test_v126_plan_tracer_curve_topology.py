from __future__ import annotations

import math

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedActorKind, ProjectedLine
from laserprog_studio.tool_core.sketch import SketchCompileOptions, SketchDocument
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.editable_source import deserialize_sketch, serialize_sketch
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def _compile_live(sketch: SketchDocument) -> None:
    sketch.compile(
        SketchCompileOptions(
            split_curve_intersections=False,
            split_curves_at_vertices=False,
            solve_faces=True,
        )
    )


def test_line_endpoints_near_circle_are_noded_into_closed_face() -> None:
    sketch = SketchDocument()
    sketch.add_point((0.0, 0.0), point_id="center")
    sketch.add_point((10.0, 0.0), point_id="radius")
    sketch.add_circle("center", "radius", circle_id="circle")

    # The endpoints are deliberately 0.05 mm outside the analytic circle. This
    # reproduces the former sampled-arc snap gap while remaining visually joined.
    angle_a = math.radians(35.0)
    angle_b = math.radians(145.0)
    sketch.add_point((10.05 * math.cos(angle_a), 10.05 * math.sin(angle_a)), point_id="a")
    sketch.add_point((10.05 * math.cos(angle_b), 10.05 * math.sin(angle_b)), point_id="b")
    sketch.add_point((0.0, 18.0), point_id="apex")
    sketch.add_line("a", "apex", line_id="la")
    sketch.add_line("b", "apex", line_id="lb")

    original_a = sketch.points["a"].position
    original_b = sketch.points["b"].position
    _compile_live(sketch)

    assert sketch.points["a"].position == original_a
    assert sketch.points["b"].position == original_b
    assert any({"circle", "la", "lb"}.issubset(set(face.boundary_entity_ids)) for face in sketch.faces.values())


def test_line_endpoints_near_arc_are_noded_into_closed_face() -> None:
    sketch = SketchDocument()
    sketch.add_point((-10.0, 0.0), point_id="arc_start")
    sketch.add_point((10.0, 0.0), point_id="arc_end")
    sketch.add_point((0.0, 10.0), point_id="arc_control")
    sketch.add_arc("arc_start", "arc_end", "arc_control", arc_id="arc")

    # Small vertical offsets mimic line endpoints snapped to sampled arc chords.
    sketch.add_point((-10.0, 0.05), point_id="a")
    sketch.add_point((10.0, 0.05), point_id="b")
    sketch.add_point((0.0, -9.0), point_id="apex")
    sketch.add_line("a", "apex", line_id="la")
    sketch.add_line("b", "apex", line_id="lb")

    original_a = sketch.points["a"].position
    original_b = sketch.points["b"].position
    _compile_live(sketch)

    assert sketch.points["a"].position == original_a
    assert sketch.points["b"].position == original_b
    assert any({"arc", "la", "lb"}.issubset(set(face.boundary_entity_ids)) for face in sketch.faces.values())


def test_line_endpoints_near_arc_interior_are_noded_into_closed_face() -> None:
    sketch = SketchDocument()
    sketch.add_point((-10.0, 0.0), point_id="arc_start")
    sketch.add_point((10.0, 0.0), point_id="arc_end")
    sketch.add_point((0.0, 10.0), point_id="arc_control")
    sketch.add_arc("arc_start", "arc_end", "arc_control", arc_id="arc")

    # Contacts are in the middle of the arc, not at authored arc endpoints.
    radius = 10.05
    angle_a = math.radians(135.0)
    angle_b = math.radians(45.0)
    sketch.add_point((radius * math.cos(angle_a), radius * math.sin(angle_a)), point_id="a")
    sketch.add_point((radius * math.cos(angle_b), radius * math.sin(angle_b)), point_id="b")
    sketch.add_point((0.0, 0.0), point_id="apex")
    sketch.add_line("a", "apex", line_id="la")
    sketch.add_line("b", "apex", line_id="lb")

    _compile_live(sketch)

    assert any({"arc", "la", "lb"}.issubset(set(face.boundary_entity_ids)) for face in sketch.faces.values())


def test_line_endpoints_near_arc_ends_snap_to_finite_arc_not_infinite_circle() -> None:
    sketch = SketchDocument()
    sketch.add_point((-10.0, 0.0), point_id="arc_start")
    sketch.add_point((10.0, 0.0), point_id="arc_end")
    sketch.add_point((0.0, 10.0), point_id="arc_control")
    sketch.add_arc("arc_start", "arc_end", "arc_control", arc_id="arc")

    # Both points lie just beyond the arc sweep. Their nearest finite-arc points
    # are the authored endpoints, and the solver must close there.
    sketch.add_point((-10.0, -0.05), point_id="a")
    sketch.add_point((10.0, -0.05), point_id="b")
    sketch.add_point((0.0, -8.0), point_id="apex")
    sketch.add_line("a", "apex", line_id="la")
    sketch.add_line("b", "apex", line_id="lb")

    _compile_live(sketch)

    assert any({"arc", "la", "lb"}.issubset(set(face.boundary_entity_ids)) for face in sketch.faces.values())


def test_cubic_bezier_can_close_a_face_with_a_line() -> None:
    sketch = SketchDocument()
    sketch.add_point((0.0, 0.0), point_id="start")
    sketch.add_point((20.0, 0.0), point_id="end")
    sketch.add_point((2.0, 16.0), point_id="control_1")
    sketch.add_point((18.0, -6.0), point_id="control_2")
    sketch.add_bezier("start", "end", "control_1", "control_2", bezier_id="bezier")
    sketch.add_line("end", "start", line_id="chord")

    _compile_live(sketch)

    assert any({"bezier", "chord"}.issubset(set(face.boundary_entity_ids)) for face in sketch.faces.values())


def test_bezier_serialization_roundtrip_preserves_control_points() -> None:
    sketch = SketchDocument()
    for point_id, xy in {
        "start": (0.0, 0.0),
        "end": (20.0, 0.0),
        "control_1": (4.0, 12.0),
        "control_2": (16.0, -8.0),
    }.items():
        sketch.add_point(xy, point_id=point_id)
    curve = sketch.add_bezier("start", "end", "control_1", "control_2", bezier_id="curve")
    curve.metadata["label"] = "complex"

    restored = deserialize_sketch(serialize_sketch(sketch))

    assert set(restored.beziers) == {"curve"}
    restored_curve = restored.beziers["curve"]
    assert restored_curve.start_point_id == "start"
    assert restored_curve.end_point_id == "end"
    assert restored_curve.control_1_point_id == "control_1"
    assert restored_curve.control_2_point_id == "control_2"
    assert restored_curve.metadata["label"] == "complex"


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


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_plan_tracer_bezier_mode_creates_selectable_complex_curve_from_four_clicks() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    _click(tool, ctx, 1.0, 2.0)
    tool._set_active_tool(ctx, "bezier", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 220.0, 100.0)
    _click(tool, ctx, 130.0, 180.0)
    _click(tool, ctx, 190.0, 20.0)

    assert tool._state.pending_bezier_start_id is None
    assert tool._state.pending_bezier_end_id is None
    assert tool._state.pending_bezier_control_1_id is None
    assert len(tool._state.sketch.beziers) == 1
    actors = [
        actor
        for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE)
        if actor.metadata.get("plan_trace_sketch_bezier_id")
    ]
    assert len(actors) == 1
    curve_id = actors[0].metadata["plan_trace_sketch_bezier_id"]
    assert curve_id in tool._state.sketch.beziers
    assert actors[0].metadata.get("curve_type") == "bezier"
    assert any(
        isinstance(item, ProjectedLine)
        and item.actor_kind == ProjectedActorKind.ARC
        and dict(item.metadata).get("plan_trace_sketch_bezier_id") == curve_id
        for item in ctx.projected_drawing.snapshot(TOOL_PLAN_TRACE).primitives
    )


def test_bezier_selection_reports_curve_length() -> None:
    from laserprog_studio.tooling.plan_trace_2d.selection_measure import measure_selected_path

    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    _click(tool, ctx, 1.0, 2.0)
    tool._set_active_tool(ctx, "bezier", reason="test", render=False)
    for x, y in ((100.0, 100.0), (220.0, 100.0), (125.0, 180.0), (195.0, 20.0)):
        _click(tool, ctx, x, y)

    actor = next(
        actor
        for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE)
        if actor.metadata.get("plan_trace_sketch_bezier_id")
    )
    ctx.selection.select(actor.id)
    measurement = measure_selected_path(ctx, tool._state.sketch, owner_tool=TOOL_PLAN_TRACE)

    assert measurement is not None
    assert measurement.entity_count == 1
    assert measurement.component_count == 1
    assert measurement.total_length > 120.0


def test_exact_arc_snap_has_priority_over_display_segments() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    _click(tool, ctx, 1.0, 2.0)
    tool._set_active_tool(ctx, "arc", reason="test", render=False)
    for x, y in ((100.0, 100.0), (220.0, 100.0), (160.0, 180.0)):
        _click(tool, ctx, x, y)

    targets = tool._services.snap_targets._build_live_snap_targets(ctx)
    exact = [target for target in targets if bool(getattr(target, "is_arc", False))]
    sampled = [target for target in targets if str(getattr(target, "id", "")).find(":seg:") >= 0]

    assert exact and sampled
    assert min(int(target.priority) for target in exact) > max(int(target.priority) for target in sampled)


def test_editable_source_deserialization_does_not_split_authored_arc_topology() -> None:
    """Reopening/cancelling a Plan Tracer source must not grow its sketch graph."""

    sketch = SketchDocument()
    sketch.add_point((0.0, 0.0), point_id="s")
    sketch.add_point((10.0, 0.0), point_id="e")
    sketch.add_point((5.0, 5.0), point_id="c")
    # This point lies analytically on the arc.  The Sketch kernel's default
    # compile policy intentionally splits an arc at such vertices, whereas the
    # live Plan Tracer policy keeps authored curves stable.
    sketch.add_point((8.5355339059, 3.5355339059), point_id="p_on_arc")
    sketch.add_arc("s", "e", "c", arc_id="arc")

    payload = serialize_sketch(sketch)
    expected_counts = (len(sketch.points), len(sketch.lines), len(sketch.arcs), len(sketch.circles), len(sketch.beziers))

    for _ in range(5):
        restored = deserialize_sketch(payload)
        assert (len(restored.points), len(restored.lines), len(restored.arcs), len(restored.circles), len(restored.beziers)) == expected_counts
        assert set(restored.arcs) == {"arc"}
        payload = serialize_sketch(restored)

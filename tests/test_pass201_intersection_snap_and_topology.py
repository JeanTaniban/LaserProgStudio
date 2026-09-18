from __future__ import annotations

from laserprog_studio.tool_api import snap
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.sketch import SketchDocument
from laserprog_studio.tool_core.snap import SnapKind, SnapSource
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


def test_snap_manager_returns_semantic_line_line_intersection() -> None:
    ctx = ToolContext()
    result = ctx.snap.smart(
        (5.0, 5.0, 0.0),
        (5.0, 5.0),
        ctx,
        extra_targets=[
            snap.segment("edge.a", (0.0, 0.0, 0.0), (10.0, 10.0, 0.0), source=SnapSource.CUSTOM_EDGE, priority=70),
            snap.segment("edge.b", (0.0, 10.0, 0.0), (10.0, 0.0, 0.0), source=SnapSource.CUSTOM_EDGE, priority=70),
        ],
    )

    assert result.snapped is True
    assert result.kind == SnapKind.INTERSECTION
    assert result.source == SnapSource.INTERSECTION
    assert result.label == "Intersection"
    assert result.position == (5.0, 5.0, 0.0)


def test_sketch_compiler_splits_crossing_lines_with_generated_intersection_vertex() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b = sketch.add_point((10.0, 10.0), point_id="b")
    c = sketch.add_point((0.0, 10.0), point_id="c")
    d = sketch.add_point((10.0, 0.0), point_id="d")
    sketch.add_line(a.id, b.id, line_id="ab")
    sketch.add_line(c.id, d.id, line_id="cd")

    report = sketch.compile()

    generated = [point for point in sketch.points.values() if point.metadata.get("generated_by") == "line_intersection"]
    assert report.intersection_points == 1
    assert len(generated) == 1
    assert generated[0].position == (5.0, 5.0)
    assert len(sketch.lines) == 4
    assert all(generated[0].id in {line.start_point_id, line.end_point_id} for line in sketch.lines.values())


def test_plan_tracer_cursor_uses_intersection_snap_style() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    # First diagonal.
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(100.0, 100.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(200.0, 200.0), button=MouseButton.LEFT), ctx)
    # Second diagonal, crossing the first one. The compiler creates the real
    # topology vertex, and the snap API exposes it as a semantic intersection.
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(100.0, 200.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(200.0, 100.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(150.0, 150.0)), ctx)

    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["snap_kind"] == SnapKind.VERTEX.value
    assert cursor.metadata["snap_label"] == "Vertex"
    assert cursor.points[0][:2] == (150.0, 150.0)

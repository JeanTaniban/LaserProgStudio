from __future__ import annotations

from laserprog_studio.tool_api import dimensions as dimension_api
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.dimensions import DimensionKind
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedText
from laserprog_studio.tool_core.sketch import SketchDocument
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
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float, *modifiers: str) -> None:
    assert tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_PRESS,
            screen_pos=(x, y),
            button=MouseButton.LEFT,
            modifiers=frozenset(modifiers),
        ),
        ctx,
    )


def test_dimension_api_measures_angle_between_two_lines() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b = sketch.add_point((10.0, 0.0), point_id="b")
    c = sketch.add_point((0.0, 10.0), point_id="c")
    first = sketch.add_line(a.id, b.id, line_id="x")
    second = sketch.add_line(a.id, c.id, line_id="y")

    dimension = dimension_api.add_dimension(sketch, dimension_api.DimensionSpec.angle(first.id, second.id, offset=16.0))
    measurement = dimension_api.measure_dimension(sketch, dimension)
    layout = dimension_api.layout_dimension(sketch, dimension)

    assert measurement.valid is True
    assert measurement.label == "90.0°"
    assert layout.valid is True
    assert layout.metadata["layout_kind"] == "angle"
    assert layout.label == "90.0°"


def test_dimension_tool_clicking_edge_creates_edge_length_dimension() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    a = tool._state.sketch.add_point((0.0, 0.0), point_id="a")
    b = tool._state.sketch.add_point((30.0, 0.0), point_id="b")
    line = tool._state.sketch.add_line(a.id, b.id, line_id="l_edge")
    tool._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "dimension", reason="test", render=False)

    _click(tool, ctx, 15.0, 0.0)

    assert len(tool._state.sketch.dimensions) == 1
    dimension = next(iter(tool._state.sketch.dimensions.values()))
    assert dimension.kind == DimensionKind.EDGE_LENGTH
    assert dimension.references[0].id == line.id
    text_items = [item for item in ctx.projected_drawing.snapshot(tool.id).primitives if isinstance(item, ProjectedText)]
    assert any("30 mm" in item.text for item in text_items)
    assert ctx.preview.items(owner_tool=tool.id) == ()


def test_dimension_tool_alt_clicking_circle_creates_radius_dimension() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    center = tool._state.sketch.add_point((0.0, 0.0), point_id="center")
    radius = tool._state.sketch.add_point((10.0, 0.0), point_id="radius")
    circle = tool._state.sketch.add_circle(center.id, radius.id, circle_id="circle")
    tool._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "dimension", reason="test", render=False)

    _click(tool, ctx, 0.0, 10.0, "alt")

    assert len(tool._state.sketch.dimensions) == 1
    dimension = next(iter(tool._state.sketch.dimensions.values()))
    assert dimension.kind == DimensionKind.RADIUS
    assert dimension.references[0].id == circle.id
    measurement = dimension_api.measure_dimension(tool._state.sketch, dimension)
    assert measurement.label == "R 10 mm"


def test_dimension_tool_shift_clicking_two_edges_creates_angle_dimension() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    origin = tool._state.sketch.add_point((0.0, 0.0), point_id="o")
    x = tool._state.sketch.add_point((20.0, 0.0), point_id="x")
    y = tool._state.sketch.add_point((0.0, 20.0), point_id="y")
    first = tool._state.sketch.add_line(origin.id, x.id, line_id="lx")
    second = tool._state.sketch.add_line(origin.id, y.id, line_id="ly")
    tool._compile_and_sync_sketch(ctx, render=False)
    tool._set_active_tool(ctx, "dimension", reason="test", render=False)

    _click(tool, ctx, 10.0, 0.0, "shift")
    assert tool._state.pending_dimension_line_id == first.id
    _click(tool, ctx, 0.0, 10.0, "shift")

    assert tool._state.pending_dimension_line_id is None
    assert len(tool._state.sketch.dimensions) == 1
    dimension = next(iter(tool._state.sketch.dimensions.values()))
    assert dimension.kind == DimensionKind.ANGLE
    assert {ref.id for ref in dimension.references} == {first.id, second.id}
    assert dimension_api.measure_dimension(tool._state.sketch, dimension).label == "90.0°"

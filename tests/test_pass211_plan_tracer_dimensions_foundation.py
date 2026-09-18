from __future__ import annotations

from laserprog_studio.tool_api import dimensions as dimension_api
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
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


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_dimension_api_measures_aligned_distance_without_ui_dependencies() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b = sketch.add_point((3.0, 4.0), point_id="b")

    dimension = dimension_api.add_dimension(sketch, dimension_api.DimensionSpec.aligned_distance(a.id, b.id, offset=12.0))
    measurement = dimension_api.measure_dimension(sketch, dimension)
    layout = dimension_api.layout_dimension(sketch, dimension)

    assert measurement.valid is True
    assert measurement.value == 5.0
    assert measurement.label == "5 mm"
    assert layout.valid is True
    assert layout.label == "5 mm"
    assert layout.dimension_line[0] != a.position
    assert layout.witness_lines[0][0] == a.position


def test_sketch_deleting_referenced_point_removes_dependent_dimensions() -> None:
    sketch = SketchDocument()
    a = sketch.add_point((0.0, 0.0), point_id="a")
    b = sketch.add_point((10.0, 0.0), point_id="b")
    dimension_api.add_dimension(sketch, dimension_api.DimensionSpec.aligned_distance(a.id, b.id))

    assert len(sketch.dimensions) == 1
    sketch.delete_point_cascade(a.id, compile_after=False)

    assert len(sketch.dimensions) == 0


def test_plan_tracer_dimension_tool_creates_selectable_passive_dimension() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "dimension", reason="test", render=False)

    _click(tool, ctx, 10.0, 10.0)
    assert tool._state.pending_dimension_start_id is not None
    _click(tool, ctx, 40.0, 10.0)

    assert tool._state.pending_dimension_start_id is None
    assert len(tool._state.sketch.dimensions) == 1
    actor = next(actor for actor in ctx.selection.actors(owner_tool=tool.id) if actor.metadata.get("plan_trace_role") == "dimension")
    assert actor.selectable is True
    assert actor.metadata.get("plan_trace_sketch_dimension_id") in tool._state.sketch.dimensions
    text_items = [item for item in ctx.projected_drawing.snapshot(tool.id).primitives if isinstance(item, ProjectedText)]
    assert any("mm" in item.text for item in text_items)
    assert ctx.preview.items(owner_tool=tool.id) == ()


def test_plan_tracer_dimension_can_be_deleted_and_undone() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "dimension", reason="test", render=False)
    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 20.0, 0.0)
    actor = next(actor for actor in ctx.selection.actors(owner_tool=tool.id) if actor.metadata.get("plan_trace_role") == "dimension")

    ctx.selection.select(actor.id)
    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Delete"), ctx) is True
    assert len(tool._state.sketch.dimensions) == 0

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="z", modifiers=frozenset({"ctrl"})), ctx) is True
    assert len(tool._state.sketch.dimensions) == 1

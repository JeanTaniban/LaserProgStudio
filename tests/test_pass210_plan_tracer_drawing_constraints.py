from __future__ import annotations

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.planar_tools import FixedPlanarView, make_locked_plane
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


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float, *, shift: bool = False) -> None:
    modifiers = frozenset({"shift"}) if shift else frozenset()
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT, modifiers=modifiers), ctx)


def test_planar_api_angle_constraint_uses_locked_plane_basis() -> None:
    plane = make_locked_plane(FixedPlanarView.TOP, depth=3.0)

    result = plan2d.constrain_angle_step_on_plan(plane, (0.0, 0.0, 3.0), (10.0, 2.0, 3.0), angle_step_degrees=45.0)

    assert result.applied is True
    assert result.kind == "angle_step"
    assert abs(result.world_pos[1]) < 1.0e-6
    assert result.label == "Angle 45°"


def test_plan_tracer_shift_line_constrains_end_to_nearest_45_degree_direction() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 200.0, 120.0, shift=True)

    assert len(tool._state.sketch.lines) == 1
    line = next(iter(tool._state.sketch.lines.values()))
    start = tool._state.sketch.points[line.start_point_id].position
    end = tool._state.sketch.points[line.end_point_id].position
    assert abs(start[1] - end[1]) < 1.0e-6
    assert tool._state.last_constraint_label == "Angle 45°"


def test_plan_tracer_shift_rectangle_creates_square_from_first_corner() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)

    _click(tool, ctx, 10.0, 10.0)
    _click(tool, ctx, 60.0, 40.0, shift=True)

    xs = [point.position[0] for point in tool._state.sketch.points.values()]
    ys = [point.position[1] for point in tool._state.sketch.points.values()]
    width = max(xs) - min(xs)
    height = max(ys) - min(ys)
    assert abs(width - height) < 1.0e-6
    assert width > 0.0
    assert len(tool._state.sketch.lines) == 4
    assert len(tool._state.sketch.faces) == 1
    assert tool._state.last_constraint_label == "Square"

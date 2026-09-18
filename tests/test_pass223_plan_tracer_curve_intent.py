from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.plan_trace_2d.curve_intent import ArcIntent, arc_control_from_intent, signed_side
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool

ROOT = Path(__file__).resolve().parents[1]
PLAN_TRACE = ROOT / "src" / "laserprog_studio" / "tooling" / "plan_trace_2d"


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=1)


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


def test_curve_intent_model_separates_arc_side_and_major_sweep_policy() -> None:
    control = arc_control_from_intent((0.0, 0.0), (10.0, 0.0), side=1.0, angle_degrees=270.0, major=True)

    assert control is not None
    assert signed_side((0.0, 0.0), (10.0, 0.0), control) > 0.0
    intent = ArcIntent.from_points((0.0, 0.0), (10.0, 0.0), control)
    assert intent.major is True
    assert round(intent.sweep_degrees, 6) == 270.0


def test_plan_tracer_arc_metric_rebuild_preserves_major_side_intent() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "arc", reason="test", render=False)

    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 200.0, 100.0)
    _click(tool, ctx, 150.0, 120.0)

    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.arc_intent is not None
    assert tool._state.metric_draft.arc_intent.major is False

    assert tool.apply_metric_value(ctx, "angle", "270 deg") is True
    assert tool._state.metric_draft is not None
    assert tool._state.metric_draft.arc_intent is not None
    assert tool._state.metric_draft.arc_intent.major is True
    assert signed_side(tool._state.metric_draft.start_xy, tool._state.metric_draft.end_xy, tool._state.metric_draft.control_xy) > 0.0

    arc = next(iter(tool._state.sketch.arcs.values()))
    assert arc.metadata.get("curve_intent") == "arc"
    assert arc.metadata.get("curve_major") is True
    assert arc.metadata.get("curve_side") == "left"


def test_curve_intent_split_is_not_hidden_inside_drawing_or_metric_rebuilders() -> None:
    drawing = (PLAN_TRACE / "drawing.py").read_text(encoding="utf-8")
    rebuilders = (PLAN_TRACE / "metric_rebuilders.py").read_text(encoding="utf-8")
    intent = (PLAN_TRACE / "curve_intent.py").read_text(encoding="utf-8")

    assert "class ArcIntent" in intent
    assert "class HalfCircleIntent" in intent
    assert "arc_control_from_intent" in rebuilders
    assert "curve_intent_metadata" in drawing
    assert "math.sqrt" not in drawing
    assert "sagitta" not in rebuilders

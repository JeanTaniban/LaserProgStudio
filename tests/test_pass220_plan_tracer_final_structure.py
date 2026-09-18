from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import plan2d
from laserprog_studio.tool_api.surface import supported_import_paths, public_api_summary
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
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


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float, *, shift: bool = False) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT, modifiers=frozenset({"shift"} if shift else ())), ctx)


def test_public_surface_lists_plan2d_as_active_public_api_and_aliases_as_supported() -> None:
    summary = public_api_summary()
    assert summary["active_domains"] == 8
    active_imports = set(summary["active_import_paths"])
    assert "laserprog_studio.tool_api.plan2d" in active_imports
    assert "laserprog_studio.tool_api.planar_drawing" not in active_imports
    assert "laserprog_studio.tool_api.dimensions" not in active_imports
    assert "laserprog_studio.tool_api.metrics" not in active_imports
    supported_imports = set(supported_import_paths())
    assert "laserprog_studio.tool_api.planar_drawing" in supported_imports
    assert "laserprog_studio.tool_api.dimensions" in supported_imports
    assert "laserprog_studio.tool_api.metrics" in supported_imports
    names = {domain["name"] for domain in summary["domains"] if domain["status"] == "active"}
    assert "Plan 2D" in names


def test_plan_tracer_ui_service_uses_public_visual_api_not_overlay_core() -> None:
    overlay_source = (PLAN_TRACE / "overlay.py").read_text(encoding="utf-8")
    assert "from laserprog_studio.tool_api.visual import" in overlay_source
    assert "tool_core.overlay" not in overlay_source
    assert "PySide6" not in overlay_source
    assert "QWidget" not in overlay_source


def test_plan_coordinate_facades_round_trip_locked_plane() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    assert tool._state.plane is not None

    world = plan2d.plan_xy_to_world(tool._state.plane, (12.5, -4.0))
    xy = plan2d.world_to_plan_xy(tool._state.plane, world)
    assert tuple(round(v, 6) for v in xy) == (12.5, -4.0)


def test_state_machine_clears_pending_shape_state_on_mode_switch_and_escape() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(tool, ctx, 0.0, 0.0)
    assert tool._state.pending_line_start_id is not None

    tool.on_overlay_button_clicked("plan_trace_2d.tool.rectangle", ctx)
    assert tool._state.active_tool == "rectangle"
    assert tool._state.pending_line_start_id is None
    assert tool._state_invariant_issues() == ()

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Escape"), ctx) is True
    assert tool._state.active_tool == "modify"
    assert tool._state.pending_rectangle_corner_id is None
    assert tool._state_invariant_issues() == ()


def test_metric_invalid_geometry_rolls_back_session_and_sketch() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)

    _click(tool, ctx, 0.0, 0.0)
    _click(tool, ctx, 20.0, 0.0)
    assert tool._state.metric_draft is not None
    previous_length = tool._state.metric_draft.session.as_values()["length"]
    assert previous_length > 1.0
    before_points = {pid: tuple(point.position) for pid, point in tool._state.sketch.points.items()}
    before_lines = tuple(sorted((line.start_point_id, line.end_point_id) for line in tool._state.sketch.lines.values()))

    assert tool.apply_metric_value(ctx, "length", "0 mm") is False
    assert tool._state.metric_draft is not None
    assert round(tool._state.metric_draft.session.as_values()["length"], 6) == round(previous_length, 6)
    after_points = {pid: tuple(point.position) for pid, point in tool._state.sketch.points.items()}
    after_lines = tuple(sorted((line.start_point_id, line.end_point_id) for line in tool._state.sketch.lines.values()))
    assert after_points == before_points
    assert after_lines == before_lines
    assert ctx.overlay.window("plan_trace_2d.metric_overlay") is not None
    assert ctx.overlay.window("plan_trace_2d.metric_overlay").visible is True  # type: ignore[union-attr]

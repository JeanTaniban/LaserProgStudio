from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.projected_drawing import ProjectedHandle
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec


class _FaceScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 7.0),
            object_id="part_a",
            object_index=3,
            normal=(0.0, 0.0, 1.0),
        )


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _FaceScene()
    ctx.pick.bind_context(ctx)
    return ctx


def test_planar_drawing_api_picks_locked_height_from_scene_face() -> None:
    ctx = _ctx()
    picked = plan2d.pick_plan_height(ctx, (10.0, 20.0))
    assert picked.object_id == "part_a"
    assert picked.hit_kind == "face"
    assert picked.plane.view.value == "top"
    assert picked.plane.depth == 7.0
    assert picked.world_pos == (10.0, 20.0, 7.0)


def test_plan_trace_registry_uses_new_creator_runtime_not_legacy_hooks() -> None:
    spec = get_tool_spec(TOOL_PLAN_TRACE)
    runtime = get_studio_tool(TOOL_PLAN_TRACE)
    assert spec is not None
    assert spec.open_hook is None
    assert spec.close_hook is None
    assert type(runtime).__name__ == "PlanTrace2DTool"


def test_plan_trace_first_pass_locks_plane_and_places_minimal_dot_point() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)

    assert ctx.overlay.window("plan_trace_2d.anchor_prompt") is not None
    assert ctx.overlay.window("plan_trace_2d.toolbox") is None or not ctx.overlay.window("plan_trace_2d.toolbox").visible

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(1.0, 2.0), world_pos=(1.0, 2.0, 7.0)), ctx)
    assert not any(actor.metadata.get("plan_trace_role") == "cursor" for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE))

    tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_PRESS,
            screen_pos=(1.0, 2.0),
            world_pos=(1.0, 2.0, 7.0),
            button=MouseButton.LEFT,
        ),
        ctx,
    )
    assert tool._state.plane is not None
    assert tool._state.display_plane is not None
    assert tool._state.phase == "draw"
    assert ctx.overlay.window("plan_trace_2d.toolbox") is not None
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.point"

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(30.0, 40.0), world_pos=(30.0, 40.0, 7.0)), ctx)
    tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_PRESS,
            screen_pos=(30.0, 40.0),
            world_pos=(30.0, 40.0, 7.0),
            button=MouseButton.LEFT,
        ),
        ctx,
    )

    point_actors = [actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point"]
    assert len(point_actors) == 1
    assert point_actors[0].metadata["point_style"] == "minimal"
    assert point_actors[0].points[0] == (30.0, 40.0, 7.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert point_actors[0].metadata["plan_trace_semantic_world_pos"] == (30.0, 40.0, 7.0)
    point_handle = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(point_actors[0].id)
    cursor_handle = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE).get(f"{TOOL_PLAN_TRACE}:cursor")
    assert isinstance(point_handle, ProjectedHandle) and point_handle.shape.value == "minimal"
    assert isinstance(cursor_handle, ProjectedHandle) and cursor_handle.shape.value == "diamond"
    assert ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE) == ()


def test_escape_keeps_plan_trace_open_and_current_mode_cursor_visible() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), world_pos=(1.0, 2.0, 7.0), button=MouseButton.LEFT),
        ctx,
    )
    tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="escape"), ctx)

    assert tool._state.active_tool == "modify"
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.modify"
    cursor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:cursor")
    assert cursor is not None
    assert cursor.metadata["api_ui_visible"] is True


def test_overlay_buttons_are_real_exclusive_tool_palette_buttons() -> None:
    source = read_qt_overlay_runtime_source()
    manager_source = Path("src/laserprog_studio/tool_core/overlay/manager.py").read_text(encoding="utf-8")
    assert "button.setCheckable" in source
    assert "button.setChecked" in source
    assert "_overlay_button_clicked" in source
    assert "self.set_group_active(button.group, button_id)" in manager_source


def test_plan_tracer_docs_explain_api_owned_styles_snap_and_point_only_first_pass() -> None:
    doc = Path("docs/tool_creator/17_plan_tracer_2d.md").read_text(encoding="utf-8")
    direction = Path("docs/tool_creator/00_creator_ui_direction.md").read_text(encoding="utf-8")
    assert "Plan tracer 2D" in doc
    assert "diamond" in doc
    assert "minimal dot" in doc
    assert "Point placement only" in doc
    assert "tool_api.plan2d" in doc
    assert "plan2d" in direction

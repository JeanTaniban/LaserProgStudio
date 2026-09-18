from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_api import planar_drawing as plan2d
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _NoHitScene:
    def pick_face_at(self, screen_pos, **_filters):
        return PickResult.none(screen_pos)

    def pick_object_at(self, screen_pos, **_filters):
        return PickResult.none(screen_pos)


class _HitScene:
    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult(
            "face",
            screen_pos=screen_pos,
            world_pos=(float(x), float(y), 12.0),
            object_id="face_12",
            object_index=2,
        )


def _ctx(scene) -> ToolContext:
    ctx = ToolContext()
    ctx.scene = scene
    ctx.pick.bind_context(ctx)
    return ctx


def test_opening_overlay_is_anchor_prompt_only_then_toolbox_replaces_it_after_raycast() -> None:
    ctx = _ctx(_HitScene())
    tool = PlanTrace2DCreatorTool()

    tool.on_open(ctx)

    prompt = ctx.overlay.window("plan_trace_2d.anchor_prompt")
    assert prompt is not None and prompt.visible
    assert prompt.buttons == []
    assert not ctx.overlay.button("plan_trace_2d.tool.point")

    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(4.0, 5.0), world_pos=(99.0, 99.0, 99.0), button=MouseButton.LEFT), ctx)

    assert ctx.overlay.window("plan_trace_2d.anchor_prompt").visible is False
    toolbox = ctx.overlay.window("plan_trace_2d.toolbox")
    assert toolbox is not None and toolbox.visible
    assert ctx.overlay.group_active["plan_trace_2d.tool"] == "plan_trace_2d.tool.point"
    assert sum(1 for button in ctx.overlay.buttons.values() if button.group == "plan_trace_2d.tool" and button.checked) == 1


def test_anchor_depth_uses_raycast_hit_not_event_world_position() -> None:
    ctx = _ctx(_HitScene())
    picked = plan2d.pick_plan_anchor_by_raycast(ctx, (4.0, 5.0), view="top")

    assert picked.hit is True
    assert picked.object_id == "face_12"
    assert picked.plane.depth == 12.0
    assert picked.display_plane.depth == 12.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET
    assert picked.anchor_world == (4.0, 5.0, 12.0)
    assert picked.display_world == (4.0, 5.0, 12.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)


def test_plan_tracer_uses_ground_origin_when_raycast_misses_even_if_event_world_exists() -> None:
    ctx = _ctx(_NoHitScene())
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)

    tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_PRESS,
            screen_pos=(8.0, 9.0),
            world_pos=(8.0, 9.0, 123.0),
            button=MouseButton.LEFT,
        ),
        ctx,
    )

    assert tool._state.plane is not None
    assert tool._state.plane.normal == (0.0, 0.0, 1.0)
    assert tool._state.plane.depth == 0.0
    assert tool._state.phase == "draw"
    assert tool._state.anchor_world == (0.0, 0.0, 0.0)
    anchor = ctx.selection.actor(f"{TOOL_PLAN_TRACE}:height_anchor")
    assert anchor is not None
    assert anchor.points[0][0:3] == (0.0, 0.0, plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert "ground" in (ctx.status.latest().message or "").lower()


def test_placed_point_stores_semantic_depth_and_displays_on_visible_plane() -> None:
    ctx = _ctx(_HitScene())
    tool = PlanTrace2DCreatorTool()
    tool.on_open(ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), world_pos=(1.0, 2.0, 99.0), button=MouseButton.LEFT), ctx)

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(30.0, 40.0), world_pos=(30.0, 40.0, 12.75)), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(30.0, 40.0), world_pos=(30.0, 40.0, 12.75), button=MouseButton.LEFT), ctx)

    point = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point")
    assert point.points[0] == (30.0, 40.0, 12.0 + plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET)
    assert point.metadata["plan_trace_semantic_world_pos"] == (30.0, 40.0, 12.0)
    assert tool._state.points[0][1] == (30.0, 40.0, 12.0)


def test_docs_describe_two_phase_overlay_and_raycast_only_anchor() -> None:
    doc = Path("docs/tool_creator/17_plan_tracer_2d.md").read_text(encoding="utf-8")
    assert "first overlay is an anchor prompt only" in doc
    assert "raycast only" in doc
    assert "event.world_pos" in doc
    assert "display_plane" in doc

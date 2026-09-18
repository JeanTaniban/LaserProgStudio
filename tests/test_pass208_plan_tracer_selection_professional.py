from __future__ import annotations

from laserprog_studio.tool_api import actors
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool, PlanTrace2DTool
from laserprog_studio.tooling.registry import get_tool_spec


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


class _App:
    def __init__(self) -> None:
        self.tool_context = ToolContext()
        self.scene = _HitScene()
        self.tool_context.scene = self.scene
        self.tool_context.pick.bind_context(self.tool_context)


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def test_selection_hit_priority_prefers_point_over_coincident_edge() -> None:
    ctx = ToolContext()
    # Register the edge first on purpose: old distance-only selection would keep
    # the first exact hit. The API now treats topology level as the primary key.
    ctx.actor_registry("owner").add(
        actors.line(
            "edge_a",
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            owner_tool="owner",
            metadata={"plan_trace_role": "edge", "selection_priority": 70},
            hit_radius_px=12.0,
        )
    )
    ctx.actor_registry("owner").add(
        actors.point(
            "point_a",
            (5.0, 0.0, 0.0),
            owner_tool="owner",
            metadata={"plan_trace_role": "point", "selection_priority": 100},
            hit_radius_px=12.0,
        )
    )

    hit = ctx.selection.hit_test((5.0, 0.0), lambda p: (float(p[0]), float(p[1])), owner_tool="owner", selectable_only=True)

    assert hit is not None
    assert hit.actor_id == "point_a"
    assert hit.priority == 100


def test_plan_tracer_configures_api_box_selection_and_shift_drag_selects_points() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)

    _click(tool, ctx, 10.0, 10.0)
    _click(tool, ctx, 20.0, 20.0)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    assert ctx.selection_box.config.enabled is True
    assert ctx.selection_box.config.owner_tool == TOOL_PLAN_TRACE
    assert ctx.selection_box.config.activation_modifier.value == "shift"

    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(-100.0, -100.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})), ctx) is True
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(30.0, 30.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})), ctx) is True
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(30.0, 30.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})), ctx) is True

    selected_roles = [ctx.selection.actor(actor_id).metadata.get("plan_trace_role") for actor_id in ctx.selection.ids()]
    assert selected_roles.count("point") == 2
    assert ctx.inspector.value("plan_trace_2d.selection") == "2 point(s)"


def test_runtime_bypasses_native_modify_interaction_for_shift_click_toggle() -> None:
    runtime = PlanTrace2DTool(get_tool_spec(TOOL_PLAN_TRACE))
    app = _App()
    runtime.on_open(app)
    runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), app)
    ctx = app.tool_context
    tool = runtime.creator

    _click(tool, ctx, 42.0, 42.0)
    point_id = next(iter(tool._state.sketch.points))
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(42.0, 42.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})), app) is True
    assert ctx.selection.is_selected(point_id)

    assert runtime.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(42.0, 42.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})), app) is True
    assert not ctx.selection.is_selected(point_id)


def test_selection_hit_nearest_edge_beats_noncoincident_nearby_point() -> None:
    ctx = ToolContext()
    ctx.actor_registry("owner").add(
        actors.point(
            "point_a",
            (10.0, 0.0, 0.0),
            owner_tool="owner",
            metadata={"plan_trace_role": "point", "selection_priority": 100},
            hit_radius_px=12.0,
        )
    )
    ctx.actor_registry("owner").add(
        actors.line(
            "edge_a",
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            owner_tool="owner",
            metadata={"plan_trace_role": "edge", "selection_priority": 70},
            hit_radius_px=12.0,
        )
    )

    hit = ctx.selection.hit_test(
        (5.0, 0.0),
        lambda p: (float(p[0]), float(p[1])),
        owner_tool="owner",
        selectable_only=True,
    )

    assert hit is not None
    assert hit.actor_id == "edge_a"
    assert hit.distance_px == 0.0

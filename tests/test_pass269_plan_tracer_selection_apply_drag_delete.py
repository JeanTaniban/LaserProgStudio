from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedFace, ProjectedHandle, ProjectedLine
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


class _HitScene:
    def __init__(self) -> None:
        self.meshes = [SimpleNamespace(name="source_part", vertices=(), triangles=())]

    def pick_face_at(self, screen_pos, **_filters):
        x, y = screen_pos
        return PickResult("face", screen_pos=screen_pos, world_pos=(float(x), float(y), 7.0), object_id="face_7", object_index=0)


class _ApplyButton:
    def __init__(self) -> None:
        self.enabled = False

    def setEnabled(self, value: bool) -> None:
        self.enabled = bool(value)


class _ApplyOwner:
    def __init__(self, tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
        self.tool = tool
        self.ctx = ctx
        self.btn_apply_preview = _ApplyButton()
        self.update_calls = 0
        self.selected_indices = [0]
        self.active_index = 0

    def update_preview_state(self) -> None:
        self.update_calls += 1
        self.btn_apply_preview.setEnabled(self.tool.can_apply(self.ctx))


def _ctx() -> ToolContext:
    ctx = ToolContext()
    ctx.scene = _HitScene()
    ctx.pick.bind_context(ctx)
    ctx.document.bind(ctx.scene)
    return ctx


def _lock_plane(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool.on_open(ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(1.0, 2.0), button=MouseButton.LEFT), ctx)
    assert tool._state.display_plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def _draw_rectangle(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 180.0, 160.0)
    assert tool._state.sketch.faces


def test_plan_tracer_refreshes_inspector_apply_state_when_a_face_becomes_available() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    owner = _ApplyOwner(tool, ctx)
    ctx.owner = owner

    _lock_plane(tool, ctx)
    assert owner.btn_apply_preview.enabled is False

    _draw_rectangle(tool, ctx)

    assert owner.update_calls >= 1
    assert tool.can_apply(ctx) is True
    assert owner.btn_apply_preview.enabled is True


def test_plan_tracer_blocks_host_scene_selection_while_modify_is_active() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    owner = _ApplyOwner(tool, ctx)
    ctx.owner = owner
    ctx.scene_selection.set_selected([0])

    _lock_plane(tool, ctx)
    assert ctx.scene_selection.selected_indices() == ()
    assert owner.selected_indices == []
    assert owner.active_index is None

    ctx.scene_selection.set_selected([0])
    assert ctx.scene_selection.selected_indices() == (0,)
    tool.on_scene_selection_changed(ctx)
    assert ctx.scene_selection.selected_indices() == ()

    ctx.scene_selection.set_selected([0])
    handled = tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(500.0, 500.0), button=MouseButton.LEFT), ctx)
    assert handled is True
    assert ctx.scene_selection.selected_indices() == ()


def test_selected_face_replaces_normal_blue_fill_with_yellow_orange_feedback() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    _draw_rectangle(tool, ctx)

    face_actor = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "face")
    ctx.selection.select(face_actor.id)
    registry = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE)
    registry.sync_interaction_state(render=False)

    selected_fill = registry.get(face_actor.id)
    assert isinstance(selected_fill, ProjectedFace)
    assert selected_fill.style.fill_color == "#f0a805"
    assert selected_fill.style.fill_opacity >= 0.3
    assert not ctx.preview.items(owner_tool=TOOL_PLAN_TRACE)


def test_modify_point_drag_repaints_connected_edges_before_release() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    _draw_rectangle(tool, ctx)
    tool._set_active_tool(ctx, "modify", reason="test", render=False)

    registry = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE)
    line_before = tuple(item for item in registry.snapshot().lines if isinstance(item, ProjectedLine))
    assert line_before
    before = {item.id: item.points for item in line_before}
    point_actor = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point")

    assert ctx.selection.select(point_actor.id)
    assert ctx.selection.begin_grab(point_actor.id, (point_actor.points[0][0], point_actor.points[0][1]), world_pos=point_actor.points[0])

    result = tool.resolve_drag_positions(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(point_actor.points[0][0] + 30.0, point_actor.points[0][1] + 20.0)), ctx)

    assert result is not None
    line_primitives = tuple(item for item in registry.snapshot().lines if isinstance(item, ProjectedLine))
    assert line_primitives
    assert any(item.points != before.get(item.id) for item in line_primitives)
    # Faces are intentionally rebuilt on release; the mouse-move fast path only
    # updates directly connected edges/curves to stay fluid on dense sketches.
    assert not ctx.preview.items(owner_tool=TOOL_PLAN_TRACE)


def test_deleting_a_point_removes_its_gizmo_handle_and_tool_actor() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    tool._set_active_tool(ctx, "line", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 160.0, 100.0)

    point_actor = next(actor for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE) if actor.metadata.get("plan_trace_role") == "point")
    registry = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE)
    assert isinstance(registry.get(point_actor.id), ProjectedHandle)
    assert not ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE)
    assert ctx.selection.select(point_actor.id)

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Delete"), ctx) is True

    assert ctx.selection.actor(point_actor.id) is None
    assert registry.get(point_actor.id) is None
    assert not ctx.gizmos.handles(owner_tool=TOOL_PLAN_TRACE)

from __future__ import annotations

from laserprog_studio.application._tool_core_diag_scene_painter import ToolCoreDiagScenePainter
from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
from laserprog_studio.tool_core import ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tool_core.app_services import PickResult
from laserprog_studio.tool_core.events import MouseButton
from laserprog_studio.tool_core.projected_drawing import ProjectedFace
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


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
    assert tool._state.plane is not None


def _click(tool: PlanTrace2DCreatorTool, ctx: ToolContext, x: float, y: float) -> None:
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT), ctx)


def _draw_rectangle(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    tool._set_active_tool(ctx, "rectangle", reason="test", render=False)
    _click(tool, ctx, 100.0, 100.0)
    _click(tool, ctx, 180.0, 160.0)
    assert tool._state.sketch.faces
    tool._set_active_tool(ctx, "modify", reason="test", render=False)


def _native_click_face(tool: PlanTrace2DCreatorTool, ctx: ToolContext) -> None:
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(140.0, 130.0), button=MouseButton.LEFT)
    result = handle_native_creator_ui_event(
        press,
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
    )
    assert result.handled is True
    tool.on_native_interaction_result(press, ctx, result)

    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(140.0, 130.0), button=MouseButton.LEFT)
    release_result = handle_native_creator_ui_event(
        release,
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        world_to_screen=ctx.viewport.world_to_screen,
        render=False,
    )
    tool.on_native_interaction_result(release, ctx, release_result)
    # The real Creator adapter forwards unhandled releases to the tool; this is
    # the path that used to recompile the generated face under a new id and lose
    # the selection.
    if not release_result.handled:
        tool.on_event(release, ctx)


def test_face_selection_survives_release_compile_and_stays_orange() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    _draw_rectangle(tool, ctx)

    _native_click_face(tool, ctx)

    selected = tuple(ctx.selection.ids())
    assert len(selected) == 1
    selected_actor = ctx.selection.actor(selected[0])
    assert selected_actor is not None
    assert selected_actor.metadata.get("plan_trace_role") == "face"

    registry = ctx.projected_drawing.for_tool(TOOL_PLAN_TRACE)
    registry.sync_interaction_state(render=False)
    face_primitive = registry.get(selected_actor.id)
    assert isinstance(face_primitive, ProjectedFace)
    assert face_primitive.style.fill_color == "#f0a805"
    assert not ctx.preview.items(owner_tool=TOOL_PLAN_TRACE)


def test_delete_after_face_click_removes_generated_face_only() -> None:
    ctx = _ctx()
    tool = PlanTrace2DCreatorTool()
    _lock_plane(tool, ctx)
    _draw_rectangle(tool, ctx)

    _native_click_face(tool, ctx)
    assert tool._services.selection._delete_selected_points(ctx) is True

    assert not tool._state.sketch.faces
    assert tool._state.sketch.lines
    assert tool._state.sketch.suppressed_face_signatures
    assert not any(actor.metadata.get("plan_trace_role") == "face" for actor in ctx.selection.actors(owner_tool=TOOL_PLAN_TRACE))


class _FakeProp:
    def __init__(self) -> None:
        self.color = None

    def SetColor(self, r: float, g: float, b: float) -> None:
        self.color = (round(float(r), 6), round(float(g), 6), round(float(b), 6))


class _FakeActor:
    def __init__(self) -> None:
        self.prop = _FakeProp()

    def GetProperty(self):
        return self.prop


def test_persistent_pyvista_face_actor_accepts_hex_color_updates() -> None:
    actor = _FakeActor()

    ToolCoreDiagScenePainter._update_mesh_actor_style(actor, color="#f0a805")

    assert actor.prop.color == (round(240 / 255, 6), round(168 / 255, 6), round(5 / 255, 6))

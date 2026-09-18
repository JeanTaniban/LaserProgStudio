from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR
from laserprog_studio.tooling.vent_generator.settings import VentGeneratorSettings
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(float(x), float(y), 0.0), button=MouseButton.LEFT)


def _ctx_and_tool() -> tuple[ToolContext, VentGeneratorCreatorTool]:
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    return ctx, tool


def _prepare_move_drag(ctx: ToolContext, tool: VentGeneratorCreatorTool) -> str:
    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(80, 0), ctx) is True
    tool.on_overlay_button_clicked("vent.generator.mode.MOD", ctx)
    actor_id = "vent.generator.route.waypoint.01"
    assert ctx.selection.actor(actor_id) is not None
    ctx.selection.select(actor_id, replace=True)
    ctx.selection.begin_grab(actor_id, (80.0, 0.0), (80.0, 0.0, 0.0))
    return actor_id


def test_pass302_vent_generator_exposes_only_route_smart_snap_control() -> None:
    ctx, _tool = _ctx_and_tool()
    values = ctx.inspector.values()

    assert values["smart_snap"] is True
    assert "grid_snap" not in values
    assert "grid_step" not in values
    assert "snap_tolerance" not in values
    assert VentGeneratorSettings.from_values(values).smart_snap is True


def test_pass302_route_smart_snap_aligns_without_snapping_to_route_midpoint_during_modify_drag() -> None:
    ctx, tool = _ctx_and_tool()
    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(100, 0), ctx) is True
    assert tool.on_event(_release(200, 0), ctx) is True
    tool.on_overlay_button_clicked("vent.generator.mode.MOD", ctx)
    payload = ctx.owner.planar_tool_state.payload
    actor_id = "vent.generator.route.waypoint.02"
    ctx.selection.select(actor_id, replace=True)
    ctx.selection.begin_grab(actor_id, (200.0, 0.0), (200.0, 0.0, 0.0))

    event = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(51.0, 1.0),
        world_pos=(51.0, 1.0, 0.0),
        button=MouseButton.LEFT,
    )
    replacements = tool.resolve_drag_positions(event, ctx)

    assert replacements is not None
    assert actor_id in replacements
    assert payload.waypoints[2] == (51.0, 0.0)


def test_pass302_shift_constrains_vent_modify_drag_to_straight_axis() -> None:
    ctx, tool = _ctx_and_tool()
    _prepare_move_drag(ctx, tool)

    event = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(120.0, 37.0),
        world_pos=(120.0, 37.0, 0.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"shift"}),
    )
    replacements = tool.resolve_drag_positions(event, ctx)

    assert replacements is not None
    payload = ctx.owner.planar_tool_state.payload
    assert abs(payload.waypoints[1][1]) < 1.0e-6



def test_pass302_route_smart_snap_does_not_snap_directly_to_existing_waypoint() -> None:
    from laserprog_studio.tooling.vent_generator.snap import snap_vent_route_point

    ctx, tool = _ctx_and_tool()
    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(100, 0), ctx) is True
    payload = ctx.owner.planar_tool_state.payload

    result = snap_vent_route_point(payload, (100.2, 0.1), tolerance=6.0)

    assert result.point != (100.0, 0.0)
    assert result.kind != "route_point"
    assert result.source_id != "vent.generator.route.waypoint.01"


def test_pass302_vent_snap_attraction_radius_stays_small_for_free_drag() -> None:
    from laserprog_studio.tooling.vent_generator.snap import VENT_ROUTE_SNAP_TOLERANCE, snap_vent_route_point

    ctx, tool = _ctx_and_tool()
    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(100, 0), ctx) is True
    payload = ctx.owner.planar_tool_state.payload

    near = snap_vent_route_point(payload, (55.0, VENT_ROUTE_SNAP_TOLERANCE - 0.1))
    far = snap_vent_route_point(payload, (55.0, VENT_ROUTE_SNAP_TOLERANCE + 0.1))

    assert near.snapped is True
    assert near.point == (55.0, 0.0)
    assert far.snapped is False
    assert far.point == (55.0, VENT_ROUTE_SNAP_TOLERANCE + 0.1)


class _FakePlanarController:
    def __init__(self, state: PlanarToolState) -> None:
        self.state = state
        self.draw_calls = 0

    def draw_planar_preview(self, *args, **kwargs) -> None:  # pragma: no cover - should not be called during fast drag.
        self.draw_calls += 1


def test_pass302_modify_drag_uses_position_only_update_not_heavy_preview() -> None:
    ctx, tool = _ctx_and_tool()
    actor_id = _prepare_move_drag(ctx, tool)
    fake = _FakePlanarController(ctx.owner.planar_tool_state)
    ctx.owner.planar_tool_controller = fake

    event = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(120.0, 1.0),
        world_pos=(120.0, 1.0, 0.0),
        button=MouseButton.LEFT,
    )
    replacements = tool.resolve_drag_positions(event, ctx)

    assert replacements is not None
    assert actor_id in replacements
    assert fake.draw_calls == 0


def test_pass302_modify_drag_can_snap_to_scene_vertex_via_public_snap_api() -> None:
    scene_mesh = WorkMesh(
        name="snap_panel",
        vertices=[(10.0, 20.0, 0.0), (40.0, 20.0, 0.0), (10.0, 50.0, 0.0)],
        triangles=[(0, 1, 2)],
    )
    ctx, tool = _ctx_and_tool()
    ctx.document.bind(SceneDocument.from_meshes("scene", [scene_mesh]))
    ctx.scene_cache.rebuild(ctx, scope="snap")
    actor_id = _prepare_move_drag(ctx, tool)

    event = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(10.2, 20.2),
        world_pos=(10.2, 20.2, 0.0),
        button=MouseButton.LEFT,
    )
    replacements = tool.resolve_drag_positions(event, ctx)

    assert replacements is not None
    assert actor_id in replacements
    payload = ctx.owner.planar_tool_state.payload
    assert payload.waypoints[1] == (10.0, 20.0)



def test_pass302_vent_snap_feedback_never_registers_extra_snap_cursor_gizmo() -> None:
    ctx, tool = _ctx_and_tool()
    actor_id = _prepare_move_drag(ctx, tool)

    event = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(120.0, 1.0),
        world_pos=(120.0, 1.0, 0.0),
        button=MouseButton.LEFT,
    )
    replacements = tool.resolve_drag_positions(event, ctx)

    assert replacements is not None
    assert actor_id in replacements
    assert ctx.selection.actor("vent.generator.route.snap") is None
    assert "vent.generator.route.snap" not in {item.id for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items()}


def test_pass302_add_drag_pending_link_is_dirty_for_fast_preview_updates() -> None:
    from laserprog_studio.tooling.vent_generator.feedback import sync_vent_route_visuals

    ctx, tool = _ctx_and_tool()
    assert tool.on_event(_release(0, 0), ctx) is True
    state = ctx.owner.planar_tool_state
    payload = state.payload

    state.pending_plane_point = (20.0, 0.0)
    sync_vent_route_visuals(ctx, payload, state=state, render=False, full=False, position_only=True)
    projected = {str(item.id): item for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items()}

    assert "vent.generator.preview.pending_link" in ctx.selection.state.dirty_visual_preview_ids
    assert projected["vent.generator.preview.pending_link"].points[-1] == (20.0, 0.0, 0.0)

    state.pending_plane_point = (40.0, 0.0)
    sync_vent_route_visuals(ctx, payload, state=state, render=False, full=False, position_only=True)
    projected = {str(item.id): item for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items()}

    assert "vent.generator.preview.pending_link" in ctx.selection.state.dirty_visual_preview_ids
    assert projected["vent.generator.preview.pending_link"].points[-1] == (40.0, 0.0, 0.0)


def test_pass302_vent_snap_hint_spheres_are_forbidden_in_projected_drawing_source() -> None:
    from pathlib import Path

    preview_source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")
    feedback_source = Path("src/laserprog_studio/tooling/vent_generator/feedback.py").read_text(encoding="utf-8")

    assert "if isinstance(payload, VentPathDraft):" in preview_source
    assert "large PyVista sphere gizmos" in preview_source
    assert "FORBIDDEN_VENT_SNAP_CURSOR_IDS" in feedback_source
    assert 'cursor_id="vent.generator.route.snap"' not in feedback_source

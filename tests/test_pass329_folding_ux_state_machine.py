# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.folding.models import FoldingPhase
from laserprog_studio.tooling.folding.workflow_overlay import FOLDING_ACTION_PREFIX, FOLDING_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.folding_tool import FoldingCreatorTool
from laserprog_studio.tooling.ids import TOOL_FOLDING


def _box() -> WorkMesh:
    return WorkMesh(
        name="fold target",
        vertices=[
            (0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 8.0, 0.0), (0.0, 8.0, 0.0),
            (0.0, 0.0, 2.0), (20.0, 0.0, 2.0), (20.0, 8.0, 2.0), (0.0, 8.0, 2.0),
        ],
        triangles=[
            (0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6),
            (0, 4, 5), (0, 5, 1), (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3), (3, 7, 4), (3, 4, 0),
        ],
        color="#AACCEE",
    )


class _PickScene:
    def __init__(self, mesh: WorkMesh) -> None:
        self.mesh = mesh

    def pick_object_at(self, _screen_pos, **_filters):
        return {"kind": "object", "object_id": self.mesh.mesh_id, "object_index": 0}

    def pick_face_at(self, _screen_pos, **_filters):
        return {
            "kind": "face",
            "object_id": self.mesh.mesh_id,
            "object_index": 0,
            "element_index": 0,
            "world_pos": (2.0, 1.0, 0.0),
            "normal": (0.0, 0.0, 1.0),
        }


def _context() -> tuple[ToolContext, WorkMesh]:
    mesh = _box()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    ctx = ToolContext(scene=_PickScene(mesh))
    ctx.document.bind(store)
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    return ctx, mesh


def _field(window, field_id: str) -> str:
    return next(field.value for field in window.fields if field.id == field_id)


def _advance_to_place_start(tool: FoldingCreatorTool, ctx: ToolContext) -> None:
    for pos in ((5.0, 5.0), (6.0, 6.0)):
        tool.wants_pointer_press_passthrough(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=pos, button=MouseButton.LEFT), ctx)
        assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=pos, button=MouseButton.LEFT), ctx)
    assert tool.session.phase is FoldingPhase.PLACE_START


def test_folding_opens_with_a_visible_phase_aware_viewport_window() -> None:
    ctx, _mesh = _context()
    tool = FoldingCreatorTool()
    tool.open(ctx)

    window = ctx.overlay.window(FOLDING_WORKFLOW_WINDOW_ID)
    assert window is not None and window.visible is True
    assert window.owner_tool == TOOL_FOLDING
    assert window.anchor == "viewport_top_left"
    assert _field(window, "folding.workflow.step") == "Step 1 of 5 · Select the mesh"
    assert "yellow outline" in _field(window, "folding.workflow.status").lower()
    assert f"{FOLDING_ACTION_PREFIX}cancel" in {button.id for button in window.buttons}
    assert ctx.inspector.panel is not None and ctx.inspector.panel.id == "folding.tool"


def test_qt_camera_passthrough_keeps_the_release_needed_to_select_a_mesh() -> None:
    ctx, mesh = _context()
    tool = FoldingCreatorTool()
    tool.open(ctx)

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(50.0, 40.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_press_passthrough(press, ctx) is True
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(52.0, 41.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_release_passthrough(release, ctx) is True
    assert tool.on_event(release, ctx) is True

    assert tool.session.target_object_id == mesh.mesh_id
    assert tool.session.phase is FoldingPhase.SELECT_FACE
    window = ctx.overlay.window(FOLDING_WORKFLOW_WINDOW_ID)
    assert _field(window, "folding.workflow.step") == "Step 2 of 5 · Select the drawing face"
    ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_FOLDING).items()}
    assert "folding:target" in ids


def test_a_real_left_drag_remains_camera_navigation_and_does_not_select() -> None:
    ctx, _mesh = _context()
    tool = FoldingCreatorTool()
    tool.open(ctx)

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(10.0, 10.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_press_passthrough(press, ctx)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(40.0, 30.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_release_passthrough(release, ctx)
    assert tool.on_event(release, ctx) is False
    assert tool.session.phase is FoldingPhase.SELECT_MESH


def test_scene_selection_change_during_pointer_press_cannot_consume_the_next_phase() -> None:
    ctx, mesh = _context()
    tool = FoldingCreatorTool()
    tool.open(ctx)
    ctx.scene_selection.select_indices((0,), active_index=0)

    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(30.0, 20.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_press_passthrough(press, ctx)
    tool.on_scene_selection_changed(ctx)
    assert tool.session.phase is FoldingPhase.SELECT_MESH
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(30.0, 20.0), button=MouseButton.LEFT), ctx)
    assert tool.session.target_object_id == mesh.mesh_id
    assert tool.session.phase is FoldingPhase.SELECT_FACE


def test_face_hover_and_each_click_update_the_visual_state_and_overlay() -> None:
    ctx, _mesh = _context()
    tool = FoldingCreatorTool()
    tool.open(ctx)

    tool.wants_pointer_press_passthrough(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(5.0, 5.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(5.0, 5.0), button=MouseButton.LEFT), ctx)
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(6.0, 6.0), button=MouseButton.NONE), ctx)
    ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_FOLDING).items()}
    assert "folding:hovered_face" in ids

    tool.wants_pointer_press_passthrough(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(6.0, 6.0), button=MouseButton.LEFT), ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(6.0, 6.0), button=MouseButton.LEFT), ctx)
    assert tool.session.phase is FoldingPhase.PLACE_START
    ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_FOLDING).items()}
    assert "folding:selected_face" in ids

    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(2.0, 2.0), button=MouseButton.NONE), ctx)
    assert "folding:cursor" in {item.id for item in ctx.projected_drawing.for_tool(TOOL_FOLDING).items()}

    for pos, expected in [((2.0, 2.0), FoldingPhase.PLACE_END), ((16.0, 2.0), FoldingPhase.ADJUST_CURVE)]:
        tool.wants_pointer_press_passthrough(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=pos, button=MouseButton.LEFT), ctx)
        assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=pos, button=MouseButton.LEFT), ctx)
        assert tool.session.phase is expected

    window = ctx.overlay.window(FOLDING_WORKFLOW_WINDOW_ID)
    assert _field(window, "folding.workflow.step") == "Step 5 of 5 · Adjust the folding curve"
    buttons = {button.id: button for button in window.buttons}
    assert buttons[f"{FOLDING_ACTION_PREFIX}apply"].enabled is True
    assert {"folding:curve", "folding:control:1", "folding:control:2"}.issubset(
        {item.id for item in ctx.projected_drawing.for_tool(TOOL_FOLDING).items()}
    )


def test_v148_folding_uses_official_plan_cursor_and_smart_snap(monkeypatch) -> None:
    ctx, _mesh = _context()
    tool = FoldingCreatorTool()
    tool.open(ctx)
    _advance_to_place_start(tool, ctx)

    import laserprog_studio.tooling.folding_tool as folding_module

    monkeypatch.setattr(
        folding_module.plan2d,
        "smart_snap_on_plan",
        lambda *_args, **_kwargs: SimpleNamespace(
            world_pos=(10.0, 4.0, 0.0),
            snapped=True,
            kind="midpoint",
            label="Midpoint",
        ),
    )
    tool.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(9.2, 4.1), button=MouseButton.NONE), ctx)

    assert tool.session.hover_point == (10.0, 4.0, 0.0)
    cursor = ctx.projected_drawing.for_tool(TOOL_FOLDING).get("folding:cursor")
    assert cursor is not None
    metadata = dict(cursor.metadata)
    assert metadata["snap_kind"] == "midpoint"
    assert metadata["snap_label"] == "Midpoint"
    assert metadata["plan_trace_role"] == "cursor"


def test_v148_shift_constrains_the_folding_axis_like_plan_tracer(monkeypatch) -> None:
    ctx, _mesh = _context()
    tool = FoldingCreatorTool()
    tool.open(ctx)
    _advance_to_place_start(tool, ctx)

    import laserprog_studio.tooling.folding_tool as folding_module

    monkeypatch.setattr(
        folding_module.plan2d,
        "smart_snap_on_plan",
        lambda *_args, **kwargs: SimpleNamespace(
            world_pos=kwargs["candidate_world"],
            snapped=False,
            kind="free",
            label="Free",
        ),
    )

    start = (2.0, 2.0)
    tool.wants_pointer_press_passthrough(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=start, button=MouseButton.LEFT), ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=start, button=MouseButton.LEFT), ctx)
    assert tool.session.phase is FoldingPhase.PLACE_END

    constrained_move = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(8.0, 4.0),
        button=MouseButton.NONE,
        modifiers=frozenset({"shift"}),
    )
    tool.on_event(constrained_move, ctx)
    assert tool.session.hover_point is not None
    assert abs(tool.session.hover_point[1] - 2.0) <= 1.0e-9
    cursor = ctx.projected_drawing.for_tool(TOOL_FOLDING).get("folding:cursor")
    assert cursor is not None and dict(cursor.metadata)["snap_kind"] == "angle"

    release = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(8.0, 4.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"shift"}),
    )
    tool.wants_pointer_press_passthrough(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(8.0, 4.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})),
        ctx,
    )
    assert tool.on_event(release, ctx)
    assert tool.session.phase is FoldingPhase.ADJUST_CURVE
    assert tool.session.curve.end is not None
    assert abs(tool.session.curve.end[1] - 2.0) <= 1.0e-9


def test_overlay_cancel_uses_the_standard_host_lifecycle_when_available() -> None:
    calls: list[str] = []
    owner = SimpleNamespace(discard_preview_and_close_tool=lambda: calls.append("cancel"))
    ctx, _mesh = _context()
    ctx.attach_owner(owner)
    tool = FoldingCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{FOLDING_ACTION_PREFIX}cancel", ctx)
    assert calls == ["cancel"]

# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.tool_api.gizmos import build_creator_ui_motifs
from laserprog_studio.tool_api.interaction import handle_native_creator_ui_event
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.base import ToolSpec
from laserprog_studio.tooling.creator_runtime import CreatorStudioToolAdapter
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool
from laserprog_studio.application.creator_pointer_interaction import handle_creator_tool_pointer_event


def _event(event_type, screen, world, *, button=MouseButton.LEFT):
    return ToolEvent(event_type, screen_pos=screen, world_pos=world, button=button)


def test_native_runtime_is_public_and_chooses_fast_paths(monkeypatch) -> None:
    import laserprog_studio.tool_api.gizmos as gizmos

    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass178", families=("point_styles",))
    calls = {"drag": 0, "interaction": 0}
    original_drag = gizmos.refresh_creator_ui_drag
    original_interaction = gizmos.refresh_creator_ui_interaction

    def drag_proxy(*args, **kwargs):
        calls["drag"] += 1
        return original_drag(*args, render=False, **{k: v for k, v in kwargs.items() if k != "render"})

    def interaction_proxy(*args, **kwargs):
        calls["interaction"] += 1
        return original_interaction(*args, render=False, **{k: v for k, v in kwargs.items() if k != "render"})

    monkeypatch.setattr(gizmos, "refresh_creator_ui_drag", drag_proxy)
    monkeypatch.setattr(gizmos, "refresh_creator_ui_interaction", interaction_proxy)

    press = handle_native_creator_ui_event(
        _event(ToolEventType.MOUSE_PRESS, (17.0, 72.0), (17.0, 72.0, 0.35)),
        ctx,
        owner_tool="test.pass178",
        render=True,
    )
    assert press.handled
    move = handle_native_creator_ui_event(
        _event(ToolEventType.MOUSE_MOVE, (22.0, 76.0), (22.0, 76.0, 0.35)),
        ctx,
        owner_tool="test.pass178",
        render=True,
    )
    assert move.moved == 1
    assert calls["interaction"] >= 1
    assert calls["drag"] == 1



def test_creator_adapter_uses_native_actor_runtime_for_projected_catalog(monkeypatch) -> None:
    import laserprog_studio.tool_api.gizmos as gizmos

    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)
    adapter = CreatorStudioToolAdapter(
        spec=ToolSpec(id=tool.id, label=tool.label, category="tool", panel_index=0),
        creator=tool,
    )
    context = SimpleNamespace(tool_context=ctx)
    calls = {"interaction": 0}
    original = gizmos.refresh_creator_ui_interaction

    def interaction_proxy(*args, **kwargs):
        calls["interaction"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(gizmos, "refresh_creator_ui_interaction", interaction_proxy)
    handle = next(item for item in ctx.projected_drawing.snapshot(tool.id).handles if item.constraint.value == "axis_x")
    event = _event(ToolEventType.MOUSE_PRESS, (handle.position[0], handle.position[1]), handle.position)
    assert adapter.on_event(event, context) is True
    assert calls["interaction"] >= 1
    assert ctx.selection.actors(owner_tool=tool.id)


def test_left_button_camera_pan_skips_creator_hit_test_when_no_actor_is_grabbed() -> None:
    class Qt:
        LeftButton = 1
        MiddleButton = 2
        RightButton = 4
        NoButton = 0
        ShiftModifier = 8
        ControlModifier = 16
        AltModifier = 32

    class QEvent:
        MouseButtonPress = 1
        MouseMove = 2
        MouseButtonRelease = 3

    class Event:
        def buttons(self):
            return Qt.LeftButton

        def modifiers(self):
            return Qt.NoButton

    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="gizmo_catalog", families=("point_styles",))
    ctx.selection.state.grab_active = False

    def forbidden_hit_test(*_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("camera pan must not hit-test Creator actors on every move")

    ctx.selection.hit_test = forbidden_hit_test  # type: ignore[method-assign]

    class Tool:
        def tool_context(self, _context):
            return ctx

        def on_event(self, *_args, **_kwargs):  # pragma: no cover - failure path
            raise AssertionError("camera pan move must not be forwarded to creator tool")

    owner = SimpleNamespace(context=SimpleNamespace())
    handled = handle_creator_tool_pointer_event(
        owner,
        Tool(),
        QEvent.MouseMove,
        Event(),
        120.0,
        90.0,
        Qt.LeftButton,
        Qt=Qt,
        QEvent=QEvent,
    )
    assert handled is False


def test_grab_drag_depth_uses_grabbed_actor_without_scene_hit_test() -> None:
    from laserprog_studio.application.creator_pointer_interaction import creator_depth_for_hit_or_selection

    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="gizmo_catalog", families=("point_styles",))
    actor_id = "gizmo_catalog:point_styles:solid:line_grab:a"
    ctx.selection.select(actor_id)
    ctx.selection.begin_grab(actor_id, (17.0, 72.0), (17.0, 72.0, 0.35))

    def forbidden_hit_test(*_args, **_kwargs):  # pragma: no cover - failure path
        raise AssertionError("grab depth must reuse grabbed actor instead of hit-testing")

    ctx.selection.hit_test = forbidden_hit_test  # type: ignore[method-assign]

    class Owner:
        active_tool = "gizmo_catalog"

        def _world_to_display(self, _position):
            return (0.0, 0.0, 0.77)

    assert creator_depth_for_hit_or_selection(Owner(), ctx, 22.0, 76.0) == 0.77


def test_docs_state_native_runtime_and_end_only_camera_refresh() -> None:
    docs = "\n".join(
        Path(path).read_text(encoding="utf-8")
        for path in (
            "docs/tool_creator/00_creator_ui_direction.md",
            "docs/tool_creator/06_overlay_preview_gizmos.md",
            "docs/tool_creator/16_gizmo_catalog_tool.md",
            "docs/archive/passes/pass178_native_creator_ui_runtime_camera_pan.md",
        )
    )
    assert "handle_native_creator_ui_event" in docs
    assert "CreatorStudioToolAdapter" in docs
    assert "empty camera" in docs.lower()
    assert "field-of-view" in docs
    assert "after camera" in docs.lower()

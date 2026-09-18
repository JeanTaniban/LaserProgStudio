# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import actors
from laserprog_studio.tool_api.selection_box import BoxSelectionActivationModifier, BoxSelectionMode, BoxSelectionTarget
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType


def _identity_screen(point):
    return (float(point[0]), float(point[1]))


def test_pass138_box_selection_handle_event_requires_shift_by_default() -> None:
    ctx = ToolContext()
    owner = "test.pass138.shift"
    ctx.actor_registry(owner).add(actors.point("p", (50, 50, 0), interaction="selectable"))
    ctx.selection_box.configure(enabled=True, targets=[BoxSelectionTarget.TOOL_ACTORS], owner_tool=owner, mode=BoxSelectionMode.REPLACE)

    handled = ctx.selection_box.handle_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0, 0), button=MouseButton.LEFT),
        world_to_screen=_identity_screen,
    )

    assert handled is False
    assert not ctx.selection_box.pending

    handled_shift = ctx.selection_box.handle_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0, 0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})),
        world_to_screen=_identity_screen,
    )

    assert handled_shift is False
    assert ctx.selection_box.pending


def test_pass138_shift_activation_keeps_configured_box_mode() -> None:
    ctx = ToolContext()
    owner = "test.pass138.mode"
    ctx.actor_registry(owner).add(actors.point("p", (50, 50, 0), interaction="selectable"))
    ctx.selection_box.configure(
        enabled=True,
        targets=[BoxSelectionTarget.TOOL_ACTORS],
        owner_tool=owner,
        mode=BoxSelectionMode.REPLACE,
        activation_modifier=BoxSelectionActivationModifier.SHIFT,
    )

    ctx.selection_box.handle_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0, 0), button=MouseButton.LEFT, modifiers=frozenset({"shift"})), world_to_screen=_identity_screen)
    ctx.selection_box.handle_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(60, 60), button=MouseButton.LEFT, modifiers=frozenset({"shift"})), world_to_screen=_identity_screen)
    result = ctx.selection_box.finish((60, 60), world_to_screen=_identity_screen)

    assert result.completed
    assert result.mode is BoxSelectionMode.REPLACE
    assert result.tool_actor_ids == ("p",)


def test_pass138_diagnostic_lab_starts_box_selection_only_with_shift() -> None:
    from laserprog_studio.application.tool_core_diag_controller import ToolCoreDiagController

    class _Owner:
        pass

    controller = ToolCoreDiagController.create(type("Ctx", (), {"owner": _Owner()})())
    controller.runner.run_api_lab_setup()
    controller._api_lab_active = True

    assert controller._handle_api_lab_pointer_press(9999.0, 9999.0, shift_down=False) is False
    assert not controller.runner.ctx.selection_box.pending

    assert controller._handle_api_lab_pointer_press(9999.0, 9999.0, shift_down=True) is True
    assert controller.runner.ctx.selection_box.pending


def test_pass138_selection_box_overlay_uses_reusable_overlay_widget() -> None:
    source = Path("src/laserprog_studio/ui/selection_box_overlay.py").read_text(encoding="utf-8")
    controller = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])
    legacy = Path("src/laserprog_studio/controllers/selection_box.py").read_text(encoding="utf-8")

    assert "set_selection_rect" in source
    assert "CompositionMode_SourceOver" in source
    assert "clear_selection_rect" in source
    assert "must *not* cover the full" in source
    assert "band.set_selection_rect(rect)" in controller
    assert "band.clear_selection_rect()" in controller
    assert "band.set_selection_rect(rect)" in legacy
    assert "band.clear_selection_rect()" in legacy

from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import VentPathDraft, VentSectionKind
from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.vent_generator import CUSTOM_PRESET_ID, PRESET_CHOICES, values_for_vent_preset, vent_preset_description
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _ctx_and_tool() -> tuple[ToolContext, VentGeneratorCreatorTool]:
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    return ctx, tool


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(float(x), float(y), 0.0), button=MouseButton.LEFT)


def test_pass243_vent_presets_are_declared_as_user_facing_starters() -> None:
    choice_ids = {choice_id for choice_id, _label in PRESET_CHOICES}

    assert CUSTOM_PRESET_ID in choice_ids
    assert {"rect_compact", "rect_airbox", "rect_fill_block", "round_small", "round_large_flared"}.issubset(choice_ids)
    assert values_for_vent_preset("round_small")["section_kind"] == VentSectionKind.ROUND.value
    assert "current manual values" in vent_preset_description(CUSTOM_PRESET_ID)


def test_pass243_vent_preset_loads_dimensions_then_manual_edit_switches_to_custom() -> None:
    ctx, _tool = _ctx_and_tool()

    ctx.inspector.update_value("quick_preset", "round_large_flared")
    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)
    assert ctx.inspector.value("section_kind") == VentSectionKind.ROUND.value
    assert ctx.inspector.value("section_area") == 490.9
    assert ctx.inspector.value("fill_area") is False
    assert ctx.inspector.field_state("rect_width").visible is False
    assert payload.section.kind is VentSectionKind.ROUND
    assert "flared round" in ctx.inspector.value("preset_help").lower()

    ctx.inspector.update_value("section_area", 600.0)
    assert ctx.inspector.value("quick_preset") == CUSTOM_PRESET_ID
    assert "custom values" in ctx.inspector.value("preset_help").lower()
    assert ctx.owner.vent_generator_settings["section_area"] == 600.0


def test_pass243_start_over_restores_defaults_and_clears_route() -> None:
    ctx, tool = _ctx_and_tool()
    ctx.inspector.update_value("quick_preset", "rect_airbox")
    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(80, 0), ctx) is True
    assert ctx.inspector.value("rect_width") == 28.0

    ctx.inspector.trigger("start_over")

    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)
    assert payload.waypoints == []
    assert ctx.inspector.value("quick_preset") == CUSTOM_PRESET_ID
    assert ctx.inspector.value("rect_width") == 10.0
    assert ctx.inspector.value("rect_height") == 10.0
    assert ctx.inspector.value("wall_thickness") == 3.0
    assert ctx.inspector.value("mode") == "ADD"
    assert "Started over" in ctx.status.latest(level="info").message


def test_pass243_overlay_start_over_action_matches_inspector_action() -> None:
    ctx, tool = _ctx_and_tool()
    ctx.inspector.update_value("quick_preset", "rect_fill_block")
    tool.on_event(_release(0, 0), ctx)
    tool.on_event(_release(70, 0), ctx)

    tool.on_overlay_button_clicked("vent.generator.action.start_over", ctx)

    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)
    assert payload.waypoints == []
    assert ctx.inspector.value("quick_preset") == CUSTOM_PRESET_ID
    assert ctx.inspector.value("fill_area") is False

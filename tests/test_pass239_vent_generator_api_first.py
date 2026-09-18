from __future__ import annotations

from pathlib import Path

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import VentFlareSide, VentSectionKind, VentPathDraft, make_locked_plane
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR
from laserprog_studio.tooling.vent_generator import VentGeneratorSettings, apply_settings_to_payload
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def test_vent_generator_uses_the_shared_declarative_creator_panel() -> None:
    panel = get_tool_panel_spec(TOOL_VENT_GENERATOR)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"
    assert not Path("src/laserprog_studio/ui/vent_tool_panel.py").exists()
    assert not Path("src/laserprog_studio/application/vent_ui_state_service.py").exists()


def test_vent_generator_panel_fields_are_adaptive_without_qt_widgets() -> None:
    ctx = ToolContext()
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.field_state("section_area").visible is False
    assert ctx.inspector.field_state("rect_width").visible is True
    assert ctx.inspector.field_state("fill_area").visible is True
    assert ctx.inspector.field_state("flare_factor").visible is False

    ctx.inspector.update_value("section_kind", VentSectionKind.ROUND.value)
    assert ctx.inspector.field_state("section_area").visible is True
    assert ctx.inspector.field_state("rect_width").visible is False
    assert ctx.inspector.field_state("fill_area").visible is False

    ctx.inspector.update_value("flare_side", VentFlareSide.BOTH.value)
    assert ctx.inspector.field_state("flare_factor").visible is True


def test_vent_generator_settings_apply_cleanly_to_payload() -> None:
    payload = VentPathDraft(make_locked_plane("top"))
    settings = VentGeneratorSettings.from_values(
        {
            "section_kind": "rectangle",
            "rect_width": 42.0,
            "rect_height": 12.0,
            "wall_thickness": 2.4,
            "target_length": 180.0,
            "fill_area": True,
            "flare_side": "both",
            "flare_factor": 1.6,
        }
    )
    apply_settings_to_payload(payload, settings)

    assert payload.section.kind is VentSectionKind.RECTANGLE
    assert payload.section.width == 42.0
    assert payload.section.height == 12.0
    assert payload.section.area == 42.0 * 12.0
    assert payload.wall_thickness == 2.4
    assert payload.target_length == 180.0
    assert payload.fill_area is True
    assert payload.flare_side is VentFlareSide.BOTH
    assert payload.flare_factor == 1.6

# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tooling.diag_tool import ToolCoreDiagnosticCreatorTool
from laserprog_studio.tooling.ids import TOOL_CORE_DIAGNOSTIC
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def test_pass245_tool_core_diagnostic_uses_declarative_creator_panel() -> None:
    spec = get_tool_panel_spec(TOOL_CORE_DIAGNOSTIC)
    assert spec is not None
    assert spec.builder == "panel_declarative_creator_tool"
    assert not Path("src/laserprog_studio/ui/tool_panel_diagnostic_panel.py").exists()


def test_pass245_tool_core_diagnostic_panel_is_a_complete_api_lab() -> None:
    tool = ToolCoreDiagnosticCreatorTool()
    panel = tool._panel(object())  # noqa: SLF001 - product contract inspection
    field_ids = set(panel.field_ids())

    assert panel.id == "tool_core_diagnostic.workspace"
    assert panel.owner_tool == TOOL_CORE_DIAGNOSTIC
    assert {"actor_kind", "interaction", "move", "point_style", "line_style", "visual_state"}.issubset(field_ids)
    assert {"box_enabled", "box_target", "box_mode", "box_inside_policy"}.issubset(field_ids)
    assert {"camera_size_mode", "minimal_dot_normal", "minimal_dot_active", "diag_report"}.issubset(field_ids)

    actions = {
        choice_id
        for section in panel.sections
        for field in section.fields
        for choice_id, _label in field.choices
        if field.kind == "button_row"
    }
    assert {
        "open_lab",
        "add_actor",
        "delete_selected",
        "move_selected",
        "select_all",
        "clear_lab",
        "self_test",
        "api_tests",
        "api_benchmark",
        "full_validation",
        "run_all",
        "handle_demo",
        "hover_state",
        "grab_state",
        "selection_demo",
        "ui_showcase",
    }.issubset(actions)

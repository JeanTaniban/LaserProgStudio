# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner
from laserprog_studio.tool_core.input import EventRouter
from laserprog_studio.tooling.ids import TOOL_CORE_DIAGNOSTIC
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.toolbar_catalog import default_toolbar_item_ids, get_toolbar_item_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def test_pass104_tool_core_diagnostic_is_registered_by_default() -> None:
    assert get_tool_spec(TOOL_CORE_DIAGNOSTIC) is not None
    assert get_studio_tool(TOOL_CORE_DIAGNOSTIC) is not None
    assert get_toolbar_item_spec("tool:core_diagnostic").tool_id == TOOL_CORE_DIAGNOSTIC
    assert "tool:core_diagnostic" in default_toolbar_item_ids()
    panel = get_tool_panel_spec(TOOL_CORE_DIAGNOSTIC)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"


def test_pass104_diagnostic_runner_exercises_every_shared_layer() -> None:
    runner = CoreDiagRunner()
    snapshot = runner.run_all()
    stats = runner.backend_stats()

    assert snapshot.handles >= 5
    assert snapshot.previews >= 4
    assert runner.last_api_test_report is not None and runner.last_api_test_report.ok
    assert runner.last_api_lab_benchmark is not None and runner.last_api_lab_benchmark.ok
    assert any("Full" in entry or "Creator API" in entry or "API Lab" in entry for entry in runner.log)
    assert stats["removed"] == 0
    assert snapshot.profiler_values.get("diag.api_lab.benchmark") == 1


def test_pass104_event_router_is_part_of_the_shared_tool_core_package() -> None:
    assert EventRouter.__name__ == "EventRouter"
    source = Path("src/laserprog_studio/tool_core/input/router.py")
    assert source.exists()
    text = source.read_text(encoding="utf-8")
    assert "ctx.begin_drag()" in text
    assert "ctx.end_drag()" in text


def test_pass104_gui_panel_exposes_precise_diagnostic_actions() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    for label in ["API Lab", "Add actor", "Delete selected", "Move selected", "Select all", "API tests", "API benchmark", "Full validation", "Clear"]:
        assert label in source
    assert "diag_report" in source
    assert "ToolCoreDiagnosticCreatorTool" in source
    assert "_controller(ctx)" in source

# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import TOOL_API_VERSION, ApiDiagnosticReport, run_creator_api_self_test
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.diagnostic.runner import CoreDiagRunner


def test_pass128_creator_api_self_test_report_covers_full_sdk_surface() -> None:
    report = run_creator_api_self_test(ToolContext(), owner_tool="test.pass128")

    assert isinstance(report, ApiDiagnosticReport)
    assert report.api_version == TOOL_API_VERSION == "0.13.0"
    assert report.ok
    assert report.total == 14
    assert {case.category for case in report.cases} == {
        "Core",
        "UI",
        "Interaction",
        "Document",
        "Viewport",
        "Operations",
        "Workflow",
        "Domain",
        "Planar",
        "Lifecycle",
        "Diagnostics",
    }
    markdown = report.to_markdown()
    assert "Creator API self-tests" in markdown
    assert "14/14 passed" in markdown
    assert "operations + jobs + status" in markdown


def test_pass128_tool_core_diagnostic_runner_exposes_creator_api_test_suite() -> None:
    runner = CoreDiagRunner()
    snapshot = runner.run_creator_api_tests()

    assert runner.last_api_test_report is not None
    assert runner.last_api_test_report.ok
    assert "Creator API self-tests: 14/14 passed" in runner.log
    assert snapshot.profiler_values["diag.creator_api_tests.runs"] == 1


def test_pass128_diagnostic_panel_has_visible_api_tests_entrypoint() -> None:
    factory_source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    controller_source = "\n".join(path.read_text(encoding="utf-8") for path in [Path("src/laserprog_studio/application/tool_core_diag_controller.py"), *Path("src/laserprog_studio/application/tool_core_diag").glob("*.py")])

    assert "API tests" in factory_source
    assert "run_creator_api_tests" in factory_source
    assert "API Lab" in factory_source
    assert "Full validation" in factory_source
    assert "Creator API self-tests" in controller_source
    assert "last_api_test_report" in controller_source

# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import (
    TOOL_API_VERSION,
    active_import_paths,
    audit_tool_api_surface,
    supported_import_paths,
    public_api_summary,
)
from laserprog_studio.tool_api import application, core, plan2d, scene, visual, workflow
from laserprog_studio.tool_api.surface import public_api_markdown
from laserprog_studio.tool_api.diagnostics import run_creator_api_self_test
from laserprog_studio.tool_core import ToolContext


def test_pass129_creator_api_has_grouped_public_domains() -> None:
    assert TOOL_API_VERSION == "0.13.0"
    assert active_import_paths() == (
        "laserprog_studio.tool_api.core",
        "laserprog_studio.tool_api.scene",
        "laserprog_studio.tool_api.visual",
        "laserprog_studio.tool_api.application",
        "laserprog_studio.tool_api.workflow",
        "laserprog_studio.tool_api.plan2d",
        "laserprog_studio.tool_api.surface_selection",
        "laserprog_studio.tool_api.diagnostics",
    )
    assert "laserprog_studio.tool_api" in supported_import_paths()
    assert core.CreatorTool
    assert scene.actors
    assert visual.inspector
    assert application.OperationResult
    assert workflow.ToolWorkflowManager
    assert plan2d.ArcIntent

    summary = public_api_summary()
    assert summary["active_domains"] == 8
    assert summary["supported_domains"] >= 7
    markdown = public_api_markdown()
    assert "Recommended domains" in markdown
    assert "Do not import directly" in markdown


def test_pass129_surface_cleanup_audit_is_reusable_and_blocker_free() -> None:
    findings = audit_tool_api_surface()

    assert findings
    assert not [finding for finding in findings if finding.severity == "blocker"]
    assert any(finding.code == "ACTIVE_DOMAIN_COUNT" and finding.ok for finding in findings)
    assert any(finding.code == "IMPORT_OK" for finding in findings)


def test_pass129_creator_api_self_test_includes_surface_check() -> None:
    report = run_creator_api_self_test(ToolContext(), owner_tool="test.pass129")

    assert report.ok
    assert report.total == 14
    assert any(case.name == "public surface map" for case in report.cases)

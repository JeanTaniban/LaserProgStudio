from __future__ import annotations

import sys

from _path_setup import ROOT  # noqa: F401

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from laserprog_studio.tool_api.diagnostic_lab import CreatorApiDiagnosticLab
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.diag_tool import ToolCoreDiagnosticCreatorTool


def test_headless_creator_api_lab_panel_buttons_execute_actions() -> None:
    ctx = ToolContext()
    lab = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diagnostic")
    lab.setup()

    before = lab.snapshot().actors
    event = ctx.inspector.trigger("add_actor")

    assert event.action_id == "add_actor"
    assert lab.snapshot().actors == before + 1
    assert "Added" in ctx.inspector.value("lab_report")

    ctx.inspector.trigger("select_all")
    assert lab.snapshot().selected >= 1

    selected_before = lab.snapshot().selected
    ctx.inspector.trigger("move_selected")
    assert lab.snapshot().selected == selected_before
    assert "Moved" in ctx.inspector.value("lab_report")

    ctx.inspector.trigger("delete_selected")
    assert lab.snapshot().selected == 0
    assert "Deleted" in ctx.inspector.value("lab_report")


def test_tool_core_diagnostic_open_lab_switches_to_functional_lab_panel() -> None:
    ctx = ToolContext()
    tool = ToolCoreDiagnosticCreatorTool()
    tool.open(ctx)

    ctx.inspector.trigger("open_lab")
    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "tool_core_diagnostic.api_lab"

    before = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diagnostic").snapshot().actors
    ctx.inspector.trigger("add_actor")
    after = CreatorApiDiagnosticLab(ctx, owner_tool="tool_core_diagnostic").snapshot().actors

    assert after == before + 1
    assert "Added" in ctx.inspector.value("lab_report")

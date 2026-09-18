from __future__ import annotations

from pathlib import Path

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.tool_api.core import ToolContext
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def test_plan_tracer_uses_only_the_shared_declarative_creator_panel() -> None:
    panel = get_tool_panel_spec(TOOL_PLAN_TRACE)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"
    assert not Path("src/laserprog_studio/ui/tool_panel_plan_trace.py").exists()


def test_plan_tracer_panel_exposes_professional_user_controls() -> None:
    ctx = ToolContext()
    tool = PlanTrace2DCreatorTool()
    tool.open(ctx)

    panel = ctx.inspector.panel
    assert panel is not None
    assert panel.id == "plan_trace_2d.panel"
    assert "snap" in (panel.description or "").lower()
    assert len(panel.fields()) >= 20

    values = ctx.inspector.values()
    assert values["plan_trace_2d.mode"] == "point"
    assert values["plan_trace_2d.smart_snap"] is True
    assert values["plan_trace_2d.grid_snap"] is False
    assert ctx.inspector.field_state("plan_trace_2d.grid_step").visible is False
    assert set(ctx.inspector.panel.field_ids()) >= {
        "plan_trace_2d.mode",
        "plan_trace_2d.smart_snap",
        "plan_trace_2d.grid_snap",
        "plan_trace_2d.grid_step",
        "plan_trace_2d.counts",
        "plan_trace_2d.metric",
        "plan_trace_2d.status",
        "refresh",
        "restore_faces",
        "delete_selection",
        "reset",
    }

    mode_summary = ctx.modes.describe(owner_tool=TOOL_PLAN_TRACE)
    assert mode_summary["tools"][0]["modes"] == [
        "modify",
        "point",
        "line",
        "polyline",
        "rectangle",
        "circle",
        "arc",
        "half_circle",
        "dimension",
    ]


def test_plan_tracer_inspector_drives_modes_and_snap_state() -> None:
    ctx = ToolContext()
    tool = PlanTrace2DCreatorTool()
    tool.open(ctx)

    ctx.inspector.update_value("plan_trace_2d.grid_snap", True)
    ctx.inspector.update_value("plan_trace_2d.grid_step", 12.5)
    assert ctx.snap.grid_enabled is True
    assert ctx.snap.grid_provider.enabled is True
    assert ctx.snap.grid_provider.grid_size == 12.5
    assert ctx.inspector.field_state("plan_trace_2d.grid_step").visible is True

    ctx.inspector.update_value("plan_trace_2d.smart_snap", False)
    assert ctx.snap.smart_enabled is False

    ctx.inspector.update_value("plan_trace_2d.mode", "rectangle")
    assert tool._state.active_tool == "rectangle"
    assert ctx.modes.active(TOOL_PLAN_TRACE).id == "rectangle"
    assert ctx.inspector.value("plan_trace_2d.tool") == "Rectangle"

    ctx.inspector.trigger("reset")
    assert tool._state.active_tool == "point"
    assert ctx.modes.active(TOOL_PLAN_TRACE).id == "point"
    assert ctx.inspector.value("plan_trace_2d.status").startswith("Pick a face")

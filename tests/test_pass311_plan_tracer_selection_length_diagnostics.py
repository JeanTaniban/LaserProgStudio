# -*- coding: utf-8 -*-
from __future__ import annotations

import json

from laserprog_studio.diagnostics import plan_trace_selection_length_debug as diag
from laserprog_studio.tool_api import ToolContext
from laserprog_studio.tool_api.plan2d.actors import register_plan_line
from laserprog_studio.tool_core.sketch import SketchDocument
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE
from laserprog_studio.tooling.plan_trace_2d.selection_measure import measure_selected_path
from laserprog_studio.tooling.plan_trace_2d_tool import PlanTrace2DCreatorTool


def test_selection_length_diagnostic_records_measurement_and_inspector_manager(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(diag, "_diagnostics_dir", lambda: tmp_path)
    ctx = ToolContext()
    tool = PlanTrace2DCreatorTool()
    ctx.inspector.set_panel(tool._services.overlay._panel())
    sketch = SketchDocument()
    p0 = sketch.add_point((0.0, 0.0), point_id="p0")
    p1 = sketch.add_point((12.0, 0.0), point_id="p1")
    line = sketch.add_line(p0.id, p1.id, line_id="l0")
    actor_id = f"{TOOL_PLAN_TRACE}:line:{line.id}"
    register_plan_line(
        ctx,
        owner_tool=TOOL_PLAN_TRACE,
        line_id=actor_id,
        start_world_pos=(0.0, 0.0, 0.0),
        end_world_pos=(12.0, 0.0, 0.0),
        sketch_line_id=line.id,
    )
    ctx.selection.select(actor_id)

    diag.reset_selection_length_diagnostics("test", ctx=ctx, sketch=sketch)
    measurement = measure_selected_path(ctx, sketch, owner_tool=TOOL_PLAN_TRACE)
    assert measurement is not None
    ctx.inspector.set_display_value("plan_trace_2d.selection_length", measurement.display_text())
    summary = diag.export_selection_length_summary(ctx=ctx, sketch=sketch, reason="test")

    entries = [json.loads(line) for line in diag.selection_length_diagnostics_path().read_text(encoding="utf-8").splitlines()]
    assert any(entry["stage"] == "measurement.done" and entry["result"]["total_length"] == 12.0 for entry in entries)
    assert any(entry["stage"] == "inspector.manager.write" and entry["validated"] != "—" for entry in entries)
    assert summary is not None and summary.exists()
    assert "likely_breakpoint" in summary.read_text(encoding="utf-8")

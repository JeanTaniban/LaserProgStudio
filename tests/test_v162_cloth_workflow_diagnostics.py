from __future__ import annotations

import json

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth import diagnostics as cloth_diag
from laserprog_studio.tooling.cloth.diagnostics import ClothWorkflowDiagnostics
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def test_cloth_diagnostics_require_explicit_debug_preference(monkeypatch) -> None:
    import laserprog_studio.services.debug_mode as debug_mode

    monkeypatch.setattr(debug_mode, "should_record_diagnostics", lambda _owner=None: True)
    monkeypatch.setattr(debug_mode, "debug_mode_source", lambda: "pytest")
    assert not cloth_diag.diagnostics_enabled()

    monkeypatch.setattr(debug_mode, "debug_mode_source", lambda: "settings")
    assert cloth_diag.diagnostics_enabled()


def test_disabled_cloth_recorder_never_writes_files(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cloth_diag, "_diagnostics_dir", lambda: tmp_path)
    recorder = ClothWorkflowDiagnostics()
    recorder.enabled = False
    recorder.record("should.not.exist")
    assert recorder.export(reason="disabled") is None
    assert not list(tmp_path.iterdir())


def test_close_attempt_exports_solver_overlay_and_state_diagnostics(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cloth_diag, "_diagnostics_dir", lambda: tmp_path)
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    second = tool._drawing.create_surface_from_positions(((20, 0, 0), (30, 0, 0), (30, 10, 0), (20, 10, 0)))
    assert first.committed and second.committed
    tool._set_selected_textile_groups(((first.created_patch_id,), (second.created_patch_id,)))
    tool._sync_workspace_selection()

    recorder = ClothWorkflowDiagnostics()
    recorder.enabled = True
    recorder.reset(reason="test", tool=tool, ctx=ctx)
    tool._cloth_diagnostics = recorder
    tool._enter_close(ctx)

    jsonl_path, json_path, md_path = cloth_diag.diagnostics_paths()
    assert jsonl_path.exists() and json_path.exists() and md_path.exists()
    events = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    stages = {event["stage"] for event in events}
    assert "close.analyze.solver.input.normalized" in stages
    assert "close.analyze.solver.anchors.built" in stages
    assert "close.analyze.proposals_assigned" in stages
    assert "close.analyze.overlay_after_solver" in stages
    assert ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID) is not None
    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["latest_state"]["overlay"]["present"] is True
    assert summary["latest_state"]["workspace"]["overlay_mode"] == "close"


def test_close_exception_exports_traceback_and_keeps_overlay(tmp_path, monkeypatch) -> None:
    import laserprog_studio.tooling.cloth_tool as cloth_tool_module

    monkeypatch.setattr(cloth_diag, "_diagnostics_dir", lambda: tmp_path)
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    second = tool._drawing.create_surface_from_positions(((20, 0, 0), (30, 0, 0), (30, 10, 0), (20, 10, 0)))
    tool._set_selected_textile_groups(((first.created_patch_id,), (second.created_patch_id,)))
    tool._sync_workspace_selection()
    recorder = ClothWorkflowDiagnostics()
    recorder.enabled = True
    recorder.reset(reason="test", tool=tool, ctx=ctx)
    tool._cloth_diagnostics = recorder

    monkeypatch.setattr(cloth_tool_module, "analyze_textile_close_groups", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("close boom")))
    tool._enter_close(ctx)

    summary = json.loads(cloth_diag.diagnostics_paths()[1].read_text(encoding="utf-8"))
    assert summary["error_count"] >= 1
    assert any("close boom" in str(error.get("traceback", "")) for error in summary["errors"])
    assert ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID) is not None

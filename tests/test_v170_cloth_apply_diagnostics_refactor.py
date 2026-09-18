from __future__ import annotations

import json
from types import SimpleNamespace

from laserprog_studio.project import ProjectStore
from laserprog_studio.tool_api.core import ToolContext
from laserprog_studio.tooling.cloth.diagnostics import ClothWorkflowDiagnostics
from laserprog_studio.tooling.cloth.models import ClothWorkflowPhase
from laserprog_studio.tooling.cloth.workflow_actions import canonical_cloth_action
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _project_context() -> tuple[ToolContext, ProjectStore]:
    store = ProjectStore.new_empty(scene_name="Main")
    owner = SimpleNamespace(
        project_store=store,
        rebuild_scene=lambda **_kwargs: None,
        update_preview_state=lambda: None,
        _sync_history_buttons=lambda: None,
        sync_scene_tabs=lambda: None,
        update_project_title=lambda: None,
        update_inspector=lambda: None,
    )
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store.active_model_store)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    return ctx, store


def _surface(tool: ClothCreatorTool) -> None:
    outcome = tool._drawing.create_surface_from_positions(
        ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 10.0, 0.0), (0.0, 10.0, 0.0))
    )
    assert outcome.committed


def test_apply_recovers_stale_validation_blocked_phase() -> None:
    ctx, store = _project_context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    _surface(tool)
    tool.session.phase = ClothWorkflowPhase.VALIDATION_BLOCKED

    assert tool._apply_and_continue(ctx)
    assert store.active_model_store.committed_meshes
    assert tool.session.phase is ClothWorkflowPhase.EDITING


def test_apply_route_exception_is_visible_instead_of_being_rethrown() -> None:
    tool = ClothCreatorTool()
    messages: list[str] = []
    tool._apply_and_continue = lambda _ctx: (_ for _ in ()).throw(RuntimeError("route exploded"))  # type: ignore[method-assign]
    tool._sync = lambda _ctx, message, **_kwargs: messages.append(str(message))  # type: ignore[method-assign]

    tool.on_overlay_button_clicked("cloth.workflow.action.apply_output", SimpleNamespace(status=SimpleNamespace(info=lambda _m: None)))

    assert messages
    assert "stopped safely" in messages[-1]
    assert "route exploded" in messages[-1]


def test_apply_pipeline_reports_missing_scene_api() -> None:
    tool = ClothCreatorTool()
    _surface(tool)
    tool.session.phase = ClothWorkflowPhase.EDITING
    messages: list[str] = []
    tool._sync = lambda _ctx, message, **_kwargs: messages.append(str(message))  # type: ignore[method-assign]
    ctx = SimpleNamespace(status=SimpleNamespace(info=lambda _m: None))

    assert not tool.on_apply(ctx)
    assert any("linked-output scene API" in message for message in messages)


def test_apply_diagnostics_export_contains_pipeline_stages(tmp_path, monkeypatch) -> None:
    from laserprog_studio.tooling.cloth import diagnostics as diagnostic_module

    ctx, _store = _project_context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    _surface(tool)

    recorder = ClothWorkflowDiagnostics(owner=None)
    recorder.enabled = True
    recorder.reset(reason="test", tool=tool, ctx=ctx)
    tool._cloth_diagnostics = recorder

    paths = (
        tmp_path / "cloth_workflow_debug.jsonl",
        tmp_path / "cloth_workflow_debug.json",
        tmp_path / "cloth_workflow_debug.md",
    )
    monkeypatch.setattr(diagnostic_module, "diagnostics_paths", lambda: paths)

    assert tool._apply_and_continue(ctx)

    payload = json.loads(paths[1].read_text(encoding="utf-8"))
    stages = payload["stage_counts"]
    assert stages["apply.request.start"] >= 1
    assert stages["apply.pipeline.prepare_plan.end"] >= 1
    assert stages["apply.pipeline.scene_write.end"] >= 1
    assert payload["latest_apply_events"]
    assert payload["latest_state"]["apply"]["validation_present"] is True


def test_action_aliases_are_canonicalized_in_one_place() -> None:
    assert canonical_cloth_action("apply_continue") == "apply_output"
    assert canonical_cloth_action("apply_close") == "apply_closure"
    assert canonical_cloth_action("open_close") == "open_closure"


def test_qt_overlay_diagnostics_follow_preferences_for_cloth(monkeypatch) -> None:
    from laserprog_studio.services import debug_mode
    from laserprog_studio.tool_core.overlay import qt_edit_diagnostics

    monkeypatch.setattr(debug_mode, "should_record_diagnostics", lambda _owner=None: True)
    assert qt_edit_diagnostics._should_record(button_id="cloth.workflow.action.apply_output")

    monkeypatch.setattr(debug_mode, "should_record_diagnostics", lambda _owner=None: False)
    assert not qt_edit_diagnostics._should_record(button_id="cloth.workflow.action.apply_output")


def test_draw_polyline_action_is_not_misrouted_to_open_draw() -> None:
    assert canonical_cloth_action("draw_polyline") == "draw_polyline"


def test_real_overlay_apply_button_runs_full_pipeline() -> None:
    ctx, store = _project_context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    _surface(tool)

    tool.on_overlay_button_clicked("cloth.workflow.action.apply_output", ctx)

    assert store.active_model_store.committed_meshes
    assert tool.session.phase is ClothWorkflowPhase.EDITING
    assert tool.session.editing_existing is True

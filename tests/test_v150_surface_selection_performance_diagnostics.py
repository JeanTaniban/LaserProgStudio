from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tooling.smart_surface_selection_diagnostics import SurfaceSelectionPerformanceRecorder
from laserprog_studio.tooling.smart_surface_selection_test_tool import SmartSurfaceSelectionTestCreatorTool


def _cube() -> WorkMesh:
    vertices = [
        (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    return WorkMesh("Cube", vertices, triangles)


def test_auto_diagnostics_expose_all_levels_and_phase_timings() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    events: list[tuple[str, dict]] = []
    result = surface_selection.auto_surface_region(snapshot, 0, diagnostics=lambda stage, payload: events.append((stage, payload)))
    assert result.automatic
    assert len(events) == 1
    stage, payload = events[0]
    assert stage == "auto.solve"
    assert payload["level_count"] == 40
    assert len(payload["levels"]) == 40
    assert payload["elapsed_ms"] >= payload["candidates_ms"]
    assert {"region_ms", "boundary_ms", "metrics_ms", "crossing_evaluations"}.issubset(payload["levels"][0])


def test_snapshot_caches_area_aggregates_and_lookup_maps() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    assert snapshot.total_area == sum(snapshot.areas)
    assert snapshot.mean_area == snapshot.total_area / len(snapshot.areas)
    assert snapshot.edge_face_map is snapshot.edge_face_lookup
    assert snapshot.shared_edge_map is snapshot.shared_edge_lookup


def test_recorder_exports_jsonl_json_and_markdown(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    recorder = SurfaceSelectionPerformanceRecorder(enabled=True)
    recorder.reset(reason="test")
    operation = recorder.begin("hover", mesh_faces=120)
    operation.sink("evaluate.total", elapsed_ms=12.5, mesh_faces=120)
    operation.finish(outcome="ok", selected_faces=20)
    paths = recorder.export(reason="test_export")
    assert all(path.exists() for path in paths)
    assert "evaluate.total" in paths[0].read_text(encoding="utf-8")
    assert "End-to-end operations" in paths[2].read_text(encoding="utf-8")


def test_click_can_adopt_the_existing_hover_result_without_recomputing() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    hover = surface_selection.auto_surface_region(snapshot, 0)
    tool = SmartSurfaceSelectionTestCreatorTool()
    tool._diagnostics_enabled = False
    tool._diagnostics.enabled = False
    tool._hover_snapshot = snapshot
    tool._hover_face = 0
    tool._hover_result = hover
    tool._pick = lambda _ctx, _screen, operation=None: (None, snapshot, 0)
    tool._sync = lambda *_args, **_kwargs: None
    tool._update_timing_fields = lambda *_args, **_kwargs: None
    ctx = ToolContext()
    event = SimpleNamespace(screen_pos=(10.0, 10.0), shift=False, ctrl=False)
    assert tool._handle_click(ctx, event)
    assert tool._session.result is hover
    assert tool._session.seed_face == 0


def test_test_tool_panel_exposes_performance_diagnostics(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tool = SmartSurfaceSelectionTestCreatorTool()
    ctx = ToolContext()
    tool.on_open(ctx)
    try:
        panel = ctx.inspector.panel
        assert panel is not None
        assert {"capture_diagnostics", "last_hover_ms", "last_click_ms", "diagnostics_path"}.issubset(panel.field_ids())
    finally:
        tool.on_close(ctx)

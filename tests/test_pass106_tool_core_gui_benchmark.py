# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import CoreDiagRunner, ToolCoreGuiBenchmark


def test_pass106_deep_gui_benchmark_compares_multiple_approaches() -> None:
    report = ToolCoreGuiBenchmark().run()

    case_ids = {result.case_id for result in report.results}
    assert "gpu_glyph_mapper" in case_ids
    assert "single_actor_point_cloud" in case_ids
    assert "actor_churn_reference" in case_ids
    assert "line_polydata_batch" in case_ids
    assert len(report.results) >= 6
    assert report.best() is not None
    assert "actor churn" in "\n".join(report.bugs).lower()


def test_pass106_benchmark_report_exports_markdown_with_recommendation() -> None:
    report = ToolCoreGuiBenchmark().run()
    text = report.to_markdown()

    assert "Tool Core GUI/Gizmo benchmark" in text
    assert "vtkGlyph3DMapper" in text
    assert "Recommendation" in text
    assert "Actor churn" in text or "actor churn" in text


def test_pass106_runner_exposes_deep_gui_benchmark() -> None:
    runner = CoreDiagRunner()
    snap = runner.run_gui_benchmark()

    assert runner.last_bench_report is not None
    assert snap.profiler_values.get("diag.gui_benchmark.runs") == 1
    assert any("GUI benchmark" in entry for entry in runner.log)


def test_pass106_diagnostic_panel_exposes_benchmark_actions() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])
    assert "API benchmark" in source
    assert "run_api_lab_benchmark" in source


def test_pass106_live_benchmark_module_has_expected_vtk_and_cleanup_paths() -> None:
    source = Path("src/laserprog_studio/application/tool_core_diag_bench.py").read_text(encoding="utf-8")
    assert "vtkGlyph3DMapper" in source
    assert "clear_tool_core_bench_scene" in source
    assert "actor churn canary" in source
    assert "Modified()" in source


def test_pass106_doc_exists() -> None:
    text = Path("docs/archive/passes/pass106_tool_core_deep_gui_benchmark.md").read_text(encoding="utf-8")
    assert "vtkGlyph3DMapper-style cache" in text
    assert "No actor creation during drag" in text

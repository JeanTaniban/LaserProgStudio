# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.diagnostic import BenchmarkAnalyzer, BenchmarkMarkdownParser, CoreDiagRunner, ToolCoreGuiBenchmark


def test_pass107_report_parser_detects_live_text_and_actor_churn_flags() -> None:
    text = """
- **batched PolyData points**: 0.302 ms/step, actors 1/0, bugs: none
- **vtkGlyph3DMapper cached spheres**: 1.424 ms/step, actors 1/0, bugs: none
- **limited text labels**: 31.879 ms/step, actors 1/0, bugs: Average step above 16 ms; likely visible lag
- **actor churn canary**: 199.008 ms/step, actors 240/216, bugs: Actor churn detected by design; production tools must avoid this pattern
"""
    metrics = BenchmarkMarkdownParser().parse(text)
    analysis = BenchmarkAnalyzer().analyze(metrics)

    codes = {finding.code for finding in analysis.findings}
    assert "TEXT_LABELS_TOO_SLOW" in codes
    assert "ACTOR_CHURN_FORBIDDEN" in codes
    assert any(decision.selected == "vtkGlyph3DMapper cached glyphs" for decision in analysis.decisions)
    assert "hover-only" in analysis.to_markdown()


def test_pass107_benchmark_adds_lod_glyphs_and_hover_only_label_cases() -> None:
    report = ToolCoreGuiBenchmark().run()
    ids = {result.case_id for result in report.results}

    assert "glyph_lod_cache" in ids
    assert "hover_only_label" in ids
    assert "interactive LOD" in report.to_markdown()
    assert "hover-only" in report.recommendation or "hover-only" in report.to_markdown()


def test_pass107_runner_exposes_benchmark_analysis_policy() -> None:
    runner = CoreDiagRunner()
    runner.run_gui_benchmark()
    snapshot = runner.run_benchmark_analysis()

    assert runner.last_diag_analysis is not None
    assert runner.last_diag_analysis.decisions
    assert snapshot.profiler_values.get("diag.benchmark_analysis.runs") == 1
    assert any("Benchmark analysis" in entry for entry in runner.log)


def test_pass107_diagnostic_panel_exposes_analysis_buttons() -> None:
    source = "\n".join([
        Path("src/laserprog_studio/ui/tool_panel_factory.py").read_text(encoding="utf-8"),
        Path("src/laserprog_studio/tooling/diag_tool.py").read_text(encoding="utf-8"),
    ])

    assert "Full validation" in source
    assert "run_full_api_validation" in source


def test_pass107_live_benchmark_contains_text_alternatives_and_lod_probe() -> None:
    source = Path("src/laserprog_studio/application/tool_core_diag_bench.py").read_text(encoding="utf-8")

    assert "cached glyphs interactive LOD" in source
    assert "single hover text label" in source
    assert "limited text labels" in source
    assert "low-detail during drag" in source


def test_pass107_docs_exist() -> None:
    text = Path("docs/archive/passes/pass107_tool_core_feedback_analysis.md").read_text(encoding="utf-8")

    assert "TEXT_LABELS_TOO_SLOW" in text
    assert "ACTOR_CHURN_FORBIDDEN" in text
    assert "vtkGlyph3DMapper" in text

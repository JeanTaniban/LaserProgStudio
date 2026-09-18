# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Callable

from ...studio_log import log_exception
from ...tool_core.diagnostic import BenchmarkAnalyzer, CoreDiagSnapshot, ProbeMetric
from ..tool_core_diag_scene import ToolCoreDiagScenePainter


class ToolCoreDiagReportingLayer:
    """Extracted responsibilities for :class:`ToolCoreDiagController`."""

    def analyze_saved_benchmark_report(self) -> None:
        try:
            from pathlib import Path

            path = Path.cwd() / "diagnostics" / "tool_core_gui_benchmark.md"
            if not path.exists():
                self.status_message("No saved benchmark report found", 2200)
                self._write_report("Saved benchmark report not found")
                return
            analysis = BenchmarkAnalyzer().analyze_markdown(path.read_text(encoding="utf-8"))
            self.runner.last_diag_analysis = analysis
            self._last_report_path = str(path)
            self._write_report("Saved benchmark report analyzed")
            self.status_message("Saved benchmark report analyzed", 1800)
        except Exception:
            log_exception("tool_core_diag_analyze_saved_benchmark_report")
            self.status_message("Benchmark report analysis failed; see logs", 2600)

    def export_overlay_drag_diagnostics(self) -> None:
        """Write the draggable overlay diagnostic report for user feedback."""
        try:
            from pathlib import Path

            out_dir = Path.cwd() / "diagnostics"
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / "tool_core_overlay_drag.md"
            report = self.runner.ctx.overlay.drag_report()
            out.write_text(report.to_markdown(), encoding="utf-8")
            self._last_overlay_drag_report_path = str(out)
            self._write_report("Overlay drag diagnostics exported")
            self.status_message("Overlay drag diagnostics exported", 2200)
        except Exception:
            log_exception("tool_core_diag_export_overlay_drag_diagnostics")
            self.status_message("Overlay drag diagnostic export failed; see logs", 2600)

    def _run(self, label: str, func: Callable[[], CoreDiagSnapshot], *, render_scene: bool = False) -> None:
        try:
            snapshot = func()
            if render_scene:
                self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            self._sync_overlay_windows()
            self._write_report(label, snapshot)
            self.status_message(f"{label} OK", 1800)
        except Exception:
            log_exception(f"tool_core_diag_{label.lower().replace(' ', '_')}")
            self.status_message(f"{label} failed; see logs", 2600)

    def _write_report(self, title: str, snapshot: CoreDiagSnapshot | None = None) -> None:
        if snapshot is None:
            snapshot = self.runner.snapshot()
        stats = self.runner.backend_stats()
        bench_report = self.runner.last_bench_report
        lines = [
            f"{title}",
            "",
            f"Handles: {snapshot.handles}",
            f"Previews: {snapshot.previews}",
            f"Overlay buttons: {snapshot.overlay_buttons}",
            f"Overlay windows: {len(self.runner.ctx.overlay.windows)}",
            f"Selected items: {snapshot.selected}",
            f"Faces: {snapshot.faces}",
            f"Undo commands: {snapshot.commands_done}",
            f"Snap cache rebuilds: {snapshot.snap_cache_rebuilds}",
            f"Camera size mode: {self.camera_size_update_mode}",
            f"Camera size refreshes: {self._camera_size_refresh_count}",
            f"Minimal dot normal: {self._minimal_dot_normal_px} px",
            f"Minimal dot hover/grab: {self._minimal_dot_active_px} px",
        ]
        drag_report = self.runner.ctx.overlay.drag_report()
        lines.extend([
            f"Overlay drag samples: {len(drag_report.samples)}",
            f"Overlay drag issues: {len(drag_report.issues)}",
        ])
        for issue in drag_report.issues[:4]:
            lines.append(f"  ! {issue.code}: {issue.message}")
        if self._last_scene_stats:
            lines.extend(["", "Viewport showcase:"])
            for key, value in sorted(self._last_scene_stats.items()):
                lines.append(f"  {key}: {value}")
        if bench_report is not None:
            best = bench_report.best()
            lines.extend(["", "GUI benchmark:"])
            if best is not None:
                lines.append(f"  best: {best.label}")
                lines.append(f"  avg: {best.avg_ms:.4f} ms/update")
                lines.append(f"  score: {best.score:.2f}")
            lines.append(f"  flags: {len(bench_report.bugs)}")
            lines.append(f"  recommendation: {bench_report.recommendation}")
        analysis = getattr(self.runner, "last_diag_analysis", None)
        if analysis is not None:
            lines.extend(["", "Benchmark analysis:"])
            lines.append(f"  blockers: {len(analysis.blockers)}")
            lines.append(f"  warnings: {len(analysis.warnings)}")
            for decision in analysis.decisions[:5]:
                lines.append(f"  - {decision.topic}: {decision.selected}")
            for finding in analysis.findings[:5]:
                lines.append(f"  ! {finding.code}: {finding.message}")
        api_lab_benchmark = getattr(self.runner, "last_api_lab_benchmark", None)
        if api_lab_benchmark is not None:
            lines.extend(["", "Creator API Lab benchmark:"])
            lines.append(f"  status: {'PASS' if api_lab_benchmark.ok else 'FAIL'}")
            lines.append(f"  cases: {len(api_lab_benchmark.cases)}")
            for case in api_lab_benchmark.cases:
                marker = "OK" if case.passed else "FAIL"
                lines.append(f"  - {marker} {case.name}: {case.avg_ms:.4f} ms ({case.details})")
            for flag in api_lab_benchmark.flags:
                lines.append(f"  ! {flag}")

        api_report = getattr(self.runner, "last_api_test_report", None)
        if api_report is not None:
            lines.extend(["", "Creator API self-tests:"])
            lines.append(f"  status: {'PASS' if api_report.ok else 'FAIL'}")
            lines.append(f"  cases: {api_report.passed}/{api_report.total}")
            for case in api_report.cases:
                marker = "OK" if case.passed else "FAIL"
                lines.append(f"  - {marker} {case.category} / {case.name}: {case.details} ({case.duration_ms:.2f} ms)")

        if self._last_live_bench:
            lines.extend(["", "Live viewport benchmark:"])
            for key, value in sorted(self._last_live_bench.items()):
                if key == "results":
                    continue
                lines.append(f"  {key}: {value}")
            for result in self._last_live_bench.get("results", []) if isinstance(self._last_live_bench, dict) else []:
                try:
                    bug_text = "; ".join(result.bugs) if result.bugs else "ok"
                    lines.append(f"  - {result.label}: {result.avg_ms:.3f} ms/step, actors {result.actors_created}/{result.actors_removed}, {bug_text}")
                except Exception:
                    pass
        if self._last_report_path:
            lines.extend(["", f"Report file: {self._last_report_path}"])
        if self._last_overlay_drag_report_path:
            lines.extend(["", f"Overlay drag report: {self._last_overlay_drag_report_path}"])
        if stats:
            lines.extend(
                [
                    "",
                    "Gizmo backend:",
                    f"  created: {stats.get('created', 0)}",
                    f"  pos updates: {stats.get('position_updates', 0)}",
                    f"  visibility: {stats.get('visibility_updates', 0)}",
                    f"  removed: {stats.get('removed', 0)}",
                    f"  light renders: {stats.get('light_renders', 0)}",
                    f"  full renders: {stats.get('full_renders', 0)}",
                ]
            )
        if snapshot.profiler_values:
            lines.append("")
            lines.append("Profiler:")
            for key, value in sorted(snapshot.profiler_values.items()):
                lines.append(f"  {key}: {value}")
        if self.runner.log:
            lines.append("")
            lines.append("Log:")
            lines.extend(f"  - {entry}" for entry in self.runner.log[-10:])
        text = "\n".join(lines)
        owner = self.owner
        label = getattr(owner, "tool_core_diag_report", None)
        if label is not None and hasattr(label, "setPlainText"):
            try:
                label.setPlainText(text)
            except Exception:
                pass
        try:
            self.ui_log(f"[TOOL_CORE_DIAG] {title}")
        except Exception:
            pass

    def _refresh_analysis_from_current_results(self) -> None:
        metrics: list[ProbeMetric] = []
        report = self.runner.last_bench_report
        if report is not None:
            metrics.extend(
                ProbeMetric(
                    result.label,
                    result.avg_ms,
                    result.actors_created,
                    result.actors_deleted,
                    tuple(result.bugs),
                    source="deterministic",
                )
                for result in report.results
            )
        if isinstance(self._last_live_bench, dict):
            for result in self._last_live_bench.get("results", []):
                try:
                    metrics.append(
                        ProbeMetric(
                            result.label,
                            float(result.avg_ms),
                            int(result.actors_created),
                            int(result.actors_removed),
                            tuple(result.bugs),
                            source="live",
                        )
                    )
                except Exception:
                    pass
        if metrics:
            self.runner.last_diag_analysis = BenchmarkAnalyzer().analyze(metrics)

    def _export_benchmark_report(self) -> None:
        report = self.runner.last_bench_report
        if report is None:
            return
        try:
            from pathlib import Path

            root = Path.cwd()
            out_dir = root / "diagnostics"
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / "tool_core_gui_benchmark.md"
            text = report.to_markdown()
            api_lab_benchmark = getattr(self.runner, "last_api_lab_benchmark", None)
            if api_lab_benchmark is not None:
                text += "\n\n" + api_lab_benchmark.to_markdown() + "\n"
            if self._last_live_bench:
                text += "\n\n## Live viewport probe\n\n"
                for result in self._last_live_bench.get("results", []) if isinstance(self._last_live_bench, dict) else []:
                    bugs = ", ".join(result.bugs) if result.bugs else "none"
                    text += f"- **{result.label}**: {result.avg_ms:.3f} ms/step, actors {result.actors_created}/{result.actors_removed}, bugs: {bugs}\n"
                live_bugs = self._last_live_bench.get("bugs", []) if isinstance(self._last_live_bench, dict) else []
                if live_bugs:
                    text += "\nLive flags:\n" + "\n".join(f"- {bug}" for bug in live_bugs) + "\n"
            analysis = getattr(self.runner, "last_diag_analysis", None)
            if analysis is not None:
                text += "\n\n" + analysis.to_markdown() + "\n"
            out.write_text(text, encoding="utf-8")
            self._last_report_path = str(out)
        except Exception:
            log_exception("tool_core_diag_export_benchmark_report")



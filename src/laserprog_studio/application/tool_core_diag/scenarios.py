# -*- coding: utf-8 -*-
from __future__ import annotations

from ...studio_log import log_exception
from ..tool_core_diag_bench import LiveViewportBenchmark, clear_tool_core_bench_scene
from ..tool_core_diag_scene import ToolCoreDiagScenePainter, clear_tool_core_diag_scene


class ToolCoreDiagScenarioLayer:
    """Extracted responsibilities for :class:`ToolCoreDiagController`."""

    def run_overlay(self) -> None:
        self._run("Overlay", self.runner.run_overlay)

    def run_overlay_types(self) -> None:
        cursor = (int(self._last_pointer_px[0]), int(self._last_pointer_px[1]))
        self.runner.ctx.overlay.clear_drag_diagnostics()
        self._run("Overlay types", lambda: self.runner.run_overlay_types(cursor), render_scene=False)
        self._sync_overlay_windows()

    def run_gizmos(self) -> None:
        self._run("Gizmos", self.runner.run_gizmos)

    def run_drag(self) -> None:
        self._run("Drag burst", self.runner.run_drag_burst)

    def run_snap(self) -> None:
        self._run("Snap + preview", self.runner.run_snap_preview)

    def run_faces(self) -> None:
        self._run("Faces + command stack", self.runner.run_face_command)

    def run_events(self) -> None:
        self._run("Selection + events", self.runner.run_selection_events)

    def run_ui_showcase(self) -> None:
        self._run("UI/Gizmo showcase", self.runner.run_ui_showcase, render_scene=True)

    def run_ui_handles(self) -> None:
        self._run("UI handle states", self.runner.run_ui_handles, render_scene=True)

    def run_ui_primitives(self) -> None:
        self._run("UI primitives", self.runner.run_ui_primitives, render_scene=True)

    def run_ui_text(self) -> None:
        self._run("UI text", self.runner.run_ui_text, render_scene=True)

    def run_ui_stress(self) -> None:
        self._run("UI stress", self.runner.run_ui_stress, render_scene=True)

    def run_selection_demo(self) -> None:
        self._handle_demo_grabbed_id = None
        self._selection_demo_active = True
        self._selection_drag_last_world = None
        self._run("Selection demo", self.runner.run_selection_demo, render_scene=True)

    def run_api_lab_setup(self) -> None:
        self._handle_demo_grabbed_id = None
        self._selection_demo_active = False
        self._api_lab_active = True
        self._selection_drag_last_world = None
        self._run("Creator API Lab", self.runner.run_api_lab_setup, render_scene=True)

    def api_lab_set_options(self, *, actor_kind: str | None = None, interaction: str | None = None, move: str | None = None, point_style: str | None = None, line_style: str | None = None, visual_state: str | None = None, box_enabled: str | bool | None = None, box_target: str | None = None, box_mode: str | None = None, box_inside_policy: str | None = None) -> None:
        try:
            self.runner.api_lab_set_options(actor_kind=actor_kind, interaction=interaction, move=move, point_style=point_style, line_style=line_style, visual_state=visual_state, box_enabled=box_enabled, box_target=box_target, box_mode=box_mode, box_inside_policy=box_inside_policy)
            self._write_report("API Lab options updated")
        except Exception:
            log_exception("tool_core_diag_api_lab_set_options")

    def api_lab_add_actor(self) -> None:
        self._api_lab_active = True
        self._run("API Lab add actor", self.runner.api_lab_add_actor, render_scene=True)

    def api_lab_delete_selected(self) -> None:
        self._api_lab_active = True
        self._run("API Lab delete selected", self.runner.api_lab_delete_selected, render_scene=True)

    def api_lab_select_all(self) -> None:
        self._api_lab_active = True
        self._run("API Lab select all", self.runner.api_lab_select_all, render_scene=True)

    def api_lab_move_selected(self) -> None:
        self._api_lab_active = True
        self._run("API Lab move selected", self.runner.api_lab_move_selected, render_scene=True)

    def api_lab_clear(self) -> None:
        self._api_lab_active = True
        removed = clear_tool_core_diag_scene(self.owner)
        self._last_scene_stats = {"status": "cleared", "actors": removed}
        self._run("API Lab clear", self.runner.api_lab_clear, render_scene=True)

    def run_api_lab_benchmark(self) -> None:
        self._api_lab_active = True
        self._run("API Lab benchmark", self.runner.run_api_lab_benchmark, render_scene=True)
        self._refresh_analysis_from_current_results()
        self._export_benchmark_report()

    def run_full_api_validation(self) -> None:
        self._api_lab_active = True
        self._run("Full API validation", self.runner.run_full_api_validation, render_scene=True)
        self._last_live_bench = LiveViewportBenchmark(self.owner).run()
        self._refresh_analysis_from_current_results()
        self._export_benchmark_report()
        self._write_report("Full API validation")

    def run_creator_api_demo(self) -> None:
        self._handle_demo_grabbed_id = None
        self._selection_demo_active = False
        self._selection_drag_last_world = None
        self._run("Creator API demo", self.runner.run_creator_api_demo, render_scene=True)

    def run_creator_api_tests(self) -> None:
        self._handle_demo_grabbed_id = None
        self._selection_demo_active = False
        self._selection_drag_last_world = None
        try:
            snapshot = self.runner.run_creator_api_tests()
            self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            self._sync_overlay_windows()
            self._write_report("Creator API self-tests", snapshot)
            report = getattr(self.runner, "last_api_test_report", None)
            if report is not None and not report.ok:
                self.status_message(f"Creator API tests failed: {report.failed}/{report.total}", 3200)
            else:
                self.status_message("Creator API tests OK", 2200)
        except Exception:
            log_exception("tool_core_diag_creator_api_tests")
            self.status_message("Creator API tests failed; see logs", 2600)

    def run_handle_demo(self) -> None:
        self._selection_demo_active = False
        self._handle_demo_grabbed_id = None
        self._run("Handle demo", self.runner.run_handle_demo, render_scene=True)

    def run_handle_demo_hover(self) -> None:
        self._selection_demo_active = False
        self._handle_demo_grabbed_id = None
        self._run("Handle demo hover", self.runner.run_handle_demo_hover, render_scene=True)

    def run_handle_demo_grabbed(self) -> None:
        self._selection_demo_active = False
        self._handle_demo_grabbed_id = None
        self._run("Handle demo grabbed", self.runner.run_handle_demo_grabbed, render_scene=True)

    def run_gui_benchmark(self) -> None:
        self._run("Deep GUI benchmark", self.runner.run_gui_benchmark)
        self._export_benchmark_report()

    def run_live_gui_benchmark(self) -> None:
        try:
            snapshot = self.runner.run_gui_benchmark()
            self._last_live_bench = LiveViewportBenchmark(self.owner).run()
            self._refresh_analysis_from_current_results()
            self._write_report("Live GUI benchmark", snapshot)
            self._export_benchmark_report()
            self.status_message("Live GUI benchmark OK", 1800)
        except Exception:
            log_exception("tool_core_diag_live_gui_benchmark")
            self.status_message("Live GUI benchmark failed; see logs", 2600)

    def run_benchmark_analysis(self) -> None:
        self._run("Benchmark analysis", self.runner.run_benchmark_analysis)
        self._refresh_analysis_from_current_results()
        self._export_benchmark_report()
        self._write_report("Benchmark analysis")

    def clear_gui_benchmark(self) -> None:
        removed = clear_tool_core_bench_scene(self.owner)
        self._last_live_bench = {"status": "cleared", "removed": removed}
        self._write_report("GUI benchmark viewport cleared")

    def clear_ui_showcase(self) -> None:
        removed = clear_tool_core_diag_scene(self.owner)
        self.runner.ctx.overlay.close_tool_windows("tool_core_diag", include_persistent=True)
        self._sync_overlay_windows()
        self._last_scene_stats = {"status": "cleared", "actors": removed}
        self._write_report("UI/Gizmo viewport cleared")

    def run_all(self) -> None:
        self._run("Full diagnostic", self.runner.run_all, render_scene=True)



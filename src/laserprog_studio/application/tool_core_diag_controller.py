# -*- coding: utf-8 -*-
from __future__ import annotations

from ..studio_log import log_exception
from ..tool_core.diagnostic import CoreDiagRunner
from .action_controller import WindowController
from .tool_core_diag import (
    ToolCoreDiagOverlayLayer,
    ToolCoreDiagPointerLayer,
    ToolCoreDiagReportingLayer,
    ToolCoreDiagScenarioLayer,
    ToolCoreDiagViewSettingsLayer,
)
from .tool_core_diag_scene import ToolCoreDiagScenePainter, clear_tool_core_diag_scene


class ToolCoreDiagController(
    ToolCoreDiagScenarioLayer,
    ToolCoreDiagOverlayLayer,
    ToolCoreDiagViewSettingsLayer,
    ToolCoreDiagPointerLayer,
    ToolCoreDiagReportingLayer,
    WindowController,
):
    """Bridge between the Qt diagnostic panel and the shared tool-core layers.

    The controller owns the Qt/application lifecycle. Scenario actions, pointer
    interaction, viewport sizing and report generation live in focused mixins
    under :mod:`laserprog_studio.application.tool_core_diag`.
    """

    @classmethod
    def create(cls, context):
        return cls(context)

    def __init__(self, context):
        super().__init__(context)
        self.runner = CoreDiagRunner()
        self._last_scene_stats: dict[str, int | str] = {}
        self._last_live_bench: dict[str, object] = {}
        self._last_report_path: str = ""
        self._last_overlay_drag_report_path: str = ""
        self._handle_demo_grabbed_id: str | None = None
        self._handle_demo_grab_depth: float = 0.5
        self._selection_demo_active: bool = False
        self._api_lab_active: bool = False
        self._api_lab_empty_press_cleared: bool = False
        self._api_lab_empty_press_start: tuple[float, float] | None = None
        self._api_lab_empty_press_had_selection: bool = False
        self._api_lab_box_active: bool = False
        self._selection_drag_last_world: tuple[float, float, float] | None = None
        self._selection_drag_depth: float = 0.5
        self._camera_size_update_mode: str = "end"
        self._camera_size_refresh_count: int = 0
        self._last_pointer_px: tuple[int, int] = (340, 160)
        self._minimal_dot_normal_px: int = int(getattr(self.runner.ctx.gizmos, "minimal_dot_normal_radius_px", 5))
        self._minimal_dot_active_px: int = int(getattr(self.runner.ctx.gizmos, "minimal_dot_active_radius_px", 9))
        self._apply_minimal_dot_size(render=False, write_report=False)

    def open_tool(self) -> None:
        try:
            self.runner.reset()
            self._apply_minimal_dot_size(render=False, write_report=False)
            self._sync_minimal_dot_sliders()
            self._sync_camera_size_button()
            self._api_lab_active = True
            self.runner.run_api_lab_setup()
            self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            self._sync_overlay_windows()
            self._write_report("Creator API Lab opened")
        except Exception:
            log_exception("tool_core_diag_open")

    def close_tool(self, *, render: bool = False) -> None:  # noqa: ARG002
        try:
            self._api_lab_active = False
            self.runner.reset()
            if render:
                clear_tool_core_diag_scene(self.owner)
            self._write_report("Tool Core Diagnostic closed")
        except Exception:
            log_exception("tool_core_diag_close")

    def reset(self) -> None:
        self._api_lab_active = True
        self._run("Reset", self.runner.reset)
        self._run("Creator API Lab", self.runner.run_api_lab_setup, render_scene=True)
        self._apply_minimal_dot_size(render=False, write_report=False)

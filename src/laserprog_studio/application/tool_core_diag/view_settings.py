# -*- coding: utf-8 -*-
from __future__ import annotations

from ...studio_log import log_exception
from ..tool_core_diag_scene import ToolCoreDiagScenePainter


class ToolCoreDiagViewSettingsLayer:
    """Extracted responsibilities for :class:`ToolCoreDiagController`."""

    @property
    def camera_size_update_mode(self) -> str:
        return "live" if self._camera_size_update_mode == "live" else "end"

    def set_camera_size_update_mode(self, mode: str) -> None:
        # Pass114 production policy: keep camera-dependent GUI sizing on the
        # end-of-camera-move path. Live refresh remains blocked here so future
        # tools do not accidentally reintroduce heavy per-frame guide updates.
        self._camera_size_update_mode = "end"
        self._sync_camera_size_button()
        self.refresh_camera_sized_guides(reason="camera size mode: end", render=True, write_report=True)

    def toggle_camera_size_update_mode(self) -> None:
        self.set_camera_size_update_mode("end")

    def refresh_camera_sized_guides(self, *, reason: str = "camera changed", render: bool = True, write_report: bool = False) -> bool:
        """Refresh camera-dependent guide geometry without rebuilding handles.

        Point sprites stay in pixel units, but rings, arrows, axes and other
        world-space guides must be recomputed from the active camera. The
        persistent painter mutates PolyData in place, so this is safe to call
        at the end of a camera move or throttled during live camera motion.
        """
        try:
            if not self._has_camera_sized_guides():
                return False
            self._camera_size_refresh_count += 1
            self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
            self._last_scene_stats["camera_size_mode"] = self.camera_size_update_mode
            self._last_scene_stats["camera_size_refreshes"] = self._camera_size_refresh_count
            if write_report:
                self._write_report(reason)
            return bool(render)
        except Exception:
            log_exception("tool_core_diag_refresh_camera_sized_guides")
            return False

    def refresh_camera_size_live_if_enabled(self) -> bool:
        # End-only mode: no continuous camera refresh in the diagnostic layer.
        return False

    def refresh_camera_size_after_move(self) -> bool:
        if self.camera_size_update_mode == "live":
            # Live mode already refreshes during movement; still do one final
            # pass to catch the exact final camera matrix after VTK settles.
            return self.refresh_camera_sized_guides(reason="camera size final", render=True, write_report=False)
        return self.refresh_camera_sized_guides(reason="camera size end", render=True, write_report=False)

    def _sync_camera_size_button(self) -> None:
        try:
            button = getattr(self.owner, "tool_core_diag_camera_size_button", None)
            if button is None:
                return
            button.blockSignals(True)
            button.setChecked(False)
            button.setEnabled(False)
            button.setText("Camera size: end")
            button.setToolTip("End-only policy: guides resize after camera movement, not continuously.")
            button.blockSignals(False)
        except Exception:
            pass

    def set_minimal_dot_normal_px(self, value: int) -> None:
        self._minimal_dot_normal_px = max(1, int(value))
        if self._minimal_dot_active_px < self._minimal_dot_normal_px:
            self._minimal_dot_active_px = self._minimal_dot_normal_px
        self._apply_minimal_dot_size(render=True, write_report=True)

    def set_minimal_dot_active_px(self, value: int) -> None:
        self._minimal_dot_active_px = max(1, int(value))
        if self._minimal_dot_active_px < self._minimal_dot_normal_px:
            self._minimal_dot_normal_px = self._minimal_dot_active_px
        self._apply_minimal_dot_size(render=True, write_report=True)

    def _apply_minimal_dot_size(self, *, render: bool = True, write_report: bool = False) -> None:
        try:
            self.runner.ctx.gizmos.set_minimal_dot_radii(
                normal_px=self._minimal_dot_normal_px,
                active_px=self._minimal_dot_active_px,
            )
            changed = self.runner.ctx.gizmos.update_style_metrics(
                owner_tool="tool_core_diag",
                style_id="minimal",
                kind_prefix="demo_",
            )
            self._sync_minimal_dot_sliders()
            if render and self._has_handle_demo():
                self._last_scene_stats = ToolCoreDiagScenePainter(self.owner).render_context(self.runner.ctx)
                self._last_scene_stats["minimal_dot_changed"] = changed
                self._last_scene_stats["minimal_dot_normal_px"] = self._minimal_dot_normal_px
                self._last_scene_stats["minimal_dot_active_px"] = self._minimal_dot_active_px
            if write_report:
                self._write_report("Minimal dot size updated")
        except Exception:
            log_exception("tool_core_diag_apply_minimal_dot_size")

    def _sync_minimal_dot_sliders(self) -> None:
        try:
            normal_slider = getattr(self.owner, "tool_core_diag_minimal_normal_slider", None)
            active_slider = getattr(self.owner, "tool_core_diag_minimal_active_slider", None)
            normal_label = getattr(self.owner, "tool_core_diag_minimal_normal_value", None)
            active_label = getattr(self.owner, "tool_core_diag_minimal_active_value", None)
            if normal_slider is not None:
                normal_slider.blockSignals(True)
                normal_slider.setValue(int(self._minimal_dot_normal_px))
                normal_slider.blockSignals(False)
            if active_slider is not None:
                active_slider.blockSignals(True)
                active_slider.setValue(int(self._minimal_dot_active_px))
                active_slider.blockSignals(False)
            if normal_label is not None and hasattr(normal_label, "setText"):
                normal_label.setText(f"{int(self._minimal_dot_normal_px)} px")
            if active_label is not None and hasattr(active_label, "setText"):
                active_label.setText(f"{int(self._minimal_dot_active_px)} px")
        except Exception:
            pass



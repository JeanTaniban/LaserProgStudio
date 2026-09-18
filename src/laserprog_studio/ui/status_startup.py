# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class UIStatusStartupLayer:
    def _build_status_bar(self) -> None:
        self.statusBar().showMessage("LaserProg Studio V18 ready - safe AMD/VTK profile")
        log("[UI] Status bar created")

    def _is_high_volume_diagnostic_log(self, msg: str) -> bool:
        try:
            text = str(msg)
            prefixes = (
                "[GIZMO_DIAG]", "[GIZMO_TRACE]", "[PICKING_DIAG]",
                "[SELECTION_DIAG]", "[TRANSFORM_DIAG]", "[CLIPBOARD_DIAG]",
                "[TEXTURE_GIZMO_EVT]", "[TEXTURE_GIZMO]", "[TEXTURE_GIZMO_MOVE]",
                "[BOUNDS]", "[DISPLAY_PIPELINE]", "[KEY_DIAG]",
            )
            return text.startswith(prefixes)
        except Exception:
            return False

    def _is_optimized_suppressed_log(self, msg: str) -> bool:
        """Return True for normal-use chatter that should not hit UI or disk.

        In optimized mode, logs are intentionally sparse.  Exceptions still go
        through log_exception(), and important project/export/tool milestones are
        kept.  This prevents the diagnostics file and QTextEdit document from
        becoming a performance sink during long sessions.
        """
        try:
            text = str(msg)
            if "[ERROR]" in text or "[ERREUR]" in text or "[WARN]" in text:
                return False
            if self._is_high_volume_diagnostic_log(text):
                return True
            prefixes = (
                "[INSPECTOR]", "[LIGHT_OVERLAY]", "[MATERIAL_RENDER]",
                "[TEXTURE] Actor texture attached", "[TEXTURE] Preview",
                "[3D] Rebuild", "[3D] Scene OK", "[DISPLAY] mode=", "[DISPLAY] edges=",
                "[PICKING] Empty click", "[SELECTION] tool=", "[SELECTION] Cleared",
                "[CAMERA] Focus", "[GIZMO] hidden", "[GIZMO] Start", "[GIZMO] End",
                "[SNAP]", "[VTK]", "[POST_START] Render initial OK",
            )
            return text.startswith(prefixes)
        except Exception:
            return False

    def _performance_debug_enabled(self) -> bool:
        try:
            from ..services.debug_mode import should_record_diagnostics
            return bool(should_record_diagnostics(self))
        except Exception:
            return bool(getattr(self, "_performance_mode", "optimized") == "debug" or getattr(self, "_diagnostic_verbose", False))

    def set_performance_mode(self, mode: str = "optimized") -> None:
        """Switch between optimized runtime and detailed debug diagnostics."""
        try:
            mode = "debug" if str(mode).lower().strip() in {"debug", "diag", "diagnostic", "verbose"} else "optimized"
            self._performance_mode = mode
            self._diagnostic_verbose = mode == "debug"
            try:
                from ..services.debug_mode import set_debug_mode_enabled
                set_debug_mode_enabled(mode == "debug", persist=True)
            except Exception:
                pass
            self._gizmo_hover_min_interval_ms = 16.0 if mode == "debug" else 24.0
            self._texture_drag_min_px = 0.35 if mode == "debug" else 1.0
            self._texture_poll_interval_ms = 33 if mode == "debug" else 50
            self._layout_overlay_sync_delay_ms = 45 if mode == "debug" else 90
            try:
                if hasattr(self, "act_perf_optimized"):
                    self.act_perf_optimized.blockSignals(True)
                    self.act_perf_optimized.setChecked(mode == "optimized")
                    self.act_perf_optimized.blockSignals(False)
                if hasattr(self, "act_perf_debug"):
                    self.act_perf_debug.blockSignals(True)
                    self.act_perf_debug.setChecked(mode == "debug")
                    self.act_perf_debug.blockSignals(False)
            except Exception:
                pass
            try:
                label = "Debug diagnostics ON" if mode == "debug" else "Optimized mode — diagnostics OFF"
                self.statusBar().showMessage(label, 2200)
            except Exception:
                pass
            # This one line is intentionally visible even in optimized mode.
            log(f"[PERF] mode={mode}")
            try:
                self.log_text.append(f"[PERF] mode={mode}")
            except Exception:
                pass
        except Exception:
            log_exception("set_performance_mode")

    def ui_log(self, msg: str) -> None:
        text = str(msg)
        verbose = bool(getattr(self, "_diagnostic_verbose", False))
        optimized = str(getattr(self, "_performance_mode", "optimized")) == "optimized"
        if optimized and self._is_optimized_suppressed_log(text):
            return
        if self._is_high_volume_diagnostic_log(text) and not verbose:
            return
        # In optimized mode, avoid writing every lightweight UI message to disk.
        # Disk flushes and QTextEdit appends were a major source of progressive lag.
        if (not optimized) or bool(getattr(self, "_optimized_log_file_echo", False)):
            log(text)
        elif text.startswith(("[UI]", "[PROJECT]", "[EXPORT]", "[ENGRAVE]", "[PERF]")):
            log(text)
        try:
            self.log_text.append(text)
        except Exception:
            pass

    def _post_start(self) -> None:
        self.ui_log("[POST_START] Window visible. Empty scene ready.")
        self._log_inspector_state_if_changed("post start", force=True)
        self._sync_history_buttons()
        self._sync_light_transform_overlay()
        try:
            self.initialize_empty_viewport_guides(render=False)
        except Exception:
            log_exception("post_start_empty_viewport_guides")
        try:
            self.plotter.render()
            self.ui_log("[POST_START] Render initial OK")
        except Exception:
            log_exception("post_start render")

# -*- coding: utf-8 -*-
from __future__ import annotations

from ...studio_log import log_exception
from ...tool_core.overlay import OverlayFieldSpec, ToolButtonSpec, sync_qt_overlay_windows


class ToolCoreDiagOverlayLayer:
    """Extracted responsibilities for :class:`ToolCoreDiagController`."""

    def show_blender_style_popover(self, qx: float | None = None, qy: float | None = None) -> bool:
        """Open a non-draggable Blender-like middle-click popover near the pointer."""
        try:
            cursor = (
                int(self._last_pointer_px[0] if qx is None else qx),
                int(self._last_pointer_px[1] if qy is None else qy),
            )
            self._last_pointer_px = cursor
            self.runner.ctx.overlay.show_context_popover_at_cursor(
                "diag.overlay.middle_popover",
                owner_tool="tool_core_diag",
                title="Viewport options",
                cursor_px=cursor,
                fields=[
                    self._overlay_field("diag.overlay.middle_popover.mode", "Mode", "Dummy option A"),
                    self._overlay_field("diag.overlay.middle_popover.snap", "Snap", "Smart snap preview"),
                    self._overlay_field("diag.overlay.middle_popover.axis", "Axis", "Local / Global"),
                    self._overlay_field("diag.overlay.middle_popover.note", "Info", "Middle-click popover, non-draggable"),
                ],
                buttons=[
                    self._overlay_button("diag.overlay.middle_popover.option_a", "Option A"),
                    self._overlay_button("diag.overlay.middle_popover.option_b", "Option B"),
                    self._overlay_button("diag.overlay.middle_popover.apply", "Apply"),
                    self._overlay_button("diag.overlay.middle_popover.close", "Close"),
                ],
                width_px=270,
            )
            self._sync_overlay_windows()
            self._write_report("Middle-click Blender-style popover")
            return True
        except Exception:
            log_exception("tool_core_diag_show_blender_style_popover")
            return False

    def close_click_away_overlays(self) -> bool:
        """Close transient click-away overlays after a viewport click."""
        try:
            closed = self.runner.ctx.overlay.handle_click_outside(owner_tool="tool_core_diag")
            if closed:
                self._sync_overlay_windows()
                self._write_report("Click-away overlays closed")
            return bool(closed)
        except Exception:
            log_exception("tool_core_diag_close_click_away_overlays")
            return False

    @staticmethod
    def _overlay_field(field_id: str, label: str, value: str):
        from ..tool_core.overlay import OverlayFieldSpec

        return OverlayFieldSpec(field_id, label, value, kind="info")

    @staticmethod
    def _overlay_button(button_id: str, label: str):
        from ..tool_core.overlay import ToolButtonSpec

        return ToolButtonSpec(button_id, label, icon="option", checkable=False, enabled=True)

    def _sync_overlay_windows(self) -> None:
        try:
            visible = sync_qt_overlay_windows(self.owner, self.runner.ctx.overlay)
            self._last_scene_stats["qt_overlay_windows"] = visible
        except Exception:
            log_exception("tool_core_diag_sync_overlay_windows")



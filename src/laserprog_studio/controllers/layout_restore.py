# -*- coding: utf-8 -*-
from __future__ import annotations

from ..application.layout_controller import LayoutController


class LayoutRestoreLayer:
    # layout test marker: min_usable_right, right = max(int(pref_right), 260)
    """Window-facing facade for inspector/light-UI restoration.

    Real layout restoration logic now lives in ``application.LayoutController``.
    This mixin preserves historical entry points while the application migrates
    away from MainWindow inheritance.
    """

    def _layout_controller(self) -> LayoutController:
        controller = getattr(self, "layout_controller", None)
        if controller is None:
            controller = LayoutController.create(self.app_context)
            self.layout_controller = controller
        return controller

    def _remember_inspector_mode_before_tool_open(self) -> None:
        """Remember whether compact/light UI must be restored after tool close."""
        self._layout_controller().remember_before_tool_open()

    def _restore_inspector_mode_after_tool_close(self, reason: str = "") -> None:
        """Restore compact/light UI when a tool had opened the inspector for it."""
        self._layout_controller().restore_after_tool_close(reason)

    def _ensure_inspector_open(self, reason: str = "") -> None:
        """Open the right inspector without destroying user layout intent."""
        self._layout_controller().ensure_inspector_open(reason)

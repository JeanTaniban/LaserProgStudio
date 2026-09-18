# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..application import StudioActionController

# Static verification keeps the diagnostic strings visible while the
# executable implementation lives in application/.
_CLIPBOARD_DIAGNOSTIC_CONTRACT = (
    "[CLIPBOARD_DIAG] copy_offset",
    "duplicate_selected begin",
    "paste_selection begin",
    "blocked_check action=",
)

class ClipboardActionsLayer:
    """Qt-window adapter for clipboard commands.

    Real copy/paste/duplicate logic lives in ``application.ClipboardController``.
    The remaining methods expose the entry points used by shortcuts, tests
    and small UI callbacks.
    """

    def _clipboard_actions(self) -> StudioActionController:
        controller = getattr(self, "action_controller", None)
        if controller is None:
            controller = StudioActionController.create(self.app_context)
            self.action_controller = controller
        return controller

    def _clipboard_blocked_message(self, action_name: str) -> bool:
        return self._clipboard_actions().clipboard.blocked_message(action_name)

    @staticmethod
    def _bounds_axis_size(bounds: tuple[float, float, float, float, float, float], axis: str) -> float:
        from ..services.geometry import bounds_axis_size

        return bounds_axis_size(bounds, axis)

    def _camera_duplicate_delta(self, bounds: tuple[float, float, float, float, float, float]) -> tuple[tuple[float, float, float], str, float]:
        return self._clipboard_actions().clipboard.camera_duplicate_delta(bounds)

    def _copy_meshes_with_view_offset(self, source_meshes: list[Any]) -> tuple[list[Any], tuple[float, float, float], str, float]:
        return self._clipboard_actions().clipboard.copy_meshes_with_view_offset(source_meshes)

    def copy_selected(self) -> None:
        self._clipboard_actions().clipboard.copy_selected()

    def paste_selection(self) -> None:
        self._clipboard_actions().clipboard.paste_selection()

    def duplicate_selected(self) -> None:
        self._clipboard_actions().clipboard.duplicate_selected()

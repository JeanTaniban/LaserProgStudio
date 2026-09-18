# -*- coding: utf-8 -*-
from __future__ import annotations

from ..application import StudioActionController


class HistoryActionsLayer:
    """Window-facing facade for history commands.

    The implementation has moved to ``application.HistoryController`` so undo
    and redo are no longer buried inside the MainWindow mixin hierarchy.  This
    facade keeps QAction connections and older tests stable during the migration.
    """

    def _history_actions(self) -> StudioActionController:
        controller = getattr(self, "action_controller", None)
        if controller is None:
            controller = StudioActionController.create(self.app_context)
            self.action_controller = controller
        return controller

    def undo_scene(self) -> None:
        self._history_actions().history.undo_scene()

    def redo_scene(self) -> None:
        self._history_actions().history.redo_scene()

    def _capture_drag_undo_snapshot(self) -> None:
        self._history_actions().history.capture_drag_undo_snapshot()

    def _commit_drag_undo_snapshot(self, reason: str) -> None:
        self._history_actions().history.commit_drag_undo_snapshot(reason)

# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..application.boolean_controller import BooleanController


class BooleanActionsLayer:
    """Window-facing facade for boolean mesh commands.

    Boolean operations are now implemented by ``application.BooleanController``.
    These controller entry points are kept for QAction connections, toolbar items
    and older tests while the app moves away from MainWindow mixin inheritance.
    """

    def _boolean_actions(self) -> BooleanController:
        controller = getattr(self, "boolean_controller", None)
        if controller is None:
            controller = BooleanController.create(self.app_context)
            self.boolean_controller = controller
        return controller

    def _active_boolean_cutter_index(self) -> int | None:
        return self._boolean_actions().active_boolean_cutter_index()

    def _boolean_blocked_message(self) -> bool:
        return self._boolean_actions().blocked_message()

    def _touching_mesh_indices(self, cutter_index: int, meshes: list[Any]) -> list[int]:
        return self._boolean_actions().touching_mesh_indices(cutter_index, meshes)

    def boolean_subtract_touching(self) -> None:
        self._boolean_actions().subtract_touching()

    def boolean_union_selected(self) -> None:
        self._boolean_actions().union_selected()

    def boolean_separate_selected(self) -> None:
        self._boolean_actions().separate_selected()

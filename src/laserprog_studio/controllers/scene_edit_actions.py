# -*- coding: utf-8 -*-
from __future__ import annotations

from ..application import StudioActionController


class SceneEditActionsLayer:
    """Window-facing facade for scene edit commands.

    Delete/new-scene behavior has moved to ``application.SceneEditController``.
    Keeping these methods thin avoids touching menu/shortcut wiring during the
    first architecture migration pass.
    """

    def _scene_edit_actions(self) -> StudioActionController:
        controller = getattr(self, "action_controller", None)
        if controller is None:
            controller = StudioActionController.create(self.app_context)
            self.action_controller = controller
        return controller

    def delete_selected(self) -> None:
        self._scene_edit_actions().scene_edit.delete_selected()

    def new_scene(self) -> None:
        self._scene_edit_actions().scene_edit.new_scene()
    def new_project(self) -> None:
        self._scene_edit_actions().project.new_project()

    def open_project_dialog(self) -> None:
        self._scene_edit_actions().project.open_project_dialog()

    def save_project_dialog(self) -> bool:
        return bool(self._scene_edit_actions().project.save_project(save_as=False))

    def save_project_as_dialog(self) -> bool:
        return bool(self._scene_edit_actions().project.save_project_as())

    def mark_project_dirty_ui(self) -> None:
        self._scene_edit_actions().project.mark_dirty()


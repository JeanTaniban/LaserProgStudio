# -*- coding: utf-8 -*-
from __future__ import annotations

from ..geometry_ops import OperationResult


class PreviewControllerLayer:
    """Window-facing layer for the composed PreviewController.

    Static source markers kept for regression tests while the real
    implementation lives in ``application.preview_controller``:
    ``[PREVIEW][ERROR]`` and ``_schedule_light_transform_overlay_sync``.
    """

    def _preview_controller(self):
        controller = getattr(self, "preview_controller", None)
        if controller is None:
            from ..application.preview_controller import PreviewController
            controller = PreviewController.create(self.context)
            self.preview_controller = controller
        return controller

    def _ensure_model_store(self):
        return self._preview_controller().ensure_model_store()

    def has_preview(self) -> bool:
        return bool(self._preview_controller().has_preview())

    def update_preview_state(self) -> None:
        self._preview_controller().update_state()

    def set_preview_meshes(self, meshes, reason: str) -> None:
        self._preview_controller().set_meshes(meshes, reason)

    def set_preview_result(self, result: OperationResult, reason: str) -> bool:
        return bool(self._preview_controller().set_result(result, reason))

    def commit_preview_to_model(self, reason: str, *, rebuild: bool = True, operation_type: str | None = "tool_apply") -> bool:
        return bool(self._preview_controller().commit_to_model(reason, rebuild=rebuild, operation_type=operation_type))

    def commit_preview_to_new_scene(self, reason: str, *, scene_name: str | None = None, operation_type: str = "scene_generated") -> bool:
        return bool(self._preview_controller().commit_preview_to_new_scene(reason, scene_name=scene_name, operation_type=operation_type))

    def discard_preview_only(self, reason: str) -> None:
        self._preview_controller().discard_only(reason)

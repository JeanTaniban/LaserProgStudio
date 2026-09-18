# -*- coding: utf-8 -*-
from __future__ import annotations

from ..application.render_output_controller import RenderOutputController


class RenderOutputLayer:
    """Window-facing facade for code still calling RenderOutputLayer methods."""

    def _render_output_controller(self) -> RenderOutputController:
        controller = getattr(self, "render_output_controller", None)
        if controller is None:
            controller = RenderOutputController.create(self.app_context)
            self.render_output_controller = controller
        return controller

    def _editor_camera_pose_snapshot(self, *args, **kwargs):
        return self._render_output_controller()._editor_camera_pose_snapshot(*args, **kwargs)

    def _is_scene_helper_mesh(self, *args, **kwargs):
        return self._render_output_controller()._is_scene_helper_mesh(*args, **kwargs)

    def _is_render_camera_mesh(self, *args, **kwargs):
        return self._render_output_controller()._is_render_camera_mesh(*args, **kwargs)

    def _render_camera_indices(self, *args, **kwargs):
        return self._render_output_controller()._render_camera_indices(*args, **kwargs)

    def _normalize_vec3(self, *args, **kwargs):
        return self._render_output_controller()._normalize_vec3(*args, **kwargs)

    def _camera_basis_from_pose(self, *args, **kwargs):
        return self._render_output_controller()._camera_basis_from_pose(*args, **kwargs)

    def _transform_camera_local_points(self, *args, **kwargs):
        return self._render_output_controller()._transform_camera_local_points(*args, **kwargs)

    def _make_render_camera_mesh_from_pose(self, *args, **kwargs):
        return self._render_output_controller()._make_render_camera_mesh_from_pose(*args, **kwargs)

    def _render_camera_pose_from_mesh(self, *args, **kwargs):
        return self._render_output_controller()._render_camera_pose_from_mesh(*args, **kwargs)

    def _render_camera_pose_from_scene(self, *args, **kwargs):
        return self._render_output_controller()._render_camera_pose_from_scene(*args, **kwargs)

    def capture_render_camera_from_editor(self, *args, **kwargs):
        return self._render_output_controller().capture_render_camera_from_editor(*args, **kwargs)

    def _remove_render_camera_helper(self, *args, **kwargs):
        return self._render_output_controller()._remove_render_camera_helper(*args, **kwargs)

    def _sync_render_camera_helper(self, *args, **kwargs):
        return self._render_output_controller()._sync_render_camera_helper(*args, **kwargs)

    def open_render_preview_window(self, *args, **kwargs):
        return self._render_output_controller().open_render_preview_window(*args, **kwargs)

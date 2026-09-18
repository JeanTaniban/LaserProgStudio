# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math

from ..app_context import AppContext
from ..mesh_ops import scene_bounds, bounds_size
from ..studio_log import log_exception
from .action_controller import WindowController


class _LazyQtSymbol:
    """Import a Qt symbol only when a UI operation actually needs it."""

    def __init__(self, module_name: str, symbol_name: str):
        self.module_name = module_name
        self.symbol_name = symbol_name

    def _resolve(self):
        module = __import__(self.module_name, fromlist=[self.symbol_name])
        return getattr(module, self.symbol_name)

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)


QMessageBox = _LazyQtSymbol("PySide6.QtWidgets", "QMessageBox")

try:  # pragma: no cover - exercised by UI runtime, not headless tests.
    from ..rendering.final_render_dialog import RenderPreviewDialog
except Exception:  # pragma: no cover
    class RenderPreviewDialog:  # type: ignore[no-redef]
        def __init__(self, *args, **kwargs):
            raise RuntimeError("RenderPreviewDialog requires the Qt runtime.")


class _RenderOutputOperations:
    def _editor_camera_pose_snapshot(self) -> dict[str, tuple[float, float, float]] | None:
        try:
            cam = self.plotter.camera
            pos = tuple(float(v) for v in cam.GetPosition())
            focal = tuple(float(v) for v in cam.GetFocalPoint())
            up = tuple(float(v) for v in cam.GetViewUp())
            direction = (focal[0] - pos[0], focal[1] - pos[1], focal[2] - pos[2])
            dist = math.sqrt(direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2)
            if dist <= 1e-6:
                focal = (pos[0] + 1.0, pos[1], pos[2])
                dist = 1.0
            return {"position": pos, "focal_point": focal, "view_up": up, "distance": float(dist)}
        except Exception:
            return None

    def _is_scene_helper_mesh(self, mesh) -> bool:
        try:
            return bool(getattr(mesh, "_lps_scene_helper", False))
        except Exception:
            return False

    def _is_render_camera_mesh(self, mesh) -> bool:
        try:
            return bool(getattr(mesh, "_lps_render_camera", False))
        except Exception:
            return False

    def _render_camera_indices(self) -> list[int]:
        try:
            return [i for i, m in enumerate(self.current_meshes()) if self._is_render_camera_mesh(m)]
        except Exception:
            return []

    def _normalize_vec3(self, value, fallback=(1.0, 0.0, 0.0)):
        try:
            import numpy as np
            v = np.asarray(value, dtype=float)
            n = float(np.linalg.norm(v))
            if n <= 1e-9:
                return np.asarray(fallback, dtype=float)
            return v / n
        except Exception:
            import numpy as np
            return np.asarray(fallback, dtype=float)

    def _camera_basis_from_pose(self, pose: dict):
        import numpy as np
        pos = np.asarray(pose.get("position", (0.0, 0.0, 0.0)), dtype=float)
        focal = np.asarray(pose.get("focal_point", (1.0, 0.0, 0.0)), dtype=float)
        up = np.asarray(pose.get("view_up", (0.0, 0.0, 1.0)), dtype=float)
        forward = self._normalize_vec3(focal - pos, (1.0, 0.0, 0.0))
        up = self._normalize_vec3(up, (0.0, 0.0, 1.0))
        side = np.cross(forward, up)
        if float(np.linalg.norm(side)) <= 1e-9:
            up = np.asarray((0.0, 0.0, 1.0), dtype=float)
            side = np.cross(forward, up)
            if float(np.linalg.norm(side)) <= 1e-9:
                side = np.asarray((0.0, 1.0, 0.0), dtype=float)
        side = side / (float(np.linalg.norm(side)) or 1.0)
        up = np.cross(side, forward)
        up = up / (float(np.linalg.norm(up)) or 1.0)
        return pos, forward, side, up

    def _transform_camera_local_points(self, pose: dict, local_points: list[tuple[float, float, float]], size: float) -> list[tuple[float, float, float]]:
        import numpy as np
        pos, forward, side, up = self._camera_basis_from_pose(pose)
        pts: list[tuple[float, float, float]] = []
        for x, y, z in local_points:
            p = pos + forward * (float(x) * size) + side * (float(y) * size) + up * (float(z) * size)
            pts.append((float(p[0]), float(p[1]), float(p[2])))
        return pts

    def _make_render_camera_mesh_from_pose(self, pose: dict, *, name: str = "Render Camera"):
        from laserprog_studio.domain.work_model import WorkMesh
        try:
            size = max(bounds_size(scene_bounds(self.current_meshes())) * 0.065, 5.0)
        except Exception:
            size = 8.0
        # Vertices 0, 1 and 2 are semantic handles used to read camera pose after
        # the normal transform tools move/rotate the mesh:
        #   0 = camera position, 1 = forward direction marker, 2 = view-up marker.
        local = [
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (-0.42, -0.34, -0.24), (-0.42, 0.34, -0.24), (-0.42, 0.34, 0.24), (-0.42, -0.34, 0.24),
            (0.22, -0.34, -0.24), (0.22, 0.34, -0.24), (0.22, 0.34, 0.24), (0.22, -0.34, 0.24),
            (1.05, 0.0, 0.0),
            (-0.08, -0.16, 0.24), (-0.08, 0.16, 0.24), (0.36, 0.0, 0.72),
        ]
        verts = self._transform_camera_local_points(pose, local, size)
        tris = [
            (3, 4, 5), (3, 5, 6), (7, 10, 9), (7, 9, 8),
            (3, 7, 8), (3, 8, 4), (6, 5, 9), (6, 9, 10),
            (4, 8, 9), (4, 9, 5), (3, 6, 10), (3, 10, 7),
            (7, 11, 8), (8, 11, 9), (9, 11, 10), (10, 11, 7),
            (12, 13, 14),
            # Tiny semantic-marker triangles keep markers in the polydata while
            # staying visually hidden inside the camera object.
            (0, 3, 7), (1, 7, 11), (2, 12, 14),
        ]
        mesh = WorkMesh(name=name, vertices=verts, triangles=tris, color="#4FC3F7")
        setattr(mesh, "_lps_scene_helper", True)
        setattr(mesh, "_lps_render_camera", True)
        setattr(mesh, "_lps_render_camera_distance", float(pose.get("distance", size * 8.0)))
        setattr(mesh, "_lps_render_camera_size", float(size))
        return mesh

    def _render_camera_pose_from_mesh(self, mesh) -> dict[str, tuple[float, float, float]] | None:
        try:
            import numpy as np
            verts = list(getattr(mesh, "vertices", []) or [])
            if len(verts) < 3:
                return None
            pos = np.asarray(verts[0], dtype=float)
            f_marker = np.asarray(verts[1], dtype=float)
            u_marker = np.asarray(verts[2], dtype=float)
            forward = self._normalize_vec3(f_marker - pos, (1.0, 0.0, 0.0))
            up_raw = self._normalize_vec3(u_marker - pos, (0.0, 0.0, 1.0))
            side = np.cross(forward, up_raw)
            if float(np.linalg.norm(side)) <= 1e-9:
                up_raw = np.asarray((0.0, 0.0, 1.0), dtype=float)
                side = np.cross(forward, up_raw)
                if float(np.linalg.norm(side)) <= 1e-9:
                    side = np.asarray((0.0, 1.0, 0.0), dtype=float)
            side = side / (float(np.linalg.norm(side)) or 1.0)
            up = np.cross(side, forward)
            up = up / (float(np.linalg.norm(up)) or 1.0)
            distance = float(getattr(mesh, "_lps_render_camera_distance", 0.0) or 0.0)
            if distance <= 1e-6:
                try:
                    distance = max(bounds_size(scene_bounds([m for m in self.current_meshes() if not self._is_scene_helper_mesh(m)])) * 2.8, 20.0)
                except Exception:
                    distance = 60.0
            focal = pos + forward * distance
            return {
                "position": (float(pos[0]), float(pos[1]), float(pos[2])),
                "focal_point": (float(focal[0]), float(focal[1]), float(focal[2])),
                "view_up": (float(up[0]), float(up[1]), float(up[2])),
                "distance": float(distance),
            }
        except Exception:
            log_exception("render_camera_pose_from_mesh")
            return None

    def _render_camera_pose_from_scene(self) -> dict[str, tuple[float, float, float]] | None:
        try:
            meshes = self.current_meshes()
            candidates = self._render_camera_indices()
            if not candidates:
                return None
            # Prefer the selected/active camera when more than one exists.
            active = getattr(self, "active_index", None)
            if isinstance(active, int) and active in candidates:
                return self._render_camera_pose_from_mesh(meshes[active])
            for idx in getattr(self, "selected_indices", []) or []:
                if int(idx) in candidates:
                    return self._render_camera_pose_from_mesh(meshes[int(idx)])
            return self._render_camera_pose_from_mesh(meshes[candidates[0]])
        except Exception:
            log_exception("render_camera_pose_from_scene")
            return None

    def capture_render_camera_from_editor(self) -> None:
        """Create/select the render camera as a real transformable scene object."""
        try:
            existing = self._render_camera_indices()
            if existing:
                idx = existing[0]
                self.set_selection_indices([idx], reason="render camera select")
                self.active_index = idx
                # Do not refocus the editor when selecting the render camera: camera
                # placement must not disturb the user's current modelling view.
                self.ui_log(f"[RENDER_CAMERA] selected existing scene camera index={idx}")
                return

            pose = self._editor_camera_pose_snapshot()
            if pose is None:
                pose = {"position": (0.0, 0.0, 0.0), "focal_point": (1.0, 0.0, 0.0), "view_up": (0.0, 0.0, 1.0), "distance": 60.0}
            cam_mesh = self._make_render_camera_mesh_from_pose(pose)
            meshes = [copy.deepcopy(m) for m in self.current_meshes()]
            meshes.append(cam_mesh)
            new_idx = len(meshes) - 1
            self.selected_indices = [new_idx]
            self.active_index = new_idx
            self.push_meshes(meshes, "Add render camera object")
            self.set_selection_indices([new_idx], reason="render camera created")
            # Keep the editor view stable after creating the render camera object.
            self.render_camera_state = None
            self.ui_log(
                "[RENDER_CAMERA] created scene camera object "
                f"index={new_idx} pos={tuple(round(v, 3) for v in pose['position'])}"
            )
        except Exception:
            log_exception("capture_render_camera_from_editor")
            QMessageBox.warning(self, "Render camera", "Could not create the render camera.")

    def _remove_render_camera_helper(self, *, render: bool = False) -> None:
        # Cleanup for previous versions where the camera was drawn as loose
        # actors outside the hierarchy.  The camera is now a normal WorkMesh.
        plotter = getattr(self, "plotter", None)
        if plotter is None:
            return
        for name in ["render_camera_body", "render_camera_head", "render_camera_axis", "render_camera_up"]:
            try:
                plotter.remove_actor(name, render=False)
            except Exception:
                pass
        self.render_camera_actor_names = []
        if render:
            try:
                plotter.render()
            except Exception:
                pass

    def _sync_render_camera_helper(self, *, render: bool = False) -> None:
        # No-op by design: the render camera is now part of mesh_store, appears in
        # Parts, and is handled by the classic transform gizmos.
        self._remove_render_camera_helper(render=render)

    def open_render_preview_window(self) -> None:
        try:
            dialog = getattr(self, "render_preview_dialog", None)
            if dialog is None or not isinstance(dialog, RenderPreviewDialog) or not dialog.isVisible():
                dialog = RenderPreviewDialog(self)
                self.render_preview_dialog = dialog
            else:
                dialog.refresh_scene()
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
        except Exception:
            log_exception("open_render_preview_window")
            QMessageBox.warning(self, "Render", "Could not open the render window.")



class ExportController(WindowController):
    """Composable owner for 3MF, primitive and engraving export workflows.

    ``RenderOutputLayer`` is a thin Qt-window adapter. Keeping the real
    behavior here makes export features discoverable without adding more
    behavior to ``MainWindow``'s inheritance chain.
    """

    @classmethod
    def create(cls, context: AppContext) -> "ExportController":
        return cls(context)

    def _polydata_to_workmesh(self, *args, **kwargs):
        return _ExportOperations._polydata_to_workmesh(self.owner, *args, **kwargs)

    def _make_manual_workmesh(self, *args, **kwargs):
        return _ExportOperations._make_manual_workmesh(self.owner, *args, **kwargs)



    def export_3mf_dialog(self, *args, **kwargs):
        return _ExportOperations.export_3mf_dialog(self.owner, *args, **kwargs)

    def open_engrave_workspace(self, *args, **kwargs):
        return _ExportOperations.open_engrave_workspace(self.owner, *args, **kwargs)

    def close_engrave_workspace(self, *args, **kwargs):
        return _ExportOperations.close_engrave_workspace(self.owner, *args, **kwargs)

    def _engrave_config_from_ui(self, *args, **kwargs):
        return _ExportOperations._engrave_config_from_ui(self.owner, *args, **kwargs)

    def _render_current_model_to_engrave_images(self, *args, **kwargs):
        return _ExportOperations._render_current_model_to_engrave_images(self.owner, *args, **kwargs)

    def render_engrave_current(self, *args, **kwargs):
        return _ExportOperations.render_engrave_current(self.owner, *args, **kwargs)

    def _engrave_dimension_metadata(self, *args, **kwargs):
        return _ExportOperations._engrave_dimension_metadata(self.owner, *args, **kwargs)

    def _save_png_with_dimensions(self, *args, **kwargs):
        return _ExportOperations._save_png_with_dimensions(self.owner, *args, **kwargs)

    def save_engrave_all(self, *args, **kwargs):
        return _ExportOperations.save_engrave_all(self.owner, *args, **kwargs)

    def save_engrave_falcon_svg(self, *args, **kwargs):
        return _ExportOperations.save_engrave_falcon_svg(self.owner, *args, **kwargs)

    def save_engrave_dimensions_json(self, *args, **kwargs):
        return _ExportOperations.save_engrave_dimensions_json(self.owner, *args, **kwargs)

    def export_gravure_dialog(self, *args, **kwargs):
        return _ExportOperations.export_gravure_dialog(self.owner, *args, **kwargs)

    def open_3mf_dialog(self, *args, **kwargs):
        return _ExportOperations.open_3mf_dialog(self.owner, *args, **kwargs)

    def load_default_2d_preview(self, *args, **kwargs):
        return _ExportOperations.load_default_2d_preview(self.owner, *args, **kwargs)

    def load_2d_image(self, *args, **kwargs):
        return _ExportOperations.load_2d_image(self.owner, *args, **kwargs)


class RenderOutputController(WindowController):
    """Composable owner for render-camera and final-preview workflows."""

    @classmethod
    def create(cls, context: AppContext) -> "RenderOutputController":
        return cls(context)

    def _editor_camera_pose_snapshot(self, *args, **kwargs):
        return _RenderOutputOperations._editor_camera_pose_snapshot(self.owner, *args, **kwargs)

    def _is_scene_helper_mesh(self, *args, **kwargs):
        return _RenderOutputOperations._is_scene_helper_mesh(self.owner, *args, **kwargs)

    def _is_render_camera_mesh(self, *args, **kwargs):
        return _RenderOutputOperations._is_render_camera_mesh(self.owner, *args, **kwargs)

    def _render_camera_indices(self, *args, **kwargs):
        return _RenderOutputOperations._render_camera_indices(self.owner, *args, **kwargs)

    def _normalize_vec3(self, *args, **kwargs):
        return _RenderOutputOperations._normalize_vec3(self.owner, *args, **kwargs)

    def _camera_basis_from_pose(self, *args, **kwargs):
        return _RenderOutputOperations._camera_basis_from_pose(self.owner, *args, **kwargs)

    def _transform_camera_local_points(self, *args, **kwargs):
        return _RenderOutputOperations._transform_camera_local_points(self.owner, *args, **kwargs)

    def _make_render_camera_mesh_from_pose(self, *args, **kwargs):
        return _RenderOutputOperations._make_render_camera_mesh_from_pose(self.owner, *args, **kwargs)

    def _render_camera_pose_from_mesh(self, *args, **kwargs):
        return _RenderOutputOperations._render_camera_pose_from_mesh(self.owner, *args, **kwargs)

    def _render_camera_pose_from_scene(self, *args, **kwargs):
        return _RenderOutputOperations._render_camera_pose_from_scene(self.owner, *args, **kwargs)

    def capture_render_camera_from_editor(self, *args, **kwargs):
        return _RenderOutputOperations.capture_render_camera_from_editor(self.owner, *args, **kwargs)

    def _remove_render_camera_helper(self, *args, **kwargs):
        return _RenderOutputOperations._remove_render_camera_helper(self.owner, *args, **kwargs)

    def _sync_render_camera_helper(self, *args, **kwargs):
        return _RenderOutputOperations._sync_render_camera_helper(self.owner, *args, **kwargs)

    def open_render_preview_window(self, *args, **kwargs):
        return _RenderOutputOperations.open_render_preview_window(self.owner, *args, **kwargs)

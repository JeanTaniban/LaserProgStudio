# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class TransformDragLayer:
    def _update_polydata_points(self, idx: int, vertices: list[tuple[float, float, float]]) -> None:
        try:
            import numpy as np
            poly = self.polydata_by_index.get(idx)
            if poly is not None:
                poly.points = np.asarray(vertices, dtype=float)
                poly.modified()
        except Exception:
            pass

    def _drag_vertices_center(self, vertices: list[tuple[float, float, float]]) -> tuple[float, float, float]:
        try:
            if not vertices:
                return (0.0, 0.0, 0.0)
            xs = [float(v[0]) for v in vertices]
            ys = [float(v[1]) for v in vertices]
            zs = [float(v[2]) for v in vertices]
            return ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5)
        except Exception:
            return (0.0, 0.0, 0.0)

    def _drag_actor_position(self, idx: int) -> tuple[float, float, float]:
        try:
            actor = self.actors_by_index.get(int(idx))
            if actor is not None:
                p = actor.GetPosition()
                return (float(p[0]), float(p[1]), float(p[2]))
        except Exception:
            pass
        return (0.0, 0.0, 0.0)

    def _set_drag_actor_offset(self, idx: int, offset: tuple[float, float, float]) -> bool:
        try:
            actor = self.actors_by_index.get(int(idx))
            if actor is None:
                return False
            start_positions = getattr(self, "_drag_start_actor_position_by_index", {}) or {}
            base = start_positions.get(int(idx), (0.0, 0.0, 0.0))
            actor.SetPosition(float(base[0]) + float(offset[0]), float(base[1]) + float(offset[1]), float(base[2]) + float(offset[2]))
            return True
        except Exception:
            return False

    def _restore_drag_actor_position(self, idx: int) -> None:
        try:
            actor = self.actors_by_index.get(int(idx))
            if actor is None:
                return
            start_positions = getattr(self, "_drag_start_actor_position_by_index", {}) or {}
            base = start_positions.get(int(idx), (0.0, 0.0, 0.0))
            actor.SetPosition(float(base[0]), float(base[1]), float(base[2]))
        except Exception:
            pass

    def _drag_actor_preview_enabled(self) -> bool:
        """Return True when live transform drag should use actor transforms.

        The selected mesh remains the source of truth.  During mouse-move we only
        move/rotate/scale the existing VTK actors; vertices and polydata are
        committed once on release.  This removes the most expensive part of the
        old gizmo loop while keeping undo/history deterministic.
        """
        try:
            value = os.environ.get("LPS_TRANSFORM_ACTOR_PREVIEW", "1").strip().lower()
            return value not in {"0", "false", "no", "off"}
        except Exception:
            return True

    def _drag_audit_increment(self, name: str, value: int = 1) -> None:
        try:
            from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

            audit.increment(str(name), int(value))
        except Exception:
            pass

    def _capture_drag_actor_state(self, indices: list[int]) -> None:
        """Snapshot actor transforms so live preview can be restored precisely."""
        try:
            positions: dict[int, tuple[float, float, float]] = {}
            matrices: dict[int, Any] = {}
            for raw in indices:
                idx = int(raw)
                actor = self.actors_by_index.get(idx)
                if actor is None:
                    continue
                try:
                    p = actor.GetPosition()
                    positions[idx] = (float(p[0]), float(p[1]), float(p[2]))
                except Exception:
                    positions[idx] = (0.0, 0.0, 0.0)
                try:
                    mat = actor.GetUserMatrix()
                    if mat is not None:
                        import vtk

                        copy_mat = vtk.vtkMatrix4x4()
                        copy_mat.DeepCopy(mat)
                        matrices[idx] = copy_mat
                    else:
                        matrices[idx] = None
                except Exception:
                    matrices[idx] = None
            self._drag_start_actor_position_by_index = positions
            self._drag_start_actor_user_matrix_by_index = matrices
        except Exception:
            self._drag_start_actor_position_by_index = {}
            self._drag_start_actor_user_matrix_by_index = {}

    def _restore_drag_actor_transform(self, idx: int) -> None:
        try:
            actor = self.actors_by_index.get(int(idx))
            if actor is None:
                return
            positions = getattr(self, "_drag_start_actor_position_by_index", {}) or {}
            p = positions.get(int(idx), (0.0, 0.0, 0.0))
            actor.SetPosition(float(p[0]), float(p[1]), float(p[2]))
            matrices = getattr(self, "_drag_start_actor_user_matrix_by_index", {}) or {}
            actor.SetUserMatrix(matrices.get(int(idx), None))
        except Exception:
            pass

    def _vtk_matrix_from_numpy(self, matrix: Any):
        try:
            import vtk
            import numpy as np

            arr = np.asarray(matrix, dtype=float)
            if arr.shape != (4, 4):
                return None
            vtk_mat = vtk.vtkMatrix4x4()
            for r in range(4):
                for c in range(4):
                    vtk_mat.SetElement(r, c, float(arr[r, c]))
            return vtk_mat
        except Exception:
            return None

    def _apply_drag_actor_matrix(self, indices: list[int], matrix: Any) -> None:
        try:
            vtk_mat = self._vtk_matrix_from_numpy(matrix)
            if vtk_mat is None:
                return
            for raw in indices:
                idx = int(raw)
                actor = self.actors_by_index.get(idx)
                if actor is None:
                    continue
                # Preserve any pre-existing user matrix by applying the live matrix
                # in front of it.  Most scene actors have no user matrix, but this
                # keeps the path safe for future imported actors.
                final_mat = vtk_mat
                try:
                    original = (getattr(self, "_drag_start_actor_user_matrix_by_index", {}) or {}).get(idx)
                    if original is not None:
                        import vtk

                        combined = vtk.vtkMatrix4x4()
                        vtk.vtkMatrix4x4.Multiply4x4(vtk_mat, original, combined)
                        final_mat = combined
                except Exception:
                    pass
                actor.SetUserMatrix(final_mat)
        except Exception:
            pass

    def _drag_translation_matrix(self, offset: tuple[float, float, float]):
        import numpy as np

        mat = np.eye(4, dtype=float)
        mat[:3, 3] = np.asarray(offset, dtype=float)
        return mat

    def _drag_rotation_matrix(self, center: tuple[float, float, float], axis_vector: tuple[float, float, float], angle: float):
        import numpy as np

        q = self._quat_from_axis_angle_tuple(axis_vector, float(angle))
        rot = self._quat_to_matrix(q)
        c = np.asarray(center, dtype=float)
        mat = np.eye(4, dtype=float)
        mat[:3, :3] = rot
        mat[:3, 3] = c - rot @ c
        return mat

    def _axis_scale_affine(self, pivot: tuple[float, float, float], axis_vector: tuple[float, float, float], factor: float):
        import numpy as np

        axis = np.asarray(axis_vector, dtype=float)
        n = float(np.linalg.norm(axis))
        if n <= 1e-12:
            return np.eye(4, dtype=float)
        u = axis / n
        a = np.eye(3, dtype=float) + (float(factor) - 1.0) * np.outer(u, u)
        p = np.asarray(pivot, dtype=float)
        mat = np.eye(4, dtype=float)
        mat[:3, :3] = a
        mat[:3, 3] = p - a @ p
        return mat

    def _drag_scale_matrix(self, axis: str, factor: float):
        try:
            import numpy as np

            pivot = getattr(self, "_drag_scale_pivot", None)
            if pivot is None:
                return np.eye(4, dtype=float)
            locked = bool(getattr(self, "scale_ratio_locked", False))
            scale_axes = getattr(self, "_drag_scale_axes", None) or {}
            if locked:
                mat = np.eye(4, dtype=float)
                for logical in ("x", "y", "z"):
                    vec = scale_axes.get(logical, (None,))[0] if isinstance(scale_axes, dict) else None
                    if vec is None:
                        vec = self._gizmo_axis_definitions().get(logical, ((1.0, 0.0, 0.0), "#ffffff"))[0]
                    mat = self._axis_scale_affine(pivot, vec, factor) @ mat
                return mat
            vec = self._drag_axis_vector or self._gizmo_axis_definitions().get(axis, ((1.0, 0.0, 0.0), "#ffffff"))[0]
            return self._axis_scale_affine(pivot, vec, factor)
        except Exception:
            import numpy as np

            return np.eye(4, dtype=float)

    def _drag_qpos_changed_enough(self, qx: float, qy: float, *, min_px: float = 0.25) -> bool:
        try:
            last = getattr(self, "_drag_last_update_qpos", None)
            q = (float(qx), float(qy))
            if last is not None:
                dx = q[0] - float(last[0])
                dy = q[1] - float(last[1])
                if (dx * dx + dy * dy) ** 0.5 < float(min_px):
                    self._drag_audit_increment("transform.drag.skipped_subpixel")
                    return False
            self._drag_last_update_qpos = q
            return True
        except Exception:
            return True

    def _request_drag_render(self, reason: str) -> None:
        try:
            # The central scheduler already coalesces raw mouse events and uses
            # the interactive 60 FPS budget.  A second 45 FPS throttle here made
            # translation visibly trail behind the cursor, especially on 120 Hz
            # mice.  Keep a local fallback only when the scheduler is unavailable.
            request = getattr(self, "request_render", None)
            if callable(request):
                request(reason=reason)
                return
            if self._drag_render_due(interval=1.0 / 60.0):
                self.plotter.render()
            else:
                self._drag_audit_increment("transform.drag.render_throttled_fallback")
        except Exception:
            try:
                self.plotter.render()
            except Exception:
                pass

    def _live_drag_readout(
        self,
        mode: str,
        indices: list[int],
        meshes: list[Any],
        vertices_by_index: dict[int, list[tuple[float, float, float]]] | None = None,
        *,
        translation_center: tuple[float, float, float] | None = None,
    ) -> None:
        try:
            if not self._drag_readout_due(interval=0.12):
                self._drag_audit_increment("transform.drag.readout_throttled")
                return
            if str(mode) == self.TRANSFORM_TRANSLATE:
                self._update_drag_translation_readout(indices, meshes, vertices_by_index, center=translation_center)
            else:
                # Rotation/scale do not mutate the mesh on every mouse tick in the
                # actor-preview path.  A full inspector refresh would therefore show
                # stale mesh bounds; keep it for drag end only.
                try:
                    self._sync_light_transform_fields()
                except Exception:
                    pass
        except Exception:
            pass

    def _commit_live_transform_preview(self) -> None:
        """Commit the final actor-preview transform into mesh/polydata once."""
        try:
            mode = getattr(self, "_drag_transform_mode", None)
            indices = list(getattr(self, "_drag_mesh_indices", None) or ([] if getattr(self, "_drag_mesh_index", None) is None else [getattr(self, "_drag_mesh_index")]))
            if not mode or not indices or not getattr(self, "_drag_start_vertices_by_index", None):
                return
            meshes = self.current_meshes()
            indices = [int(i) for i in indices if 0 <= int(i) < len(meshes) and int(i) in self._drag_start_vertices_by_index]
            if not indices:
                return
            committed = False
            if mode == self.TRANSFORM_TRANSLATE:
                # Fast actor preview stores only one final offset.  Materialise
                # translated vertices once here instead of allocating them on every
                # mouse move.  The legacy live-mesh path remains as a fallback.
                offset = getattr(self, "_drag_live_translation_offset", None)
                if offset is not None:
                    ox, oy, oz = (float(offset[0]), float(offset[1]), float(offset[2]))
                    for i in indices:
                        start_vertices = self._drag_start_vertices_by_index.get(i)
                        if start_vertices is None:
                            continue
                        final_vertices = [(float(x) + ox, float(y) + oy, float(z) + oz) for x, y, z in start_vertices]
                        meshes[i].vertices = final_vertices
                        self._update_polydata_points(i, final_vertices)
                        committed = True
                else:
                    live = getattr(self, "_drag_live_vertices_by_index", None) or {}
                    for i in indices:
                        vertices = live.get(i)
                        if vertices is None:
                            continue
                        final_vertices = [(float(x), float(y), float(z)) for x, y, z in vertices]
                        meshes[i].vertices = final_vertices
                        self._update_polydata_points(i, final_vertices)
                        committed = True
            elif mode == self.TRANSFORM_ROTATE:
                angle = float(getattr(self, "_drag_rotation_applied_angle", None) or getattr(self, "_drag_rotation_accum_angle", None) or 0.0)
                center = getattr(self, "_drag_rotation_center", None)
                axis_vector = getattr(self, "_drag_axis_vector", None)
                if center is not None and axis_vector is not None:
                    delta_quat = self._quat_from_axis_angle_tuple(axis_vector, angle)
                    active = self._drag_mesh_index if self._drag_mesh_index in indices else indices[-1]
                    start_euler = self._drag_start_rotation_euler or self._mesh_rotation_euler(meshes[active])
                    logical_axis = self._logical_axis_from_handle(getattr(self, "_drag_axis", None))
                    for i in indices:
                        start_vertices = self._drag_start_vertices_by_index[i]
                        start_quat, _start_euler_i = self._drag_start_rotation_state_by_index.get(i, (self._mesh_rotation_quat(meshes[i]), self._mesh_rotation_euler(meshes[i])))
                        target_quat = self._quat_normalize(self._quat_multiply(delta_quat, start_quat))
                        new_vertices = self._rotate_vertices_by_quaternion_tuple(start_vertices, center, delta_quat)
                        meshes[i].vertices = new_vertices
                        if i == active:
                            live_euler = list(start_euler)
                            applied_deg = math.degrees(float(angle))
                            if logical_axis == "x":
                                live_euler[0] = self._normalize_angle_deg(live_euler[0] + applied_deg)
                            elif logical_axis == "y":
                                live_euler[1] = self._normalize_angle_deg(live_euler[1] + applied_deg)
                            elif logical_axis == "z":
                                live_euler[2] = self._normalize_angle_deg(live_euler[2] + applied_deg)
                            else:
                                live_euler = list(self._euler_xyz_deg_from_quat(target_quat))
                            self._set_mesh_rotation_state(meshes[i], target_quat, tuple(live_euler))
                        else:
                            self._set_mesh_rotation_state(meshes[i], target_quat, self._euler_xyz_deg_from_quat(target_quat))
                        self._update_polydata_points(i, new_vertices)
                        committed = True
            elif mode == self.TRANSFORM_SCALE:
                axis = self._logical_axis_from_handle(getattr(self, "_drag_axis", None))
                factor = float(getattr(self, "_drag_scale_factor", 1.0) or 1.0)
                if axis is not None:
                    locked = bool(getattr(self, "scale_ratio_locked", False))
                    scale_axes = getattr(self, "_drag_scale_axes", None) or {}
                    axis_vector = self._drag_axis_vector or self._gizmo_axis_definitions().get(axis, ((1.0, 0.0, 0.0), "#ffffff"))[0]
                    for i in indices:
                        if locked:
                            vertices = list(self._drag_start_vertices_by_index[i])
                            for logical in ("x", "y", "z"):
                                vec = scale_axes.get(logical, (None,))[0] if isinstance(scale_axes, dict) else None
                                if vec is None:
                                    vec = self._gizmo_axis_definitions().get(logical, ((1.0, 0.0, 0.0), "#ffffff"))[0]
                                vertices = self._scale_vertices_along_vector(vertices, self._drag_scale_pivot, vec, factor)
                        else:
                            vertices = self._scale_vertices_along_vector(self._drag_start_vertices_by_index[i], self._drag_scale_pivot, axis_vector, factor)
                        meshes[i].vertices = vertices
                        self._update_polydata_points(i, vertices)
                        committed = True
            for i in indices:
                self._restore_drag_actor_transform(i)
            if committed:
                self._drag_audit_increment(f"transform.drag.{mode}.commit_once")
        except Exception:
            log_exception("commit_live_transform_preview")

    def _commit_live_translation_preview(self) -> None:
        """Commit actor-position preview vertices into real mesh/polydata data.

        Translation drag used to rewrite every VTK point for every mouse event.
        That is extremely expensive when a dragged board overlaps another board
        because VTK has to update geometry/bounds continuously.  During live
        translation we now move actors with SetPosition(); on release we write the
        final vertices once and reset actor transforms.
        """
        try:
            if getattr(self, "_drag_transform_mode", None) != self.TRANSFORM_TRANSLATE:
                return
            live = getattr(self, "_drag_live_vertices_by_index", None) or {}
            if not live:
                return
            meshes = self.current_meshes()
            for raw, vertices in list(live.items()):
                idx = int(raw)
                if not (0 <= idx < len(meshes)):
                    continue
                final_vertices = [(float(x), float(y), float(z)) for x, y, z in vertices]
                meshes[idx].vertices = final_vertices
                self._restore_drag_actor_position(idx)
                self._update_polydata_points(idx, final_vertices)
        except Exception:
            log_exception("commit_live_translation_preview")

    def _drag_perf_now(self) -> float:
        try:
            import time
            return float(time.monotonic())
        except Exception:
            return 0.0

    def _drag_render_due(self, *, interval: float = 1.0 / 45.0) -> bool:
        """Throttle expensive PyVista renders while the mouse is moving."""
        now = self._drag_perf_now()
        last = float(getattr(self, "_drag_last_render_time", 0.0) or 0.0)
        if now <= 0.0 or last <= 0.0 or (now - last) >= float(interval):
            self._drag_last_render_time = now
            return True
        self._drag_render_skipped = True
        return False

    def _drag_readout_due(self, *, interval: float = 0.10) -> bool:
        """Throttle inspector/light-overlay updates during live transforms."""
        now = self._drag_perf_now()
        last = float(getattr(self, "_drag_last_readout_time", 0.0) or 0.0)
        if now <= 0.0 or last <= 0.0 or (now - last) >= float(interval):
            self._drag_last_readout_time = now
            return True
        return False

    def _update_drag_translation_readout(
        self,
        indices: list[int],
        meshes: list[Any],
        vertices_by_index: dict[int, list[tuple[float, float, float]]] | None = None,
        *,
        center: tuple[float, float, float] | None = None,
    ) -> None:
        """Lightweight live readout for translation drag.

        Full ``update_inspector()`` refreshes oriented bounds, Box metrics and the
        full light overlay. Running it for every mouse event is visibly expensive
        on scenes with many objects.  During drag we only update the position
        fields and the compact overlay; the full inspector is refreshed once at
        release.
        """
        try:
            if center is not None:
                c = (float(center[0]), float(center[1]), float(center[2]))
            elif vertices_by_index:
                live_vertices = [v for i in indices for v in vertices_by_index.get(int(i), [])]
                c = self._drag_vertices_center(live_vertices)
            else:
                c = self._selection_center(indices, meshes)
            values = {self.pos_x: c[0], self.pos_y: c[1], self.pos_z: c[2]}
            previous = bool(getattr(self, "_updating_transform_fields", False))
            self._updating_transform_fields = True
            try:
                for widget, value in values.items():
                    widget.blockSignals(True)
                    widget.setValue(float(value))
                    widget.blockSignals(False)
            finally:
                self._updating_transform_fields = previous
            try:
                self._sync_light_transform_fields()
            except Exception:
                pass
        except Exception:
            pass

    def _start_gizmo_drag(self, axis: str, qx: float, qy: float) -> None:
        if self.transform_mode == self.TRANSFORM_ROTATE:
            self._start_gizmo_rotate_drag(axis, qx, qy)
        elif self.transform_mode == self.TRANSFORM_SCALE:
            self._start_gizmo_scale_drag(axis, qx, qy)
        else:
            self._start_gizmo_translate_drag(axis, qx, qy)

    def _start_gizmo_translate_drag(self, axis: str, qx: float, qy: float) -> None:
        try:
            if self.active_index is None or self.mesh_store is None or not self._transform_tools_available():
                return
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            if not indices:
                return
            axis = axis.lower()
            axis_def = self._gizmo_axis_definitions().get(axis)
            if axis_def is None:
                return
            vec = axis_def[0]
            c = self._selection_center(indices, meshes)
            length = self._gizmo_length_at(c, meshes)
            display_basis = None
            try:
                from laserprog_studio.application.transform_gizmo_api import native_transform_drag_basis

                display_basis = native_transform_drag_basis(self, axis, world_length=length)
            except Exception:
                display_basis = None
            if display_basis is not None:
                sx_qt, sy_qt, world_per_pixel, display_sign = display_basis
                vec = (vec[0] * display_sign, vec[1] * display_sign, vec[2] * display_sign)
                sx, sy = float(sx_qt), -float(sy_qt)  # stored below converts VTK Y to Qt Y
                norm = math.hypot(sx, sy)
                length_for_screen = max(float(world_per_pixel) * max(norm, 1.0), 1.0e-9)
            else:
                p0 = self._world_to_display(c)
                p1 = self._world_to_display((c[0] + vec[0] * length, c[1] + vec[1] * length, c[2] + vec[2] * length))
                sx, sy = p1[0] - p0[0], p1[1] - p0[1]
                norm = math.hypot(sx, sy)
                length_for_screen = length
            # The 2D gizmo backend returns a normalized screen direction
            # (norm ~= 1), while the legacy 3D projection returned a pixel
            # vector. Only reject a genuinely degenerate direction.
            if norm < 1.0e-6:
                return
            self._capture_drag_undo_snapshot()
            self._gizmo_delta_display_signature = None
            self._drag_axis = axis
            self._drag_transform_mode = self.TRANSFORM_TRANSLATE
            self._drag_mesh_index = self.active_index
            self._drag_mesh_indices = list(indices)
            self._drag_start_qpos = (qx, qy)
            self._drag_start_vertices_by_index = {i: list(meshes[i].vertices) for i in indices}
            self._drag_start_vertices = list(self._vertices_for_indices(indices, meshes))
            self._drag_translation_moving_profile = build_translation_moving_profile(self._drag_start_vertices)
            self._drag_translation_start_center = self._drag_vertices_center(self._drag_start_vertices)
            self._drag_live_translation_offset = (0.0, 0.0, 0.0)
            self._capture_drag_actor_state(list(indices))
            self._drag_live_vertices_by_index = {}
            # Native/API translate gizmos are lightweight enough to follow the
            # dragged selection.  Capture the initial declaration so live updates
            # can apply the current offset without rebuilding the whole gizmo.
            try:
                self._native_transform_gizmo_drag_base_snapshot = getattr(self, "_native_transform_gizmo_snapshot", None)
                self._native_transform_gizmo_drag_live_offset = (0.0, 0.0, 0.0)
            except Exception:
                pass
            try:
                self._drag_translation_snap_cache = build_translation_snap_cache(meshes=meshes, moving_index=indices[-1], moving_indices=set(indices))
            except Exception:
                self._drag_translation_snap_cache = None
            self._drag_last_update_qpos = None
            self._drag_last_render_time = 0.0
            self._drag_last_readout_time = 0.0
            self._drag_last_update_qpos = None
            self._drag_render_skipped = False
            self._drag_axis_origin = c
            self._drag_axis_vector = vec
            self._drag_axis_screen = (sx / norm, -sy / norm, length_for_screen / norm)  # Qt Y is inverted vs VTK display Y.
            self._highlight_transform_axis(axis)
            self.ui_log(f"[GIZMO] Start translate axis {axis.upper()} on selection {indices}")
        except Exception:
            log_exception("start_gizmo_translate_drag")

    def _start_gizmo_rotate_drag(self, axis: str, qx: float, qy: float) -> None:
        try:
            if self.active_index is None or self.mesh_store is None or not self._transform_tools_available():
                return
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            if not indices:
                return
            axis = axis.lower()
            axis_def = self._gizmo_axis_definitions().get(axis)
            if axis_def is None:
                return
            vec = axis_def[0]
            active = self._active_or_first_selected_index(indices) or indices[-1]
            m = meshes[active]
            c = self._selection_center(indices, meshes)
            start_vec = self._rotation_vector_from_qt(qx, qy, c, vec)
            self._capture_drag_undo_snapshot()
            self._gizmo_delta_display_signature = None
            self._drag_start_rotation_quat = self._mesh_rotation_quat(m)
            self._drag_start_rotation_euler = self._mesh_rotation_euler(m)
            self._drag_start_rotation_state_by_index = {i: (self._mesh_rotation_quat(meshes[i]), self._mesh_rotation_euler(meshes[i])) for i in indices}
            self._capture_drag_actor_state(list(indices))
            self._drag_last_update_qpos = None
            self._drag_axis = axis
            self._drag_transform_mode = self.TRANSFORM_ROTATE
            self._drag_mesh_index = active
            self._drag_mesh_indices = list(indices)
            self._drag_start_qpos = (qx, qy)
            self._drag_start_vertices_by_index = {i: list(meshes[i].vertices) for i in indices}
            self._drag_start_vertices = list(self._vertices_for_indices(indices, meshes))
            self._drag_axis_origin = c
            self._drag_axis_vector = vec
            self._drag_axis_screen = None
            self._drag_rotation_center = c
            self._drag_rotation_last_vector = start_vec
            self._drag_rotation_accum_angle = 0.0
            self._drag_rotation_applied_angle = 0.0
            self._highlight_transform_axis(axis)
            self.ui_log(f"[GIZMO] Start rotate axis {axis.upper()} on selection {indices}")
        except Exception:
            log_exception("start_gizmo_rotate_drag")

    def _start_gizmo_scale_drag(self, handle: str, qx: float, qy: float) -> None:
        try:
            if self.active_index is None or self.mesh_store is None or not self._transform_tools_available():
                return
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            if not indices:
                return
            handle = (handle or "").lower().strip()
            axis = self._logical_axis_from_handle(handle)
            if axis is None:
                return
            active = self._active_or_first_selected_index(indices) or indices[-1]
            local_bounds, c, axes = self._oriented_bounds_for_selection(indices, meshes)
            axis_def = axes.get(axis)
            if axis_def is None:
                return
            vec = axis_def[0]
            length = self._gizmo_length_at(c, meshes)
            display_basis = None
            try:
                from laserprog_studio.application.transform_gizmo_api import native_transform_drag_basis

                display_basis = native_transform_drag_basis(self, axis, world_length=length)
            except Exception:
                display_basis = None
            if display_basis is not None:
                sx_qt, sy_qt, world_per_pixel, _display_sign = display_basis
                sx, sy = float(sx_qt), -float(sy_qt)
                norm = math.hypot(sx, sy)
                length_for_screen = max(float(world_per_pixel) * max(norm, 1.0), 1.0e-9)
            else:
                p0 = self._world_to_display(c)
                p1 = self._world_to_display((c[0] + vec[0] * length, c[1] + vec[1] * length, c[2] + vec[2] * length))
                sx, sy = p1[0] - p0[0], p1[1] - p0[1]
                norm = math.hypot(sx, sy)
                length_for_screen = length
            # Overlay2D exposes a unit screen direction. The old 2-pixel
            # guard incorrectly rejected every scale drag on that backend.
            if norm < 1.0e-6:
                return
            side = self._scale_edge_side(handle)
            xmin, xmax, ymin, ymax, zmin, zmax = [float(v) for v in local_bounds]
            pivot_coords = [(xmin + xmax) * 0.5, (ymin + ymax) * 0.5, (zmin + zmax) * 0.5]
            if side is not None:
                if axis == "x":
                    pivot_coords[0] = xmax if side == "min" else xmin
                elif axis == "y":
                    pivot_coords[1] = ymax if side == "min" else ymin
                elif axis == "z":
                    pivot_coords[2] = zmax if side == "min" else zmin
            pivot = self._local_scale_point_to_world((float(pivot_coords[0]), float(pivot_coords[1]), float(pivot_coords[2])), axes)
            self._capture_drag_undo_snapshot()
            self._gizmo_delta_display_signature = None
            self._drag_axis = handle
            self._drag_transform_mode = self.TRANSFORM_SCALE
            self._drag_mesh_index = active
            self._drag_mesh_indices = list(indices)
            self._drag_start_qpos = (qx, qy)
            self._drag_start_vertices_by_index = {i: list(meshes[i].vertices) for i in indices}
            self._drag_start_vertices = list(self._vertices_for_indices(indices, meshes))
            self._capture_drag_actor_state(list(indices))
            self._drag_last_update_qpos = None
            self._drag_axis_origin = c
            self._drag_axis_vector = vec
            self._drag_axis_screen = (sx / norm, -sy / norm, length_for_screen / norm)
            self._drag_scale_bounds = local_bounds
            self._drag_scale_axes = axes
            self._drag_scale_pivot = (float(pivot[0]), float(pivot[1]), float(pivot[2]))
            self._drag_scale_factor = 1.0
            self._highlight_transform_axis(axis)
            if side is None:
                self.ui_log(f"[GIZMO] Start local scale axis {axis.upper()} from center on selection {indices}")
            else:
                self.ui_log(f"[GIZMO] Start local scale edge {axis.upper()}_{side.upper()} with opposite edge fixed on selection {indices}")
        except Exception:
            log_exception("start_gizmo_scale_drag")

    def _update_gizmo_drag(self, qx: float, qy: float) -> None:
        if self._drag_transform_mode == self.TRANSFORM_ROTATE:
            self._update_gizmo_rotate_drag(qx, qy)
        elif self._drag_transform_mode == self.TRANSFORM_SCALE:
            self._update_gizmo_scale_drag(qx, qy)
        else:
            self._update_gizmo_translate_drag(qx, qy)

    def _update_gizmo_translate_drag(self, qx: float, qy: float) -> None:
        try:
            if not self._drag_qpos_changed_enough(qx, qy):
                return
            if self._drag_axis is None or self._drag_axis_vector is None or self._drag_axis_screen is None:
                return
            indices = list(self._drag_mesh_indices or ([] if self._drag_mesh_index is None else [self._drag_mesh_index]))
            if not indices or not self._drag_start_vertices_by_index:
                return
            meshes = self.current_meshes()
            indices = [i for i in indices if 0 <= i < len(meshes) and i in self._drag_start_vertices_by_index]
            if not indices:
                return
            sx, sy, world_per_pixel = self._drag_axis_screen
            q0x, q0y = self._drag_start_qpos or (qx, qy)
            dot = (float(qx) - q0x) * sx + (float(qy) - q0y) * sy
            amount = dot * world_per_pixel
            vx, vy, vz = self._drag_axis_vector
            snap_axis = self._logical_axis_from_handle(self._drag_axis)
            correction = 0.0
            snap = None
            raw_offset = (vx * amount, vy * amount, vz * amount)

            if snap_axis in {"x", "y", "z"}:
                settings = self._snap_settings()
                cache = getattr(self, "_drag_translation_snap_cache", None)
                moving_profile = getattr(self, "_drag_translation_moving_profile", None)
                if cache is not None and moving_profile is not None:
                    scalar_offset = {"x": raw_offset[0], "y": raw_offset[1], "z": raw_offset[2]}[snap_axis]
                    snap = compute_translation_snap_offset_cached(
                        cache=cache,
                        moving_profile=moving_profile,
                        axis=snap_axis,
                        offset=scalar_offset,
                        settings=settings,
                    )
                    self._drag_audit_increment("transform.drag.translate.snap_scalar_cached")
                else:
                    # Compatibility fallback for hot-reloaded/legacy sessions that
                    # started a drag before the moving profile existed.
                    group_start = [v for i in indices for v in self._drag_start_vertices_by_index[i]]
                    group_proposed = [(x + raw_offset[0], y + raw_offset[1], z + raw_offset[2]) for x, y, z in group_start]
                    if cache is not None:
                        snap = compute_translation_snap_cached(
                            cache=cache,
                            start_vertices=group_start,
                            proposed_vertices=group_proposed,
                            axis=snap_axis,
                            settings=settings,
                        )
                    else:
                        snap = compute_translation_snap(
                            meshes=meshes,
                            moving_index=indices[-1],
                            moving_indices=set(indices),
                            start_vertices=group_start,
                            proposed_vertices=group_proposed,
                            axis=snap_axis,
                            settings=settings,
                        )
                    self._drag_audit_increment("transform.drag.translate.snap_vertex_fallback")
                if snap is not None and snap.mode != "none":
                    correction = float(snap.correction)
                    self._set_snap_status(snap.label or snap.mode)
                else:
                    self._set_snap_status(None)

            offset = raw_offset
            if snap_axis == "x":
                offset = (offset[0] + correction, offset[1], offset[2])
            elif snap_axis == "y":
                offset = (offset[0], offset[1] + correction, offset[2])
            elif snap_axis == "z":
                offset = (offset[0], offset[1], offset[2] + correction)
            self._drag_live_translation_offset = offset

            if self._drag_actor_preview_enabled():
                for i in indices:
                    self._set_drag_actor_offset(i, offset)
                try:
                    from laserprog_studio.application.transform_gizmo_api import move_native_translate_gizmo_live

                    if move_native_translate_gizmo_live(self, offset=offset, render=False):
                        self._drag_audit_increment("transform.drag.translate.gizmo_follow")
                except Exception:
                    pass
                self._drag_live_vertices_by_index = {}
                self._drag_audit_increment("transform.drag.translate.actor_offset_fast_path")
            else:
                proposed_by_index: dict[int, list[tuple[float, float, float]]] = {}
                ox, oy, oz = offset
                for i in indices:
                    proposed_by_index[i] = [(x + ox, y + oy, z + oz) for x, y, z in self._drag_start_vertices_by_index[i]]
                    meshes[i].vertices = proposed_by_index[i]
                    self._update_polydata_points(i, proposed_by_index[i])
                self._drag_live_vertices_by_index = proposed_by_index
                self._drag_audit_increment("transform.drag.translate.mesh_live")

            start_center = getattr(self, "_drag_translation_start_center", None)
            live_center = None
            if start_center is not None:
                live_center = (
                    float(start_center[0]) + float(offset[0]),
                    float(start_center[1]) + float(offset[1]),
                    float(start_center[2]) + float(offset[2]),
                )
            self._live_drag_readout(
                self.TRANSFORM_TRANSLATE,
                indices,
                meshes,
                getattr(self, "_drag_live_vertices_by_index", None) or None,
                translation_center=live_center,
            )
            self._request_drag_render("transform.drag.translate")
        except Exception:
            log_exception("update_gizmo_translate_drag")

    def _update_gizmo_rotate_drag(self, qx: float, qy: float) -> None:
        try:
            if not self._drag_qpos_changed_enough(qx, qy):
                return
            if self._drag_axis is None or self._drag_axis_vector is None or self._drag_rotation_center is None:
                return
            indices = list(self._drag_mesh_indices or ([] if self._drag_mesh_index is None else [self._drag_mesh_index]))
            if not indices or not self._drag_start_vertices_by_index:
                return
            meshes = self.current_meshes()
            indices = [i for i in indices if 0 <= i < len(meshes) and i in self._drag_start_vertices_by_index]
            if not indices:
                return
            active = self._drag_mesh_index if self._drag_mesh_index in indices else indices[-1]
            curr_vec = self._rotation_vector_from_qt(qx, qy, self._drag_rotation_center, self._drag_axis_vector)
            if curr_vec is not None and self._drag_rotation_last_vector is not None:
                delta = self._signed_angle_between(self._drag_rotation_last_vector, curr_vec, self._drag_axis_vector)
                if abs(delta) <= math.radians(60.0):
                    self._drag_rotation_accum_angle += delta
                    self._drag_rotation_last_vector = curr_vec
            elif self._drag_rotation_last_vector is None and self._drag_start_qpos is not None:
                q0x, q0y = self._drag_start_qpos
                self._drag_rotation_accum_angle = ((float(qx) - q0x) - (float(qy) - q0y)) * math.radians(0.45)
            raw_angle = float(self._drag_rotation_accum_angle)
            start_euler = self._drag_start_rotation_euler or self._mesh_rotation_euler(meshes[active])
            logical_axis = self._logical_axis_from_handle(self._drag_axis)
            base_abs_deg = 0.0
            if logical_axis == "x":
                base_abs_deg = float(start_euler[0])
            elif logical_axis == "y":
                base_abs_deg = float(start_euler[1])
            elif logical_axis == "z":
                base_abs_deg = float(start_euler[2])
            angle, snap_label, _snapped_abs_deg = self._snap_rotation_angle(raw_angle, base_abs_deg)
            self._drag_rotation_applied_angle = float(angle)
            self._set_snap_status(snap_label if snap_label else None)
            if self._drag_actor_preview_enabled():
                self._apply_drag_actor_matrix(indices, self._drag_rotation_matrix(self._drag_rotation_center, self._drag_axis_vector, angle))
                self._drag_audit_increment("transform.drag.rotate.actor_preview")
            else:
                delta_quat = self._quat_from_axis_angle_tuple(self._drag_axis_vector, angle)
                for i in indices:
                    start_vertices = self._drag_start_vertices_by_index[i]
                    start_quat, _start_euler_i = self._drag_start_rotation_state_by_index.get(i, (self._mesh_rotation_quat(meshes[i]), self._mesh_rotation_euler(meshes[i])))
                    target_quat = self._quat_normalize(self._quat_multiply(delta_quat, start_quat))
                    new_vertices = self._rotate_vertices_by_quaternion_tuple(start_vertices, self._drag_rotation_center, delta_quat)
                    meshes[i].vertices = new_vertices
                    self._set_mesh_rotation_state(meshes[i], target_quat, self._euler_xyz_deg_from_quat(target_quat))
                    self._update_polydata_points(i, new_vertices)
                self._drag_audit_increment("transform.drag.rotate.mesh_live")
            self._live_drag_readout(self.TRANSFORM_ROTATE, indices, meshes)
            self._request_drag_render("transform.drag.rotate")
        except Exception:
            log_exception("update_gizmo_rotate_drag")

    def _update_gizmo_scale_drag(self, qx: float, qy: float) -> None:
        try:
            if not self._drag_qpos_changed_enough(qx, qy):
                return
            if self._drag_axis is None or self._drag_axis_screen is None or self._drag_scale_bounds is None or self._drag_scale_pivot is None:
                return
            axis = self._logical_axis_from_handle(self._drag_axis)
            if axis is None:
                return
            indices = list(self._drag_mesh_indices or ([] if self._drag_mesh_index is None else [self._drag_mesh_index]))
            if not indices or not self._drag_start_vertices_by_index:
                return
            meshes = self.current_meshes()
            indices = [i for i in indices if 0 <= i < len(meshes) and i in self._drag_start_vertices_by_index]
            if not indices:
                return
            sx, sy, world_per_pixel = self._drag_axis_screen
            q0x, q0y = self._drag_start_qpos or (qx, qy)
            dot = (float(qx) - q0x) * sx + (float(qy) - q0y) * sy
            amount = dot * world_per_pixel
            b = self._drag_scale_bounds
            dim_lookup = {"x": float(b[1] - b[0]), "y": float(b[3] - b[2]), "z": float(b[5] - b[4])}
            start_dim = max(dim_lookup.get(axis, 1.0), 1e-6)
            side = self._scale_edge_side(self._drag_axis)
            new_dim = start_dim - amount if side == "min" else start_dim + amount
            min_dim = max(0.10, start_dim * 0.015)
            max_dim = max(start_dim * 50.0, min_dim * 10.0)
            new_dim = max(min_dim, min(max_dim, float(new_dim)))
            factor = float(new_dim / start_dim)
            axis_vector = self._drag_axis_vector or self._gizmo_axis_definitions().get(axis, ((1.0, 0.0, 0.0), "#ffffff"))[0]
            locked = bool(getattr(self, "scale_ratio_locked", False))
            scale_axes = getattr(self, "_drag_scale_axes", None) or {}

            def scaled_vertices_for_index(index: int, scale_factor: float) -> list[tuple[float, float, float]]:
                if locked:
                    vertices = list(self._drag_start_vertices_by_index[index])
                    for logical in ("x", "y", "z"):
                        vec = scale_axes.get(logical, (None,))[0] if isinstance(scale_axes, dict) else None
                        if vec is None:
                            vec = self._gizmo_axis_definitions().get(logical, ((1.0, 0.0, 0.0), "#ffffff"))[0]
                        vertices = self._scale_vertices_along_vector(vertices, self._drag_scale_pivot, vec, scale_factor)
                    return vertices
                return self._scale_vertices_along_vector(self._drag_start_vertices_by_index[index], self._drag_scale_pivot, axis_vector, scale_factor)

            snap_label = None
            # The X/Y/Z cube handles stay free-form; only the adaptive rectangle
            # frame edges participate in smart snap so direct axis scaling remains
            # predictable and never jumps to contacts unexpectedly.
            if side is not None and self._scale_handle_is_frame_edge(self._drag_axis):
                settings = self._snap_settings()
                if settings.smart_enabled:
                    proposed_by_index = {i: scaled_vertices_for_index(i, factor) for i in indices}
                    group_proposed = [v for i in indices for v in proposed_by_index[i]]
                    snap = find_smart_scale_edge_snap(
                        meshes=meshes,
                        moving_index=indices[-1],
                        moving_indices=set(indices),
                        proposed_vertices=group_proposed,
                        axis=axis,
                        axis_vector=axis_vector,
                        dragged_anchor=side,
                        tolerance=max(float(settings.smart_tolerance), 0.0),
                    )
                    if snap.mode == "smart":
                        snapped_dim = new_dim - snap.correction if side == "min" else new_dim + snap.correction
                        snapped_dim = max(min_dim, min(max_dim, float(snapped_dim)))
                        if abs(snapped_dim - new_dim) > 1e-9:
                            new_dim = snapped_dim
                            factor = float(new_dim / start_dim)
                            snap_label = snap.label or snap.mode
            self._drag_scale_factor = factor
            self._set_snap_status(snap_label)
            if self._drag_actor_preview_enabled():
                self._apply_drag_actor_matrix(indices, self._drag_scale_matrix(axis, factor))
                self._drag_audit_increment("transform.drag.scale.actor_preview")
            else:
                for i in indices:
                    new_vertices = scaled_vertices_for_index(i, factor)
                    meshes[i].vertices = new_vertices
                    self._update_polydata_points(i, new_vertices)
                self._drag_audit_increment("transform.drag.scale.mesh_live")
            self._live_drag_readout(self.TRANSFORM_SCALE, indices, meshes)
            self._request_drag_render("transform.drag.scale")
        except Exception:
            log_exception("update_gizmo_scale_drag")

    def _finish_gizmo_drag(self) -> None:
        try:
            axis = self._drag_axis
            idx = self._drag_mesh_index
            mode = self._drag_transform_mode
            dragged_indices = list(self._drag_mesh_indices or ([] if idx is None else [idx]))
            if axis is not None and mode is not None:
                self._commit_live_transform_preview()
                self._commit_drag_undo_snapshot(f"Gizmo {mode}")
                try:
                    from ..rendering.incremental_scene import sync_mesh_render_signatures

                    sync_mesh_render_signatures(self, dragged_indices)
                except Exception:
                    pass
            else:
                self._drag_undo_snapshot = None
            applied_angle = float(self._drag_rotation_applied_angle or self._drag_rotation_accum_angle or 0.0)
            angle_deg = math.degrees(applied_angle)
            scale_factor = float(self._drag_scale_factor or 1.0)
            self._drag_axis = None
            self._drag_transform_mode = None
            self._drag_mesh_index = None
            self._drag_mesh_indices = []
            self._drag_start_qpos = None
            self._drag_start_vertices = None
            self._drag_start_vertices_by_index = {}
            self._drag_start_actor_position_by_index = {}
            self._drag_start_actor_user_matrix_by_index = {}
            self._drag_live_vertices_by_index = {}
            self._drag_start_rotation_state_by_index = {}
            self._drag_axis_origin = None
            self._drag_axis_vector = None
            self._drag_axis_screen = None
            self._drag_rotation_center = None
            self._drag_rotation_last_vector = None
            self._drag_rotation_accum_angle = 0.0
            self._drag_rotation_applied_angle = 0.0
            self._drag_start_rotation_quat = None
            self._drag_start_rotation_euler = None
            self._drag_scale_bounds = None
            self._drag_scale_axes = None
            self._drag_scale_pivot = None
            self._drag_scale_factor = 1.0
            self._drag_translation_snap_cache = None
            self._drag_translation_moving_profile = None
            self._drag_translation_start_center = None
            self._drag_live_translation_offset = None
            try:
                self._native_transform_gizmo_drag_base_snapshot = None
                self._native_transform_gizmo_drag_live_offset = None
            except Exception:
                pass
            self._drag_last_render_time = 0.0
            self._drag_last_readout_time = 0.0
            self._drag_last_update_qpos = None
            self._drag_render_skipped = False
            self._gizmo_live_refresh_pending = False
            self._set_snap_status(None)
            # Axis highlight is persistent (click) and should not be cleared at drag end.
            self._apply_highlighted_transform_axis()
            self.update_gizmo(render=False)
            self.refresh_actor_styles(render=False)
            self.update_inspector()
            self._gizmo_delta_display_signature = None
            request = getattr(self, "request_render", None)
            if callable(request):
                request(reason="transform.drag.finish", force=True)
            else:
                self.plotter.render()
            if axis is not None and idx is not None:
                logical_axis = self._logical_axis_from_handle(axis) or str(axis).upper()
                if mode == self.TRANSFORM_ROTATE:
                    self.ui_log(f"[GIZMO] End rotate axis {str(logical_axis).upper()} part {idx} angle={angle_deg:.1f} deg")
                elif mode == self.TRANSFORM_SCALE:
                    self.ui_log(f"[GIZMO] End scale axis {str(logical_axis).upper()} part {idx} factor={scale_factor:.3f}")
                else:
                    self.ui_log(f"[GIZMO] End translate axis {str(logical_axis).upper()} part {idx}")
        except Exception:
            log_exception("finish_gizmo_drag")

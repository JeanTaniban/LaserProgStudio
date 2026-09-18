# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from ..rendering.handles import ArrowHandleDimensions, make_arrow_handle_mesh, split_handle_dimensions_from_gizmo_length


class SplitPlaneToolLayer:
    def _clear_split_plane_actor(self, render: bool = True) -> None:
        try:
            actors = [
                getattr(self, "split_plane_actor", None),
                getattr(self, "split_plane_edge_actor", None),
                getattr(self, "split_plane_handle_actor", None),
            ]
            overlay = getattr(self, "gizmo_overlay_renderer", None)
            for actor in actors:
                if actor is None:
                    continue
                try:
                    if overlay is not None:
                        overlay.RemoveActor(actor)
                except Exception:
                    pass
                try:
                    self.plotter.remove_actor(actor, render=False)
                except Exception:
                    pass
            self.split_plane_actor = None
            self.split_plane_edge_actor = None
            self.split_plane_handle_actor = None
            if render:
                try:
                    self.plotter.render()
                except Exception:
                    pass
        except Exception:
            log_exception("clear_split_plane_actor")

    def _split_reference_center(self) -> tuple[float, float, float]:
        """Center used as the zero origin for the split-plane forward offset."""
        try:
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            if indices:
                return self._selection_center(indices, meshes)
            b = scene_bounds(meshes)
            return self._bounds_center_tuple(b)
        except Exception:
            return (0.0, 0.0, 0.0)

    def _split_plane_offset(self) -> float:
        """Signed distance from the selection center along the split plane normal."""
        try:
            return float(self.split_offset.value())
        except Exception:
            return 0.0

    def _split_offset_limits(self) -> tuple[float, float]:
        """Allowed forward offset range so the plane stays inside the selection.

        This is intentionally simple and robust: project every selected vertex on
        the current plane normal relative to the selection center, then clamp the
        offset to that interval. For a multi-selection this constrains the plane
        inside the combined projected extent.
        """
        try:
            import numpy as np
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            if not indices:
                return (0.0, 0.0)
            center = np.asarray(self._selection_center(indices, meshes), dtype=float)
            normal = np.asarray(self._split_plane_normal(), dtype=float)
            n = float(np.linalg.norm(normal))
            if n <= 1e-12:
                return (0.0, 0.0)
            normal = normal / n
            values: list[float] = []
            for idx in indices:
                if 0 <= int(idx) < len(meshes):
                    for vx, vy, vz in getattr(meshes[int(idx)], "vertices", []):
                        values.append(float(np.dot(np.asarray((vx, vy, vz), dtype=float) - center, normal)))
            if not values:
                return (0.0, 0.0)
            lo = float(min(values))
            hi = float(max(values))
            if hi < lo:
                lo, hi = hi, lo
            return (lo, hi)
        except Exception:
            log_exception("split_offset_limits")
            return (0.0, 0.0)

    def _clamp_split_offset(self, value: float) -> float:
        try:
            lo, hi = self._split_offset_limits()
            return float(min(max(float(value), float(lo)), float(hi)))
        except Exception:
            return float(value)

    def _set_split_plane_offset(self, offset: float, *, render: bool = True) -> None:
        try:
            value = self._clamp_split_offset(float(offset))
            self._set_split_values_blocked({self.split_offset: value})
            self._sync_modifier_plane_actor(render=render)
        except Exception:
            log_exception("set_split_plane_offset")

    def _suggested_split_plane_size(self) -> float:
        try:
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            if indices:
                return max(bounds_size(self._selection_world_bounds(indices, meshes)) * 1.4, 20.0)
            return max(bounds_size(scene_bounds(meshes)) * 1.2, 20.0)
        except Exception:
            return 120.0

    def _reset_split_plane_for_current_selection(self, *, render: bool = True, update_size: bool = True) -> None:
        """Recenter the split plane on the current target while preserving rotation."""
        try:
            values: dict[Any, float] = {self.split_offset: 0.0}
            if update_size and hasattr(self, "split_size"):
                values[self.split_size] = self._suggested_split_plane_size()
            self._set_split_values_blocked(values)
            self._sync_modifier_plane_actor(render=render)
            if hasattr(self, "split_report"):
                if self._selected_transform_indices():
                    self.split_report.setText("Plane recentered on the selected target. Move it with the yellow forward handle or the offset value.")
                else:
                    self.split_report.setText("Select one or more target parts to place the split plane.")
        except Exception:
            log_exception("reset_split_plane_for_current_selection")

    def _split_plane_origin(self) -> tuple[float, float, float]:
        try:
            c = self._split_reference_center()
            n = self._split_plane_normal()
            o = self._clamp_split_offset(self._split_plane_offset())
            return (float(c[0] + n[0] * o), float(c[1] + n[1] * o), float(c[2] + n[2] * o))
        except Exception:
            return (0.0, 0.0, 0.0)

    def _split_plane_normal(self) -> tuple[float, float, float]:
        try:
            import numpy as np
            q = self._quat_from_euler_xyz_deg(float(self.split_rx.value()), float(self.split_ry.value()), float(self.split_rz.value()))
            mat = self._quat_to_matrix(q)
            n = np.asarray(mat[:, 2], dtype=float)
            norm = float(np.linalg.norm(n))
            if norm <= 1e-12:
                return (0.0, 0.0, 1.0)
            n = n / norm
            return (float(n[0]), float(n[1]), float(n[2]))
        except Exception:
            return (0.0, 0.0, 1.0)

    def _split_plane_inplane_vectors(self) -> tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]:
        try:
            import numpy as np
            q = self._quat_from_euler_xyz_deg(float(self.split_rx.value()), float(self.split_ry.value()), float(self.split_rz.value()))
            mat = self._quat_to_matrix(q)
            out = []
            for col in (0, 1, 2):
                v = np.asarray(mat[:, col], dtype=float)
                n = float(np.linalg.norm(v))
                if n <= 1e-12:
                    v = np.asarray(((1,0,0),(0,1,0),(0,0,1))[col], dtype=float)
                else:
                    v = v / n
                out.append((float(v[0]), float(v[1]), float(v[2])))
            return out[0], out[1], out[2]
        except Exception:
            return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)

    def _add_split_overlay_actor(self, mesh: Any, *, color: str, opacity: float = 1.0, pickable: bool = False, line_width: float | None = None) -> Any | None:
        """Add an actor for the split modifier in the foreground overlay renderer."""
        try:
            import vtk
            overlay = self._ensure_gizmo_overlay_renderer()
            if overlay is None:
                return None
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(mesh)
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            r, g, b = parse_hex_color(color)
            prop = actor.GetProperty()
            prop.SetColor(float(r), float(g), float(b))
            prop.SetOpacity(float(opacity))
            prop.SetAmbient(1.0)
            prop.SetDiffuse(0.0)
            prop.SetSpecular(0.0)
            if line_width is not None:
                try:
                    prop.SetLineWidth(float(line_width))
                except Exception:
                    pass
            try:
                actor.SetPickable(bool(pickable))
            except Exception:
                if pickable:
                    actor.PickableOn()
                else:
                    actor.PickableOff()
            overlay.AddActor(actor)
            return actor
        except Exception:
            log_exception("add_split_overlay_actor")
            return None

    def _split_plane_handle_dimensions(self, origin: tuple[float, float, float], plane_size: float) -> ArrowHandleDimensions:
        """Return camera-adaptive dimensions for the Cut/Split plane handle.

        The controller owns only the camera/selection context. Low-level handle
        proportions and mesh construction live in ``rendering.handles`` so other
        future manipulators can reuse the same sizing rules instead of copying
        PyVista/VTK magic numbers into tool controllers.
        """
        eps = 1.0e-6
        try:
            gizmo_len = float(self._gizmo_length_at(origin, self.current_meshes()))
        except Exception:
            try:
                gizmo_len = max(float(self._camera_visible_height_at(origin)) * 0.16, eps)
            except Exception:
                gizmo_len = max(float(plane_size) * 0.10, eps)
        return split_handle_dimensions_from_gizmo_length(gizmo_len)

    def _sync_modifier_plane_actor(self, render: bool = True) -> None:
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_SPLIT:
                self._clear_split_plane_actor(render=False)
                return
            # v58: Split modifier is now drawn and dragged by Projected Drawing 2D
            # from tooling.split_tool. Keep this historical PyVista overlay as a
            # no-op fallback only for old unmigrated hosts; the current app must
            # not create a second 3D plane/handle on top of the 2D API gizmo.
            if getattr(self, "tool_context", None) is not None:
                self._clear_split_plane_actor(render=False)
                return
            if not hasattr(self, "split_offset"):
                return
            if not self._selected_transform_indices():
                self._clear_split_plane_actor(render=False)
                return
            import pyvista as pv
            import numpy as np
            # Keep the UI value inside the current target extent before drawing.
            current_offset = self._split_plane_offset()
            clamped_offset = self._clamp_split_offset(current_offset)
            if abs(float(clamped_offset) - float(current_offset)) > 1e-6:
                self._set_split_values_blocked({self.split_offset: clamped_offset})
            origin = self._split_plane_origin()
            normal = self._split_plane_normal()
            size = max(float(self.split_size.value()), 1e-6)
            x_axis, y_axis, forward = self._split_plane_inplane_vectors()
            self._clear_split_plane_actor(render=False)

            plane = pv.Plane(center=origin, direction=normal, i_size=size, j_size=size, i_resolution=1, j_resolution=1)
            self.split_plane_actor = self._add_split_overlay_actor(plane, color="#66D9FF", opacity=0.34, pickable=False)

            # Foreground outline, kept separate so the plane stays readable even when transparent.
            try:
                x = np.asarray(x_axis, dtype=float)
                y = np.asarray(y_axis, dtype=float)
                c = np.asarray(origin, dtype=float)
                half = float(size) * 0.5
                pts = np.asarray([c - x*half - y*half, c + x*half - y*half, c + x*half + y*half, c - x*half + y*half], dtype=float)
                lines = np.asarray([5, 0, 1, 2, 3, 0], dtype=np.int64)
                edge = pv.PolyData(pts)
                edge.lines = lines
                self.split_plane_edge_actor = self._add_split_overlay_actor(edge, color="#FFFFFF", opacity=0.95, pickable=False, line_width=2.0)
            except Exception:
                pass

            # Forward handle: grab this arrow to slide the cutting plane along its normal.
            try:
                handle_dims = self._split_plane_handle_dimensions(origin, size)
                arrow = make_arrow_handle_mesh(origin, forward, handle_dims)
                self.split_plane_handle_actor = self._add_split_overlay_actor(arrow, color="#FFD54F", opacity=1.0, pickable=True)
                try:
                    self.ui_log(
                        f"[SPLIT_HANDLE] len={float(handle_dims.length):.4f} "
                        f"shaft_radius={float(handle_dims.shaft_radius):.5f} tip_radius={float(handle_dims.tip_radius):.5f}"
                    )
                except Exception:
                    pass
            except Exception:
                self.split_plane_handle_actor = None
                log_exception("sync_split_plane_handle")

            if render:
                self.plotter.render()
        except Exception:
            log_exception("sync_modifier_plane_actor")

    def _on_split_plane_params_changed(self, *_args) -> None:
        if bool(getattr(self, "_updating_split_plane_fields", False)):
            return
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) == self.TOOL_MOD_SPLIT:
                # Rotation changes alter the plane normal, so the allowed forward
                # offset interval must be recomputed and the value clamped.
                if hasattr(self, "split_offset"):
                    value = float(self.split_offset.value())
                    clamped = self._clamp_split_offset(value)
                    if abs(value - clamped) > 1e-6:
                        self._set_split_values_blocked({self.split_offset: clamped})
                self._sync_modifier_plane_actor(render=True)
        except Exception:
            log_exception("on_split_plane_params_changed")

    def _set_split_values_blocked(self, values: dict[Any, float]) -> None:
        self._updating_split_plane_fields = True
        try:
            for widget, value in values.items():
                try:
                    widget.blockSignals(True)
                    widget.setValue(float(value))
                    widget.blockSignals(False)
                except Exception:
                    pass
        finally:
            self._updating_split_plane_fields = False

    def _initialize_split_modifier_from_selection(self) -> None:
        try:
            if not self._selected_transform_indices():
                self._clear_split_plane_actor(render=False)
                if hasattr(self, "split_report"):
                    self.split_report.setText("Select one or more target parts before opening the split modifier.")
                return
            self._set_split_values_blocked({
                self.split_offset: 0.0,
                self.split_size: self._suggested_split_plane_size(),
            })
            self._sync_modifier_plane_actor(render=False)
            if hasattr(self, "split_report"):
                self.split_report.setText("Offset 0 places the plane at the selected target center. Grab the yellow handle to move it along the plane normal.")
        except Exception:
            log_exception("initialize_split_modifier_from_selection")

    def _set_split_plane_to_selection_center(self) -> None:
        try:
            indices = self._selected_transform_indices()
            if not indices:
                self.ui_log("[SPLIT] Select a part first")
                return
            self._set_split_plane_offset(0.0, render=True)
        except Exception:
            log_exception("set_split_plane_to_selection_center")

    def _orient_split_plane_to_camera(self) -> None:
        try:
            import numpy as np
            cam = self.plotter.camera
            pos = np.asarray(cam.GetPosition(), dtype=float)
            foc = np.asarray(cam.GetFocalPoint(), dtype=float)
            direction = foc - pos
            n = float(np.linalg.norm(direction))
            if n <= 1e-12:
                return
            normal = direction / n
            # Build Euler from a matrix whose local Z follows the camera view. Keep
            # this intentionally simple: it is a convenience button, not the core
            # split math.
            up = np.asarray(cam.GetViewUp(), dtype=float)
            up = up / (float(np.linalg.norm(up)) or 1.0)
            x_axis = np.cross(up, normal)
            if float(np.linalg.norm(x_axis)) <= 1e-8:
                x_axis = np.asarray((1.0, 0.0, 0.0), dtype=float)
            x_axis = x_axis / (float(np.linalg.norm(x_axis)) or 1.0)
            y_axis = np.cross(normal, x_axis)
            y_axis = y_axis / (float(np.linalg.norm(y_axis)) or 1.0)
            mat = np.column_stack((x_axis, y_axis, normal))
            # Convert matrix to quaternion, then to the app Euler convention.
            tr = float(np.trace(mat))
            if tr > 0.0:
                s = math.sqrt(tr + 1.0) * 2.0
                qw = 0.25 * s
                qx = (mat[2, 1] - mat[1, 2]) / s
                qy = (mat[0, 2] - mat[2, 0]) / s
                qz = (mat[1, 0] - mat[0, 1]) / s
            else:
                qw, qx, qy, qz = 1.0, 0.0, 0.0, 0.0
            rx, ry, rz = self._euler_xyz_deg_from_quat(self._quat_normalize((float(qw), float(qx), float(qy), float(qz))))
            self._set_split_values_blocked({self.split_rx: rx, self.split_ry: ry, self.split_rz: rz})
            self._sync_modifier_plane_actor(render=True)
        except Exception:
            log_exception("orient_split_plane_to_camera")

    def generate_split_modifier_preview(self) -> None:
        try:
            indices = self._selected_transform_indices()
            if not indices:
                self.ui_log("[SPLIT] Select one or more parts before preview")
                QMessageBox.information(self, "Split modifier", "Select one or more parts before previewing the split.")
                return
            base_meshes = [copy.deepcopy(m) for m in self.committed_meshes()]
            valid = [i for i in indices if 0 <= int(i) < len(base_meshes)]
            if not valid:
                raise ValueError("Invalid split selection.")
            from laserprog_studio.modifiers.split_plane import split_selected_meshes_by_plane
            origin = self._split_plane_origin()
            normal = self._split_plane_normal()
            tol = max(float(self.split_tol.value()), 1e-8)
            meshes, new_selection, split_count, new_piece_count = split_selected_meshes_by_plane(
                base_meshes, valid, origin=origin, normal=normal, tolerance=tol
            )
            if split_count <= 0:
                self.ui_log("[SPLIT] Plane does not cut the selected mesh(es)")
                if hasattr(self, "split_report"):
                    self.split_report.setText("No split: the plane does not cross the selected mesh volume.")
                return
            self.set_preview_meshes(meshes, f"Split modifier preview: parts={split_count} pieces={new_piece_count}")
            self.selected_indices = [i for i in new_selection if 0 <= i < len(meshes)]
            self.active_index = self.selected_indices[-1] if self.selected_indices else None
            self.refresh_actor_styles(render=False)
            self.update_inspector()
            self.update_gizmo(render=False)
            self._sync_modifier_plane_actor(render=False)
            self.plotter.render()
            if hasattr(self, "split_report"):
                self.split_report.setText(f"Preview ready: {split_count} mesh(es) split into {new_piece_count} piece(s). Apply to validate.")
            self.ui_log(f"[SPLIT] Preview OK: selection={valid} split_meshes={split_count} new_pieces={new_piece_count}")
        except Exception as exc:
            log_exception("generate_split_modifier_preview")
            QMessageBox.warning(self, "Split modifier", str(exc))

    def _start_split_plane_handle_drag(self, qx: float, qy: float) -> None:
        try:
            origin = self._split_plane_origin()
            forward = self._split_plane_normal()
            size = max(float(self.split_size.value()), 1e-6)
            length = max(size * 0.30, 1e-6)
            p0 = self._world_to_display(origin)
            p1 = self._world_to_display((origin[0] + forward[0] * length, origin[1] + forward[1] * length, origin[2] + forward[2] * length))
            sx, sy = p1[0] - p0[0], p1[1] - p0[1]
            norm = math.hypot(sx, sy)
            if norm < 2.0:
                return
            self._split_drag_active = True
            self._split_handle_pressed = False
            self._split_drag_start_offset = float(self._split_plane_offset())
            self._split_drag_axis_vector = (float(forward[0]), float(forward[1]), float(forward[2]))
            self._split_drag_axis_screen = (sx / norm, -sy / norm, length / norm)
            self.ui_log("[SPLIT] Start moving plane along forward axis")
        except Exception:
            log_exception("start_split_plane_handle_drag")

    def _update_split_plane_handle_drag(self, qx: float, qy: float) -> None:
        try:
            if not self._split_drag_active or self._split_drag_start_offset is None or self._split_drag_axis_vector is None or self._split_drag_axis_screen is None:
                return
            q0x, q0y = self._split_handle_press_pos or (qx, qy)
            sx, sy, world_per_pixel = self._split_drag_axis_screen
            dot = (float(qx) - q0x) * sx + (float(qy) - q0y) * sy
            amount = dot * world_per_pixel
            start = float(self._split_drag_start_offset)
            new_offset = start + float(amount)
            self._set_split_plane_offset(new_offset, render=True)
        except Exception:
            log_exception("update_split_plane_handle_drag")

    def _finish_split_plane_handle_drag(self) -> None:
        try:
            was_active = bool(getattr(self, "_split_drag_active", False))
            self._split_handle_pressed = False
            self._split_handle_press_pos = None
            self._split_drag_active = False
            self._split_drag_start_offset = None
            self._split_drag_axis_vector = None
            self._split_drag_axis_screen = None
            if was_active:
                self._sync_modifier_plane_actor(render=True)
                self.ui_log("[SPLIT] End moving plane")
        except Exception:
            log_exception("finish_split_plane_handle_drag")

# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class TransformInspectorLayer:

    def _current_scale_field_values(self) -> tuple[float, float, float]:
        try:
            return (float(self.scale_x.value()), float(self.scale_y.value()), float(self.scale_z.value()))
        except Exception:
            return (1.0, 1.0, 1.0)

    def _update_scale_lock_reference(self) -> None:
        try:
            values = self._current_scale_field_values()
            if all(float(v) > 0.0 for v in values):
                self._scale_lock_last_values = values
        except Exception:
            pass

    def _is_scale_ratio_locked(self) -> bool:
        try:
            return bool(getattr(self, "scale_ratio_locked", False))
        except Exception:
            return False

    def _set_scale_ratio_locked(self, locked: bool, reason: str = "ui") -> None:
        previous = bool(getattr(self, "scale_ratio_locked", False))
        self.scale_ratio_locked = bool(locked)
        try:
            self.transform_state.scale_ratio_locked = bool(locked)
        except Exception:
            pass
        self._sync_scale_ratio_lock_widgets()
        self._update_scale_lock_reference()
        if previous != bool(locked):
            try:
                self.ui_log(f"[TRANSFORM] Scale ratio lock: {'on' if locked else 'off'} ({reason})")
            except Exception:
                pass

    def _on_scale_ratio_lock_changed(self, checked: bool) -> None:
        if bool(getattr(self, "_updating_scale_ratio_lock_widgets", False)):
            return
        self._set_scale_ratio_locked(bool(checked), "toggle")

    def _sync_scale_ratio_lock_widgets(self) -> None:
        previous = bool(getattr(self, "_updating_scale_ratio_lock_widgets", False))
        self._updating_scale_ratio_lock_widgets = True
        try:
            locked = bool(getattr(self, "scale_ratio_locked", False))
            for widget in (getattr(self, "scale_ratio_lock_check", None), getattr(self, "light_scale_ratio_lock", None)):
                if widget is None:
                    continue
                try:
                    widget.blockSignals(True)
                    widget.setChecked(locked)
                    widget.blockSignals(False)
                except Exception:
                    pass
            light_lock = getattr(self, "light_scale_ratio_lock", None)
            if light_lock is not None:
                try:
                    is_scale = str(getattr(self, "_light_transform_mode", "position")) == "scale"
                    available = bool(self._transform_tools_available())
                    refresh = getattr(self, "_refresh_light_scale_lock_button", None)
                    if callable(refresh):
                        refresh(locked=locked, is_scale=is_scale, available=available)
                    else:
                        light_lock.setVisible(is_scale)
                        light_lock.setEnabled(is_scale and available)
                except Exception:
                    pass
        finally:
            self._updating_scale_ratio_lock_widgets = previous

    def _propagate_locked_scale_change_from_widgets(self, widgets: list[Any]) -> bool:
        """When ratio lock is on, propagate the edited scale field to the others.

        The reference is the last inspector-synchronised size triple. This keeps
        ratios stable for both the right inspector and the compact transform
        overlay instead of using already-mutated spinbox values.
        """
        if not self._is_scale_ratio_locked() or bool(getattr(self, "_updating_scale_ratio_lock_fields", False)):
            return False
        try:
            sender = self.sender()
        except Exception:
            sender = None
        if sender not in widgets:
            return False
        try:
            idx = widgets.index(sender)
            current = [max(float(w.value()), 0.001) for w in widgets]
            reference = getattr(self, "_scale_lock_last_values", None)
            if not reference or len(reference) != 3 or any(float(v) <= 0.0 for v in reference):
                reference = tuple(current)
            old_axis = max(float(reference[idx]), 1e-9)
            factor = max(float(current[idx]) / old_axis, 1e-9)
            new_values = [max(float(reference[i]) * factor, 0.001) for i in range(3)]
            new_values[idx] = current[idx]
            self._updating_scale_ratio_lock_fields = True
            try:
                for widget, value in zip(widgets, new_values):
                    widget.blockSignals(True)
                    widget.setValue(float(value))
                    widget.blockSignals(False)
            finally:
                self._updating_scale_ratio_lock_fields = False
            self._scale_lock_last_values = tuple(float(v) for v in new_values)
            return True
        except Exception:
            log_exception("propagate_locked_scale_change")
            self._updating_scale_ratio_lock_fields = False
            return False

    def _set_spin_values_blocked(self, values: dict[Any, float]) -> None:
        previous = bool(getattr(self, "_updating_transform_fields", False))
        self._updating_transform_fields = True
        try:
            for widget, value in values.items():
                widget.blockSignals(True)
                widget.setValue(float(value))
                widget.blockSignals(False)
        except Exception:
            pass
        finally:
            self._updating_transform_fields = previous
        try:
            if all(hasattr(self, name) for name in ("scale_x", "scale_y", "scale_z")):
                self._update_scale_lock_reference()
                self._sync_scale_ratio_lock_widgets()
        except Exception:
            pass
        try:
            self._sync_light_transform_fields()
        except Exception:
            pass


    def _set_rotation_inspector_value(self, axis: str | None, angle_deg: float) -> None:
        axis = self._logical_axis_from_handle(axis)
        values = {self.rot_x: 0.0, self.rot_y: 0.0, self.rot_z: 0.0}
        if axis == "x":
            values[self.rot_x] = float(angle_deg)
        elif axis == "y":
            values[self.rot_y] = float(angle_deg)
        elif axis == "z":
            values[self.rot_z] = float(angle_deg)
        self._set_spin_values_blocked(values)

    def _set_scale_inspector_value(self, axis: str | None, factor: float) -> None:
        axis = self._logical_axis_from_handle(axis)
        values = {self.scale_x: 1.0, self.scale_y: 1.0, self.scale_z: 1.0}
        if axis == "x":
            values[self.scale_x] = float(factor)
        elif axis == "y":
            values[self.scale_y] = float(factor)
        elif axis == "z":
            values[self.scale_z] = float(factor)
        self._set_spin_values_blocked(values)

    def _current_delta_values(self) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
        return (
            (float(self.rot_x.value()), float(self.rot_y.value()), float(self.rot_z.value())),
            (float(self.scale_x.value()), float(self.scale_y.value()), float(self.scale_z.value())),
        )

    def _set_gizmo_delta_display_signature(self, mode: str, idx: int) -> None:
        try:
            rot_values, scale_values = self._current_delta_values()
            self._gizmo_delta_display_signature = (str(mode), int(idx), rot_values, scale_values)
        except Exception:
            self._gizmo_delta_display_signature = None

    def _display_signature_matches_current_fields(self) -> bool:
        try:
            sig = self._gizmo_delta_display_signature
            if sig is None:
                return False
            _mode, idx, rot_values, scale_values = sig
            if idx != self.active_index:
                return False
            cur_rot, cur_scale = self._current_delta_values()
            tol = 1e-6
            return all(abs(a - b) <= tol for a, b in zip(rot_values, cur_rot)) and all(abs(a - b) <= tol for a, b in zip(scale_values, cur_scale))
        except Exception:
            return False

    def _on_transform_field_changed(self, *_args) -> None:
        """Apply inspector edits immediately to the active mesh."""
        if bool(getattr(self, "_updating_transform_fields", False)):
            return
        if bool(getattr(self, "_live_transform_update_active", False)):
            return
        if self._drag_transform_mode is not None:
            return
        planar = getattr(self, "planar_tool_controller", None)
        if planar is not None and callable(getattr(planar, "update_selected_from_transform_fields", None)):
            try:
                if planar.update_selected_from_transform_fields():
                    return
            except Exception:
                log_exception("planar_transform_field_changed")
                return
        if self.active_index is None:
            return
        if not self._transform_tools_available():
            # Open tools and preview workflows own their own Apply/Cancel lifecycle. Do not silently
            # commit transform edits while a tool is active.
            self.update_inspector()
            try:
                self.statusBar().showMessage("Transform disabled while a tool is active", 1800)
            except Exception:
                pass
            return
        try:
            self._propagate_locked_scale_change_from_widgets([self.scale_x, self.scale_y, self.scale_z])
        except Exception:
            log_exception("transform_field_scale_lock")
        self.apply_transform_to_active(live=True)

    def reset_transform_fields(self) -> None:
        """Reload transform values from the active part."""
        self._gizmo_delta_display_signature = None
        self.update_inspector()

    def apply_transform_to_active(self, live: bool = False) -> None:
        indices = self._selected_transform_indices()
        if not indices:
            self.ui_log("[TRANSFORM] No selected part")
            return
        active = self._active_or_first_selected_index(indices)
        if active is None:
            self.ui_log("[TRANSFORM] No active part")
            return
        if bool(getattr(self, "_live_transform_update_active", False)) and not live:
            return
        previous_live_state = bool(getattr(self, "_live_transform_update_active", False))
        self._live_transform_update_active = True
        try:
            self._gizmo_delta_display_signature = None
            meshes = [copy.deepcopy(m) for m in self.current_meshes()]
            indices = [i for i in indices if 0 <= i < len(meshes)]
            if not indices:
                return
            active = active if active in indices else indices[-1]
            old_bounds, old_center, local_axes = self._oriented_bounds_for_selection(indices, meshes)
            old_dims = (
                max(float(old_bounds[1] - old_bounds[0]), 1e-9),
                max(float(old_bounds[3] - old_bounds[2]), 1e-9),
                max(float(old_bounds[5] - old_bounds[4]), 1e-9),
            )
            target_pos = (float(self.pos_x.value()), float(self.pos_y.value()), float(self.pos_z.value()))
            target_dims = (
                max(float(self.scale_x.value()), 0.001),
                max(float(self.scale_y.value()), 0.001),
                max(float(self.scale_z.value()), 0.001),
            )
            sx = target_dims[0] / old_dims[0]
            sy = target_dims[1] / old_dims[1]
            sz = target_dims[2] / old_dims[2]

            active_mesh = meshes[active]
            current_quat = self._mesh_rotation_quat(active_mesh)
            current_euler = self._mesh_rotation_euler(active_mesh)
            target_euler = self._normalize_euler_deg((float(self.rot_x.value()), float(self.rot_y.value()), float(self.rot_z.value())))
            if all(abs(a - b) <= 1e-6 for a, b in zip(current_euler, target_euler)):
                target_quat = current_quat
            else:
                target_quat = self._quat_from_euler_xyz_deg(*target_euler)
            delta_quat = self._quat_normalize(self._quat_multiply(target_quat, self._quat_inverse(current_quat)))
            dx, dy, dz = target_pos[0] - old_center[0], target_pos[1] - old_center[1], target_pos[2] - old_center[2]

            for idx in indices:
                m = meshes[idx]
                vertices = self._scale_vertices_along_vector(m.vertices, old_center, local_axes["x"][0], sx)
                vertices = self._scale_vertices_along_vector(vertices, old_center, local_axes["y"][0], sy)
                vertices = self._scale_vertices_along_vector(vertices, old_center, local_axes["z"][0], sz)
                vertices = self._rotate_vertices_by_quaternion_tuple(vertices, old_center, delta_quat)
                m.vertices = [(x + dx, y + dy, z + dz) for x, y, z in vertices]
                if idx == active:
                    self._set_mesh_rotation_state(m, target_quat, target_euler)
                else:
                    q = self._quat_normalize(self._quat_multiply(delta_quat, self._mesh_rotation_quat(m)))
                    self._set_mesh_rotation_state(m, q, self._euler_xyz_deg_from_quat(q))
            self.selected_indices = [i for i in self.selected_indices if i in indices]
            self.active_index = active
            action = "Live transform" if live else "Transform reset/update"
            if len(indices) == 1:
                self.push_meshes(meshes, f"{action} on {active:02d} - {meshes[active].name}")
            else:
                self.push_meshes(meshes, f"{action} on selection {indices}")
            self.update_inspector()
            self._update_scale_lock_reference()
        except Exception:
            log_exception("apply_transform_to_active")
        finally:
            self._live_transform_update_active = previous_live_state

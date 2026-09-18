# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import datetime as _dt
import math
from typing import Any

from ..app_context import AppContext
from ..bootstrap import compute_paths
from ..mesh_ops import bounds_size, scene_bounds
from ..studio_log import log_exception

from .owner_delegating_controller import OwnerDelegatingController
from .background_tasks import task_manager_for


def _qmessagebox():
    from PySide6.QtWidgets import QMessageBox
    return QMessageBox


def _qtimer():
    from PySide6.QtCore import QTimer
    return QTimer


TOOLBOX_DIR = compute_paths().toolbox_dir


class ModifierPreviewController(OwnerDelegatingController):
    """Preview workflows for modifier tools.

    This controller keeps the current UI-backed modifier previews together while
    removing them from MainWindow inheritance. Later passes can split it again
    into individual StudioTool implementations.
    """

    @classmethod
    def create(cls, context: AppContext) -> "ModifierPreviewController":
        return cls(context)

    def _mesh_triangle_count(self, mesh) -> int:
        try:
            return int(len(getattr(mesh, "triangles", []) or []))
        except Exception:
            return 0

    def _clear_relief_modifier_preview_state(self) -> None:
        try:
            self._relief_anchor = None
            if hasattr(self, "relief_report"):
                self.relief_report.setText("Pick a face to place the text.")
        except Exception:
            pass

    def _initialize_relief_modifier_from_selection(self, render: bool | None = None) -> None:
        try:
            idxs = self._selected_transform_indices()
            self._relief_anchor = None
            if hasattr(self, "relief_report"):
                if not idxs:
                    self.relief_report.setText("Select a part before opening Relief.")
                else:
                    self.relief_report.setText(f"Target: {idxs[-1]}\nPick a face.")
        except Exception:
            log_exception("initialize_relief_modifier")

    def _relief_target_index(self) -> int | None:
        try:
            idxs = self._selected_transform_indices()
            if not idxs:
                return None
            if self.active_index in idxs:
                return int(self.active_index)  # type: ignore[arg-type]
            return int(idxs[-1])
        except Exception:
            return None

    def _relief_mode_code(self) -> str:
        try:
            text = self.relief_mode_combo.currentText().lower()
            return "subtract" if "cut" in text or "subtract" in text or "cut" in text or "subtract" in text else "relief"
        except Exception:
            return "relief"

    def _relief_align_code(self) -> str:
        try:
            text = self.relief_align_combo.currentText().lower()
            if "left" in text or "left" in text:
                return "left"
            if "right" in text or "right" in text:
                return "right"
        except Exception:
            pass
        return "center"

    def _relief_font_family(self) -> str:
        try:
            return str(self.relief_font_combo.currentFont().family())
        except Exception:
            return ""

    def _on_relief_params_changed(self, *args) -> None:
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_RELIEF:
                return
            if getattr(self, "_relief_anchor", None) is not None:
                self._schedule_relief_preview(delay_ms=220)
        except Exception:
            log_exception("relief_params_changed")

    def _schedule_relief_preview(self, *, delay_ms: int = 220) -> None:
        try:
            self._relief_preview_generation = int(getattr(self, "_relief_preview_generation", 0)) + 1
            generation = int(self._relief_preview_generation)
            if hasattr(self, "relief_report") and delay_ms > 0:
                self.relief_report.setText("Parameters changed. Preview updates after a short pause…")
            _qtimer().singleShot(int(max(delay_ms, 0)), lambda g=generation: self._run_relief_preview_if_current(g))
        except Exception:
            log_exception("schedule_relief_preview")

    def _run_relief_preview_if_current(self, generation: int) -> None:
        try:
            if int(generation) != int(getattr(self, "_relief_preview_generation", -1)):
                return
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_RELIEF:
                return
            self.generate_relief_modifier_preview()
        except Exception:
            log_exception("run_relief_preview_if_current")

    def _set_relief_anchor_from_pick(self, mesh_index: int, point, normal) -> None:
        try:
            from laserprog_studio.geometry_ops.text_relief import ReliefAnchor
            self._relief_anchor = ReliefAnchor(int(mesh_index), (float(point[0]), float(point[1]), float(point[2])), (float(normal[0]), float(normal[1]), float(normal[2])))
            self._schedule_relief_preview(delay_ms=0)
        except Exception:
            log_exception("set_relief_anchor")

    def generate_relief_modifier_preview(self) -> None:
        try:
            from laserprog_studio.geometry_ops.text_relief import add_text_relief_preview
            anchor = getattr(self, "_relief_anchor", None)
            target = self._relief_target_index()
            if target is None:
                if hasattr(self, "relief_report"):
                    self.relief_report.setText("Select a target part.")
                return
            if anchor is None:
                if hasattr(self, "relief_report"):
                    self.relief_report.setText(f"Target: {target}\nPick a face.")
                return
            if int(anchor.mesh_index) != int(target):
                if hasattr(self, "relief_report"):
                    self.relief_report.setText("Pick a face on the selected part.")
                return
            text = self.relief_text.text() if hasattr(self, "relief_text") else "Text"
            size = float(self.relief_size.value()) if hasattr(self, "relief_size") else 12.0
            depth = float(self.relief_depth.value()) if hasattr(self, "relief_depth") else 1.5
            rotation = float(self.relief_rotation.value()) if hasattr(self, "relief_rotation") else 0.0
            base = [copy.deepcopy(m) for m in self.committed_meshes()]
            result = add_text_relief_preview(
                base,
                anchor,
                text=text,
                size_mm=size,
                depth_mm=depth,
                rotation_deg=rotation,
                mode=self._relief_mode_code(),
                align=self._relief_align_code(),
                font_family=self._relief_font_family(),
            )
            if not result.ok:
                if hasattr(self, "relief_report"):
                    self.relief_report.setText("\n".join(str(e) for e in result.errors))
                for error in result.errors:
                    self.ui_log(f"[RELIEF][ERROR] {error}")
                return
            self.set_preview_meshes(result.meshes, "Relief preview")
            if hasattr(self, "relief_report"):
                mode_label = "cut / subtract" if self._relief_mode_code() == "subtract" else "raised"
                self.relief_report.setText(
                    f"Relief ready: '{text}'\n"
                    f"Mode: {mode_label}\n"
                    f"Preview object added: {len(result.meshes) - 1}"
                )
            for warning in result.warnings:
                self.ui_log(f"[RELIEF] {warning}")
        except Exception as exc:
            log_exception("generate_relief_modifier_preview")
            if hasattr(self, "relief_report"):
                self.relief_report.setText(str(exc))


    def _clear_extrude_down_modifier_state(self) -> None:
        try:
            self._extrude_down_preview_generation = int(getattr(self, "_extrude_down_preview_generation", 0)) + 1
            self._clear_split_plane_actor(render=False)
            if hasattr(self, "extrude_down_report"):
                self.extrude_down_report.setText("Select one or more parts.")
        except Exception:
            pass

    def _extrude_down_selected_indices(self) -> list[int]:
        try:
            return self._selected_transform_indices()
        except Exception:
            return [int(i) for i in getattr(self, "selected_indices", [])]

    def _extrude_down_limits(self) -> tuple[float, float]:
        try:
            meshes = self.committed_meshes()
            idxs = self._extrude_down_selected_indices()
            values: list[float] = []
            for idx in idxs:
                if 0 <= int(idx) < len(meshes):
                    values.extend(float(v[2]) for v in getattr(meshes[int(idx)], "vertices", []) or [])
            if not values:
                return (0.0, 0.0)
            lo = max(0.0, float(min(values)))
            hi = max(lo, float(max(values)))
            return (lo, hi)
        except Exception:
            return (0.0, 0.0)

    def _suggested_extrude_down_plane_size(self) -> float:
        try:
            meshes = self.current_meshes()
            indices = self._extrude_down_selected_indices()
            if indices:
                return max(bounds_size(self._selection_world_bounds(indices, meshes)) * 1.4, 20.0)
            return max(bounds_size(scene_bounds(meshes)) * 1.2, 20.0)
        except Exception:
            return 120.0

    def _set_extrude_down_values_blocked(self, values: dict[Any, float]) -> None:
        self._updating_extrude_down_fields = True
        try:
            for widget, value in values.items():
                try:
                    widget.blockSignals(True)
                    widget.setValue(float(value))
                    widget.blockSignals(False)
                except Exception:
                    pass
        finally:
            self._updating_extrude_down_fields = False

    def _clamp_extrude_down_z(self, value: float) -> float:
        try:
            lo, hi = self._extrude_down_limits()
            return float(min(max(float(value), float(lo)), float(hi)))
        except Exception:
            return float(value)

    def _initialize_extrude_down_modifier_from_selection(self, render: bool | None = None) -> None:
        try:
            idxs = self._extrude_down_selected_indices()
            if not idxs:
                self._clear_split_plane_actor(render=False)
                if hasattr(self, "extrude_down_report"):
                    self.extrude_down_report.setText("Select one or more parts before opening Extrude down.")
                return
            lo, hi = self._extrude_down_limits()
            # Start around the lower third of the selected volume: useful for feet/socle creation.
            start_z = float(lo + (hi - lo) * 0.33) if hi > lo else float(hi)
            values = {self.extrude_down_z: start_z, self.extrude_down_size: self._suggested_extrude_down_plane_size()}
            self._set_extrude_down_values_blocked(values)
            self._sync_extrude_down_plane_actor(render=False)
            self._schedule_extrude_down_preview(delay_ms=240)
        except Exception:
            log_exception("initialize_extrude_down_modifier")

    def _extrude_down_plane_origin(self) -> tuple[float, float, float]:
        try:
            meshes = self.current_meshes()
            idxs = self._extrude_down_selected_indices()
            if idxs:
                c = self._selection_center(idxs, meshes)
            else:
                c = self._bounds_center_tuple(scene_bounds(meshes))
            z = self._clamp_extrude_down_z(float(self.extrude_down_z.value())) if hasattr(self, "extrude_down_z") else 0.0
            return (float(c[0]), float(c[1]), float(z))
        except Exception:
            return (0.0, 0.0, 0.0)

    def _sync_extrude_down_plane_actor(self, render: bool = True) -> None:
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_EXTRUDE_DOWN:
                return
            # v58: Extrude Down owns its support plane through Projected Drawing
            # 2D in tooling.extrude_down_tool. Avoid resurrecting the retired
            # PyVista split-plane handle for migrated Creator API modifiers.
            if getattr(self, "tool_context", None) is not None:
                self._clear_split_plane_actor(render=False)
                return
            if not hasattr(self, "extrude_down_z") or not self._extrude_down_selected_indices():
                self._clear_split_plane_actor(render=False)
                return
            current_z = float(self.extrude_down_z.value())
            clamped_z = self._clamp_extrude_down_z(current_z)
            if abs(clamped_z - current_z) > 1e-6:
                self._set_extrude_down_values_blocked({self.extrude_down_z: clamped_z})
            import numpy as np
            import pyvista as pv
            origin = self._extrude_down_plane_origin()
            normal = (0.0, 0.0, 1.0)
            size = max(float(self.extrude_down_size.value()), 1e-6)
            self._clear_split_plane_actor(render=False)
            plane = pv.Plane(center=origin, direction=normal, i_size=size, j_size=size, i_resolution=1, j_resolution=1)
            self.split_plane_actor = self._add_split_overlay_actor(plane, color="#69F0AE", opacity=0.30, pickable=False)
            try:
                x = np.asarray((1.0, 0.0, 0.0), dtype=float)
                y = np.asarray((0.0, 1.0, 0.0), dtype=float)
                c = np.asarray(origin, dtype=float)
                half = float(size) * 0.5
                pts = np.asarray([c - x*half - y*half, c + x*half - y*half, c + x*half + y*half, c - x*half + y*half], dtype=float)
                edge = pv.PolyData(pts)
                edge.lines = np.asarray([5, 0, 1, 2, 3, 0], dtype=np.int64)
                self.split_plane_edge_actor = self._add_split_overlay_actor(edge, color="#FFFFFF", opacity=0.95, pickable=False, line_width=2.0)
            except Exception:
                pass
            try:
                dims = self._split_plane_handle_dimensions(origin, size)
                from laserprog_studio.rendering.handles import make_arrow_handle_mesh
                arrow = make_arrow_handle_mesh(origin, normal, dims)
                self.split_plane_handle_actor = self._add_split_overlay_actor(arrow, color="#FFD54F", opacity=1.0, pickable=True)
            except Exception:
                self.split_plane_handle_actor = None
                log_exception("sync_extrude_down_handle")
            if render:
                self.plotter.render()
        except Exception:
            log_exception("sync_extrude_down_plane_actor")

    def _on_extrude_down_params_changed(self, *_args) -> None:
        if bool(getattr(self, "_updating_extrude_down_fields", False)):
            return
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_EXTRUDE_DOWN:
                return
            if hasattr(self, "extrude_down_z"):
                z = float(self.extrude_down_z.value())
                clamped = self._clamp_extrude_down_z(z)
                if abs(z - clamped) > 1e-6:
                    self._set_extrude_down_values_blocked({self.extrude_down_z: clamped})
            self._sync_extrude_down_plane_actor(render=True)
            self._schedule_extrude_down_preview(delay_ms=240)
        except Exception:
            log_exception("extrude_down_params_changed")

    def _schedule_extrude_down_preview(self, *, delay_ms: int = 240) -> None:
        try:
            self._extrude_down_preview_generation = int(getattr(self, "_extrude_down_preview_generation", 0)) + 1
            generation = int(self._extrude_down_preview_generation)
            if hasattr(self, "extrude_down_report"):
                self.extrude_down_report.setText("Plane moved. Preview updates after a short pause…")
            _qtimer().singleShot(int(max(delay_ms, 0)), lambda g=generation: self._run_extrude_down_preview_if_current(g))
        except Exception:
            log_exception("schedule_extrude_down_preview")

    def _run_extrude_down_preview_if_current(self, generation: int) -> None:
        try:
            if int(generation) != int(getattr(self, "_extrude_down_preview_generation", -1)):
                return
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_EXTRUDE_DOWN:
                return
            self.generate_extrude_down_modifier_preview()
        except Exception:
            log_exception("run_extrude_down_preview_if_current")

    def _update_extrude_down_report(self, *, base_meshes=None, preview_meshes=None, warnings: list[str] | tuple[str, ...] = (), error: str | None = None) -> None:
        if not hasattr(self, "extrude_down_report"):
            return
        if error:
            self.extrude_down_report.setText(error)
            return
        base_meshes = self.committed_meshes() if base_meshes is None else base_meshes
        idxs = self._extrude_down_selected_indices()
        before = sum(self._mesh_triangle_count(base_meshes[i]) for i in idxs if 0 <= i < len(base_meshes))
        if preview_meshes is None:
            self.extrude_down_report.setText(f"Selected: {len(idxs)}\nTriangles before: {before}")
            return
        after = sum(self._mesh_triangle_count(preview_meshes[i]) for i in idxs if 0 <= i < len(preview_meshes))
        extra = "\n" + "\n".join(str(w) for w in warnings) if warnings else ""
        self.extrude_down_report.setText(
            f"Preview ready.\n"
            f"Selected: {len(idxs)}\n"
            f"Triangles: {before} → {after}{extra}"
        )

    def generate_extrude_down_modifier_preview(self) -> None:
        try:
            from laserprog_studio.geometry_ops.extrude_down import extrude_selected_meshes_down
            idxs = self._extrude_down_selected_indices()
            if not idxs:
                self._update_extrude_down_report(error="Select at least one part to extrude down.")
                return
            base = [copy.deepcopy(m) for m in self.committed_meshes()]
            z = float(self.extrude_down_z.value()) if hasattr(self, "extrude_down_z") else 0.0
            tol = max(float(self.extrude_down_tol.value()), 1e-8) if hasattr(self, "extrude_down_tol") else 1e-5
            generation = int(getattr(self, "_extrude_down_preview_generation", 0) or 0)
            if generation <= 0:
                self._extrude_down_preview_generation = 1
                generation = 1
            if hasattr(self, "extrude_down_report"):
                self.extrude_down_report.setText("Computing preview in background…")

            def _worker():
                return extrude_selected_meshes_down([copy.deepcopy(m) for m in base], idxs, plane_z=z, ground_z=0.0, tolerance=tol)

            def _success(result) -> None:
                if int(generation) != int(getattr(self, "_extrude_down_preview_generation", -1)):
                    return
                if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_EXTRUDE_DOWN:
                    return
                if not result.ok:
                    self._update_extrude_down_report(error="\n".join(result.errors))
                    for error in result.errors:
                        self.ui_log(f"[EXTRUDE_DOWN][ERROR] {error}")
                    return
                self.set_preview_meshes(result.meshes, f"Extrude down preview z={z:.3f}")
                self.selected_indices = [i for i in idxs if 0 <= i < len(result.meshes)]
                self.active_index = self.selected_indices[-1] if self.selected_indices else None
                self.refresh_actor_styles(render=False)
                self.update_inspector()
                self.update_gizmo(render=False)
                self._sync_extrude_down_plane_actor(render=False)
                self.plotter.render()
                self._update_extrude_down_report(base_meshes=base, preview_meshes=result.meshes, warnings=result.warnings)
                for warning in result.warnings:
                    self.ui_log(f"[EXTRUDE_DOWN] {warning}")

            def _error(exc: BaseException) -> None:
                self._update_extrude_down_report(error=str(exc))
                log_exception("generate_extrude_down_modifier_preview.worker")

            task_manager_for(self.owner).run(
                "preview.extrude_down",
                _worker,
                on_success=_success,
                on_error=_error,
                description="Extrude down preview",
            )
        except Exception as exc:
            log_exception("generate_extrude_down_modifier_preview")
            self._update_extrude_down_report(error=str(exc))

    def _start_extrude_down_handle_drag(self, qx: float, qy: float) -> None:
        try:
            origin = self._extrude_down_plane_origin()
            forward = (0.0, 0.0, 1.0)
            size = max(float(self.extrude_down_size.value()), 1e-6)
            length = max(size * 0.30, 1e-6)
            p0 = self._world_to_display(origin)
            p1 = self._world_to_display((origin[0], origin[1], origin[2] + length))
            sx, sy = p1[0] - p0[0], p1[1] - p0[1]
            norm = math.hypot(sx, sy)
            if norm < 2.0:
                return
            self._split_drag_active = True
            self._split_handle_pressed = False
            self._split_drag_start_offset = float(self.extrude_down_z.value())
            self._split_drag_axis_vector = forward
            self._split_drag_axis_screen = (sx / norm, -sy / norm, length / norm)
            self.ui_log("[EXTRUDE_DOWN] Start moving horizontal plane")
        except Exception:
            log_exception("start_extrude_down_handle_drag")

    def _update_extrude_down_handle_drag(self, qx: float, qy: float) -> None:
        try:
            if not self._split_drag_active or self._split_drag_start_offset is None or self._split_drag_axis_screen is None:
                return
            q0x, q0y = self._split_handle_press_pos or (qx, qy)
            sx, sy, world_per_pixel = self._split_drag_axis_screen
            dot = (float(qx) - q0x) * sx + (float(qy) - q0y) * sy
            new_z = float(self._split_drag_start_offset) + dot * float(world_per_pixel)
            new_z = self._clamp_extrude_down_z(new_z)
            self._set_extrude_down_values_blocked({self.extrude_down_z: new_z})
            self._sync_extrude_down_plane_actor(render=True)
            self._schedule_extrude_down_preview(delay_ms=240)
        except Exception:
            log_exception("update_extrude_down_handle_drag")

    def _finish_extrude_down_handle_drag(self) -> None:
        try:
            was_active = bool(getattr(self, "_split_drag_active", False))
            self._split_handle_pressed = False
            self._split_handle_press_pos = None
            self._split_drag_active = False
            self._split_drag_start_offset = None
            self._split_drag_axis_vector = None
            self._split_drag_axis_screen = None
            if was_active:
                self._sync_extrude_down_plane_actor(render=True)
                self._schedule_extrude_down_preview(delay_ms=240)
                self.ui_log("[EXTRUDE_DOWN] End moving plane")
        except Exception:
            log_exception("finish_extrude_down_handle_drag")

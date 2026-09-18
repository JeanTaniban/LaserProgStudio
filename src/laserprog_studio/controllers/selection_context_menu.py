# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import time
from typing import Any

try:
    from ..studio_log import log_exception
except Exception:  # pragma: no cover
    def log_exception(_where: str) -> None:
        pass


class SelectionContextMenuLayer:
    """Viewport right-click context menu for the current selection.

    A short right click opens the menu. A right drag remains camera pan.  The
    press/release thresholds are intentionally small so the two gestures do not
    fight each other.
    """

    _RIGHT_CONTEXT_MAX_MOVE_PX = 5.0
    _RIGHT_CONTEXT_MAX_SECONDS = 0.38

    def _selection_context_actions(self):
        from ..application.selection_context_actions import SelectionContextActionsController

        controller = getattr(self, "_selection_context_actions_controller", None)
        if controller is None:
            controller = SelectionContextActionsController.create(self)
            self._selection_context_actions_controller = controller
        return controller

    def _selection_context_indices(self) -> list[int]:
        try:
            getter = getattr(self, "_selected_transform_indices", None)
            if callable(getter):
                return list(getter())
        except Exception:
            pass
        out: list[int] = []
        for raw in getattr(self, "selected_indices", []) or []:
            try:
                out.append(int(raw))
            except Exception:
                pass
        return out

    def _right_selection_context_press(self, qx: float, qy: float) -> bool:
        # The context menu is now useful even without selection because it also
        # owns scene creation actions such as ``Primitive board``.  We still
        # keep the small movement threshold below so a real right-drag remains
        # camera pan and does not feel sticky.
        candidate = True
        self._right_context_press_pos = (float(qx), float(qy))
        self._right_context_press_time = time.monotonic()
        self._right_context_candidate = candidate
        return candidate

    def _right_selection_context_moved_px(self, qx: float, qy: float) -> float:
        pos = getattr(self, "_right_context_press_pos", None)
        if not pos:
            return 0.0
        x0, y0 = pos
        return max(abs(float(qx) - float(x0)), abs(float(qy) - float(y0)))

    def _right_selection_context_should_delay_pan(self, qx: float, qy: float) -> bool:
        if not bool(getattr(self, "_right_context_candidate", False)):
            return False
        return self._right_selection_context_moved_px(qx, qy) <= float(self._RIGHT_CONTEXT_MAX_MOVE_PX)

    def _right_selection_context_should_open(self, qx: float, qy: float, *, now: float | None = None) -> bool:
        if not bool(getattr(self, "_right_context_candidate", False)):
            return False
        moved = self._right_selection_context_moved_px(qx, qy)
        press_time = float(getattr(self, "_right_context_press_time", 0.0) or 0.0)
        elapsed = (time.monotonic() if now is None else float(now)) - press_time
        return moved <= float(self._RIGHT_CONTEXT_MAX_MOVE_PX) and elapsed <= float(self._RIGHT_CONTEXT_MAX_SECONDS)

    def _right_selection_context_start_pan_from_press(self, qx: float, qy: float) -> None:
        pos = getattr(self, "_right_context_press_pos", None)
        if pos:
            self._right_pan_last = (float(pos[0]), float(pos[1]))
        else:
            self._right_pan_last = (float(qx), float(qy))
        self._right_pan_active = True
        self._right_context_candidate = False

    def _clear_right_selection_context_state(self) -> None:
        self._right_context_press_pos = None
        self._right_context_press_time = 0.0
        self._right_context_candidate = False

    def _show_selection_context_menu(self, qx: float, qy: float) -> bool:
        indices = self._selection_context_indices()
        try:
            from PySide6.QtCore import QPoint
            from PySide6.QtWidgets import QMenu

            menu = QMenu(getattr(self, "plotter", None) or self)
            try:
                menu.setObjectName("selection_context_menu")
            except Exception:
                pass

            action_board = menu.addAction("Primitive board")
            action_board.setToolTip("Create a board using Preferences > Laser engraving at the clicked scene position.")

            def _run_board() -> None:
                self.create_primitive_board_from_context(qx, qy)

            action_board.triggered.connect(_run_board)

            if indices:
                menu.addSeparator()
                action_open = menu.addAction("Open in new scene")
                action_open.setToolTip("Copy the selected mesh(es), center them at the world origin, and open them in a new scene.")

                def _run_open() -> None:
                    self.open_selection_in_new_scene_from_context()

                action_open.triggered.connect(_run_open)
            try:
                menu.aboutToHide.connect(lambda: setattr(self, "_selection_context_menu", None))
            except Exception:
                pass
            self._selection_context_menu = menu
            plotter = getattr(self, "plotter", None)
            if plotter is not None and callable(getattr(plotter, "mapToGlobal", None)):
                global_pos = plotter.mapToGlobal(QPoint(int(round(qx)), int(round(qy))))
            else:
                global_pos = QPoint(int(round(qx)), int(round(qy)))
            menu.popup(global_pos)
            try:
                self.ui_log(f"[SELECTION_CONTEXT] menu opened selection_count={len(indices)} at=({qx:.1f},{qy:.1f})")
            except Exception:
                pass
            return True
        except Exception:
            log_exception("show_selection_context_menu")
            return False


    @staticmethod
    def _primitive_vec_add(a: tuple[float, float, float], b: tuple[float, float, float], scale: float = 1.0) -> tuple[float, float, float]:
        return (float(a[0]) + float(b[0]) * float(scale), float(a[1]) + float(b[1]) * float(scale), float(a[2]) + float(b[2]) * float(scale))

    @staticmethod
    def _primitive_vec_normalized(value: Any, fallback: tuple[float, float, float] = (0.0, 0.0, 1.0)) -> tuple[float, float, float]:
        try:
            v = (float(value[0]), float(value[1]), float(value[2]))
            length = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
            if not math.isfinite(length) or length <= 1.0e-12:
                return fallback
            return (v[0] / length, v[1] / length, v[2] / length)
        except Exception:
            return fallback

    def _context_qt_to_vtk_candidates(self, qx: float, qy: float) -> list[tuple[int, int, str]]:
        for name in ("_qt_to_vtk_candidates", "_qt_to_vtk_primary_candidates"):
            converter = getattr(self, name, None)
            if callable(converter):
                try:
                    candidates = list(converter(qx, qy))
                    if candidates:
                        return [(int(x), int(y), str(label)) for x, y, label in candidates]
                except Exception:
                    pass
        try:
            height = int(getattr(getattr(self, "plotter", None), "height", lambda: 0)())
            return [(int(round(qx)), max(0, height - int(round(qy)) - 1), "fallback")]
        except Exception:
            return [(int(round(qx)), int(round(qy)), "fallback")]

    def _pick_context_surface_from_qt(self, qx: float, qy: float):
        try:
            import vtk

            actors = getattr(self, "actors_by_index", {}) or {}
            if not actors:
                return None
            picker = vtk.vtkCellPicker()
            picker.SetTolerance(0.0008)
            picker.PickFromListOn()
            for actor in actors.values():
                try:
                    picker.AddPickList(actor)
                except Exception:
                    pass
            renderer = getattr(getattr(self, "plotter", None), "renderer", None)
            if renderer is None:
                return None
            for vx, vy, _label in self._context_qt_to_vtk_candidates(qx, qy):
                try:
                    picker.Pick(int(vx), int(vy), 0, renderer)
                    picked_actor = picker.GetActor() or picker.GetViewProp()
                    resolved = self._resolve_picked_actor(picked_actor) if callable(getattr(self, "_resolve_picked_actor", None)) else None
                    if not resolved or resolved[0] != "mesh":
                        continue
                    idx = int(resolved[1])
                    cell_id = int(picker.GetCellId())
                    if cell_id < 0:
                        continue
                    meshes = self.current_meshes() if callable(getattr(self, "current_meshes", None)) else []
                    if not (0 <= idx < len(meshes)):
                        continue
                    normal = None
                    normal_getter = getattr(self, "_mesh_triangle_normal", None)
                    if callable(normal_getter):
                        normal = normal_getter(meshes[idx], cell_id)
                    if normal is None:
                        try:
                            normal = tuple(float(v) for v in picker.GetPickNormal())
                        except Exception:
                            normal = (0.0, 0.0, 1.0)
                    point = picker.GetPickPosition()
                    point_tuple = (float(point[0]), float(point[1]), float(point[2]))
                    normal_tuple = self._primitive_vec_normalized(normal)
                    # Mesh triangle winding is not always reliable in imported files.
                    # For placement we bias the normal away from the mesh center so the
                    # board is created against the visible outside face, not embedded.
                    try:
                        verts = getattr(meshes[idx], "vertices", []) or []
                        if verts:
                            cx = sum(float(v[0]) for v in verts) / float(len(verts))
                            cy = sum(float(v[1]) for v in verts) / float(len(verts))
                            cz = sum(float(v[2]) for v in verts) / float(len(verts))
                            away = (point_tuple[0] - cx, point_tuple[1] - cy, point_tuple[2] - cz)
                            if away[0] * normal_tuple[0] + away[1] * normal_tuple[1] + away[2] * normal_tuple[2] < 0.0:
                                normal_tuple = (-normal_tuple[0], -normal_tuple[1], -normal_tuple[2])
                    except Exception:
                        pass
                    return (
                        idx,
                        point_tuple,
                        normal_tuple,
                        cell_id,
                    )
                except Exception:
                    continue
            return None
        except Exception:
            log_exception("pick_context_surface_from_qt")
            return None

    def _context_ground_point_from_qt(self, qx: float, qy: float) -> tuple[float, float, float]:
        try:
            from laserprog_studio.tooling._texture_projection_geometry import display_to_world_on_plane

            point = display_to_world_on_plane(self, float(qx), float(qy), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
            if point is not None:
                return (float(point[0]), float(point[1]), 0.0)
        except Exception:
            pass
        return (0.0, 0.0, 0.0)

    def _primitive_board_preferences(self):
        prefs = getattr(self, "project_preferences", None)
        if prefs is not None:
            return prefs
        try:
            from ..services.project_preferences import load_project_preferences

            prefs = load_project_preferences()
            self.project_preferences = prefs
            return prefs
        except Exception:
            from ..services.project_preferences import ProjectPreferences

            return ProjectPreferences()

    def create_primitive_board_from_context(self, qx: float, qy: float) -> bool:
        try:
            from ..geometry_ops.primitive_board import board_spec_from_preferences, make_board_primitive_mesh

            prefs = self._primitive_board_preferences()
            laser = getattr(prefs, "laser", prefs)
            thickness = max(float(getattr(laser, "default_board_thickness_mm", 3.0)), 0.001)
            hit = self._pick_context_surface_from_qt(qx, qy)
            if hit is not None:
                _idx, point, normal, _cell_id = hit
                center = self._primitive_vec_add(point, normal, thickness * 0.5)
                placement_label = "face"
            else:
                point = self._context_ground_point_from_qt(qx, qy)
                normal = (0.0, 0.0, 1.0)
                center = (float(point[0]), float(point[1]), thickness * 0.5)
                placement_label = "ground"
            spec = board_spec_from_preferences(prefs, center=center, normal=normal, name="Primitive board")
            board = make_board_primitive_mesh(spec)
            meshes = list(self.current_meshes()) if callable(getattr(self, "current_meshes", None)) else []
            meshes.append(board)
            new_index = len(meshes) - 1
            self.push_meshes(meshes, "Added primitive board", semantic_operation_type="create_primitive_board")
            try:
                self.set_selection_indices([new_index], reason="primitive_board")
            except Exception:
                try:
                    self.selected_indices = [new_index]
                    self.active_index = new_index
                    self.refresh_actor_styles()
                    self.update_gizmo()
                except Exception:
                    pass
            try:
                self.statusBar().showMessage(f"Primitive board created ({placement_label})", 2200)
            except Exception:
                pass
            try:
                self.ui_log(
                    f"[PRIMITIVE_BOARD] created placement={placement_label} center=({center[0]:.3f},{center[1]:.3f},{center[2]:.3f}) "
                    f"normal=({normal[0]:.3f},{normal[1]:.3f},{normal[2]:.3f}) size=({spec.width_mm:.3f},{spec.height_mm:.3f},{spec.thickness_mm:.3f})"
                )
            except Exception:
                pass
            return True
        except Exception:
            log_exception("create_primitive_board_from_context")
            try:
                self.statusBar().showMessage("Could not create primitive board", 2200)
            except Exception:
                pass
            return False

    def open_selection_in_new_scene_from_context(self) -> bool:
        try:
            result = self._selection_context_actions().open_selection_in_new_scene()
            if result is None:
                try:
                    self.statusBar().showMessage("No selected mesh to open in a new scene", 1600)
                except Exception:
                    pass
                return False
            try:
                self.statusBar().showMessage(f"Opened selection in new scene: {result.scene_name}", 2200)
            except Exception:
                pass
            return True
        except Exception:
            log_exception("open_selection_in_new_scene_from_context")
            return False


__all__ = ["SelectionContextMenuLayer"]

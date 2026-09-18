# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class SelectionBoxLayer:
    """Rubber-band selection around the existing VTK navigation layer.

    Free 3D view keeps left-drag for orbiting, so rectangle selection starts
    with Shift+Left drag. In fixed orthographic views, left-drag is already a
    selection/transform gesture, so it can start the rectangle directly.
    """

    def _selection_box_candidate_allowed(self, event: Any | None = None) -> bool:
        try:
            active = getattr(self, "active_tool", self.TOOL_NONE)
            if active not in {self.TOOL_NONE, self.TOOL_MOD_SPLIT}:
                allows_multi = False
                try:
                    allows_multi = bool(self._active_tool_allows_scene_multi_selection())
                except Exception:
                    allows_multi = False
                if not allows_multi:
                    return False
            if self._drag_axis is not None or getattr(self, "_split_drag_active", False):
                return False
            mods = event.modifiers() if event is not None else QApplication.keyboardModifiers()
            return bool((mods & Qt.ShiftModifier) or self._is_fixed_camera_mode())
        except Exception:
            return False

    def _begin_selection_box_candidate(self, qx: float, qy: float, *, additive: bool) -> None:
        try:
            self._selection_box_candidate = True
            self._selection_box_active = False
            self._selection_box_start = (float(qx), float(qy))
            self._selection_box_last = (float(qx), float(qy))
            self._selection_box_additive = bool(additive)
            self._qt_click_pos = (float(qx), float(qy))
            try:
                import time
                self._qt_click_time = time.monotonic()
            except Exception:
                self._qt_click_time = 0.0
        except Exception:
            log_exception("selection_box_candidate")

    def _ensure_selection_box_band(self):
        try:
            band = getattr(self, "_selection_box_band", None)
            if band is None:
                from ..ui.selection_box_overlay import SelectionBoxOverlay
                band = SelectionBoxOverlay(self.plotter)
                self._selection_box_band = band
            return band
        except Exception:
            log_exception("ensure_selection_box_band")
            return None

    def _selection_box_rect(self, qx: float, qy: float):
        try:
            from PySide6.QtCore import QPoint, QRect
            x0, y0 = getattr(self, "_selection_box_start", (qx, qy)) or (qx, qy)
            return QRect(QPoint(int(round(x0)), int(round(y0))), QPoint(int(round(qx)), int(round(qy)))).normalized()
        except Exception:
            return None

    def _update_selection_box_drag(self, qx: float, qy: float) -> bool:
        try:
            if not bool(getattr(self, "_selection_box_candidate", False)):
                return False
            start = getattr(self, "_selection_box_start", None)
            if start is None:
                return False
            self._selection_box_last = (float(qx), float(qy))
            moved = max(abs(float(qx) - start[0]), abs(float(qy) - start[1]))
            if moved < 8.0 and not bool(getattr(self, "_selection_box_active", False)):
                return True
            self._selection_box_active = True
            rect = self._selection_box_rect(qx, qy)
            band = self._ensure_selection_box_band()
            if band is not None and rect is not None:
                try:
                    band.set_selection_rect(rect)
                except Exception:
                    band.setGeometry(rect)
                try:
                    band.raise_()
                except Exception:
                    pass
                if not band.isVisible():
                    band.show()
            return True
        except Exception:
            log_exception("update_selection_box_drag")
            return False

    def _hide_selection_box_band(self) -> None:
        try:
            band = getattr(self, "_selection_box_band", None)
            if band is not None:
                try:
                    band.clear_selection_rect()
                except Exception:
                    pass
                band.hide()
        except Exception:
            pass

    def _clear_selection_box_state(self) -> None:
        self._selection_box_candidate = False
        self._selection_box_active = False
        self._selection_box_start = None
        self._selection_box_last = None
        self._selection_box_additive = False
        self._hide_selection_box_band()

    def _plotter_qt_size(self) -> tuple[float, float]:
        try:
            return float(self.plotter.width()), float(self.plotter.height())
        except Exception:
            return 1.0, 1.0

    def _render_window_pixel_size(self) -> tuple[float, float]:
        try:
            rw = self.plotter.ren_win
            w, h = rw.GetSize()
            if float(w) > 0 and float(h) > 0:
                return float(w), float(h)
        except Exception:
            pass
        return self._plotter_qt_size()

    def _display_to_qt_xy(self, display_x: float, display_y: float) -> tuple[int, int]:
        """Convert VTK display pixels to Qt widget coordinates.

        VTK display coordinates are measured from the bottom-left of the render
        window and may use physical pixels on high-DPI screens. Qt mouse events
        and the selection overlay use logical widget coordinates from the
        top-left. Mixing the two spaces was the main reason rectangle selection
        could draw correctly but never intersect any projected actor.
        """
        qt_w, qt_h = self._plotter_qt_size()
        rw_w, rw_h = self._render_window_pixel_size()
        sx = qt_w / max(rw_w, 1.0)
        sy = qt_h / max(rw_h, 1.0)
        qx = float(display_x) * sx
        qy = qt_h - (float(display_y) * sy)
        return int(round(qx)), int(round(qy))

    def _actor_bounds_to_qt_rect(self, bounds):
        try:
            from PySide6.QtCore import QPoint, QRect
            if bounds is None or len(bounds) < 6:
                return None
            xmin, xmax, ymin, ymax, zmin, zmax = [float(v) for v in bounds[:6]]
            corners = [
                (x, y, z)
                for x in (xmin, xmax)
                for y in (ymin, ymax)
                for z in (zmin, zmax)
            ]
            pts: list[tuple[int, int]] = []
            for corner in corners:
                try:
                    dx, dy, _dz = self._world_to_display(corner)
                    pts.append(self._display_to_qt_xy(dx, dy))
                except Exception:
                    pass
            if not pts:
                return None
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            return QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys))).normalized()
        except Exception:
            log_exception("actor_bounds_to_qt_rect")
            return None

    def _indices_intersecting_selection_box(self, rect) -> list[int]:
        if rect is None:
            return []
        try:
            meshes = self.current_meshes()
            hits: list[int] = []
            for idx in sorted(int(i) for i in self.actors_by_index.keys()):
                bounds = None
                actor = self.actors_by_index.get(idx)
                if actor is not None:
                    try:
                        bounds = actor.GetBounds()
                    except Exception:
                        bounds = None
                if bounds is None and 0 <= idx < len(meshes):
                    try:
                        bounds = mesh_bounds(meshes[idx])
                    except Exception:
                        bounds = None
                actor_rect = self._actor_bounds_to_qt_rect(bounds)
                if actor_rect is not None and rect.intersects(actor_rect):
                    hits.append(idx)
            return hits
        except Exception:
            log_exception("indices_intersecting_selection_box")
            return []

    def _finish_selection_box(self, qx: float, qy: float) -> bool:
        try:
            if not bool(getattr(self, "_selection_box_candidate", False)):
                return False
            active = bool(getattr(self, "_selection_box_active", False))
            rect = self._selection_box_rect(qx, qy)
            additive = bool(getattr(self, "_selection_box_additive", False))
            start = getattr(self, "_selection_box_start", None)
            self._hide_selection_box_band()
            if not active or rect is None or start is None:
                self._clear_selection_box_state()
                return False
            self._qt_click_pos = None
            hits = self._indices_intersecting_selection_box(rect)
            try:
                self.ui_log(f"[SELECTION_BOX] finish rect={rect.getRect()} hits={hits} actors={len(getattr(self, 'actors_by_index', {}))}")
            except Exception:
                pass
            if additive:
                merged = list(getattr(self, "selected_indices", []) or [])
                for idx in hits:
                    if idx not in merged:
                        merged.append(idx)
                self.set_selection_indices(merged, reason="box additive")
            else:
                self.set_selection_indices(hits, reason="box")
            try:
                self.ui_log(f"[SELECTION_BOX] hits={hits} additive={additive} rect={rect.getRect()}")
            except Exception:
                pass
            self._clear_selection_box_state()
            return True
        except Exception:
            log_exception("finish_selection_box")
            self._clear_selection_box_state()
            return True

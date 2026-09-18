# -*- coding: utf-8 -*-
from __future__ import annotations

"""Selection-box visual overlay.

The selection rectangle is intentionally implemented with a VTK 2D overlay
actor when a VTK/PyVista renderer is available.  Qt transparent child widgets must *not* cover the full OpenGL/VTK viewport;
transparent child widgets above OpenGL/VTK viewports are fragile on several platforms: a full-size widget
can black out the viewport, while a moving transparent child widget can leave
stale painted pixels behind if the OpenGL surface is not repainted immediately.

The VTK path uses two persistent 2D actors (one fill, one outline) and updates
only their display-coordinate points during drag.  No actor is added/removed on
mouse move, so there is no Qt backing-store accumulation and no actor churn.

A small Qt fallback is kept for test environments or non-VTK parents.  The
fallback hides and immediately repaints the old geometry before moving to the
new one; it is not the preferred production path for QVTK/QOpenGL widgets.
"""

from typing import Any
from time import monotonic

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class SelectionBoxOverlay(QWidget):
    """Reusable rubber-band rectangle for box selection.

    Production path:
        VTK display-coordinate Actor2D objects, updated in place.

    Fallback path:
        A tiny transparent QWidget matching only the rectangle bounds.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self._selection_rect = QRect()
        self._visible = False
        self._mode = "qt"
        self._plotter = parent
        self._renderer = self._resolve_renderer(parent)
        self._vtk = None
        self._vtk_fill_actor = None
        self._vtk_outline_actor = None
        self._vtk_fill_points = None
        self._vtk_outline_points = None
        self._vtk_ready = False
        self._last_vtk_integrity_check_time = 0.0
        self._vtk_integrity_check_interval_s = 0.50
        self._last_vtk_render_time = 0.0
        self._vtk_render_interval_s = 1.0 / 60.0
        if self._renderer is not None and self._try_import_vtk() is not None:
            self._mode = "vtk"
            # Keep the QWidget itself hidden: the rendered rectangle belongs to
            # the VTK renderer, avoiding transparent Qt/OpenGL composition bugs.
            super().hide()
        else:
            super().hide()

    # ------------------------------------------------------------------
    # Public API used by both the classic controller and the Creator API Lab
    # ------------------------------------------------------------------
    def set_selection_rect(self, rect: QRect | None) -> None:
        """Set the rubber-band rect in parent/widget coordinates."""
        if self._mode == "vtk":
            self._set_vtk_selection_rect(rect)
            return
        self._set_qt_selection_rect(rect)

    def clear_selection_rect(self) -> None:
        self.set_selection_rect(None)

    def show(self) -> None:  # noqa: D401
        """Show the current rectangle without showing a Qt child in VTK mode."""
        if self._mode == "vtk":
            if not self._selection_rect.isNull() and self._selection_rect.isValid():
                self._set_vtk_visibility(True)
                self._request_vtk_render(force=True)
            return
        self._visible = True
        super().show()

    def hide(self) -> None:  # noqa: D401
        """Hide the rectangle."""
        if self._mode == "vtk":
            if not self._visible and self._selection_rect.isNull():
                return
            self._set_vtk_visibility(False)
            self._visible = False
            self._request_vtk_render(force=True)
            return
        self._visible = False
        super().hide()

    def isVisible(self) -> bool:  # noqa: N802
        if self._mode == "vtk":
            return bool(self._visible)
        return bool(super().isVisible())

    def raise_(self) -> None:  # noqa: D401
        """No-op in VTK mode; QWidget raise in fallback mode."""
        if self._mode != "vtk":
            try:
                super().raise_()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # VTK persistent actor implementation
    # ------------------------------------------------------------------
    @staticmethod
    def _resolve_renderer(parent: Any) -> Any | None:
        renderer = getattr(parent, "renderer", None)
        if renderer is not None:
            return renderer
        try:
            ren_win = parent.GetRenderWindow()
            renderers = ren_win.GetRenderers()
            return renderers.GetFirstRenderer()
        except Exception:
            return None

    def _try_import_vtk(self):
        if self._vtk is not None:
            return self._vtk
        try:
            import vtk  # type: ignore

            self._vtk = vtk
            return vtk
        except Exception:
            return None

    def _renderer_is_attached(self, renderer: Any) -> bool:
        if renderer is None:
            return False
        try:
            ren_win = self._plotter.GetRenderWindow()
            has_renderer = getattr(ren_win, "HasRenderer", None)
            if callable(has_renderer):
                return bool(has_renderer(renderer))
        except Exception:
            pass
        return True

    @staticmethod
    def _renderer_has_prop(renderer: Any, actor: Any) -> bool | None:
        if renderer is None or actor is None:
            return None
        try:
            props = renderer.GetViewProps()
            is_present = getattr(props, "IsItemPresent", None)
            if callable(is_present):
                return bool(is_present(actor))
        except Exception:
            return None
        return None

    def _ensure_vtk_actors(self, *, force_integrity: bool = False) -> bool:
        # Keep the rectangle entirely local to this widget.  Do not import the
        # application renderer bridge here and do not switch renderers merely
        # because a wrapper object changed identity: both behaviours can disturb
        # the shared foreground renderer used by every projected-drawing tool.
        if self._vtk_ready:
            now = monotonic()
            # Actor membership checks walk the renderer prop collection and are
            # unnecessary on every mouse pixel.  Check periodically; geometry
            # updates remain direct vtkPoints mutations in between.
            if (
                not force_integrity
                and (now - float(self._last_vtk_integrity_check_time)) < float(self._vtk_integrity_check_interval_s)
            ):
                return True
            self._last_vtk_integrity_check_time = now
            if not self._renderer_is_attached(self._renderer):
                self._renderer = self._resolve_renderer(self._plotter)
                self._vtk_ready = False
                self._vtk_fill_actor = None
                self._vtk_outline_actor = None
                self._vtk_fill_points = None
                self._vtk_outline_points = None
            else:
                missing = False
                for actor in (self._vtk_fill_actor, self._vtk_outline_actor):
                    present = self._renderer_has_prop(self._renderer, actor)
                    if present is False:
                        missing = True
                        break
                if not missing:
                    return True
                # A scene rebuild removed only the rubber-band props. Re-add
                # those two props to the same renderer; never clear or replace
                # any other overlay actors.
                try:
                    add2d = getattr(self._renderer, "AddActor2D", None)
                    for actor in (self._vtk_fill_actor, self._vtk_outline_actor):
                        if actor is None:
                            continue
                        if callable(add2d):
                            add2d(actor)
                        else:
                            self._renderer.AddActor(actor)
                    return True
                except Exception:
                    self._vtk_ready = False
        vtk = self._try_import_vtk()
        renderer = self._renderer
        if vtk is None or renderer is None:
            return False
        try:
            coord_fill = vtk.vtkCoordinate()
            coord_fill.SetCoordinateSystemToDisplay()
            coord_outline = vtk.vtkCoordinate()
            coord_outline.SetCoordinateSystemToDisplay()

            fill_points = vtk.vtkPoints()
            fill_points.SetNumberOfPoints(4)
            fill_poly = vtk.vtkCellArray()
            fill_poly.InsertNextCell(4)
            for i in range(4):
                fill_poly.InsertCellPoint(i)
            fill_data = vtk.vtkPolyData()
            fill_data.SetPoints(fill_points)
            fill_data.SetPolys(fill_poly)
            fill_mapper = vtk.vtkPolyDataMapper2D()
            fill_mapper.SetInputData(fill_data)
            fill_mapper.SetTransformCoordinate(coord_fill)
            fill_actor = vtk.vtkActor2D()
            fill_actor.SetMapper(fill_mapper)
            fill_actor.GetProperty().SetColor(90.0 / 255.0, 170.0 / 255.0, 255.0 / 255.0)
            fill_actor.GetProperty().SetOpacity(0.18)
            fill_actor.SetVisibility(False)

            outline_points = vtk.vtkPoints()
            outline_points.SetNumberOfPoints(5)
            outline_lines = vtk.vtkCellArray()
            outline_lines.InsertNextCell(5)
            for i in range(5):
                outline_lines.InsertCellPoint(i)
            outline_data = vtk.vtkPolyData()
            outline_data.SetPoints(outline_points)
            outline_data.SetLines(outline_lines)
            outline_mapper = vtk.vtkPolyDataMapper2D()
            outline_mapper.SetInputData(outline_data)
            outline_mapper.SetTransformCoordinate(coord_outline)
            outline_actor = vtk.vtkActor2D()
            outline_actor.SetMapper(outline_mapper)
            outline_actor.GetProperty().SetColor(80.0 / 255.0, 170.0 / 255.0, 255.0 / 255.0)
            outline_actor.GetProperty().SetOpacity(0.92)
            outline_actor.GetProperty().SetLineWidth(1.0)
            outline_actor.SetVisibility(False)

            add2d = getattr(renderer, "AddActor2D", None)
            if callable(add2d):
                add2d(fill_actor)
                add2d(outline_actor)
            else:
                renderer.AddActor(fill_actor)
                renderer.AddActor(outline_actor)

            self._vtk_fill_actor = fill_actor
            self._vtk_outline_actor = outline_actor
            self._vtk_fill_points = fill_points
            self._vtk_outline_points = outline_points
            self._vtk_ready = True
            self._last_vtk_integrity_check_time = monotonic()
            return True
        except Exception:
            return False

    def _set_vtk_selection_rect(self, rect: QRect | None) -> None:
        if rect is None or not rect.isValid() or rect.normalized().width() <= 0 or rect.normalized().height() <= 0:
            if self._selection_rect.isNull() and not self._visible:
                return
            self._selection_rect = QRect()
            self._set_vtk_visibility(False)
            self._visible = False
            self._request_vtk_render(force=True)
            return
        # The first frame of every gesture performs an integrity check so a
        # renderer rebuild between gestures cannot leave the blue rectangle
        # invisible for the first half-second. Subsequent mouse pixels use the
        # periodic lightweight path and never scan the renderer prop list.
        first_frame = not self._visible or self._selection_rect.isNull()
        if not self._ensure_vtk_actors(force_integrity=first_frame):
            self._mode = "qt"
            self._set_qt_selection_rect(rect)
            return

        target = QRect(rect).normalized()
        if target == self._selection_rect and self._visible:
            return
        self._selection_rect = target
        x0, y0, x1, y1 = self._qt_rect_to_vtk_display_rect(target)

        fill_points = self._vtk_fill_points
        outline_points = self._vtk_outline_points
        if fill_points is not None:
            fill_points.SetPoint(0, x0, y0, 0.0)
            fill_points.SetPoint(1, x1, y0, 0.0)
            fill_points.SetPoint(2, x1, y1, 0.0)
            fill_points.SetPoint(3, x0, y1, 0.0)
            fill_points.Modified()
        if outline_points is not None:
            outline_points.SetPoint(0, x0, y0, 0.0)
            outline_points.SetPoint(1, x1, y0, 0.0)
            outline_points.SetPoint(2, x1, y1, 0.0)
            outline_points.SetPoint(3, x0, y1, 0.0)
            outline_points.SetPoint(4, x0, y0, 0.0)
            outline_points.Modified()

        self._set_vtk_visibility(True)
        self._visible = True
        self._request_vtk_render(force=False)


    def _qt_rect_to_vtk_display_rect(self, rect: QRect) -> tuple[float, float, float, float]:
        """Convert a Qt top-left-origin rect to VTK display coordinates.

        Qt mouse/overlay coordinates use a top-left origin.  VTK display
        coordinates use a bottom-left origin and may be scaled by the render
        window pixel size on high-DPI displays.
        """
        target = QRect(rect).normalized()
        parent = self.parentWidget()
        qt_w = float(parent.width()) if parent is not None else max(1.0, float(target.right() + 1))
        qt_h = float(parent.height()) if parent is not None else max(1.0, float(target.bottom() + 1))
        rw_w = qt_w
        rw_h = qt_h
        try:
            ren_win = self._plotter.GetRenderWindow()
            size = ren_win.GetSize()
            if size and float(size[0]) > 0 and float(size[1]) > 0:
                rw_w = float(size[0])
                rw_h = float(size[1])
        except Exception:
            pass
        sx = rw_w / max(1.0, qt_w)
        sy = rw_h / max(1.0, qt_h)
        left = float(target.left()) * sx
        right = float(target.right()) * sx
        top = (qt_h - float(target.top())) * sy
        bottom = (qt_h - float(target.bottom())) * sy
        return (min(left, right), min(top, bottom), max(left, right), max(top, bottom))

    def _set_vtk_visibility(self, visible: bool) -> None:
        for actor in (self._vtk_fill_actor, self._vtk_outline_actor):
            if actor is not None:
                try:
                    actor.SetVisibility(bool(visible))
                except Exception:
                    pass

    def _request_vtk_render(self, *, force: bool = False) -> None:
        now = monotonic()
        if not force and (now - float(self._last_vtk_render_time)) < float(self._vtk_render_interval_s):
            return
        self._last_vtk_render_time = now
        plotter = self._plotter
        try:
            render = getattr(plotter, "render", None)
            if callable(render):
                render()
                return
        except Exception:
            pass
        try:
            parent = self.parentWidget()
            if parent is not None:
                parent.update()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # QWidget fallback implementation
    # ------------------------------------------------------------------
    def _set_qt_selection_rect(self, rect: QRect | None) -> None:
        parent = self.parentWidget()
        old_geometry = QRect(self.geometry()).adjusted(-4, -4, 4, 4)

        def repaint_old() -> None:
            if parent is None or not old_geometry.isValid():
                return
            try:
                parent.update(old_geometry)
                parent.repaint(old_geometry)
            except Exception:
                try:
                    parent.update(old_geometry)
                except Exception:
                    pass

        if rect is None or not rect.isValid() or rect.normalized().width() <= 0 or rect.normalized().height() <= 0:
            self._selection_rect = QRect()
            if super().isVisible():
                super().hide()
            self._visible = False
            repaint_old()
            return

        target = QRect(rect).normalized()
        geometry = target.adjusted(-1, -1, 2, 2)
        if parent is not None:
            geometry = geometry.intersected(parent.rect().adjusted(-1, -1, 1, 1))

        # Hide and synchronously repaint the old OpenGL area before moving the
        # fallback widget.  update() alone can be queued behind mouse moves and
        # leaves trails on some QVTK/QOpenGL compositions.
        was_visible = super().isVisible()
        if was_visible:
            super().hide()
        repaint_old()

        if self.geometry() != geometry:
            super().setGeometry(geometry)

        local_width = max(1, geometry.width() - 1)
        local_height = max(1, geometry.height() - 1)
        self._selection_rect = QRect(1, 1, local_width - 1, local_height - 1).normalized()
        self._visible = True
        if not super().isVisible():
            super().show()
        self.update()

    def paintEvent(self, event):  # noqa: N802, ANN001
        if self._mode == "vtk":
            return
        rect = QRect(self._selection_rect).normalized()
        if not rect.isValid() or rect.width() <= 0 or rect.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        draw_rect = rect.adjusted(0, 0, -1, -1)
        painter.fillRect(draw_rect, QColor(90, 170, 255, 46))
        pen = QPen(QColor(80, 170, 255, 210))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(draw_rect)
        painter.end()

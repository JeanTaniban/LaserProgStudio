# -*- coding: utf-8 -*-
"""Qt widget classes used by the Tool Core overlay adapter.

This module intentionally contains the native QWidget subclasses so
``qt_adapter.py`` can stay focused on synchronizing overlay specs with Qt
widgets.  PySide is still imported lazily by the adapter; these builders only
receive the Qt classes after the optional dependency is available.
"""

from __future__ import annotations

from typing import Any


def build_tool_core_overlay_frame(QFrame: type, Qt: Any, adapter: Any) -> type:
    class ToolCoreOverlayFrame(QFrame):  # pragma: no cover - exercised in GUI
        def __init__(self, parent: Any, window_id: str) -> None:
            super().__init__(parent)
            self.window_id = window_id
            # The Qt adapter now owns native overlay dragging end-to-end.
            # Local-offset mode (`self._drag_offset_local`) is kept
            # out of the hot path: global deltas plus pointer-exit cancel
            # avoid stale offsets when soft-wall constraints block motion.
            self._dragging = False
            self._drag_start_global = None
            self._drag_start_pos = None
            self._drag_pointer_offset_px = None
            self._last_drag_record_t = 0.0
            self._drag_was_constrained = False
            self._drag_cancelled = False
            self._tool_core_overlay_drag_dirty_rect = None
            self._tool_core_overlay_redrawing = False
            self._tool_core_overlay_hovered = False
            try:
                self.setAttribute(Qt.WA_ShowWithoutActivating, True)
                self.setAttribute(Qt.WA_TranslucentBackground, True)
                self.setAttribute(Qt.WA_NoSystemBackground, False)
                self.setAttribute(Qt.WA_StyledBackground, True)
                self.setAutoFillBackground(False)
            except Exception:
                pass

        def enterEvent(self, event: Any) -> None:  # noqa: N802
            self._tool_core_overlay_hovered = True
            try:
                self.update()
                super().enterEvent(event)
            except Exception:
                pass

        def leaveEvent(self, event: Any) -> None:  # noqa: N802
            self._tool_core_overlay_hovered = False
            try:
                self.update()
                super().leaveEvent(event)
            except Exception:
                pass

        def paintEvent(self, event: Any) -> None:  # noqa: N802
            try:
                adapter._paint_overlay_frame(self, event)
            except Exception:
                pass

        def mousePressEvent(self, event: Any) -> None:  # noqa: N802
            spec = adapter.manager.window(self.window_id)
            if spec is None or not spec.movable:
                return super().mousePressEvent(event)
            try:
                if event.button() != Qt.LeftButton:
                    return super().mousePressEvent(event)
                global_pos = adapter._event_global_pos(event)
                if global_pos is None:
                    return super().mousePressEvent(event)
                if not adapter._press_hits_visible_frame(self, event, spec):
                    # Guard against stale/oversized Qt geometry: after a
                    # clamped drag, a click beside the painted overlay must
                    # never start a new drag just because the child widget
                    # still owns an invisible rectangle there.
                    adapter._record_drag_sample(self, "reject", global_pos, "press outside visible overlay frame")
                    try:
                        event.ignore()
                    except Exception:
                        pass
                    return super().mousePressEvent(event)
                # Deep fix: use one constraint only.  Local widget
                # coordinates change while the widget moves, so the native
                # adapter drives overlay drag from global mouse deltas.  The
                # old local-coordinate path made the overlay jump.
                self._drag_start_global = global_pos
                self._drag_start_pos = (int(self.x()), int(self.y()))
                self._drag_pointer_offset_px = adapter._pointer_offset_px(self, global_pos)
                self._last_drag_record_t = 0.0
                self._drag_cancelled = False
                self._dragging = True
                adapter._remember_drag_dirty(self, self.geometry())
                try:
                    self.setProperty("overlayDragging", True)
                except Exception:
                    pass
                adapter.manager.set_window_position(self.window_id, int(self.x()), int(self.y()))
                adapter._record_drag_sample(self, "press", global_pos, "global-delta drag start; native soft-wall drag", force=True)
                try:
                    self.setCursor(Qt.ClosedHandCursor)
                except Exception:
                    pass
                self.raise_()
                event.accept()
                return
            except Exception:
                pass
            return super().mousePressEvent(event)

        def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
            if not self._dragging:
                return super().mouseMoveEvent(event)
            try:
                global_pos = adapter._event_global_pos(event)
                if global_pos is None or self._drag_start_global is None or self._drag_start_pos is None:
                    return super().mouseMoveEvent(event)
                dx = int(global_pos.x()) - int(self._drag_start_global.x())
                dy = int(global_pos.y()) - int(self._drag_start_global.y())
                x = int(self._drag_start_pos[0]) + dx
                y = int(self._drag_start_pos[1]) + dy
                spec = adapter.manager.window(self.window_id)
                requested = (int(x), int(y))
                # Native fast path: moving the child widget is enough for
                # Qt to schedule exposed regions.  During drag the runtime
                # uses a cheap wall-like constraint instead of the placement
                # solver used during sync.  This avoids solver jumps and keeps
                # the mouse/overlay relation stable near viewport edges or
                # other overlays.
                x, y = adapter._constrain_live_drag_pos(self, spec, int(x), int(y))
                constrained = (int(x), int(y)) != requested
                moved = (int(x), int(y)) != (int(self.x()), int(self.y()))
                old_geometry = self.geometry() if moved else None
                if moved:
                    self.move(int(x), int(y))
                    adapter._remember_drag_dirty(self, old_geometry, self.geometry())
                try:
                    self._tool_core_overlay_pending_pos = (int(x), int(y))
                except Exception:
                    pass
                note = "global-delta drag move; qt-move fast-path; live-wall-constraint"
                if constrained:
                    if not adapter._pointer_inside_widget_global_rect(self, global_pos):
                        adapter._cancel_drag(
                            self,
                            global_pos,
                            "global-delta drag cancelled; pointer left constrained overlay rect",
                        )
                        try:
                            event.accept()
                        except Exception:
                            pass
                        return
                    # Do not warp the OS cursor.  OS cursor warping creates a
                    # visible stutter and can leave a platform mouse grab in
                    # a bad state when focus changes mid-drag.  Instead the
                    # runtime absorbs the blocked delta by rebasing the drag
                    # origin to the current pointer and constrained overlay
                    # position.  The overlay feels like it hits a hard wall,
                    # and the next opposite pointer movement takes effect
                    # immediately without a hidden payback distance.
                    self._drag_start_global = global_pos
                    self._drag_start_pos = (int(x), int(y))
                    try:
                        self._drag_was_constrained = True
                    except Exception:
                        pass
                    note = "global-delta drag move; qt-move fast-path; soft-wall-rebase; clamped-anchor-reset"
                adapter._record_drag_sample(self, "move", global_pos, note)
                event.accept()
                return
            except Exception:
                pass
            return super().mouseMoveEvent(event)

        def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
            if self._dragging:
                try:
                    global_pos = adapter._event_global_pos(event) or self._drag_start_global
                    adapter._finish_drag(self, commit=True)
                    if global_pos is not None:
                        adapter._record_drag_sample(self, "release", global_pos, "global-delta drag release", force=True)
                except Exception:
                    pass
                try:
                    event.accept()
                except Exception:
                    pass
                return
            if getattr(self, "_drag_cancelled", False):
                # Swallow the button release that may still be delivered by
                # Qt's implicit press-time mouse routing after the runtime
                # has already cancelled a constrained overlay drag.
                self._drag_cancelled = False
                try:
                    event.accept()
                except Exception:
                    pass
                return
            return super().mouseReleaseEvent(event)

        def focusOutEvent(self, event: Any) -> None:  # noqa: N802
            # Defensive recovery: a native drag should never keep mouse
            # input captured after the overlay/application loses focus.
            # The runtime does not call explicit mouse grabbing for normal overlay drag,
            # but releaseMouse() is still safe here and clears stale grabs
            # left by older sessions or platform edge cases.
            if self._dragging:
                try:
                    adapter._finish_drag(self, commit=True)
                except Exception:
                    pass
            return super().focusOutEvent(event)

        def hideEvent(self, event: Any) -> None:  # noqa: N802
            # If a tool closes the overlay while dragging, leave no stale drag
            # capture behind.  This avoids the next press starting from a bad
            # offset.  A release-time clean redraw intentionally hides/shows
            # the child once; that internal hide must not recursively finish
            # the drag again.
            if not bool(getattr(self, "_tool_core_overlay_redrawing", False)):
                adapter._finish_drag(self, commit=True)
            return super().hideEvent(event)
    return ToolCoreOverlayFrame


def build_tool_core_overlay_button(QPushButton: type) -> type:
    class ToolCoreOverlayButton(QPushButton):  # pragma: no cover - exercised in GUI
        """Vector-icon overlay button used by compact CAD toolbars.

        Tools only provide stable icon ids (for example ``sketch.line``).
        The Qt adapter owns the actual rendering, so tool authors do not
        have to ship images, tune padding, or reimplement selected/hover
        states for every overlay palette.
        """

        def paintEvent(self, event: Any) -> None:  # noqa: N802
            try:
                icon_key = str(self.property("toolCoreVectorIcon") or "")
                if not icon_key:
                    return super().paintEvent(event)
                self._paint_vector_tool_button(event, icon_key)
                return
            except Exception:
                return super().paintEvent(event)

        def _paint_vector_tool_button(self, event: Any, icon_key: str) -> None:
            from PySide6.QtCore import QPointF, QRectF, Qt
            from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF

            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.fillRect(event.rect(), Qt.transparent)

            rect = QRectF(self.rect()).adjusted(2.0, 2.0, -2.0, -2.0)
            checked = bool(self.isChecked())
            hovered = bool(self.underMouse())
            enabled = bool(self.isEnabled())
            label = str(self.property("toolCoreVectorLabel") or self.text() or "")
            paint_label = bool(self.text())
            accent = QColor(62, 195, 255, 255 if enabled else 120)
            accent_soft = QColor(62, 195, 255, 72 if enabled else 34)
            text_color = QColor(232, 240, 248, 255 if enabled else 120)
            if checked:
                bg = QColor(20, 42, 61, 188)
                border = QColor(62, 190, 255, 216)
                text_color = accent
            elif hovered:
                bg = QColor(27, 35, 45, 170)
                border = QColor(97, 116, 139, 210)
            else:
                bg = QColor(18, 23, 30, 42)
                border = QColor(72, 86, 104, 80)

            toolbar_v2 = bool(self.property("toolCoreVectorToolbarV2"))
            command_deck = bool(self.property("toolCoreVectorCommandDeck"))
            if command_deck:
                painter.setBrush(bg if (checked or hovered) else QColor(13, 19, 27, 126))
                painter.setPen(QPen(border if (checked or hovered) else QColor(72, 95, 118, 118), 1.0))
                painter.drawRoundedRect(rect, 8, 8)
                if checked:
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(accent_soft, 2.0))
                    painter.drawRoundedRect(rect.adjusted(-0.4, -0.4, 0.4, 0.4), 8, 8)
            elif toolbar_v2:
                # Compact command-rail cell: visible hit target, readable caption,
                # but no oversized ribbon tile.  The section card already groups
                # commands; each button only needs a subtle surface and a crisp
                # active/hover state.
                painter.setBrush(bg if (checked or hovered) else QColor(14, 20, 28, 72))
                painter.setPen(QPen(border if (checked or hovered) else QColor(69, 88, 108, 98), 1.0))
                painter.drawRoundedRect(rect, 8, 8)
                if checked:
                    glow_rect = rect.adjusted(-0.5, -0.5, 0.5, 0.5)
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(accent_soft, 1.8))
                    painter.drawRoundedRect(glow_rect, 8, 8)
            elif checked or hovered:
                painter.setBrush(bg)
                painter.setPen(QPen(border, 1.25))
                painter.drawRoundedRect(rect, 10, 10)
                if checked:
                    glow_rect = rect.adjusted(-0.5, -0.5, 0.5, 0.5)
                    painter.setBrush(Qt.NoBrush)
                    painter.setPen(QPen(accent_soft, 2.0))
                    painter.drawRoundedRect(glow_rect, 10, 10)

            if paint_label:
                if command_deck:
                    label_h = 17.0
                    icon_side = max(28.0, min(rect.width() - 14.0, rect.height() - label_h - 14.0, 34.0))
                    icon_top = rect.top() + 6.0
                    icon_rect = QRectF(rect.center().x() - icon_side * 0.5, icon_top, icon_side, icon_side)
                elif toolbar_v2:
                    label_h = 18.0
                    icon_side = max(22.0, min(rect.width() - 12.0, rect.height() - label_h - 12.0, 30.0))
                    icon_top = rect.top() + 6.0
                    icon_rect = QRectF(rect.center().x() - icon_side * 0.5, icon_top, icon_side, icon_side)
                else:
                    icon_side = min(rect.width() - 14.0, 25.0)
                    icon_top = rect.top() + 7.0
                    icon_rect = QRectF(rect.center().x() - icon_side * 0.5, icon_top, icon_side, icon_side)
            else:
                side = min(rect.width() - 13.0, rect.height() - 13.0, 29.0)
                icon_rect = QRectF(rect.center().x() - side * 0.5, rect.center().y() - side * 0.5 - 1.0, side, side)
            self._draw_tool_icon(painter, icon_key, icon_rect, text_color, accent)

            if paint_label:
                font = QFont(self.font())
                font.setPointSize(8 if command_deck else (8 if toolbar_v2 else 7))
                font.setWeight(QFont.Weight.Bold if checked else QFont.Weight.DemiBold)
                painter.setFont(font)
                painter.setPen(QPen(text_color, 1.0))
                if command_deck:
                    text_rect = QRectF(rect.left() + 4.0, rect.bottom() - 19.0, rect.width() - 8.0, 15.0)
                elif toolbar_v2:
                    text_rect = QRectF(rect.left() + 3.0, rect.bottom() - 20.0, rect.width() - 6.0, 16.0)
                else:
                    text_rect = QRectF(rect.left() + 4.0, rect.height() - 21.0, rect.width() - 8.0, 17.0)
                label_to_paint = label
                no_elide = bool(self.property("toolCoreVectorNoElide"))
                if no_elide:
                    # Display labels are intentionally chosen by the tool's layout
                    # contract.  Do not add visual "..." noise: if the toolbar
                    # builder has sized the slot from that caption, the renderer
                    # must paint the caption cleanly.
                    try:
                        fallback_sizes = (8, 7, 6) if command_deck else ((8, 7, 6) if toolbar_v2 else (7, 6))
                        for pt in fallback_sizes:
                            font.setPointSize(pt)
                            painter.setFont(font)
                            if painter.fontMetrics().horizontalAdvance(label) <= int(text_rect.width()):
                                break
                    except Exception:
                        pass
                else:
                    try:
                        label_to_paint = painter.fontMetrics().elidedText(label, Qt.ElideRight, int(text_rect.width()))
                    except Exception:
                        label_to_paint = label
                painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignVCenter, label_to_paint)
            if checked:
                underline = QRectF(rect.center().x() - 14.0, rect.bottom() - 3.5, 28.0, 2.5)
                painter.setBrush(accent)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(underline, 2.0, 2.0)
            painter.end()

        def _draw_tool_icon(self, painter: Any, icon_key: str, rect: Any, primary: Any, accent: Any) -> None:
            from PySide6.QtCore import QPointF, QRectF, Qt
            from PySide6.QtGui import QPainterPath, QPen, QPolygonF

            painter.save()
            painter.setClipRect(rect.adjusted(-2.0, -2.0, 2.0, 2.0))
            stroke_scale = max(1.0, min(1.85, min(float(rect.width()), float(rect.height())) / 28.0))
            white_pen = QPen(primary, 1.8 * stroke_scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            cyan_pen = QPen(accent, 1.8 * stroke_scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            cyan_thin = QPen(accent, 1.2 * stroke_scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            dash_pen = QPen(accent, 1.15 * stroke_scale, Qt.DashLine, Qt.RoundCap, Qt.RoundJoin)
            key = str(icon_key).replace("sketch.", "").replace("tool.", "")
            x, y, w, h = float(rect.x()), float(rect.y()), float(rect.width()), float(rect.height())
            cx, cy = x + w * 0.5, y + h * 0.52
            r = min(w, h) * 0.34

            def node(px: float, py: float, radius: float = 3.2) -> None:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(cyan_pen)
                painter.drawEllipse(QPointF(px, py), radius, radius)

            def square_handle(px: float, py: float, size: float = 4.5) -> None:
                rr = QRectF(px - size * 0.5, py - size * 0.5, size, size)
                painter.setPen(cyan_thin)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(rr)

            if key == "modify":
                sel = QRectF(x + w * 0.13, y + h * 0.12, w * 0.52, h * 0.58)
                painter.setPen(dash_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(sel)
                for px, py in ((sel.left(), sel.top()), (sel.right(), sel.top()), (sel.left(), sel.bottom()), (sel.right(), sel.bottom())):
                    square_handle(px, py, 5.0)
                inner = QRectF(sel.left() + w * 0.17, sel.top() + h * 0.17, w * 0.26, h * 0.22)
                painter.setPen(white_pen)
                painter.drawRect(inner)
                cursor = QPolygonF([
                    QPointF(x + w * 0.58, y + h * 0.47),
                    QPointF(x + w * 0.84, y + h * 0.70),
                    QPointF(x + w * 0.69, y + h * 0.73),
                    QPointF(x + w * 0.75, y + h * 0.90),
                    QPointF(x + w * 0.65, y + h * 0.94),
                    QPointF(x + w * 0.59, y + h * 0.77),
                    QPointF(x + w * 0.49, y + h * 0.88),
                ])
                painter.setPen(white_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPolygon(cursor)
            elif key == "point":
                painter.setPen(cyan_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r * 0.82, r * 0.82)
                painter.setBrush(accent)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(cx, cy), r * 0.28, r * 0.28)
            elif key == "line":
                a = QPointF(x + w * 0.25, y + h * 0.78)
                b = QPointF(x + w * 0.74, y + h * 0.22)
                painter.setPen(white_pen)
                painter.drawLine(a, b)
                node(a.x(), a.y(), 3.8)
                node(b.x(), b.y(), 3.8)
            elif key == "rectangle":
                rr = QRectF(x + w * 0.22, y + h * 0.22, w * 0.56, h * 0.50)
                painter.setPen(white_pen)
                painter.drawRect(rr)
                for px, py in ((rr.left(), rr.top()), (rr.right(), rr.top()), (rr.left(), rr.bottom()), (rr.right(), rr.bottom())):
                    node(px, py, 3.7)
            elif key == "circle":
                painter.setPen(white_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), r * 1.06, r * 1.06)
                painter.setPen(cyan_pen)
                painter.drawLine(QPointF(cx - r * 0.32, cy), QPointF(cx + r * 0.32, cy))
                painter.drawLine(QPointF(cx, cy - r * 0.32), QPointF(cx, cy + r * 0.32))
            elif key in {"half_circle", "half-circle"}:
                base_y = y + h * 0.70
                left = x + w * 0.20
                right = x + w * 0.80
                arc_rect = QRectF(left, y + h * 0.18, right - left, h * 1.04)
                painter.setPen(white_pen)
                painter.drawArc(arc_rect, 0, 180 * 16)
                painter.drawLine(QPointF(left, base_y), QPointF(right, base_y))
                node(left, base_y, 3.7)
                node(right, base_y, 3.7)
                painter.setPen(cyan_pen)
                painter.drawLine(QPointF(cx, base_y - 5.0), QPointF(cx, base_y + 5.0))
            elif key == "arc":
                arc_rect = QRectF(x + w * 0.17, y + h * 0.18, w * 0.68, h * 0.95)
                painter.setPen(white_pen)
                painter.drawArc(arc_rect, 40 * 16, 130 * 16)
                node(x + w * 0.25, y + h * 0.78, 3.7)
                node(x + w * 0.77, y + h * 0.25, 3.7)
            elif key in {"dimension", "measure"}:
                base_y = y + h * 0.67
                left = x + w * 0.18
                right = x + w * 0.82
                top_y = y + h * 0.30
                painter.setPen(cyan_thin)
                painter.drawLine(QPointF(left, top_y), QPointF(left, base_y + 5.0))
                painter.drawLine(QPointF(right, top_y), QPointF(right, base_y + 5.0))
                painter.setPen(white_pen)
                painter.drawLine(QPointF(left, base_y), QPointF(right, base_y))
                painter.setPen(cyan_pen)
                painter.drawLine(QPointF(left, base_y), QPointF(left + 8.0, base_y - 5.0))
                painter.drawLine(QPointF(left, base_y), QPointF(left + 8.0, base_y + 5.0))
                painter.drawLine(QPointF(right, base_y), QPointF(right - 8.0, base_y - 5.0))
                painter.drawLine(QPointF(right, base_y), QPointF(right - 8.0, base_y + 5.0))
                painter.setPen(cyan_thin)
                painter.drawText(QRectF(cx - w * 0.20, y + h * 0.22, w * 0.40, h * 0.24), Qt.AlignCenter, "12")
            elif key == "delete":
                bin_rect = QRectF(x + w * 0.32, y + h * 0.32, w * 0.36, h * 0.45)
                painter.setPen(white_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(bin_rect, 2.0, 2.0)
                painter.drawLine(QPointF(bin_rect.left() - 3.0, bin_rect.top()), QPointF(bin_rect.right() + 3.0, bin_rect.top()))
                painter.setPen(cyan_pen)
                painter.drawLine(QPointF(cx - 7.0, y + h * 0.22), QPointF(cx + 7.0, y + h * 0.22))
                painter.drawLine(QPointF(cx - 5.0, y + h * 0.22), QPointF(cx - 5.0, y + h * 0.30))
                painter.drawLine(QPointF(cx + 5.0, y + h * 0.22), QPointF(cx + 5.0, y + h * 0.30))
                for dx in (-7.0, 0.0, 7.0):
                    painter.drawLine(QPointF(cx + dx, bin_rect.top() + 8.0), QPointF(cx + dx, bin_rect.bottom() - 6.0))
            elif key in {"apply", "check"}:
                painter.setPen(cyan_pen)
                painter.drawLine(QPointF(x + w * 0.22, y + h * 0.55), QPointF(x + w * 0.42, y + h * 0.74))
                painter.drawLine(QPointF(x + w * 0.42, y + h * 0.74), QPointF(x + w * 0.80, y + h * 0.28))
                painter.setPen(cyan_thin)
                painter.drawEllipse(QPointF(cx, cy), r * 1.06, r * 1.06)
            elif key in {"preview", "eye"}:
                path = QPainterPath()
                path.moveTo(x + w * 0.12, cy)
                path.cubicTo(x + w * 0.30, y + h * 0.24, x + w * 0.70, y + h * 0.24, x + w * 0.88, cy)
                path.cubicTo(x + w * 0.70, y + h * 0.78, x + w * 0.30, y + h * 0.78, x + w * 0.12, cy)
                painter.setPen(white_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawPath(path)
                painter.setPen(cyan_pen)
                painter.drawEllipse(QPointF(cx, cy), r * 0.46, r * 0.46)
            elif key in {"restart", "reset", "rebuild", "face"}:
                arc_rect = QRectF(x + w * 0.20, y + h * 0.22, w * 0.60, h * 0.58)
                painter.setPen(cyan_pen)
                painter.drawArc(arc_rect, 35 * 16, 250 * 16)
                painter.drawArc(arc_rect, 215 * 16, 250 * 16)
                painter.drawLine(QPointF(x + w * 0.78, y + h * 0.38), QPointF(x + w * 0.88, y + h * 0.36))
                painter.drawLine(QPointF(x + w * 0.78, y + h * 0.38), QPointF(x + w * 0.78, y + h * 0.26))
                painter.drawLine(QPointF(x + w * 0.22, y + h * 0.64), QPointF(x + w * 0.12, y + h * 0.66))
                painter.drawLine(QPointF(x + w * 0.22, y + h * 0.64), QPointF(x + w * 0.22, y + h * 0.76))
            elif key in {"clear", "erase"}:
                painter.setPen(white_pen)
                painter.drawLine(QPointF(x + w * 0.22, y + h * 0.72), QPointF(x + w * 0.78, y + h * 0.72))
                painter.setPen(cyan_pen)
                painter.drawLine(QPointF(x + w * 0.28, y + h * 0.28), QPointF(x + w * 0.72, y + h * 0.72))
                painter.drawLine(QPointF(x + w * 0.72, y + h * 0.28), QPointF(x + w * 0.28, y + h * 0.72))
                node(x + w * 0.30, y + h * 0.72, 3.4)
                node(x + w * 0.70, y + h * 0.72, 3.4)
            else:
                painter.setPen(cyan_pen)
                painter.drawEllipse(QPointF(cx, cy), r, r)
            painter.restore()
    return ToolCoreOverlayButton

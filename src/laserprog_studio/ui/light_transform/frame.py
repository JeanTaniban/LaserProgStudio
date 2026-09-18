# -*- coding: utf-8 -*-
from __future__ import annotations

from ..._window_deps import *


class LightTransformOverlayFrame(QFrame):
    """Embedded surface for the compact transform controls.

    This overlay must stay a *child widget* of the viewport.  Older builds used
    ``Qt.Tool | Qt.FramelessWindowHint`` to work around OpenGL composition
    issues, but that makes the overlay a real platform window on Windows.  When
    tools open/close and the overlay is shown/hidden, Windows can briefly expose
    those helper windows as tiny minimised/floating windows.

    Keeping the overlay as ``Qt.Widget`` avoids creating any extra native
    top-level window.  The widget is opaque-enough and self-painted to reduce
    the stale-alpha issue that originally motivated the floating implementation.
    """

    def __init__(self, parent: QWidget, viewport: QWidget | None = None) -> None:
        super().__init__(parent)
        self._light_overlay_viewport = viewport or parent
        self._light_overlay_hovered = False
        try:
            self.setWindowFlags(Qt.Widget)
        except Exception:
            pass
        try:
            self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        except Exception:
            pass
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, False)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAutoFillBackground(False)

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._light_overlay_hovered = True
        self.update()
        try:
            super().enterEvent(event)
        except Exception:
            pass

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._light_overlay_hovered = False
        self.update()
        try:
            super().leaveEvent(event)
        except Exception:
            pass

    def _paint_light_overlay_event(self, event) -> None:
        # Clear the alpha channel explicitly, then draw the translucent rounded
        # panel ourselves.  Relying only on stylesheet painting made the floating
        # tool window visually too transparent on some compositors even though it
        # fixed the old VTK/OpenGL alpha stacking bug.
        try:
            from PySide6.QtCore import QRectF
            from PySide6.QtGui import QColor, QPainter, QPen

            painter = QPainter(self)
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.fillRect(event.rect(), Qt.transparent)
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            painter.setRenderHint(QPainter.Antialiasing, True)
            if bool(getattr(self, "_light_overlay_hovered", False)):
                bg = QColor(23, 26, 31, 248)
                border = QColor(117, 132, 151, 225)
            else:
                bg = QColor(23, 26, 31, 242)
                border = QColor(77, 90, 106, 218)
            rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
            painter.setBrush(bg)
            painter.setPen(QPen(border, 1))
            painter.drawRoundedRect(rect, 14, 14)
            painter.end()
        except Exception:
            # Keep the controls available even if a platform paint edge-case is
            # hit; the child widgets can still render on a transparent surface.
            pass

    paintEvent = _paint_light_overlay_event

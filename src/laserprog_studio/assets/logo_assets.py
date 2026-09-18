# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def logo_png_path() -> Path:
    return Path(__file__).resolve().parent / "logo.png"


def logo_ico_path() -> Path:
    return Path(__file__).resolve().parent / "logo.ico"


def load_studio_icon():
    """Return the application icon when Qt is available.

    The import stays local so non-GUI tests can import the module safely.
    """
    try:
        from PySide6.QtGui import QIcon
    except Exception:
        return None
    path = logo_ico_path()
    if not path.exists():
        path = logo_png_path()
    return QIcon(str(path)) if path.exists() else QIcon()


def build_startup_splash_pixmap(width: int = 520, height: int = 280):
    """Build a polished startup splash using the studio logo."""
    from PySide6.QtCore import Qt, QRectF
    from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

    # Back plate.
    card_rect = QRectF(10, 10, width - 20, height - 20)
    path = QPainterPath()
    path.addRoundedRect(card_rect, 22, 22)
    painter.fillPath(path, QColor("#101722"))

    border_pen = QPen(QColor("#203049"))
    border_pen.setWidth(2)
    painter.setPen(border_pen)
    painter.drawPath(path)

    logo = QPixmap(str(logo_png_path()))
    if not logo.isNull():
        target_w = 132
        target_h = 132
        target_x = int((width - target_w) / 2)
        target_y = 34
        painter.drawPixmap(target_x, target_y, target_w, target_h, logo)

    title_font = QFont()
    title_font.setPointSize(22)
    title_font.setBold(True)
    painter.setFont(title_font)
    painter.setPen(QColor("#F2F6FC"))
    painter.drawText(QRectF(30, 176, width - 60, 36), Qt.AlignCenter, "LaserProg Studio")

    subtitle_font = QFont()
    subtitle_font.setPointSize(10)
    painter.setFont(subtitle_font)
    painter.setPen(QColor("#96A8C2"))
    painter.drawText(
        QRectF(30, 214, width - 60, 22),
        Qt.AlignCenter,
        "Precision laser design workspace",
    )

    hint_font = QFont()
    hint_font.setPointSize(9)
    painter.setFont(hint_font)
    painter.setPen(QColor("#00C853"))
    painter.drawText(QRectF(30, 242, width - 60, 18), Qt.AlignCenter, "Starting…")
    painter.end()
    return pixmap


__all__ = [
    "logo_png_path",
    "logo_ico_path",
    "load_studio_icon",
    "build_startup_splash_pixmap",
]

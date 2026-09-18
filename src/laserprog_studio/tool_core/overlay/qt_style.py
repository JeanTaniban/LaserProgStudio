# -*- coding: utf-8 -*-
"""Styling and painting helpers for Qt overlay widgets."""

from __future__ import annotations

from typing import Any

from .specs import OverlayWindowSpec


def apply_overlay_style(widget: Any, spec: OverlayWindowSpec) -> None:
    kind = str(spec.overlay_kind)
    field_color = "#f8fafc" if kind == "tooltip" else "#d8e1ec"
    title_size = "8pt" if kind == "toolbar" else "10pt"
    accent = str(getattr(spec, "accent_color", None) or "#41B2F5")
    widget.setStyleSheet(
        "QFrame#ToolCoreOverlayWindow { background-color: transparent; border: none; border-radius: 13px; }"
        f"QLabel#ToolCoreOverlayTitle {{ color: #f8fafc; font-weight: 900; font-size: {title_size}; padding: 0px 2px 1px 2px; }}"
        f"QLabel#ToolCoreOverlayField {{ color: {field_color}; font-weight: 650; padding: 1px 2px; }}"
        "QLabel#ToolCoreOverlayBadge { color: #f8fbff; font-weight: 850; font-size: 9pt; padding: 1px 8px 2px 8px; background: transparent; }"
        "QLabel#ToolCoreOverlayStatusPill { color: #f8fbff; font-weight: 950; font-size: 10pt; padding: 5px 8px; background: rgba(18, 31, 45, 226); border: 1px solid rgba(79, 151, 216, 210); border-radius: 11px; }"
        "QLabel#ToolCoreCommandDeckTitle { color: #f8fbff; font-weight: 950; font-size: 10pt; padding: 0px; }"
        "QLabel#ToolCoreCommandDeckSubtitle { color: #91a5b8; font-weight: 750; font-size: 7.5pt; padding: 0px; }"
        f"QLabel#ToolCoreCommandDeckChip {{ color: #dff3ff; font-weight: 950; font-size: 8pt; padding: 2px 8px; background: rgba(19, 42, 59, 225); border: 1px solid {accent}; border-radius: 10px; }}"
        "QFrame#ToolCoreCommandDeckSection { background: rgba(12, 18, 26, 178); border: 1px solid rgba(76, 104, 132, 148); border-radius: 10px; }"
        "QLabel#ToolCoreCommandDeckSectionTitle { color: #b9c8d8; font-weight: 950; font-size: 7.8pt; letter-spacing: 0.15px; padding: 0px; }"
        "QFrame#ToolCoreMetricBarTitleCell { background: rgba(15, 24, 35, 194); border: 1px solid rgba(64, 105, 139, 128); border-radius: 12px; }"
        "QLabel#ToolCoreMetricBarTitle { color: #f8fbff; font-weight: 950; font-size: 10pt; padding: 0px; }"
        "QLabel#ToolCoreMetricBarSubtitle { color: #8fa5bb; font-weight: 750; font-size: 8pt; padding: 0px; }"
        "QFrame#ToolCoreMetricFieldCard { background: rgba(16, 24, 35, 214); border: 1px solid rgba(68, 100, 130, 168); border-radius: 12px; }"
        "QLabel#ToolCoreMetricFieldLabel { color: #aebfd1; font-weight: 900; font-size: 8pt; padding: 0px; }"
        "QLineEdit#ToolCoreMetricFieldEdit { min-height: 30px; padding: 2px 8px; border-radius: 9px; background: #07111c; color: #ffffff; border: 1px solid #4f789d; font-weight: 950; font-size: 10.5pt; selection-background-color: #28a7e8; }"
        "QLineEdit#ToolCoreMetricFieldEdit:focus { background: #0c1d2c; border-color: #3dc9ff; color: #ffffff; }"
        "QPushButton#ToolCoreMetricActionButton { border-radius: 10px; padding: 3px 8px; font-weight: 950; font-size: 8.5pt; background: #202a35; color: #dce8f4; border: 1px solid #4d6178; }"
        "QPushButton#ToolCoreMetricActionButton:hover { background: #2d3845; color: #ffffff; border-color: #7f98b3; }"
        "QPushButton#ToolCoreMetricActionButton[overlayButtonStyle=\"primary\"] { background: #17b8ff; color: #071018; border-color: #78dcff; }"
        "QPushButton#ToolCoreMetricActionButton[overlayButtonStyle=\"primary\"]:hover { background: #5bd1ff; border-color: #d4f4ff; }"
        "QPushButton#ToolCoreMetricActionButton[overlayButtonStyle=\"ghost\"] { background: transparent; color: #9fb0c2; border-color: rgba(87, 105, 126, 122); }"
        "QPushButton#ToolCoreMetricActionButton[overlayButtonStyle=\"ghost\"]:hover { background: rgba(42, 54, 68, 190); color: #ffffff; border-color: #71859d; }"
        "QFrame#ToolCoreOverlayToolbarSection { background: rgba(15, 22, 31, 178); border: 1px solid rgba(76, 101, 128, 145); border-radius: 11px; }"
        "QLabel#ToolCoreOverlayToolbarSectionTitle { color: #b8c7d6; font-weight: 900; font-size: 8pt; letter-spacing: 0.25px; padding: 0px 2px; }"
        "QLineEdit#ToolCoreOverlayFieldEdit { min-height: 22px; padding: 2px 7px; border-radius: 8px; background: #111923; color: #f7fbff; border: 1px solid #58728e; font-weight: 800; selection-background-color: #2f8dcc; }"
        "QLineEdit#ToolCoreOverlayFieldEdit:focus { background: #162231; border-color: #83c7ff; color: #ffffff; }"
        "QLineEdit#ToolCoreOverlayFieldEdit:disabled { background: #151b22; color: #7d8a99; border-color: #354251; }"
        "QLabel#ToolCoreOverlayFieldCaption { color: #b7c6d8; font-weight: 800; padding: 1px 2px; }"
        "QPushButton#ToolCoreOverlayButton { min-height: 25px; padding: 3px 9px; border-radius: 9px; background: #252c35; color: #eef4fb; border: 1px solid #526174; font-weight: 800; }"
        "QPushButton#ToolCoreOverlayButton:hover { background: #303a46; border-color: #8193aa; color: #ffffff; }"
        "QPushButton#ToolCoreOverlayButton:checked { background: #3f536a; border-color: #b9cbe0; color: #ffffff; font-weight: 900; }"
        "QPushButton#ToolCoreOverlayButton:checked:hover { background: #4a627d; border-color: #d1e0f2; }"
        "QPushButton#ToolCoreOverlayButton:disabled { background: #1d232b; color: #778393; border-color: #333c49; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"primary\"] { background: #d7e8ff; color: #101820; border-color: #eff7ff; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"primary\"]:hover { background: #edf6ff; border-color: #ffffff; color: #0b1118; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"primary\"]:pressed { background: #bfd8f5; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"secondary\"] { background: #26303b; border-color: #5b6b7f; color: #eef4fb; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"ghost\"] { background: transparent; border-color: transparent; color: #d7e1ec; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"ghost\"]:hover { background: #27313c; border-color: #3f4d5e; color: #ffffff; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"mode\"] { min-width: 0px; background: #202832; border-color: #566578; color: #f1f5fa; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"mode\"]:hover { background: #2d3744; border-color: #93a4ba; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"mode\"]:checked { background: #46596f; border-color: #c9d9eb; color: #ffffff; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"mode\"]:checked:hover { background: #526982; border-color: #eef6ff; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"toggle\"] { background: #202832; border-color: #566578; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"toggle\"]:checked { background: #335d49; border-color: #8bd6af; color: #ffffff; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"danger\"] { background: #3b2529; border-color: #80515a; color: #ffe8eb; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"danger\"]:hover { background: #543139; border-color: #c97885; color: #ffffff; }"
        "QPushButton#ToolCoreOverlayButton[overlayButtonStyle=\"icon\"] { min-width: 31px; max-width: 38px; padding-left: 5px; padding-right: 5px; border-radius: 9px; }"
        "QPushButton#ToolCoreOverlayButton[toolPaletteButton=\"true\"] { min-width: 0px; }"
        "QPushButton#ToolCoreOverlayButton[toolCoreVectorIconSet=\"true\"] { min-width: 0px; max-width: 999px; min-height: 0px; padding: 0px; background: transparent; border-color: transparent; color: #d9e4ef; font-size: 9pt; }"
        "QPushButton#ToolCoreOverlayButton[toolCoreVectorIconSet=\"true\"]:hover { background: transparent; border-color: transparent; color: #ffffff; }"
        "QPushButton#ToolCoreOverlayButton[toolCoreVectorIconSet=\"true\"]:checked { background: transparent; border-color: transparent; color: #ffffff; }"
    )
    # Qt stylesheets do not support a CSS `cursor` property on QFrame. Using the
    # real widget cursor avoids thousands of invalid-cursor-property warnings in
    # the launcher log while overlays are rebuilt/refreshed.
    try:
        from PySide6.QtCore import Qt

        widget.setCursor(Qt.OpenHandCursor if spec.movable else Qt.ArrowCursor)
    except Exception:
        pass


def paint_overlay_frame(adapter: Any, widget: Any, event: Any) -> None:
    """Paint a transform-style rounded overlay surface behind child widgets."""

    try:
        from PySide6.QtCore import QRectF, Qt
        from PySide6.QtGui import QColor, QPainter, QPen

        spec = adapter.manager.window(str(getattr(widget, "window_id", "")))
        kind = str(getattr(spec, "overlay_kind", "palette") if spec is not None else "palette")
        if kind == "toolbar" and spec is not None and any(str(getattr(field, "id", "")) == "plan_trace_2d.command_status" for field in getattr(spec, "fields", ()) or ()):
            kind = "command_deck"
        hovered = bool(getattr(widget, "_tool_core_overlay_hovered", False))
        painter = QPainter(widget)
        painter.setCompositionMode(QPainter.CompositionMode_Source)
        painter.fillRect(event.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if kind == "modal":
            bg = QColor(41, 34, 22, 248 if hovered else 244)
            border = QColor(180, 132, 57, 226 if hovered else 205)
        elif kind == "tooltip":
            bg = QColor(15, 18, 23, 248 if hovered else 242)
            border = QColor(90, 104, 122, 220)
        elif kind == "command_deck":
            bg = QColor(9, 13, 19, 236 if hovered else 224)
            accent_value = str(getattr(spec, "accent_color", "") or "") if spec is not None else ""
            border = QColor(accent_value) if accent_value else QColor(65, 125, 174, 214 if hovered else 170)
            if accent_value:
                border.setAlpha(232 if hovered else 190)
        elif kind == "metric_bar":
            bg = QColor(8, 13, 20, 242 if hovered else 232)
            border = QColor(45, 181, 255, 230 if hovered else 190)
        elif kind == "toolbar":
            bg = QColor(10, 15, 22, 242 if hovered else 226)
            accent_value = str(getattr(spec, "accent_color", "") or "") if spec is not None else ""
            border = QColor(accent_value) if accent_value else QColor(74, 121, 166, 224 if hovered else 178)
            if accent_value:
                border.setAlpha(232 if hovered else 190)
        else:
            bg = QColor(23, 26, 31, 248 if hovered else 242)
            border = QColor(117, 132, 151, 225 if hovered else 210)
        rect = QRectF(widget.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = 13 if kind in {"toolbar", "command_deck", "metric_bar"} else 14
        if kind == "command_deck":
            painter.setBrush(bg)
            painter.setPen(QPen(border, 1.05))
            painter.drawRoundedRect(rect, radius, radius)
            painter.setBrush(Qt.NoBrush)
            rim = QColor(str(getattr(spec, "accent_color", "") or "#32B5FF"))
            rim.setAlpha(64 if hovered else 42)
            painter.setPen(QPen(rim, 2.0))
            painter.drawRoundedRect(rect.adjusted(1.6, 1.6, -1.6, -1.6), radius, radius)
            painter.end()
            return
        if kind == "metric_bar":
            painter.setBrush(bg)
            painter.setPen(QPen(border, 1.15))
            painter.drawRoundedRect(rect, radius, radius)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(QColor(45, 190, 255, 70 if hovered else 48), 2.1))
            painter.drawRoundedRect(rect.adjusted(1.7, 1.7, -1.7, -1.7), radius, radius)
            painter.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
            painter.drawLine(rect.left() + 14.0, rect.top() + 1.0, rect.right() - 14.0, rect.top() + 1.0)
            painter.end()
            return
        if kind == "toolbar":
            has_sections = bool(getattr(spec, "toolbar_sections", ()) or ())
            has_badge = any(str(getattr(field, "id", "")).endswith("mode_badge") for field in getattr(spec, "fields", ()) or ())
            panel_rect = QRectF(rect)
            if has_badge and not has_sections:
                panel_rect.setTop(34.0)
            painter.setBrush(bg)
            painter.setPen(QPen(border, 1.15))
            painter.drawRoundedRect(panel_rect, radius, radius)
            # Subtle active HUD rim, similar to transform overlays, without
            # overpowering the drawing buttons.
            painter.setBrush(Qt.NoBrush)
            rim = QColor(str(getattr(spec, "accent_color", "") or "#34A9FF"))
            rim.setAlpha(72 if hovered else 48)
            painter.setPen(QPen(rim, 2.4))
            painter.drawRoundedRect(panel_rect.adjusted(1.8, 1.8, -1.8, -1.8), radius, radius)
            if has_sections:
                painter.end()
                return
            if has_badge:
                badge_w = min(190.0, max(126.0, rect.width() * 0.22))
                badge = QRectF(rect.center().x() - badge_w * 0.5, 0.5, badge_w, 27.0)
                painter.setBrush(QColor(12, 20, 31, 240))
                painter.setPen(QPen(QColor(72, 132, 190, 205), 1.0))
                painter.drawRoundedRect(badge, 11.0, 11.0)
                notch = QRectF(badge.center().x() - 8.0, badge.bottom() - 1.0, 16.0, 10.0)
                try:
                    from PySide6.QtGui import QPainterPath

                    path = QPainterPath()
                    path.moveTo(notch.left(), notch.top())
                    path.lineTo(notch.center().x(), notch.bottom())
                    path.lineTo(notch.right(), notch.top())
                    path.closeSubpath()
                    painter.setBrush(QColor(12, 20, 31, 240))
                    painter.setPen(QPen(QColor(72, 132, 190, 205), 1.0))
                    painter.drawPath(path)
                except Exception:
                    pass
            painter.end()
            return
        painter.setBrush(bg)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, radius, radius)
        painter.end()
    except Exception:
        return

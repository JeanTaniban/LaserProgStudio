# -*- coding: utf-8 -*-
from __future__ import annotations

from ..._window_deps import *
from ..transform_icons import transform_icon
from .frame import LightTransformOverlayFrame


class LightTransformOverlayConstructionLayer:
    """Focused Light UI overlay behavior extracted from the original mixin."""

    def _make_light_transform_overlay(self, parent: QWidget) -> QFrame:
        # Keep the compact overlay embedded in the viewport.  Passing ``self``
        # here used to parent it to the main window, and combined with
        # ``Qt.Tool`` it became a real platform helper window.
        overlay = LightTransformOverlayFrame(parent, viewport=parent)
        overlay.setObjectName("LightTransformOverlay")
        try:
            overlay.setAttribute(Qt.WA_AlwaysStackOnTop, True)
        except Exception:
            pass
        overlay.setMouseTracking(True)
        overlay.installEventFilter(self)
        for watched in (parent, getattr(self, "plotter_area", None), self):
            if watched is not None:
                try:
                    watched.installEventFilter(self)
                except Exception:
                    pass
        overlay.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        layout = QHBoxLayout(overlay)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        # Keep the close/position/rotation/scale cluster geometrically stable.
        # Previously those buttons were direct children of the main row, so the
        # left icons shifted when the right-side fields/Full UI button changed
        # their size hints between transform modes.
        fixed_left = QFrame(overlay)
        fixed_left.setObjectName("LightOverlayFixedLeftCluster")
        fixed_left.setFixedWidth(224)
        fixed_left.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        fixed_left_l = QHBoxLayout(fixed_left)
        fixed_left_l.setContentsMargins(0, 0, 0, 0)
        fixed_left_l.setSpacing(6)

        self.light_btn_close = QToolButton(fixed_left)
        self.light_btn_close.setObjectName("LightOverlayCloseButton")
        self.light_btn_close.setText("X")
        self.light_btn_close.setToolTip("Disable transform and clear selection")
        self.light_btn_close.setFixedSize(42, 42)
        close_font = QFont()
        close_font.setPointSize(16)
        close_font.setBold(True)
        self.light_btn_close.setFont(close_font)
        self.light_btn_close.clicked.connect(self._on_light_overlay_close_clicked)
        fixed_left_l.addWidget(self.light_btn_close)
        fixed_left_l.addSpacing(4)

        self.light_transform_group = QButtonGroup(self)
        self.light_transform_group.setExclusive(True)
        self.light_btn_position = self._light_transform_button("Position", "Edit group position")
        self.light_btn_rotation = self._light_transform_button("Rotation", "Edit active rotation")
        self.light_btn_scale = self._light_transform_button("Scale", "Edit group size")
        for mode, btn in [
            ("position", self.light_btn_position),
            ("rotation", self.light_btn_rotation),
            ("scale", self.light_btn_scale),
        ]:
            btn.setProperty("light_mode", mode)
            self.light_transform_group.addButton(btn)
            fixed_left_l.addWidget(btn)
        self.light_btn_position.setChecked(True)
        layout.addWidget(fixed_left, 0, Qt.AlignLeft | Qt.AlignVCenter)

        sep_light = QFrame(overlay)
        sep_light.setObjectName("LightOverlaySeparator")
        sep_light.setFrameShape(QFrame.VLine)
        sep_light.setFrameShadow(QFrame.Plain)
        sep_light.setFixedHeight(38)
        layout.addWidget(sep_light)

        # The ratio lock lives inside a permanently reserved slot.  Showing the
        # lock only in Scale mode must not change the row's size hint, otherwise
        # the X / Position / Rotation / Scale cluster drifts horizontally and Qt
        # may keep the enlarged floating-window geometry afterwards.
        self.light_scale_ratio_lock_slot = QFrame(overlay)
        self.light_scale_ratio_lock_slot.setObjectName("LightOverlayLockSlot")
        self.light_scale_ratio_lock_slot.setFixedSize(48, 42)
        self.light_scale_ratio_lock_slot.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        lock_slot_l = QHBoxLayout(self.light_scale_ratio_lock_slot)
        lock_slot_l.setContentsMargins(0, 0, 0, 0)
        lock_slot_l.setSpacing(0)

        self.light_scale_ratio_lock = QToolButton(self.light_scale_ratio_lock_slot)
        self.light_scale_ratio_lock.setObjectName("LightOverlayLockButton")
        self.light_scale_ratio_lock.setText("")
        self.light_scale_ratio_lock.setToolTip("Lock size ratio while scaling")
        self.light_scale_ratio_lock.setCheckable(True)
        self.light_scale_ratio_lock.setToolButtonStyle(Qt.ToolButtonIconOnly)
        self.light_scale_ratio_lock.setIconSize(QSize(26, 26))
        self.light_scale_ratio_lock.setFixedSize(42, 40)
        try:
            self.light_scale_ratio_lock.setIcon(self._light_lock_icon(False))
        except Exception:
            pass
        self.light_scale_ratio_lock.toggled.connect(self._on_scale_ratio_lock_changed)
        lock_slot_l.addWidget(self.light_scale_ratio_lock, 0, Qt.AlignCenter)
        layout.addWidget(self.light_scale_ratio_lock_slot)

        layout.addSpacing(2)
        self.light_x = self._spin(-100000, 100000, 0, 1)
        self.light_y = self._spin(-100000, 100000, 0, 1)
        self.light_z = self._spin(-100000, 100000, 0, 1)
        for axis, spin in [("X", self.light_x), ("Y", self.light_y), ("Z", self.light_z)]:
            lbl = QLabel(axis, overlay)
            lbl.setObjectName("LightOverlayAxisLabel")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFixedWidth(18)
            layout.addWidget(lbl)
            spin.setFixedWidth(98)
            spin.setMinimumHeight(34)
            spin.valueChanged.connect(self._on_light_transform_field_changed)
            layout.addWidget(spin)
        self.light_unit_label = QLabel("mm", overlay)
        self.light_unit_label.setObjectName("LightOverlayUnitLabel")
        self.light_unit_label.setAlignment(Qt.AlignCenter)
        self.light_unit_label.setFixedWidth(38)
        layout.addWidget(self.light_unit_label)

        layout.addSpacing(8)
        self.light_btn_exit_ui = QToolButton(overlay)
        self.light_btn_exit_ui.setObjectName("LightOverlayExitButton")
        self.light_btn_exit_ui.setText("Full UI")
        self.light_btn_exit_ui.setToolTip("Exit Light UI and reopen the left and right panels")
        self.light_btn_exit_ui.setFixedSize(86, 40)
        self.light_btn_exit_ui.clicked.connect(self._on_light_overlay_exit_ui_clicked)
        layout.addWidget(self.light_btn_exit_ui)

        self.light_transform_group.buttonClicked.connect(self._on_light_transform_mode_changed)
        self._sync_light_transform_fields()
        return overlay

    def _light_lock_icon(self, locked: bool) -> QIcon:
        """Draw a crisp monochrome lock icon instead of relying on emoji fonts."""
        from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap

        pix = QPixmap(48, 48)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        stroke = QColor("#f7fbff" if locked else "#d8e1ec")
        accent = QColor("#9fb4cc" if locked else "#7e8fa3")
        painter.setPen(QPen(stroke, 4.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

        shackle = QPainterPath()
        if locked:
            shackle.moveTo(16, 24)
            shackle.lineTo(16, 18)
            shackle.cubicTo(16, 9, 32, 9, 32, 18)
            shackle.lineTo(32, 24)
        else:
            shackle.moveTo(16, 24)
            shackle.lineTo(16, 18)
            shackle.cubicTo(16, 9, 31, 9, 31, 18)
            shackle.lineTo(37, 18)
        painter.drawPath(shackle)

        painter.setBrush(accent)
        painter.setPen(QPen(stroke, 3.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawRoundedRect(12, 22, 24, 18, 5, 5)
        painter.setBrush(stroke)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(22, 29, 4, 4)
        painter.drawRoundedRect(23, 31, 2, 6, 1, 1)
        painter.end()
        return QIcon(pix)

    def _refresh_light_scale_lock_button(self, *, locked: bool, is_scale: bool, available: bool) -> None:
        lock = getattr(self, "light_scale_ratio_lock", None)
        if lock is None:
            return
        try:
            lock.setIcon(self._light_lock_icon(bool(locked)))
            lock.setToolTip(
                "Unlock size ratio" if bool(locked) and bool(is_scale)
                else "Lock size ratio while scaling"
            )
            lock.setVisible(bool(is_scale))
            lock.setEnabled(bool(is_scale) and bool(available))
        except Exception:
            pass

    def _light_transform_button(self, text: str, tooltip: str) -> QToolButton:
        parent = getattr(self, "light_transform_overlay", None)
        button = QToolButton(parent)
        button.setText(text)
        button.setToolTip(tooltip)
        button.setCheckable(True)
        button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        icon_name = {
            "position": "translate",
            "rotation": "rotate",
            "scale": "scale",
        }.get(str(text).strip().lower())
        icon = transform_icon(icon_name)
        if icon is not None and not icon.isNull():
            button.setIcon(icon)
            button.setIconSize(QSize(34, 34))
        button.setFixedSize(48, 42)
        return button

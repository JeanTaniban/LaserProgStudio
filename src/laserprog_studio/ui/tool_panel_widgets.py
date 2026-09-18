# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


def setting_row_widget(label_text: str, widget: QWidget, unit: str = "") -> QWidget:
    """Return a hideable compact parameter row for adaptive tool panels."""

    row_widget = QWidget()
    row_widget.setMinimumWidth(0)
    row_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    row = QHBoxLayout(row_widget)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(3)
    label = QLabel(label_text)
    label.setWordWrap(False)
    label.setMinimumWidth(0)
    label.setFixedWidth(76)
    label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    row.addWidget(label, 0)
    try:
        widget.setMinimumWidth(44)
        widget.setMaximumWidth(64)
        widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    except Exception:
        pass
    row.addWidget(widget, 0)
    if unit:
        unit_lbl = QLabel(unit)
        unit_lbl.setFixedWidth(22)
        unit_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        row.addWidget(unit_lbl, 0)
    row.addStretch(1)
    return row_widget


def checkbox_row_widget(checkbox: QCheckBox) -> QWidget:
    """Wrap a checkbox in a hideable row widget."""

    row_widget = QWidget()
    row_widget.setMinimumWidth(0)
    row_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    layout = QHBoxLayout(row_widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(checkbox)
    return row_widget


def pin_compact_tool_panel(widget: QWidget) -> QWidget:
    """Prevent tool-panel controls from absorbing unused vertical space.

    Qt gives wrapped QLabel instances an expanding vertical policy in some
    stacked/scrollable layouts.  In the right Tool inspector this creates huge
    blank bands between compact controls.  Pin labels and simple rows to their
    size hint so any spare height remains below the panel, not between fields.
    """

    widget.setMinimumWidth(0)
    widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
    for label in widget.findChildren(QLabel):
        policy = label.sizePolicy()
        label.setSizePolicy(policy.horizontalPolicy(), QSizePolicy.Fixed)
        label.setAlignment(label.alignment() | Qt.AlignTop)
    fixed_control_types = (QCheckBox, QComboBox, QLineEdit, QSlider, QAbstractSpinBox, QPushButton)
    for control_type in fixed_control_types:
        for child in widget.findChildren(control_type):
            policy = child.sizePolicy()
            child.setSizePolicy(policy.horizontalPolicy(), QSizePolicy.Fixed)
    return widget


def top_aligned_tool_page(panel: QWidget) -> QWidget:
    """Wrap a real tool panel so QStackedWidget cannot stretch it internally."""

    pin_compact_tool_panel(panel)
    page = QWidget()
    page.setMinimumWidth(0)
    page.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(panel, 0, Qt.AlignTop)
    layout.addStretch(1)
    return page

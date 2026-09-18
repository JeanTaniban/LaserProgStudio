# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


# This stylesheet is deliberately application-scoped.  Tool-specific and
# window-specific stylesheets still win through Qt's normal specificity rules,
# while unstyled dialogs and helper windows no longer fall back to the Windows
# light palette.
DARK_APPLICATION_STYLESHEET = r"""
QWidget {
    color: #e7eaee;
    background-color: #171a1f;
    selection-background-color: #4d6580;
    selection-color: #ffffff;
}
QMainWindow, QDialog, QMessageBox, QFileDialog, QColorDialog, QFontDialog,
QInputDialog, QWizard, QDockWidget {
    background-color: #14171b;
    color: #e7eaee;
}
QMenuBar, QMenu, QToolBar, QStatusBar {
    background-color: #1a1f25;
    color: #e7eaee;
}
QMenuBar::item:selected, QMenu::item:selected {
    background-color: #344252;
    color: #ffffff;
}
QMenu::separator {
    height: 1px;
    background: #343b45;
    margin: 5px 8px;
}
QLabel, QCheckBox, QRadioButton, QGroupBox {
    background-color: transparent;
    color: #e7eaee;
}
QGroupBox {
    border: 1px solid #343b45;
    border-radius: 8px;
    margin-top: 9px;
    padding-top: 7px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox,
QComboBox, QDateEdit, QTimeEdit, QDateTimeEdit, QKeySequenceEdit,
QListView, QListWidget, QTreeView, QTreeWidget, QTableView, QTableWidget,
QAbstractItemView {
    background-color: #1b1f24;
    color: #edf1f5;
    border: 1px solid #343b45;
    border-radius: 6px;
    selection-background-color: #4d6580;
    selection-color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
QAbstractItemView:focus {
    border-color: #71859d;
}
QComboBox QAbstractItemView {
    background-color: #1c2127;
    color: #edf1f5;
    outline: 0;
}
QPushButton, QToolButton, QDialogButtonBox QPushButton {
    background-color: #2a3038;
    color: #eef2f6;
    border: 1px solid #47515e;
    border-radius: 6px;
    padding: 5px 10px;
}
QPushButton:hover, QToolButton:hover {
    background-color: #353e49;
    border-color: #667587;
}
QPushButton:pressed, QToolButton:pressed,
QPushButton:checked, QToolButton:checked {
    background-color: #43566b;
    border-color: #8398b0;
}
QPushButton:disabled, QToolButton:disabled, QWidget:disabled {
    color: #77818d;
}
QTabWidget::pane {
    border: 1px solid #343b45;
    background-color: #171a1f;
}
QTabBar::tab {
    background-color: #20252b;
    color: #aeb6c0;
    border: 1px solid #343b45;
    padding: 6px 10px;
}
QTabBar::tab:selected {
    background-color: #303945;
    color: #ffffff;
}
QHeaderView::section {
    background-color: #242a31;
    color: #dce2e8;
    border: 0;
    border-right: 1px solid #343b45;
    border-bottom: 1px solid #343b45;
    padding: 5px;
}
QToolTip {
    color: #eef2f6;
    background-color: #23272d;
    border: 1px solid #48515c;
    padding: 5px 7px;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: #171a1f;
    border: none;
    margin: 0;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #46515e;
    border-radius: 5px;
    min-height: 24px;
    min-width: 24px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #5a6878;
}
QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
    border: none;
}
QProgressBar {
    background-color: #1b1f24;
    color: #eef2f6;
    border: 1px solid #343b45;
    border-radius: 5px;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #4d708f;
    border-radius: 4px;
}
QSplitter::handle {
    background-color: #2c333c;
}
"""


def configure_dark_mode_before_application(*, force_dark_mode: bool, use_native_dialogs: bool) -> None:
    """Set attributes that must be configured before QApplication exists."""

    if not force_dark_mode:
        return
    try:
        from PySide6.QtCore import QCoreApplication, Qt

        if not use_native_dialogs:
            attribute = getattr(Qt.ApplicationAttribute, "AA_DontUseNativeDialogs", None)
            if attribute is None:
                attribute = getattr(Qt, "AA_DontUseNativeDialogs", None)
            if attribute is not None:
                QCoreApplication.setAttribute(attribute, True)
    except Exception:
        pass


def _build_dark_palette() -> Any:
    from PySide6.QtGui import QColor, QPalette

    palette = QPalette()
    colors = {
        "Window": "#14171b",
        "WindowText": "#e7eaee",
        "Base": "#1b1f24",
        "AlternateBase": "#20252b",
        "ToolTipBase": "#23272d",
        "ToolTipText": "#eef2f6",
        "Text": "#e7eaee",
        "Button": "#2a3038",
        "ButtonText": "#eef2f6",
        "BrightText": "#ffffff",
        "Link": "#79b8ff",
        "Highlight": "#4d6580",
        "HighlightedText": "#ffffff",
        "PlaceholderText": "#858f9b",
        "Accent": "#5f83a8",
    }
    for role_name, color in colors.items():
        role = getattr(QPalette.ColorRole, role_name, None)
        if role is not None:
            palette.setColor(role, QColor(color))

    disabled = QPalette.ColorGroup.Disabled
    for role_name, color in {
        "WindowText": "#77818d",
        "Text": "#77818d",
        "ButtonText": "#77818d",
        "Highlight": "#35414d",
        "HighlightedText": "#aab2bb",
    }.items():
        role = getattr(QPalette.ColorRole, role_name, None)
        if role is not None:
            palette.setColor(disabled, role, QColor(color))
    return palette


def apply_forced_dark_theme(app: Any) -> Any:
    """Apply and keep a deterministic dark palette for every Qt window."""

    try:
        app.setStyle("Fusion")
    except Exception:
        pass
    try:
        app.setPalette(_build_dark_palette())
    except Exception:
        pass
    try:
        app.setStyleSheet(DARK_APPLICATION_STYLESHEET)
    except Exception:
        pass
    try:
        from PySide6.QtCore import Qt

        hints = app.styleHints()
        setter = getattr(hints, "setColorScheme", None)
        scheme = getattr(getattr(Qt, "ColorScheme", object), "Dark", None)
        if callable(setter) and scheme is not None:
            setter(scheme)
    except Exception:
        pass
    try:
        app.setProperty("laserprog_force_dark_mode", True)
    except Exception:
        pass

    enforcer = _DarkThemeEnforcer(app)
    try:
        app.installEventFilter(enforcer)
        app._laserprog_dark_theme_enforcer = enforcer
    except Exception:
        pass
    return enforcer


class _DarkThemeEnforcer:
    """Small QObject event filter that rejects later OS palette changes."""

    def __new__(cls, app: Any):
        try:
            from PySide6.QtCore import QObject

            class _QObjectDarkThemeEnforcer(QObject):
                def __init__(self, parent: Any) -> None:
                    super().__init__(parent)
                    self._app = parent
                    self._reapply_scheduled = False
                    self._applying = False

                def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt API
                    try:
                        from PySide6.QtCore import QEvent, QTimer

                        event_types = {
                            getattr(QEvent.Type, "ApplicationPaletteChange", None),
                            getattr(QEvent.Type, "ThemeChange", None),
                        }
                        if event is not None and event.type() in event_types and not self._applying:
                            if not self._reapply_scheduled:
                                self._reapply_scheduled = True
                                QTimer.singleShot(0, self._reapply)
                    except Exception:
                        pass
                    return False

                def _reapply(self) -> None:
                    self._reapply_scheduled = False
                    if self._applying:
                        return
                    self._applying = True
                    try:
                        self._app.setPalette(_build_dark_palette())
                        if self._app.styleSheet() != DARK_APPLICATION_STYLESHEET:
                            self._app.setStyleSheet(DARK_APPLICATION_STYLESHEET)
                    except Exception:
                        pass
                    finally:
                        self._applying = False

            return _QObjectDarkThemeEnforcer(app)
        except Exception:
            return object.__new__(cls)


__all__ = [
    "DARK_APPLICATION_STYLESHEET",
    "apply_forced_dark_theme",
    "configure_dark_mode_before_application",
]

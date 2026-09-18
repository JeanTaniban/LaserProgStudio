# -*- coding: utf-8 -*-
"""Guard against accidental top-level helper widgets during tool activation.

Most LaserProg UI controls are meant to be embedded in the main window.  A
QWidget without a parent, or a child widget with a window-type flag, can become a
platform top-level window.  On Windows this can show up as tiny minimised helper
windows when tools rebuild their panels.
"""
from __future__ import annotations

from typing import Any


_ALLOWED_OBJECT_NAMES = {
    "ToolbarPaletteDialog",
}

_ALLOWED_CLASS_SUFFIXES = (
    "QDialog",
    "QMessageBox",
    "QFileDialog",
    "QFontDialog",
    "QMenu",
    "QSplashScreen",
)


def _class_name(widget: Any) -> str:
    try:
        meta = widget.metaObject()
        name = meta.className()
        return str(name or type(widget).__name__)
    except Exception:
        return type(widget).__name__


def _object_name(widget: Any) -> str:
    try:
        return str(widget.objectName() or "")
    except Exception:
        return ""


def _is_allowed_top_level(widget: Any, owner: Any) -> bool:
    if widget is owner:
        return True
    name = _object_name(widget)
    if name in _ALLOWED_OBJECT_NAMES:
        return True
    cls = _class_name(widget)
    if cls.endswith(_ALLOWED_CLASS_SUFFIXES):
        return True
    try:
        # Real dialogs/menus intentionally set window flags.  Plain QWidget,
        # QFrame, QLabel, QToolButton, QGroupBox etc. do not belong here when a
        # normal tool opens.
        from PySide6.QtWidgets import QDialog, QMenu

        if isinstance(widget, (QDialog, QMenu)):
            return True
    except Exception:
        pass
    return False


def sanitize_unexpected_tool_top_levels(owner: Any, *, reason: str = "") -> list[str]:
    """Hide accidental visible top-level widgets and return a diagnostic list.

    This is deliberately conservative: it runs only from the tool lifecycle and
    never closes dialogs/menus.  It is a safety net in addition to the static
    fixes that keep the light overlay and Creator panels embedded.
    """

    try:
        from PySide6.QtWidgets import QApplication
    except Exception:
        return []

    app = QApplication.instance()
    if app is None:
        return []

    hits: list[str] = []
    try:
        widgets = list(app.topLevelWidgets())
    except Exception:
        widgets = []
    for widget in widgets:
        try:
            if widget is None or not bool(widget.isVisible()):
                continue
        except Exception:
            continue
        if _is_allowed_top_level(widget, owner):
            continue
        cls = _class_name(widget)
        name = _object_name(widget)
        try:
            parent = widget.parentWidget()
            parent_name = "" if parent is None else f" parent={_class_name(parent)}#{_object_name(parent)}"
        except Exception:
            parent_name = ""
        detail = f"{cls}#{name or '<unnamed>'}{parent_name}"
        hits.append(detail)
        try:
            widget.hide()
        except Exception:
            pass
    if hits:
        try:
            note = f" reason={reason}" if reason else ""
            owner.ui_log(f"[QT][TOPLEVEL_GUARD] hidden unexpected top-level widgets:{note} " + "; ".join(hits))
        except Exception:
            pass
    return hits


def schedule_tool_top_level_guard(owner: Any, *, reason: str = "") -> None:
    """Run the guard now and after Qt has processed deferred show events."""

    sanitize_unexpected_tool_top_levels(owner, reason=reason)
    try:
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, lambda: sanitize_unexpected_tool_top_levels(owner, reason=f"{reason}:event0"))
        QTimer.singleShot(80, lambda: sanitize_unexpected_tool_top_levels(owner, reason=f"{reason}:event80"))
    except Exception:
        pass


__all__ = ["sanitize_unexpected_tool_top_levels", "schedule_tool_top_level_guard"]

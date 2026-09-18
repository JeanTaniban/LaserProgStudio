# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any


def qevent() -> Any:
    from PySide6.QtCore import QEvent

    return QEvent


def qtimer() -> Any:
    from PySide6.QtCore import QTimer

    return QTimer


def qt() -> Any:
    from PySide6.QtCore import Qt

    return Qt


def qapplication() -> Any:
    from PySide6.QtWidgets import QApplication

    return QApplication

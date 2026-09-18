# -*- coding: utf-8 -*-
from __future__ import annotations

from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QDialog, QWidget


class ToolbarPaletteClickAwayFilter(QObject):
    """Close the +Tools palette when the user clicks outside it."""

    def __init__(self, dialog: QDialog, owner: QWidget) -> None:
        super().__init__(dialog)
        self._dialog = dialog
        self._owner = owner

    def eventFilter(self, obj, event):  # noqa: N802 - Qt override
        try:
            click_events = {QEvent.MouseButtonPress}
            non_client_press = getattr(QEvent, "NonClientAreaMouseButtonPress", None)
            if non_client_press is not None:
                click_events.add(non_client_press)
            if event.type() not in click_events:
                return False
            dialog = self._dialog
            if dialog is None or not dialog.isVisible():
                return False
            point = None
            try:
                point = event.globalPosition().toPoint()
            except Exception:
                try:
                    point = event.globalPos()
                except Exception:
                    point = None
            if point is None:
                return False
            if dialog.geometry().contains(point):
                return False
            button = getattr(self._owner, "btn_toolbar_palette", None)
            if button is not None:
                try:
                    button_rect = button.rect().translated(button.mapToGlobal(button.rect().topLeft()))
                    if button_rect.contains(point):
                        return False
                except Exception:
                    pass
            dialog.close()
        except Exception:
            pass
        return False

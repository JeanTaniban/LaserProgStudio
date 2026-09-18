# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class InteractionValueFieldsLayer:
    def _install_value_field_select_all(self, widget: Any) -> None:
        """Make a value field select its full text on a single click.

        Double-click is intentionally left to the native QLineEdit handler so the
        user can edit a smaller text fragment when needed.
        """
        try:
            targets = []
            if isinstance(widget, QAbstractSpinBox):
                try:
                    targets.append(widget.lineEdit())
                except Exception:
                    pass
                targets.append(widget)
            elif isinstance(widget, QLineEdit):
                targets.append(widget)
            for target in targets:
                if target is None:
                    continue
                if target.property("_lps_value_select_all_installed"):
                    target.setProperty("_lps_value_select_all", True)
                    continue
                target.setProperty("_lps_value_select_all", True)
                target.setProperty("_lps_value_select_all_installed", True)
                target.installEventFilter(self)
        except Exception:
            log_exception("install_value_field_select_all")

    def _install_value_field_select_all_globally(self) -> None:
        """Install click-to-select-all on all numeric/value fields in the UI."""
        try:
            for spin in self.findChildren(QAbstractSpinBox):
                self._install_value_field_select_all(spin)
            for edit in self.findChildren(QLineEdit):
                self._install_value_field_select_all(edit)
        except Exception:
            log_exception("install_value_field_select_all_globally")

    def _handle_value_field_select_all_event(self, obj: Any, event: Any) -> bool:
        """Return True only when the event belongs to a registered value field.

        The event is not consumed by this helper. It schedules selectAll() after
        Qt has processed the click so the native cursor/focus handling remains
        intact. Mouse double-click is deliberately not altered.
        """
        try:
            if not obj.property("_lps_value_select_all"):
                return False
            etype = event.type()
            if etype == QEvent.MouseButtonPress:
                try:
                    if event.button() != Qt.LeftButton:
                        return True
                except Exception:
                    pass

                def _select_all_later(target=obj):
                    try:
                        if isinstance(target, QAbstractSpinBox):
                            target = target.lineEdit()
                        if isinstance(target, QLineEdit):
                            target.setFocus(Qt.MouseFocusReason)
                            target.selectAll()
                    except RuntimeError:
                        pass
                    except Exception:
                        log_exception("value_field_select_all_later")

                QTimer.singleShot(0, _select_all_later)
                return True
            if etype == QEvent.MouseButtonDblClick:
                return True
        except Exception:
            log_exception("value_field_select_all_event")
        return False


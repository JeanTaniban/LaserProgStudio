# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .base import ParameterSpec, validate_values


@dataclass(slots=True)
class ParameterPanel:
    """Qt widget bundle generated from declarative ParameterSpec objects."""

    widget: Any
    editors: dict[str, Any]
    parameters: tuple[ParameterSpec, ...]

    def values(self) -> dict[str, Any]:
        raw: dict[str, Any] = {}
        for param in self.parameters:
            editor = self.editors.get(param.id)
            if editor is None:
                raw[param.id] = param.default
                continue
            if param.kind in {"float", "int"}:
                raw[param.id] = editor.value()
            elif param.kind == "bool":
                raw[param.id] = editor.isChecked()
            elif param.kind == "choice":
                raw[param.id] = editor.currentData()
            else:
                raw[param.id] = editor.text()
        return validate_values(self.parameters, raw)

    def set_values(self, values: dict[str, Any]) -> None:
        validated = validate_values(self.parameters, values)
        for param in self.parameters:
            editor = self.editors.get(param.id)
            if editor is None:
                continue
            value = validated.get(param.id, param.default)
            if param.kind in {"float", "int"}:
                editor.setValue(value)
            elif param.kind == "bool":
                editor.setChecked(bool(value))
            elif param.kind == "choice":
                for i in range(editor.count()):
                    if editor.itemData(i) == value:
                        editor.setCurrentIndex(i)
                        break
            else:
                editor.setText(str(value))

    def reset(self) -> None:
        self.set_values({param.id: param.default for param in self.parameters})


class ParameterPanelFactory:
    """Build compact Qt forms from ParameterSpec objects.

    Imports PySide lazily so tests and geometry tooling can import the parameter
    package without a desktop Qt installation.
    """

    @staticmethod
    def create_panel(
        parameters: tuple[ParameterSpec, ...],
        *,
        parent: Any = None,
        on_change: Callable[[], None] | None = None,
    ) -> ParameterPanel:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QCheckBox,
            QComboBox,
            QDoubleSpinBox,
            QGridLayout,
            QLabel,
            QLineEdit,
            QPushButton,
            QSpinBox,
            QWidget,
        )

        widget = QWidget(parent)
        layout = QGridLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(4)
        layout.setVerticalSpacing(3)
        editors: dict[str, Any] = {}

        def connect_changed(editor: Any, kind: str) -> None:
            if on_change is None:
                return
            signal = None
            if kind in {"float", "int"}:
                signal = getattr(editor, "valueChanged", None)
            elif kind == "bool":
                signal = getattr(editor, "stateChanged", None)
            elif kind == "choice":
                signal = getattr(editor, "currentIndexChanged", None)
            else:
                signal = getattr(editor, "textChanged", None)
            if signal is not None:
                signal.connect(lambda *_args: on_change())

        for row, param in enumerate(parameters):
            label = QLabel(param.label)
            label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            if param.tooltip:
                label.setToolTip(param.tooltip)
            layout.addWidget(label, row, 0)

            if param.kind == "float":
                editor = QDoubleSpinBox()
                editor.setRange(float(param.min_value if param.min_value is not None else -1_000_000), float(param.max_value if param.max_value is not None else 1_000_000))
                editor.setSingleStep(float(param.step if param.step is not None else 1.0))
                editor.setValue(float(param.default))
            elif param.kind == "int":
                editor = QSpinBox()
                editor.setRange(int(param.min_value if param.min_value is not None else -1_000_000), int(param.max_value if param.max_value is not None else 1_000_000))
                editor.setSingleStep(int(param.step if param.step is not None else 1))
                editor.setValue(int(param.default))
            elif param.kind == "bool":
                editor = QCheckBox()
                editor.setChecked(bool(param.default))
            elif param.kind == "choice":
                editor = QComboBox()
                for choice_id, choice_label in param.choices:
                    editor.addItem(choice_label, choice_id)
                for i, (choice_id, _choice_label) in enumerate(param.choices):
                    if choice_id == param.default:
                        editor.setCurrentIndex(i)
                        break
            elif param.kind == "file":
                editor = QLineEdit(str(param.default or ""))
                browse = QPushButton("...")
                browse.setMaximumWidth(28)
                # The future texture tool can connect the browse button to a
                # QFileDialog. Keeping it here avoids forcing every tool to
                # rebuild the same file row.
                layout.addWidget(browse, row, 2)
            else:
                editor = QLineEdit(str(param.default or ""))

            if param.tooltip and hasattr(editor, "setToolTip"):
                editor.setToolTip(param.tooltip)
            connect_changed(editor, param.kind)
            editors[param.id] = editor
            layout.addWidget(editor, row, 1)

        layout.setColumnStretch(1, 1)
        return ParameterPanel(widget=widget, editors=editors, parameters=parameters)

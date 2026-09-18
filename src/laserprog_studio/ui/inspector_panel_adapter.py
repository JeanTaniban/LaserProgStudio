# -*- coding: utf-8 -*-
"""Qt adapter for declarative tool-inspector panels.

The creator-facing contract lives in ``tool_core.inspector`` and has no Qt
imports.  This adapter is the bridge the right Tool area can use to render a
panel when a tool calls ``ctx.inspector.set_panel(...)``.
"""
from __future__ import annotations

from typing import Any, Callable
import time
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None

from ..tool_core.inspector import Field, InspectorManager, InspectorPanel


class InspectorPanelQtAdapter:
    """Build a compact QWidget from an ``InspectorPanel`` declaration."""

    @staticmethod
    def create_widget(
        manager: InspectorManager,
        *,
        parent: Any = None,
        on_change: Callable[[str, Any], None] | None = None,
        on_action: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> Any:
        start = time.perf_counter()
        try:
            panel = manager.panel
            if panel is None:
                return InspectorPanelQtAdapter._empty_widget(parent)
            return InspectorPanelQtAdapter.create_panel_widget(panel, manager, parent=parent, on_change=on_change, on_action=on_action)
        finally:
            if _APP_AUDIT is not None:
                try:
                    _APP_AUDIT.record_timing("inspector.create_widget", (time.perf_counter() - start) * 1000.0)
                except Exception:
                    pass

    @staticmethod
    def create_panel_widget(
        panel: InspectorPanel,
        manager: InspectorManager,
        *,
        parent: Any = None,
        on_change: Callable[[str, Any], None] | None = None,
        on_action: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> Any:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget

        root = QGroupBox(panel.title, parent)
        root.setObjectName(f"declarative_inspector_{panel.id}")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)
        if panel.description:
            description = QLabel(panel.description, root)
            description.setWordWrap(True)
            layout.addWidget(description)

        for section in panel.sections:
            group = QGroupBox(section.title, root)
            group_layout = QVBoxLayout(group)
            group_layout.setContentsMargins(6, 6, 6, 6)
            group_layout.setSpacing(4)
            for field in section.fields:
                group_layout.addWidget(InspectorPanelQtAdapter._field_widget(field, manager, parent=group, on_change=on_change, on_action=on_action))
            layout.addWidget(group)
        layout.addStretch(1)
        return root

    @staticmethod
    def _empty_widget(parent: Any = None) -> Any:
        from PySide6.QtWidgets import QLabel

        label = QLabel("No active tool panel.", parent)
        label.setWordWrap(True)
        return label

    @staticmethod
    def _field_widget(
        field: Field,
        manager: InspectorManager,
        *,
        parent: Any = None,
        on_change: Callable[[str, Any], None] | None,
        on_action: Callable[[str, dict[str, Any]], None] | None,
    ) -> Any:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFontComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox, QWidget

        state = manager.field_state(field.id)
        tooltip = field.tooltip or ""
        if state.error:
            tooltip = f"{tooltip}\n{state.error}".strip()

        if field.kind == "separator":
            line = QFrame(parent)
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setVisible(state.visible)
            return line

        if field.kind in {"title", "help"}:
            text = field.metadata.get("text", field.label) if isinstance(field.metadata, dict) else field.label
            label = QLabel(str(text), parent)
            label.setWordWrap(True)
            if field.kind == "title":
                label.setText(f"<b>{field.label}</b>")
            if tooltip:
                label.setToolTip(tooltip)
            label.setVisible(state.visible)
            return label

        if field.kind == "button":
            button = QPushButton(field.label, parent)
            if tooltip:
                button.setToolTip(tooltip)
            button.setEnabled(state.enabled and not state.readonly)
            button.setVisible(state.visible)

            def _click() -> None:
                event = manager.trigger(field.id)
                if on_action is not None:
                    on_action(event.action_id, event.values)

            button.clicked.connect(_click)
            return button

        if field.kind == "button_row":
            from PySide6.QtWidgets import QGridLayout

            row = QWidget(parent)
            row_layout = QGridLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setHorizontalSpacing(4)
            row_layout.setVerticalSpacing(4)
            metadata = field.metadata if isinstance(field.metadata, dict) else {}
            try:
                columns = int(metadata.get("columns") or 0)
            except Exception:
                columns = 0
            if columns <= 0:
                columns = 2 if len(field.choices) > 3 else max(1, len(field.choices))
            for index, (action_id, action_label) in enumerate(field.choices):
                button = QPushButton(action_label, row)
                button.setEnabled(state.enabled and not state.readonly)
                try:
                    button.setMinimumHeight(24)
                except Exception:
                    pass
                if tooltip:
                    button.setToolTip(tooltip)

                def _click(_checked=False, aid=action_id) -> None:
                    event = manager.trigger(aid)
                    if on_action is not None:
                        on_action(event.action_id, event.values)

                button.clicked.connect(_click)
                row_layout.addWidget(button, index // columns, index % columns)
            InspectorPanelQtAdapter._mark_field_editor(row, field.id)
            row.setVisible(state.visible)
            return row

        row = QWidget(parent)
        InspectorPanelQtAdapter._mark_field_editor(row, field.id)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        label = QLabel(field.label, row)
        label.setWordWrap(True)
        try:
            from PySide6.QtWidgets import QSizePolicy
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        except Exception:
            pass
        label.setMinimumWidth(72)
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        if tooltip:
            label.setToolTip(tooltip)
        row_layout.addWidget(label)

        value = manager.value(field.id, field.default)
        if field.kind == "float":
            editor = QDoubleSpinBox(row)
            editor.setRange(float(field.min_value if field.min_value is not None else -1_000_000), float(field.max_value if field.max_value is not None else 1_000_000))
            editor.setSingleStep(float(field.step if field.step is not None else 1.0))
            editor.setValue(float(value))
            editor.valueChanged.connect(lambda new_value, fid=field.id: InspectorPanelQtAdapter._update(manager, fid, new_value, on_change))
        elif field.kind == "int":
            editor = QSpinBox(row)
            editor.setRange(int(field.min_value if field.min_value is not None else -1_000_000), int(field.max_value if field.max_value is not None else 1_000_000))
            editor.setSingleStep(int(field.step if field.step is not None else 1))
            editor.setValue(int(value))
            editor.valueChanged.connect(lambda new_value, fid=field.id: InspectorPanelQtAdapter._update(manager, fid, new_value, on_change))
        elif field.kind == "bool":
            editor = QCheckBox(row)
            editor.setChecked(bool(value))
            editor.stateChanged.connect(lambda _state, fid=field.id, widget=editor: InspectorPanelQtAdapter._update(manager, fid, widget.isChecked(), on_change))
        elif field.kind == "choice":
            editor = QComboBox(row)
            try:
                editor.setMinimumContentsLength(10)
                editor.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            except Exception:
                pass
            for choice_id, choice_label in field.choices:
                editor.addItem(choice_label, choice_id)
            for index in range(editor.count()):
                if editor.itemData(index) == value:
                    editor.setCurrentIndex(index)
                    break
            editor.currentIndexChanged.connect(lambda _index, fid=field.id, widget=editor: InspectorPanelQtAdapter._update(manager, fid, widget.currentData(), on_change))
        elif field.kind == "slider":
            editor = QDoubleSpinBox(row)
            editor.setRange(float(field.min_value if field.min_value is not None else 0.0), float(field.max_value if field.max_value is not None else 1.0))
            editor.setSingleStep(float(field.step if field.step is not None else 0.01))
            editor.setValue(float(value))
            editor.valueChanged.connect(lambda new_value, fid=field.id: InspectorPanelQtAdapter._update(manager, fid, new_value, on_change))
        elif field.kind == "readonly":
            editor = QLabel(str(value), row)
            editor.setWordWrap(True)
            editor.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        elif field.kind == "file":
            editor = QWidget(row)
            file_layout = QHBoxLayout(editor)
            file_layout.setContentsMargins(0, 0, 0, 0)
            file_edit = QLineEdit(str(value), editor)
            file_button = QPushButton("…", editor)
            file_layout.addWidget(file_edit, 1)
            file_layout.addWidget(file_button)
            file_edit.textChanged.connect(lambda new_value, fid=field.id: InspectorPanelQtAdapter._update(manager, fid, new_value, on_change))

            def _browse_file() -> None:
                selected, _filter = QFileDialog.getOpenFileName(editor, field.label, str(manager.value(field.id, "")))
                if selected:
                    file_edit.setText(selected)

            file_button.clicked.connect(_browse_file)
        elif field.kind == "font":
            # Use a native font combo, not a free text field. The value stored in
            # the Creator inspector is the real family selected by Qt, which is
            # also what the relief geometry generator consumes.
            # Architecture guard: font_button = QPushButton("Font", editor)
            editor = QFontComboBox(row)
            current_family = str(value or "").strip()
            if current_family and current_family.lower() not in {"vtk vectortext", "vector text", "vtk"}:
                try:
                    editor.setCurrentFont(QFont(current_family))
                except Exception:
                    pass
            editor.currentFontChanged.connect(lambda font, fid=field.id: InspectorPanelQtAdapter._update(manager, fid, font.family(), on_change))
        else:
            display_value = ", ".join(str(v) for v in value) if field.kind in {"vector2", "vector3"} and isinstance(value, (tuple, list)) else str(value)
            editor = QLineEdit(display_value, row)
            editor.textChanged.connect(lambda new_value, fid=field.id: InspectorPanelQtAdapter._update(manager, fid, new_value, on_change))
        InspectorPanelQtAdapter._mark_field_editor(editor, field.id)
        if field.id == "plan_trace_2d.selection_length":
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                record_selection_length_event(
                    "inspector.qt.field.created",
                    field_id=field.id,
                    field_kind=field.kind,
                    manager_value=manager.value(field.id, field.default),
                    widget_class=type(editor).__name__,
                    widget_text=(editor.text() if hasattr(editor, "text") else None),
                )
            except Exception:
                pass
        if field.kind == "file":
            try:
                for child in editor.findChildren(QLineEdit):
                    InspectorPanelQtAdapter._mark_field_editor(child, field.id)
            except Exception:
                pass
        if tooltip and hasattr(editor, "setToolTip"):
            editor.setToolTip(tooltip)
        editor.setEnabled(state.enabled and not state.readonly)
        if state.readonly and hasattr(editor, "setReadOnly"):
            editor.setReadOnly(True)
        row_layout.addWidget(editor, 1)
        if field.unit:
            unit = QLabel(field.unit, row)
            unit.setMinimumWidth(24)
            try:
                unit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            except Exception:
                pass
            row_layout.addWidget(unit)
        row.setVisible(state.visible)
        return row

    @staticmethod
    def _mark_field_editor(widget: Any, field_id: str) -> None:
        try:
            widget.setProperty("inspector_field_id", str(field_id))
            widget.setObjectName(f"inspector_field_{str(field_id).replace('.', '_')}")
        except Exception:
            pass

    @staticmethod
    def _editor_has_user_focus(widget: Any) -> bool:
        try:
            if bool(widget.hasFocus()):
                return True
        except Exception:
            pass
        try:
            line_edit = widget.lineEdit()
            if bool(line_edit.hasFocus()):
                return True
        except Exception:
            pass
        try:
            focus_widget = widget.focusWidget()
            if focus_widget is not None and bool(focus_widget.hasFocus()):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def sync_widget_values(root: Any, manager: InspectorManager) -> None:
        start = time.perf_counter()
        try:
            return InspectorPanelQtAdapter._sync_widget_values_measured(root, manager)
        finally:
            if _APP_AUDIT is not None:
                try:
                    _APP_AUDIT.record_timing("inspector.sync_widget_values", (time.perf_counter() - start) * 1000.0)
                except Exception:
                    pass

    @staticmethod
    def _sync_widget_values_measured(root: Any, manager: InspectorManager) -> None:
        """Synchronise existing Qt editors with the headless inspector state.

        The live Creator panel must not rebuild its whole widget tree on every
        value change: doing so steals focus and can briefly create top-level Qt
        windows on some platforms.  Instead, layout changes rebuild the panel and
        plain value changes update the existing controls in place.
        """

        try:
            from PySide6.QtCore import QSignalBlocker
            from PySide6.QtWidgets import QAbstractSpinBox, QCheckBox, QComboBox, QFontComboBox, QLabel, QLineEdit, QWidget
        except Exception:
            return

        panel = manager.panel
        if panel is None:
            return
        field_by_id = {field.id: field for field in panel.fields()}
        try:
            widgets = root.findChildren(QWidget)
        except Exception:
            widgets = []
        for widget in widgets:
            try:
                field_id = str(widget.property("inspector_field_id") or "")
            except Exception:
                field_id = ""
            if not field_id or field_id not in field_by_id:
                continue
            field = field_by_id[field_id]
            if field.kind in {"button", "separator", "title", "help"}:
                continue
            value = manager.value(field_id, field.default)
            try:
                state = manager.field_state(field_id)
                widget.setEnabled(state.enabled and not state.readonly)
                widget.setVisible(state.visible)
            except Exception:
                pass
            try:
                blocker = QSignalBlocker(widget)
            except Exception:
                blocker = None
            try:
                user_is_editing = InspectorPanelQtAdapter._editor_has_user_focus(widget)
                if isinstance(widget, QCheckBox):
                    if not user_is_editing:
                        widget.setChecked(bool(value))
                elif isinstance(widget, QFontComboBox):
                    if not user_is_editing:
                        try:
                            from PySide6.QtGui import QFont
                            family = str(value or "").strip()
                            if family and family.lower() not in {"vtk vectortext", "vector text", "vtk"} and widget.currentFont().family() != family:
                                widget.setCurrentFont(QFont(family))
                        except Exception:
                            pass
                elif isinstance(widget, QComboBox):
                    if not user_is_editing:
                        for index in range(widget.count()):
                            if widget.itemData(index) == value:
                                widget.setCurrentIndex(index)
                                break
                elif isinstance(widget, QAbstractSpinBox):
                    # Do not normalise or rewrite the focused spin box while the
                    # user is typing.  Tools may update derived display fields,
                    # errors or visibility on every digit; the active editor must
                    # keep focus and its in-progress text buffer.
                    if not user_is_editing and hasattr(widget, "setValue"):
                        widget.setValue(value)
                elif isinstance(widget, QLineEdit):
                    if not user_is_editing:
                        display_value = ", ".join(str(v) for v in value) if field.kind in {"vector2", "vector3"} and isinstance(value, (tuple, list)) else str(value)
                        if widget.text() != display_value:
                            widget.setText(display_value)
                elif isinstance(widget, QLabel) and field.kind == "readonly":
                    before_text = widget.text()
                    widget.setText(str(value))
                    if field_id == "plan_trace_2d.selection_length":
                        try:
                            from laserprog_studio.diagnostics.plan_trace_selection_length_debug import qt_field_snapshot, record_selection_length_event

                            record_selection_length_event(
                                "inspector.qt.sync_field",
                                field_id=field_id,
                                manager_value=value,
                                before_text=before_text,
                                after_text=widget.text(),
                                after=qt_field_snapshot(root, field_id),
                            )
                        except Exception:
                            pass
            finally:
                del blocker

    @staticmethod
    def _update(manager: InspectorManager, field_id: str, value: Any, on_change: Callable[[str, Any], None] | None) -> None:
        validated = manager.update_value(field_id, value)
        if on_change is not None:
            on_change(field_id, validated)


__all__ = ["InspectorPanelQtAdapter"]

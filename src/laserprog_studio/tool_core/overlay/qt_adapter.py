"""Optional Qt adapter for Tool Core overlay windows.

The core overlay manager remains UI-toolkit independent. This adapter is a thin
bridge used by the current PySide UI to materialize OverlayWindowSpec instances
as small floating child widgets.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

from .manager import OverlayManager
from .placement import (
    OverlayRect,
    avoid_overlay_overlap,
    clamp_overlay_position,
    constrain_overlay_drag_position,
    pointer_inside_overlay_rect,
)
from .specs import OverlayWindowSpec, ToolButtonSpec
from .qt_commit import flush_overlay_edits_for_button
from .qt_layout import command_deck_shell_height_px, metric_bar_shell_height_px, rebuild_overlay_widget, sectioned_toolbar_shell_height_px
from .qt_style import apply_overlay_style, paint_overlay_frame
from .qt_widgets import build_tool_core_overlay_button, build_tool_core_overlay_frame
class QtOverlayAdapter:
    def __init__(self, owner: Any, manager: OverlayManager) -> None:
        self.owner = owner
        self.manager = manager
    def sync(self) -> int:
        try:
            from PySide6.QtCore import Qt, QTimer
            from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout
        except Exception:  # pragma: no cover - optional GUI dependency
            return 0
        adapter = self
        ToolCoreOverlayFrame = build_tool_core_overlay_frame(QFrame, Qt, adapter)
        ToolCoreOverlayButton = build_tool_core_overlay_button(QPushButton)
        parent = getattr(self.owner, "plotter", None) or getattr(self.owner, "centralWidget", lambda: None)() or self.owner
        widgets = getattr(self.owner, "_tool_core_overlay_widgets", None)
        if not isinstance(widgets, dict):
            widgets = {}
            try:
                self.owner._tool_core_overlay_widgets = widgets
            except Exception:
                pass
        valid_ids = set(self.manager.windows.keys())
        for widget_id, widget in list(widgets.items()):
            if widget_id in valid_ids:
                continue
            try:
                widget.hide()
                widget.deleteLater()
            except Exception:
                pass
            widgets.pop(widget_id, None)
        visible = 0
        any_dragging = any(bool(getattr(widget, "_dragging", False)) for widget in widgets.values())
        dragging_widget = None
        for spec in self.manager.windows.values():
            widget = widgets.get(spec.id)
            if widget is None:
                widget = ToolCoreOverlayFrame(parent, spec.id)
                widget.setObjectName("ToolCoreOverlayWindow")
                # Child overlay: keep it a plain QWidget.  FramelessWindowHint on
                # child widgets can make platform geometry handling inconsistent.
                widget.setWindowFlags(Qt.Widget)
                widget.setAttribute(Qt.WA_StyledBackground, True)
                try:
                    widget.setMouseTracking(True)
                except Exception:
                    pass
                widgets[spec.id] = widget
            else:
                try:
                    widget.window_id = spec.id
                except Exception:
                    pass
            if not spec.visible:
                widget.hide()
                continue
            widget.setProperty("overlayKind", spec.overlay_kind)
            widget.setProperty("movable", bool(spec.movable))
            dragging = bool(getattr(widget, "_dragging", False))
            if dragging:
                dragging_widget = widget
            if not dragging:
                self._apply_style(widget, spec)
                signature = self._spec_signature(spec)
                if getattr(widget, "_tool_core_overlay_signature", None) != signature:
                    self._rebuild(widget, spec, QLabel, QLineEdit, ToolCoreOverlayButton, QSizePolicy, QVBoxLayout, QHBoxLayout, QButtonGroup, Qt)
                    try:
                        widget._tool_core_overlay_signature = signature
                    except Exception:
                        pass
                else:
                    # Keep a stable size even when the logical overlay is synced
                    # during hover/drag.  Rebuilding the layout every sync was the
                    # source of the occasional one-line/teleport visual glitch.
                    # Editable overlay values still need to converge in place:
                    # metric bars link fields such as circle radius/diameter and
                    # must not rebuild the focused QLineEdit just to update the
                    # sibling field.
                    self._sync_editable_field_values(widget, spec)
                    self._stabilize_geometry(widget, spec)
                self._place(widget, parent, spec)
                if spec.movable:
                    ax, ay = self._avoid_overlap_pos(widget, spec, int(widget.x()), int(widget.y()))
                    if (int(ax), int(ay)) != (int(widget.x()), int(widget.y())):
                        widget.move(int(ax), int(ay))
                        try:
                            self.manager.set_window_position(spec.id, int(ax), int(ay))
                        except Exception:
                            pass
                if spec.movable and spec.position_px is None:
                    try:
                        self.manager.set_window_position(spec.id, int(widget.x()), int(widget.y()))
                    except Exception:
                        pass
            widget.show()
            if not dragging and not any_dragging:
                widget.raise_()
            visible += 1
        if dragging_widget is not None:
            try:
                dragging_widget.raise_()
            except Exception:
                pass
        return visible

    def clear(self) -> int:
        widgets = getattr(self.owner, "_tool_core_overlay_widgets", {}) or {}
        count = 0
        for widget in list(widgets.values()):
            try:
                widget.hide()
                widget.deleteLater()
                count += 1
            except Exception:
                pass
        try:
            self.owner._tool_core_overlay_widgets = {}
        except Exception:
            pass
        return count

    @staticmethod
    def _spec_signature(spec: OverlayWindowSpec) -> tuple:
        def _field_signature(field: Any) -> tuple:
            # Editable text/number values are synced directly into the existing
            # QLineEdit widgets.  Keeping those values out of the rebuild
            # signature prevents linked metric updates, for example circle
            # radius <-> diameter, from destroying the active editor.
            kind = str(getattr(field, "kind", "") or "")
            enabled = bool(getattr(field, "enabled", True))
            value_signature = None if kind in {"number", "text", "select"} and enabled else getattr(field, "value", None)
            return (
                getattr(field, "id", None),
                getattr(field, "label", None),
                value_signature,
                kind,
                enabled,
                getattr(field, "tooltip", None),
                tuple(getattr(field, "options", ()) or ()),
                bool(getattr(field, "live", False)),
            )

        return (
            spec.id,
            spec.title,
            spec.owner_tool,
            getattr(spec, "accent_color", None),
            spec.overlay_kind,
            int(spec.width_px),
            bool(spec.movable),
            tuple(_field_signature(f) for f in spec.fields),
            tuple((b.id, b.label, b.icon, bool(b.enabled), bool(b.checkable), bool(b.checked), b.group, b.shortcut, b.tooltip, b.style, b.display_label, b.section, b.slot_width_px) for b in spec.buttons),
            tuple((s.id, s.label) for s in getattr(spec, "toolbar_sections", ()) or ()),
        )

    @staticmethod
    def _sync_editable_field_values(widget: Any, spec: OverlayWindowSpec) -> int:
        """Update existing line edits and select controls without rebuilding."""

        try:
            edits = getattr(widget, "_tool_core_overlay_field_edits", {}) or {}
        except Exception:
            edits = {}
        try:
            selects = getattr(widget, "_tool_core_overlay_field_selects", {}) or {}
        except Exception:
            selects = {}
        if not isinstance(edits, dict):
            edits = {}
        if not isinstance(selects, dict):
            selects = {}
        if not edits and not selects:
            return 0
        changed = 0
        try:
            from PySide6.QtCore import QSignalBlocker  # type: ignore
        except Exception:  # pragma: no cover - PySide optional in tests
            QSignalBlocker = None  # type: ignore
        for field in tuple(getattr(spec, "fields", ()) or ()):
            kind = str(getattr(field, "kind", "") or "")
            field_id = str(getattr(field, "id", "") or "")
            desired = str(getattr(field, "value", "") or "")
            if kind in {"number", "text"} and bool(getattr(field, "enabled", True)):
                edit = edits.get(field_id)
                if edit is None:
                    continue
                try:
                    if bool(edit.hasFocus()):
                        continue
                except Exception:
                    pass
                try:
                    current = str(edit.text())
                except Exception:
                    current = ""
                if current == desired:
                    continue
                blocker = None
                if QSignalBlocker is not None:
                    try:
                        blocker = QSignalBlocker(edit)
                    except Exception:
                        blocker = None
                try:
                    edit.setText(desired)
                    changed += 1
                except Exception:
                    pass
                finally:
                    del blocker
                continue
            if kind == "select":
                combo = selects.get(field_id)
                if combo is None:
                    continue
                try:
                    current_data = combo.currentData()
                    current = str(current_data if current_data is not None else combo.currentText())
                except Exception:
                    current = ""
                if current == desired:
                    continue
                try:
                    index = int(combo.findData(desired))
                    if index < 0:
                        index = int(combo.findText(desired))
                except Exception:
                    index = -1
                if index < 0:
                    continue
                blocker = None
                if QSignalBlocker is not None:
                    try:
                        blocker = QSignalBlocker(combo)
                    except Exception:
                        blocker = None
                try:
                    combo.setCurrentIndex(index)
                    changed += 1
                except Exception:
                    pass
                finally:
                    del blocker
        return changed

    def _sync_window_fields_in_place(self, window_id: str) -> int:
        try:
            widgets = getattr(self.owner, "_tool_core_overlay_widgets", {}) or {}
            widget = widgets.get(str(window_id))
            spec = self.manager.window(str(window_id))
        except Exception:
            widget = None
            spec = None
        if widget is None or spec is None:
            return 0
        return self._sync_editable_field_values(widget, spec)

    @staticmethod
    def _apply_style(widget: Any, spec: OverlayWindowSpec) -> None:
        apply_overlay_style(widget, spec)

    def _paint_overlay_frame(self, widget: Any, event: Any) -> None:
        """Paint a transform-style rounded overlay surface behind child widgets."""

        paint_overlay_frame(self, widget, event)

    def _rebuild(
        self,
        widget: Any,
        spec: OverlayWindowSpec,
        QLabel: Any,
        QLineEdit: Any,
        QPushButton: Any,
        QSizePolicy: Any,
        QVBoxLayout: Any,
        QHBoxLayout: Any,
        QButtonGroup: Any,
        Qt: Any | None = None,
    ) -> None:
        rebuild_overlay_widget(
            self,
            widget,
            spec,
            QLabel,
            QLineEdit,
            QPushButton,
            QSizePolicy,
            QVBoxLayout,
            QHBoxLayout,
            QButtonGroup,
            Qt,
        )

    @staticmethod
    def _resolve_button_style(button_spec: ToolButtonSpec) -> str:
        style = str(getattr(button_spec, "style", "auto") or "auto")
        if style != "auto":
            return style
        if button_spec.group and button_spec.checkable:
            return "mode"
        if button_spec.checkable:
            return "toggle"
        if "delete" in button_spec.id.lower() or "remove" in button_spec.id.lower() or "trash" in str(button_spec.icon or "").lower():
            return "danger"
        if button_spec.icon and not button_spec.label:
            return "icon"
        return "secondary"

    @staticmethod
    def _button_label(button_spec: ToolButtonSpec, style: str) -> str:
        label = str(button_spec.label or "")
        icon = str(button_spec.icon or "")
        if style == "icon":
            return icon or label
        return label

    @staticmethod
    def _button_tooltip(button_spec: ToolButtonSpec) -> str | None:
        parts = []
        label = str(getattr(button_spec, "label", "") or "")
        if label:
            parts.append(label)
        if button_spec.tooltip:
            parts.append(str(button_spec.tooltip))
        if button_spec.shortcut:
            parts.append(f"Shortcut: {button_spec.shortcut}")
        return " · ".join(parts) if parts else None

    @staticmethod
    def _minimum_height_for_spec(spec: OverlayWindowSpec) -> int:
        # Do not let Qt collapse a freshly synced overlay into a thin horizontal
        # bar. Keep overlays compact and deterministic. A pure toolbar must never
        # reserve a large empty panel above its buttons; richer palettes still
        # receive enough height for their title, fields and action row.
        kind = str(spec.overlay_kind)
        is_command_deck = any(str(getattr(field, "id", "")) == "plan_trace_2d.command_status" for field in getattr(spec, "fields", ()) or ())
        if kind == "command_deck" or is_command_deck:
            return command_deck_shell_height_px()
        if kind == "metric_bar":
            return metric_bar_shell_height_px()
        if kind == "toolbar":
            title_h = 16 if spec.title else 0
            has_vector_icons = any(bool(getattr(button, "icon", None)) for button in spec.buttons)
            has_badge = any(str(getattr(field, "id", "")).endswith("mode_badge") for field in spec.fields)
            has_sections = bool(getattr(spec, "toolbar_sections", ()) or ())
            editable_fields = [field for field in spec.fields if field.kind in {"number", "text"} and bool(field.enabled)]
            inline_metric = bool(editable_fields) and bool(spec.buttons) and not has_badge and not has_vector_icons
            if inline_metric:
                # Numeric validation overlays are a single compact row.  Keeping
                # the old two-row minimum made them push the main drawing toolbar
                # deep into the viewport and caused label/button overlap.
                return 48
            compact_fields = [field for field in spec.fields if field not in editable_fields and not str(getattr(field, "id", "")).endswith("mode_badge")]
            fields_h = (28 if has_badge else 0) + (28 if editable_fields else 0) + max(0, len(compact_fields)) * 18
            buttons_h = 68 if has_vector_icons and spec.buttons else (32 if spec.buttons else 0)
            rows = int(bool(spec.title)) + int(has_badge) + int(bool(editable_fields)) + len(compact_fields) + int(bool(spec.buttons))
            spacing_h = max(0, rows - 1) * (5 if has_badge else 4)
            natural = 18 + title_h + fields_h + buttons_h + spacing_h
            if has_vector_icons:
                if has_sections:
                    # Sectioned HUD cards are intentionally large enough to fill
                    # the painted toolbar shell.  This prevents the black outer
                    # surface from looking like unused padding around tiny icons.
                    return max(sectioned_toolbar_shell_height_px() + 4, natural)
                return max(108 if has_badge else 82, natural)
            if editable_fields:
                return max(64, natural)
            return max(42, natural)
        title_h = 24 if spec.title else 0
        fields_h = max(0, len(spec.fields)) * 24
        buttons_h = 42 if spec.buttons else 0
        spacing_h = max(0, (1 if spec.title else 0) + len(spec.fields) + (1 if spec.buttons else 0) - 1) * 7
        return max(48, 16 + title_h + fields_h + buttons_h + spacing_h)

    def _stabilize_geometry(self, widget: Any, spec: OverlayWindowSpec) -> None:
        width = max(140, int(spec.width_px))
        try:
            layout = widget.layout()
            if layout is not None:
                layout.activate()
        except Exception:
            pass
        try:
            hint_h = int(widget.sizeHint().height())
        except Exception:
            hint_h = 0
        height = max(self._minimum_height_for_spec(spec), hint_h)
        try:
            widget.setMinimumWidth(width)
            widget.setMaximumWidth(width)
            widget.setFixedWidth(width)
            widget.setMinimumHeight(height)
            widget.setMaximumHeight(height)
            widget.resize(width, height)
        except Exception:
            pass

    def _close(self, window_id: str, widget: Any) -> None:
        self.manager.hide_window(window_id)
        widget.hide()

    def _overlay_field_edited(self, window_id: str, field_id: str, value: str) -> None:
        """Dispatch opt-in live edits without forcing a Qt rebuild.

        Only fields whose declarative spec has ``live=True`` are wired to this
        method by the layout builder.  The active QLineEdit must stay alive and
        keep its raw in-progress text, but the tool state and live preview should
        already see the new value.
        """

        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event

            record_qt_overlay_edit_event("adapter.field_edited.begin", adapter=self, window_id=window_id, field_id=field_id, value=value)
        except Exception:
            pass
        try:
            self.manager.update_field(str(window_id), str(field_id), str(value))
        except Exception:
            pass
        consumed = self._notify_active_tool_overlay_field(window_id, field_id, value)
        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event

            record_qt_overlay_edit_event("adapter.field_edited.end", adapter=self, window_id=window_id, field_id=field_id, value=value, extra={"consumed": bool(consumed)})
        except Exception:
            pass

    def _overlay_field_committed(self, window_id: str, field_id: str, value: str) -> None:
        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event

            record_qt_overlay_edit_event("adapter.field_committed.begin", adapter=self, window_id=window_id, field_id=field_id, value=value)
        except Exception:
            pass
        try:
            self.manager.update_field(str(window_id), str(field_id), str(value))
        except Exception:
            pass
        consumed = self._notify_active_tool_overlay_field(window_id, field_id, value)
        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event

            record_qt_overlay_edit_event("adapter.field_committed.end", adapter=self, window_id=window_id, field_id=field_id, value=value, extra={"consumed": bool(consumed)})
        except Exception:
            pass
        if consumed:
            # Tool-owned editable overlays such as Plan Tracer metric bars keep
            # the live QLineEdit widget stable until the pending button click is
            # delivered.  Re-syncing immediately on focus-out can destroy the
            # Validate button under the mouse, which makes the first click only
            # commit text and the second click perform the actual validation.
            # Still update sibling QLineEdits in place so linked fields such as
            # radius/diameter do not keep stale values that would be flushed on
            # the next Validate click.
            self._sync_window_fields_in_place(str(window_id))
            return
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self.sync)
        except Exception:
            try:
                self.sync()
            except Exception:
                pass

    def _overlay_button_clicked(self, button_id: str) -> None:
        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event

            record_qt_overlay_edit_event("adapter.button_clicked.begin", adapter=self, button_id=button_id)
        except Exception:
            pass
        try:
            changed = self.manager.toggle_button(button_id)
        except Exception:
            changed = False
        if not changed:
            try:
                from .qt_edit_diagnostics import record_qt_overlay_edit_event

                record_qt_overlay_edit_event("adapter.button_clicked.ignored", adapter=self, button_id=button_id, extra={"changed": False})
            except Exception:
                pass
            return
        flushed = flush_overlay_edits_for_button(self, button_id)
        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event

            record_qt_overlay_edit_event("adapter.button_clicked.after_flush", adapter=self, button_id=button_id, extra={"flushed": int(flushed)})
        except Exception:
            pass
        self._notify_active_tool_overlay_button(button_id)
        try:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self.sync)
        except Exception:
            try:
                self.sync()
            except Exception:
                pass

    def _notify_active_tool_overlay_button(self, button_id: str) -> None:
        """Notify the active Studio tool and diagnose swallowed callback errors.

        Qt must still protect the application from a tool exception, but when
        preference diagnostics are enabled we record every dispatch boundary so
        a button can never appear inert without leaving evidence.
        """

        window_id = str(button_id).rsplit(".action.", 1)[0] if ".action." in str(button_id) else None
        try:
            from .qt_edit_diagnostics import record_qt_overlay_edit_event
            record_qt_overlay_edit_event(
                "adapter.notify_button.start",
                adapter=self,
                window_id=window_id,
                button_id=str(button_id),
            )
        except Exception:
            pass
        try:
            owner = self.owner
            tool_id = getattr(owner, "active_tool", None)
            if not tool_id:
                try:
                    from .qt_edit_diagnostics import record_qt_overlay_edit_event
                    record_qt_overlay_edit_event(
                        "adapter.notify_button.no_active_tool", adapter=self,
                        window_id=window_id, button_id=str(button_id),
                    )
                except Exception:
                    pass
                return
            from laserprog_studio.tooling.registry import get_studio_tool

            tool = get_studio_tool(str(tool_id))
            callback = getattr(tool, "on_overlay_button_clicked", None)
            if not callable(callback):
                try:
                    from .qt_edit_diagnostics import record_qt_overlay_edit_event
                    record_qt_overlay_edit_event(
                        "adapter.notify_button.no_callback", adapter=self,
                        window_id=window_id, button_id=str(button_id),
                        extra={"tool_id": str(tool_id)},
                    )
                except Exception:
                    pass
                return
            context = getattr(owner, "context", None)
            if context is None:
                context = getattr(owner, "app_context", None)
            if context is None:
                try:
                    from .qt_edit_diagnostics import record_qt_overlay_edit_event
                    record_qt_overlay_edit_event(
                        "adapter.notify_button.no_context", adapter=self,
                        window_id=window_id, button_id=str(button_id),
                        extra={"tool_id": str(tool_id)},
                    )
                except Exception:
                    pass
                return
            callback(str(button_id), context)
            try:
                from .qt_edit_diagnostics import record_qt_overlay_edit_event
                record_qt_overlay_edit_event(
                    "adapter.notify_button.end", adapter=self,
                    window_id=window_id, button_id=str(button_id),
                    extra={"tool_id": str(tool_id), "callback": type(tool).__name__},
                )
            except Exception:
                pass
        except Exception as exc:
            try:
                from .qt_edit_diagnostics import record_qt_overlay_edit_event
                record_qt_overlay_edit_event(
                    "adapter.notify_button.exception", adapter=self,
                    window_id=window_id, button_id=str(button_id),
                    extra={"error_type": type(exc).__name__, "error": repr(exc)},
                )
            except Exception:
                pass

    def _notify_active_tool_overlay_field(self, window_id: str, field_id: str, value: str) -> bool:
        """Notify the active Studio tool that an editable overlay field committed.

        Returns ``True`` when the tool consumed the edit and wants to keep the
        current Qt widget alive.  That lets validation buttons receive the same
        physical click that caused QLineEdit.focusOut/editingFinished.
        """

        try:
            owner = self.owner
            tool_id = getattr(owner, "active_tool", None)
            if not tool_id:
                return False
            from laserprog_studio.tooling.registry import get_studio_tool

            tool = get_studio_tool(str(tool_id))
            callback = getattr(tool, "on_overlay_field_changed", None)
            if not callable(callback):
                try:
                    from .qt_edit_diagnostics import record_qt_overlay_edit_event

                    record_qt_overlay_edit_event("adapter.notify_field.no_callback", adapter=self, window_id=window_id, field_id=field_id, value=value, extra={"tool_id": str(tool_id)})
                except Exception:
                    pass
                return False
            context = getattr(owner, "context", None)
            if context is None:
                context = getattr(owner, "app_context", None)
            if context is None:
                try:
                    from .qt_edit_diagnostics import record_qt_overlay_edit_event

                    record_qt_overlay_edit_event("adapter.notify_field.no_context", adapter=self, window_id=window_id, field_id=field_id, value=value, extra={"tool_id": str(tool_id)})
                except Exception:
                    pass
                return False
            consumed = bool(callback(str(window_id), str(field_id), str(value), context))
            try:
                from .qt_edit_diagnostics import record_qt_overlay_edit_event

                record_qt_overlay_edit_event("adapter.notify_field.result", adapter=self, window_id=window_id, field_id=field_id, value=value, extra={"tool_id": str(tool_id), "consumed": consumed})
            except Exception:
                pass
            return consumed
        except Exception as exc:
            try:
                from .qt_edit_diagnostics import record_qt_overlay_edit_event

                record_qt_overlay_edit_event("adapter.notify_field.exception", adapter=self, window_id=window_id, field_id=field_id, value=value, extra={"error": repr(exc)})
            except Exception:
                pass
            return False

    @staticmethod
    def _place(widget: Any, parent: Any, spec: OverlayWindowSpec) -> None:
        width = int(getattr(parent, "width", lambda: 900)())
        height = int(getattr(parent, "height", lambda: 600)())
        margin = 12
        if spec.position_px is not None:
            x, y = int(spec.position_px[0]), int(spec.position_px[1])
        elif spec.anchor == "viewport_top_left":
            x, y = margin, margin
        elif spec.anchor == "viewport_top_center":
            x = max(margin, (width - widget.width()) // 2) + int(spec.cursor_offset_px[0])
            y = margin + int(spec.cursor_offset_px[1])
        elif spec.anchor == "center":
            x, y = max(margin, (width - widget.width()) // 2), max(margin, (height - widget.height()) // 2)
        elif spec.anchor == "viewport_bottom_center":
            x, y = max(margin, (width - widget.width()) // 2), max(margin, height - widget.height() - 24)
        elif spec.anchor == "cursor":
            x, y = margin + int(spec.cursor_offset_px[0]), margin + int(spec.cursor_offset_px[1])
        else:
            x = max(margin, width - widget.width() - margin) + int(spec.cursor_offset_px[0])
            y = margin + int(spec.cursor_offset_px[1])
        if spec.clamp_to_viewport:
            x = max(margin, min(int(x), max(margin, width - widget.width() - margin)))
            y = max(margin, min(int(y), max(margin, height - widget.height() - margin)))
        widget.move(int(x), int(y))

    @staticmethod
    def _event_global_pos(event: Any) -> Any:
        try:
            if hasattr(event, "globalPosition"):
                return event.globalPosition().toPoint()
        except Exception:
            pass
        try:
            if hasattr(event, "globalPos"):
                return event.globalPos()
        except Exception:
            pass
        try:
            return event.screenPos().toPoint()
        except Exception:
            return None

    def _press_hits_visible_frame(self, widget: Any, event: Any, spec: OverlayWindowSpec) -> bool:
        local_pos = self._event_local_pos(event)
        if local_pos is None:
            return True
        try:
            px, py = int(local_pos.x()), int(local_pos.y())
        except Exception:
            return True
        try:
            visible_w = max(1, min(int(widget.width()), max(140, int(spec.width_px))))
        except Exception:
            visible_w = int(spec.width_px)
        try:
            visible_h = max(1, min(int(widget.height()), max(self._minimum_height_for_spec(spec), int(widget.sizeHint().height()))))
        except Exception:
            try:
                visible_h = int(widget.height())
            except Exception:
                visible_h = 10_000
        return 0 <= px < int(visible_w) and 0 <= py < int(visible_h)

    @staticmethod
    def _event_local_pos(event: Any) -> Any:
        try:
            if hasattr(event, "position"):
                return event.position().toPoint()
        except Exception:
            pass
        try:
            if hasattr(event, "pos"):
                return event.pos()
        except Exception:
            return None
        return None

    @staticmethod
    def _clamp_pos(parent: Any, widget: Any, x: int, y: int) -> tuple[int, int]:
        margin = 12
        try:
            width = int(parent.width())
            height = int(parent.height())
            w = int(widget.width())
            h = int(widget.height())
        except Exception:
            return int(x), int(y)
        max_x = max(margin, width - w - margin)
        max_y = max(margin, height - h - margin)
        return max(margin, min(int(x), max_x)), max(margin, min(int(y), max_y))


    def _constrain_live_drag_pos(self, widget: Any, spec: OverlayWindowSpec | None, x: int, y: int) -> tuple[int, int]:
        """Cheap hot-path constraint for live draggable overlays.

        Initial/sync placement may use the more expensive no-overlap solver.
        Mouse moves during drag behave like hard walls: no overlap, no
        solver-induced teleport, and no hidden payback distance after a blocked
        movement.
        """
        if spec is None or not spec.movable:
            return int(x), int(y)
        try:
            parent = widget.parentWidget()
            viewport_size = (int(parent.width()), int(parent.height()))
            size = (int(widget.width()), int(widget.height()))
        except Exception:
            return int(x), int(y)
        if int(size[0]) <= 0 or int(size[1]) <= 0:
            return int(x), int(y)
        if not spec.clamp_to_viewport:
            viewport_x, viewport_y = int(x), int(y)
        else:
            viewport_x, viewport_y = clamp_overlay_position(int(x), int(y), size, viewport_size, margin=12)
        blockers = self._overlay_blocker_rects(widget)
        if not blockers:
            return int(viewport_x), int(viewport_y)
        return constrain_overlay_drag_position(
            int(viewport_x),
            int(viewport_y),
            int(widget.x()),
            int(widget.y()),
            size,
            blockers,
            viewport_size,
            margin=12,
            gap=8,
        )

    def _overlay_blocker_rects(self, widget: Any) -> list[OverlayRect]:
        blockers: list[OverlayRect] = []
        widgets = getattr(self.owner, "_tool_core_overlay_widgets", {}) or {}
        for other_id, other in widgets.items():
            if other is widget:
                continue
            try:
                other_spec = self.manager.window(str(other_id))
                if other_spec is not None and not other_spec.visible:
                    continue
                if not other.isVisible():
                    continue
                blockers.append(OverlayRect(int(other.x()), int(other.y()), int(other.width()), int(other.height())))
            except Exception:
                continue
        return blockers

    @staticmethod
    def _pointer_offset_px(widget: Any, global_pos: Any) -> tuple[int, int] | None:
        try:
            top_left = widget.mapToGlobal(widget.rect().topLeft())
            return int(global_pos.x()) - int(top_left.x()), int(global_pos.y()) - int(top_left.y())
        except Exception:
            return None

    @staticmethod
    def _pointer_inside_widget_global_rect(widget: Any, global_pos: Any) -> bool:
        """Return whether the pointer is still inside the real overlay frame.

        During a constrained drag the overlay may stop against a wall or another
        overlay while Qt still routes mouse moves to the pressed widget.  The
        runtime must not keep dragging with a stale pointer/anchor offset once
        the pointer has left the visible overlay rectangle.
        """
        try:
            top_left = widget.mapToGlobal(widget.rect().topLeft())
            rect = OverlayRect(int(top_left.x()), int(top_left.y()), int(widget.width()), int(widget.height()))
            return pointer_inside_overlay_rect(int(global_pos.x()), int(global_pos.y()), rect)
        except Exception:
            return True

    def _finish_drag(self, widget: Any, *, commit: bool) -> None:
        was_dragging = bool(getattr(widget, "_dragging", False))
        if commit:
            try:
                self.manager.set_window_position(str(widget.window_id), int(widget.x()), int(widget.y()))
            except Exception:
                pass
        try:
            widget._tool_core_overlay_pending_pos = None
        except Exception:
            pass
        try:
            widget._dragging = False
        except Exception:
            pass
        try:
            widget.setProperty("overlayDragging", False)
        except Exception:
            pass
        try:
            widget._drag_start_global = None
            widget._drag_start_pos = None
            widget._drag_pointer_offset_px = None
            widget._drag_was_constrained = False
        except Exception:
            pass
        try:
            widget.releaseMouse()
        except Exception:
            pass
        try:
            widget.unsetCursor()
        except Exception:
            pass
        if was_dragging:
            self._finalize_drag_redraw(widget)

    def _remember_drag_dirty(self, widget: Any, *rects: Any) -> None:
        """Accumulate the dirty region touched by a live overlay drag.

        The move hot path deliberately avoids parent repainting to keep drag
        smooth.  The accumulated union is used once on release/cancel to clean
        translucent-widget traces over the OpenGL viewport.
        """
        try:
            current = getattr(widget, "_tool_core_overlay_drag_dirty_rect", None)
            for rect in rects:
                if rect is None:
                    continue
                current = rect if current is None else current.united(rect)
            widget._tool_core_overlay_drag_dirty_rect = current
        except Exception:
            pass

    def _finalize_drag_redraw(self, widget: Any) -> None:
        """Cleanly redraw an overlay after the fast-path drag ends.

        During drag the adapter only calls QWidget.move(...) and avoids parent
        repaint work.  With semi-transparent child widgets over a VTK/OpenGL
        viewport, the old composite can remain visible until the backing widget
        is refreshed.  Release/cancel is the safe place to do one bounded redraw:
        temporarily expose the dirty union, repaint the parent/backing viewport,
        then repaint the overlay itself.
        """
        if bool(getattr(widget, "_tool_core_overlay_redrawing", False)):
            return
        dirty = None
        try:
            dirty = getattr(widget, "_tool_core_overlay_drag_dirty_rect", None)
            if dirty is None:
                dirty = widget.geometry()
            else:
                dirty = dirty.united(widget.geometry())
            dirty = dirty.adjusted(-12, -12, 12, 12)
        except Exception:
            dirty = None
        try:
            widget._tool_core_overlay_drag_dirty_rect = None
        except Exception:
            pass
        try:
            widget._tool_core_overlay_redrawing = True
        except Exception:
            pass
        try:
            parent = widget.parentWidget()
        except Exception:
            parent = None
        try:
            was_visible = bool(widget.isVisible())
        except Exception:
            was_visible = False
        try:
            if was_visible:
                widget.hide()
            self._invalidate_overlay_backing(parent, dirty)
            if was_visible:
                widget.show()
                widget.raise_()
            try:
                widget.update()
            except Exception:
                pass
            try:
                widget.repaint()
            except Exception:
                pass
            self._schedule_overlay_backing_cleanup(widget, parent, dirty)
        finally:
            try:
                widget._tool_core_overlay_redrawing = False
            except Exception:
                pass

    @staticmethod
    def _invalidate_overlay_backing(parent: Any, dirty: Any) -> None:
        if parent is None:
            return
        try:
            if dirty is not None:
                parent.update(dirty)
            else:
                parent.update()
        except TypeError:
            try:
                parent.update()
            except Exception:
                pass
        except Exception:
            pass
        try:
            if dirty is not None:
                parent.repaint(dirty)
            else:
                parent.repaint()
        except TypeError:
            try:
                parent.repaint()
            except Exception:
                pass
        except Exception:
            pass

    def _schedule_overlay_backing_cleanup(self, widget: Any, parent: Any, dirty: Any) -> None:
        """Schedule one trailing update after Qt processes the release event."""
        if parent is None:
            return
        try:
            from PySide6.QtCore import QTimer
        except Exception:
            return

        def _later() -> None:
            try:
                self._invalidate_overlay_backing(parent, dirty)
            except Exception:
                pass
            try:
                if widget is not None and widget.isVisible():
                    widget.update()
            except Exception:
                pass

        try:
            QTimer.singleShot(0, _later)
        except Exception:
            pass

    def _cancel_drag(self, widget: Any, global_pos: Any, note: str) -> None:
        """Cancel a constrained overlay drag without moving or warping the cursor."""
        try:
            self._finish_drag(widget, commit=True)
            widget._drag_cancelled = True
        except Exception:
            pass
        try:
            self._record_drag_sample(widget, "cancel", global_pos, note, force=True)
        except Exception:
            pass

    def _avoid_overlap_pos(self, widget: Any, spec: OverlayWindowSpec | None, x: int, y: int) -> tuple[int, int]:
        """Keep movable overlays from crossing each other.

        Qt child widgets are rectangular and sorted in Z-order; translucent,
        rounded, styled child widgets can leave expensive exposed-region repaint
        work when they cover each other.  The Creator overlay runtime therefore
        uses a native no-overlap policy for draggable overlays.  Tool authors do
        not implement this policy locally.
        """
        if spec is None or not spec.movable:
            return int(x), int(y)
        try:
            parent = widget.parentWidget()
            viewport_size = (int(parent.width()), int(parent.height()))
            size = (int(widget.width()), int(widget.height()))
        except Exception:
            return int(x), int(y)
        if int(size[0]) <= 0 or int(size[1]) <= 0:
            return int(x), int(y)
        blockers = self._overlay_blocker_rects(widget)
        return avoid_overlay_overlap(int(x), int(y), size, blockers, viewport_size, margin=12, gap=8)

    def _record_drag_sample(self, widget: Any, event_name: str, global_pos: Any, note: str = "", *, force: bool = False) -> None:
        try:
            if event_name == "move" and not force:
                now = perf_counter()
                last = float(getattr(widget, "_last_drag_record_t", 0.0) or 0.0)
                # Diagnostics are useful, but recording every mouse event was on
                # the overlay hot path.  Sample moves at about 25 Hz while still
                # always recording press/release.
                if now - last < 0.040:
                    return
                widget._last_drag_record_t = now
            spec = self.manager.window(str(widget.window_id))
            spec_pos = None if spec is None else spec.position_px
            self.manager.drag_diagnostics.record(
                event_name,
                str(widget.window_id),
                pointer_global_px=(int(global_pos.x()), int(global_pos.y())),
                widget_pos_px=(int(widget.x()), int(widget.y())),
                spec_pos_px=spec_pos,
                size_px=(int(widget.width()), int(widget.height())),
                note=note,
            )
        except Exception:
            pass


def sync_qt_overlay_windows(owner: Any, manager: OverlayManager) -> int:
    return QtOverlayAdapter(owner, manager).sync()

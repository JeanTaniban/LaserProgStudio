# -*- coding: utf-8 -*-
"""Host for creator-api declarative panels in the right Tool inspector."""
from __future__ import annotations

from typing import Any, Callable

from .inspector_panel_adapter import InspectorPanelQtAdapter


class DeclarativeToolPanelHost:
    """Render ``ctx.inspector`` into the existing right Tool area."""

    def __init__(self, ctx: Any, *, parent: Any = None) -> None:
        self.ctx = ctx
        self.parent = parent
        self._last_revision: int | None = None
        self._widget: Any | None = None

    @property
    def revision(self) -> int:
        manager = getattr(self.ctx, "inspector", None)
        return int(getattr(manager, "layout_revision", getattr(manager, "revision", -1)))

    def needs_rebuild(self) -> bool:
        return self._widget is None or self._last_revision != self.revision

    def widget(
        self,
        *,
        on_change: Callable[[str, Any], None] | None = None,
        on_action: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> Any:
        if self.needs_rebuild():
            self._widget = InspectorPanelQtAdapter.create_widget(
                self.ctx.inspector,
                parent=self.parent,
                on_change=on_change,
                on_action=on_action,
            )
            self._last_revision = self.revision
        return self._widget

    def rebuild(self) -> Any:
        self._last_revision = None
        return self.widget()


class LiveDeclarativeToolPanelWidget:
    """Qt widget that keeps a declarative creator panel in sync with revisions.

    Historical panels are static widgets built once in a ``QStackedWidget``.
    Creator tools are different: they set ``ctx.inspector`` when the tool opens,
    and field visibility/report values can change while the tool is active. This
    wrapper rebuilds only its child content when the inspector revision changes.
    """

    def __new__(cls, ctx_getter: Callable[[], Any], *, parent: Any = None) -> Any:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

        class _LivePanel(QWidget):
            def __init__(self) -> None:
                super().__init__(parent)
                self._last_manager_id: int | None = None
                self._last_layout_revision: int | None = None
                self._last_value_revision: int | None = None
                self._last_state_revision: int | None = None
                self._child: Any | None = None
                self._pending_auto_preview_field: str | None = None
                self._subscribed_manager: Any | None = None
                self._manager_listener_token: int | None = None
                self._refresh_queued = False
                self._auto_preview_timer = QTimer(self)
                self._auto_preview_timer.setSingleShot(True)
                self._auto_preview_timer.timeout.connect(self._run_auto_preview)
                self._layout = QVBoxLayout(self)
                self._layout.setContentsMargins(0, 0, 0, 0)
                self._layout.setSpacing(0)
                self.refresh()

            def _ctx(self) -> Any:
                try:
                    return ctx_getter()
                except Exception:
                    return None

            def _subscribe_to_manager(self, manager: Any | None) -> None:
                if manager is self._subscribed_manager:
                    return
                previous = self._subscribed_manager
                previous_token = self._manager_listener_token
                self._subscribed_manager = None
                self._manager_listener_token = None
                if previous is not None and previous_token is not None:
                    try:
                        previous.unsubscribe_changes(previous_token)
                    except Exception:
                        pass
                subscribe = getattr(manager, "subscribe_changes", None) if manager is not None else None
                if callable(subscribe):
                    try:
                        self._manager_listener_token = int(subscribe(self._on_manager_changed))
                        self._subscribed_manager = manager
                    except Exception:
                        self._manager_listener_token = None
                        self._subscribed_manager = None

            def _on_manager_changed(self) -> None:
                if self._refresh_queued:
                    return
                self._refresh_queued = True
                QTimer.singleShot(0, self._consume_manager_refresh)

            def _consume_manager_refresh(self) -> None:
                self._refresh_queued = False
                try:
                    if self.isVisible():
                        self.refresh()
                except Exception:
                    pass

            def showEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
                super().showEvent(event)
                self.refresh()

            def hideEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
                try:
                    self._auto_preview_timer.stop()
                    self._pending_auto_preview_field = None
                except Exception:
                    pass
                super().hideEvent(event)

            def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
                self._subscribe_to_manager(None)
                super().closeEvent(event)

            def _dispose_child(self) -> None:
                if self._child is None:
                    return
                # Never detach a visible QWidget before deletion. On some Qt
                # platforms that briefly turns the child into a top-level mini
                # window before ``deleteLater`` runs.
                try:
                    self._child.hide()
                except Exception:
                    pass
                self._layout.removeWidget(self._child)
                self._child.deleteLater()
                self._child = None

            def refresh(self) -> None:
                ctx = self._ctx()
                manager = getattr(ctx, "inspector", None) if ctx is not None else None
                self._subscribe_to_manager(manager)
                manager_id = id(manager) if manager is not None else None
                layout_revision = int(getattr(manager, "layout_revision", getattr(manager, "revision", -1)))
                value_revision = int(getattr(manager, "value_revision", getattr(manager, "revision", -1)))
                state_revision = int(getattr(manager, "state_revision", getattr(manager, "revision", -1)))
                is_plan_trace_panel = bool(
                    manager is not None
                    and str(getattr(getattr(manager, "panel", None), "owner_tool", "") or "") == "plan_trace"
                )
                if is_plan_trace_panel:
                    try:
                        from laserprog_studio.diagnostics.plan_trace_selection_length_debug import qt_field_snapshot, record_selection_length_event

                        record_selection_length_event(
                            "inspector.qt.refresh.begin",
                            ctx=ctx,
                            include_inspector=True,
                            manager_id=manager_id,
                            current_layout_revision=layout_revision,
                            current_value_revision=value_revision,
                            current_state_revision=state_revision,
                            last_manager_id=self._last_manager_id,
                            last_layout_revision=self._last_layout_revision,
                            last_value_revision=self._last_value_revision,
                            last_state_revision=self._last_state_revision,
                            child_exists=self._child is not None,
                            qt_field=qt_field_snapshot(self._child),
                        )
                    except Exception:
                        pass
                needs_rebuild = (
                    self._child is None
                    or self._last_manager_id != manager_id
                    or self._last_layout_revision != layout_revision
                )
                if needs_rebuild:
                    self._dispose_child()
                    if ctx is None or getattr(manager, "panel", None) is None:
                        label = QLabel("No creator tool context is active.", self)
                        label.setWordWrap(True)
                        self._child = label
                    else:
                        host = DeclarativeToolPanelHost(ctx, parent=self)
                        self._child = host.widget(on_change=self._on_child_value_changed, on_action=lambda *_args: QTimer.singleShot(0, self.refresh))
                    self._layout.addWidget(self._child)
                    self._last_manager_id = manager_id
                    self._last_layout_revision = layout_revision
                    self._last_value_revision = value_revision
                    self._last_state_revision = state_revision
                    if is_plan_trace_panel:
                        try:
                            from laserprog_studio.diagnostics.plan_trace_selection_length_debug import qt_field_snapshot, record_selection_length_event

                            record_selection_length_event(
                                "inspector.qt.refresh.end",
                                ctx=ctx,
                                include_inspector=True,
                                path="rebuild",
                                qt_field=qt_field_snapshot(self._child),
                                stored_value_revision=self._last_value_revision,
                            )
                        except Exception:
                            pass
                    return
                if (
                    (self._last_value_revision != value_revision or self._last_state_revision != state_revision)
                    and manager is not None
                    and self._child is not None
                ):
                    InspectorPanelQtAdapter.sync_widget_values(self._child, manager)
                    self._last_value_revision = value_revision
                    self._last_state_revision = state_revision
                    if is_plan_trace_panel:
                        try:
                            from laserprog_studio.diagnostics.plan_trace_selection_length_debug import qt_field_snapshot, record_selection_length_event

                            record_selection_length_event(
                                "inspector.qt.refresh.end",
                                ctx=ctx,
                                include_inspector=True,
                                path="sync_values",
                                qt_field=qt_field_snapshot(self._child),
                                stored_value_revision=self._last_value_revision,
                            )
                        except Exception:
                            pass
                elif is_plan_trace_panel:
                    try:
                        from laserprog_studio.diagnostics.plan_trace_selection_length_debug import qt_field_snapshot, record_selection_length_event

                        record_selection_length_event(
                            "inspector.qt.refresh.end",
                            ctx=ctx,
                            include_inspector=True,
                            path="no_change",
                            qt_field=qt_field_snapshot(self._child),
                            stored_value_revision=self._last_value_revision,
                        )
                    except Exception:
                        pass

            def _on_child_value_changed(self, field_id: str, _value: Any) -> None:
                # ``InspectorManager.update_value`` already emits a presentation
                # change. Route through the same coalescer so a user edit does
                # not schedule two identical Qt refreshes.
                self._on_manager_changed()
                self._schedule_auto_preview(field_id)

            def _schedule_auto_preview(self, field_id: str) -> None:
                ctx = self._ctx()
                manager = getattr(ctx, "inspector", None) if ctx is not None else None
                panel = getattr(manager, "panel", None)
                config = getattr(panel, "auto_preview", None)
                if config is None or not getattr(config, "enabled", False):
                    return
                try:
                    if not config.accepts_field(field_id):
                        return
                except Exception:
                    return
                action_id = str(getattr(config, "action_id", "preview") or "preview")
                try:
                    field_ids = set(panel.field_ids())
                    action_ids = set(field_ids)
                    for field in panel.fields():
                        if getattr(field, "kind", "") == "button_row":
                            action_ids.update(choice_id for choice_id, _label in field.choices)
                    if action_id not in action_ids:
                        return
                except Exception:
                    return
                self._pending_auto_preview_field = str(field_id)
                self._auto_preview_timer.start(max(0, int(getattr(config, "debounce_ms", 250))))

            def _run_auto_preview(self) -> None:
                ctx = self._ctx()
                manager = getattr(ctx, "inspector", None) if ctx is not None else None
                panel = getattr(manager, "panel", None)
                config = getattr(panel, "auto_preview", None)
                if manager is None or panel is None or config is None or not getattr(config, "enabled", False):
                    return
                action_id = str(getattr(config, "action_id", "preview") or "preview")
                try:
                    manager.trigger(action_id)
                except Exception:
                    return
                finally:
                    self._pending_auto_preview_field = None
                QTimer.singleShot(0, self.refresh)

        return _LivePanel()


__all__ = ["DeclarativeToolPanelHost", "LiveDeclarativeToolPanelWidget"]

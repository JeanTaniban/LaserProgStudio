# -*- coding: utf-8 -*-
"""Commit helpers for editable Qt overlay widgets."""

from __future__ import annotations

from typing import Any


def button_should_flush_overlay_edits(button_id: str) -> bool:
    text = str(button_id).lower()
    return any(token in text for token in ("validate", "apply", "confirm", "save", "ok"))


def window_id_for_button(manager: Any, button_id: str) -> str | None:
    target = str(button_id)
    try:
        for window in manager.windows.values():
            for button in getattr(window, "buttons", ()) or ():
                if str(getattr(button, "id", "")) == target:
                    return str(window.id)
    except Exception:
        return None
    return None


def flush_overlay_edits_for_button(adapter: Any, button_id: str) -> int:
    """Commit live QLineEdit values before Validate/Apply callbacks run."""

    try:
        from .qt_edit_diagnostics import record_qt_overlay_edit_event
    except Exception:  # pragma: no cover - diagnostics must never be required
        record_qt_overlay_edit_event = None  # type: ignore[assignment]

    if not button_should_flush_overlay_edits(button_id):
        if callable(record_qt_overlay_edit_event):
            record_qt_overlay_edit_event("commit.flush.skipped_token", adapter=adapter, button_id=button_id)
        return 0
    window_id = window_id_for_button(adapter.manager, button_id)
    if not window_id:
        if callable(record_qt_overlay_edit_event):
            record_qt_overlay_edit_event("commit.flush.no_window", adapter=adapter, button_id=button_id)
        return 0
    widgets = getattr(adapter.owner, "_tool_core_overlay_widgets", None) or {}
    widget = widgets.get(window_id) if isinstance(widgets, dict) else None
    edits = getattr(widget, "_tool_core_overlay_field_edits", None) if widget is not None else None
    if not isinstance(edits, dict) or not edits:
        if callable(record_qt_overlay_edit_event):
            record_qt_overlay_edit_event("commit.flush.no_edits", adapter=adapter, window_id=window_id, button_id=button_id)
        return 0
    window = adapter.manager.window(window_id)
    current = {str(field.id): str(field.value) for field in getattr(window, "fields", ()) or ()}
    captured: list[tuple[str, str]] = []
    for field_id, edit in list(edits.items()):
        try:
            value = str(edit.text())
        except Exception:
            continue
        field_key = str(field_id)
        if current.get(field_key) != value:
            captured.append((field_key, value))
    if callable(record_qt_overlay_edit_event):
        record_qt_overlay_edit_event(
            "commit.flush.captured",
            adapter=adapter,
            window_id=window_id,
            button_id=button_id,
            extra={"captured": list(captured), "current": dict(current)},
        )
    flushed = 0
    for field_key, value in captured:
        try:
            adapter.manager.update_field(window_id, field_key, value)
        except Exception:
            pass
        consumed = adapter._notify_active_tool_overlay_field(window_id, field_key, value)
        if callable(record_qt_overlay_edit_event):
            record_qt_overlay_edit_event(
                "commit.flush.notify",
                adapter=adapter,
                window_id=window_id,
                field_id=field_key,
                value=value,
                button_id=button_id,
                extra={"consumed": bool(consumed)},
            )
        flushed += 1
    return flushed


__all__ = ["flush_overlay_edits_for_button"]

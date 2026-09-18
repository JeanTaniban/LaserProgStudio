# -*- coding: utf-8 -*-
"""Lightweight diagnostics for editable Qt overlay fields.

This module is deliberately generic and does not import any application tool.
It records only overlay/Qt-layer facts: textChanged, editingFinished, button
flushes and active-tool notification results.  Tool-specific state diagnostics
stay in the tool package.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any


_DIAG_FILE = "overlay_edit_events.jsonl"


def _should_record(window_id: str | None = None, field_id: str | None = None, button_id: str | None = None, owner: Any | None = None) -> bool:
    try:
        from laserprog_studio.services.debug_mode import should_record_diagnostics
        if not should_record_diagnostics(owner):
            return False
    except Exception:
        return False
    try:
        import os
        explicit = os.environ.get("TOOL_CORE_OVERLAY_EDIT_DIAGNOSTICS", "").strip().lower() in {"1", "true", "yes", "on"}
    except Exception:
        explicit = False
    text = " ".join(str(v or "") for v in (window_id, field_id, button_id)).lower()
    return explicit or "plan_trace_2d.motif" in text or "cloth.workflow" in text


def _path() -> Path:
    path = Path.cwd() / "diagnostics"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path / _DIAG_FILE


def _safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(v) for v in value]
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def _widget_values(adapter: Any, window_id: str | None) -> dict[str, dict[str, Any]]:
    if not window_id:
        return {}
    try:
        owner = adapter.owner
        widgets = getattr(owner, "_tool_core_overlay_widgets", {}) or {}
    except Exception:
        widgets = {}
    if not isinstance(widgets, dict):
        return {}
    widget = widgets.get(str(window_id))
    if widget is None:
        return {}
    try:
        edits = getattr(widget, "_tool_core_overlay_field_edits", {}) or {}
    except Exception:
        edits = {}
    result: dict[str, dict[str, Any]] = {}
    if not isinstance(edits, dict):
        return result
    for fid, edit in edits.items():
        key = str(fid)
        try:
            text = str(edit.text())
        except Exception:
            text = "<read-error>"
        try:
            focus = bool(edit.hasFocus())
        except Exception:
            focus = False
        result[key] = {"text": text, "focus": focus}
    return result


def _manager_values(adapter: Any, window_id: str | None) -> dict[str, str]:
    if not window_id:
        return {}
    try:
        window = adapter.manager.window(str(window_id))
    except Exception:
        window = None
    result: dict[str, str] = {}
    if window is None:
        return result
    for field in tuple(getattr(window, "fields", ()) or ()):  # overlay spec
        try:
            result[str(getattr(field, "id", "") or "")] = str(getattr(field, "value", "") or "")
        except Exception:
            pass
    return result


def record_qt_overlay_edit_event(
    event: str,
    *,
    adapter: Any | None = None,
    window_id: str | None = None,
    field_id: str | None = None,
    value: Any | None = None,
    button_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    owner = getattr(adapter, "owner", None) if adapter is not None else None
    if not _should_record(window_id, field_id, button_id, owner=owner):
        return
    entry = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "event": str(event),
        "window_id": None if window_id is None else str(window_id),
        "field_id": None if field_id is None else str(field_id),
        "value": None if value is None else str(value),
        "button_id": None if button_id is None else str(button_id),
        "extra": _safe(extra or {}),
    }
    if adapter is not None:
        try:
            owner = getattr(adapter, "owner", None)
            entry["active_tool"] = str(getattr(owner, "active_tool", "") or "") if owner is not None else ""
        except Exception:
            entry["active_tool"] = ""
        entry["manager_values"] = _manager_values(adapter, window_id)
        entry["widget_values"] = _widget_values(adapter, window_id)
    try:
        _path().open("a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


__all__ = ["record_qt_overlay_edit_event"]

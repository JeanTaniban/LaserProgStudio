# -*- coding: utf-8 -*-
"""Structured diagnostics for the Plan Tracer 2D Pattern editor.

The Pattern editor is rendered by the shared declarative overlay API.  When an
editable Qt field appears disconnected, the useful question is not only "what is
in the tool state?" but also "what is in the overlay manager?" and "what is in
the live QLineEdit widgets?".  This module keeps that inspection in one place so
``motif_overlay.py`` stays focused on the Pattern workflow.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any


_MOTIF_DIAG_FILE = "plan_trace_2d_motif_overlay_debug.jsonl"


@dataclass(frozen=True)
class MotifOverlaySnapshot:
    """Snapshot of the three value layers involved in the Pattern editor."""

    state_values: dict[str, Any]
    manager_values: dict[str, str]
    widget_values: dict[str, str]
    widget_focus: dict[str, bool]
    active_tool: str
    overlay_visible: bool


def _diagnostics_dir() -> Path:
    path = Path.cwd() / "diagnostics"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return path


def _debug_enabled(ctx: Any | None = None) -> bool:
    try:
        from laserprog_studio.services.debug_mode import should_record_diagnostics
        owner = _owner_from_context(ctx) if ctx is not None else None
        return bool(should_record_diagnostics(owner))
    except Exception:
        return False


def motif_diagnostics_path() -> Path:
    return _diagnostics_dir() / _MOTIF_DIAG_FILE


def _safe_text(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def collect_overlay_manager_values(ctx: Any, window_id: str) -> dict[str, str]:
    """Return values currently stored in the declarative overlay manager."""

    try:
        window = ctx.overlay.window(str(window_id))
    except Exception:
        window = None
    values: dict[str, str] = {}
    if window is None:
        return values
    for field in tuple(getattr(window, "fields", ()) or ()):  # public overlay spec
        try:
            values[str(getattr(field, "id", "") or "")] = _safe_text(getattr(field, "value", ""))
        except Exception:
            pass
    return values


def _owner_from_context(ctx: Any) -> Any | None:
    owner = getattr(ctx, "owner", None)
    if owner is not None:
        return owner
    # Some tests/adapters keep the owner on the app-context object instead of on
    # the ToolContext.  Keep this fallback extremely defensive.
    app_context = getattr(ctx, "app_context", None)
    if app_context is not None:
        return getattr(app_context, "owner", None)
    return None


def collect_qt_widget_values(ctx: Any, window_id: str) -> tuple[dict[str, str], dict[str, bool]]:
    """Return text values read directly from live QLineEdit widgets.

    This intentionally bypasses the overlay manager.  It is the final safety net
    when Qt signals or live callbacks are suspected to be broken.
    """

    owner = _owner_from_context(ctx)
    if owner is None:
        return {}, {}
    try:
        widgets = getattr(owner, "_tool_core_overlay_widgets", {}) or {}
    except Exception:
        widgets = {}
    if not isinstance(widgets, dict):
        return {}, {}
    widget = widgets.get(str(window_id))
    if widget is None:
        return {}, {}

    edits: dict[str, Any] = {}
    try:
        stored_edits = getattr(widget, "_tool_core_overlay_field_edits", {}) or {}
        if isinstance(stored_edits, dict):
            edits.update({str(k): v for k, v in stored_edits.items()})
    except Exception:
        pass

    # Fallback for future renderers that do not populate the helper dict but do
    # still set the stable overlay field property on QLineEdit children.
    if not edits:
        try:
            from PySide6.QtWidgets import QLineEdit  # type: ignore

            for edit in widget.findChildren(QLineEdit):
                field_id = edit.property("toolCoreOverlayFieldId")
                if field_id:
                    edits[str(field_id)] = edit
        except Exception:
            pass

    values: dict[str, str] = {}
    focus: dict[str, bool] = {}
    for field_id, edit in edits.items():
        try:
            values[str(field_id)] = _safe_text(edit.text())
        except Exception:
            values[str(field_id)] = "<read-error>"
        try:
            focus[str(field_id)] = bool(edit.hasFocus())
        except Exception:
            focus[str(field_id)] = False
    try:
        selects = getattr(widget, "_tool_core_overlay_field_selects", {}) or {}
    except Exception:
        selects = {}
    if isinstance(selects, dict):
        for field_id, combo in selects.items():
            try:
                selected = combo.currentData()
                values[str(field_id)] = _safe_text(selected if selected is not None else combo.currentText())
            except Exception:
                values[str(field_id)] = "<read-error>"
            try:
                focus[str(field_id)] = bool(combo.hasFocus())
            except Exception:
                focus[str(field_id)] = False
    return values, focus


def state_value_snapshot(state: Any) -> dict[str, Any]:
    """Return the Pattern state values relevant for field/apply debugging."""

    names = (
        "motif_kind",
        "motif_preset_id",
        "motif_preset_name",
        "motif_cell_size",
        "motif_wall",
        "motif_margin",
        "motif_keep_form",
        "motif_angle",
        "motif_aspect",
        "motif_seed",
        "motif_offset_x",
        "motif_offset_y",
        "motif_preview_face_id",
        "motif_preview_face_ids",
        "pattern_face_id",
        "pattern_face_ids",
        "pattern_generated_count",
        "motif_last_status",
    )
    values: dict[str, Any] = {}
    for name in names:
        try:
            values[name] = getattr(state, name)
        except Exception:
            values[name] = None
    try:
        values["motif_pending_field_values"] = dict(getattr(state, "motif_pending_field_values", {}) or {})
    except Exception:
        values["motif_pending_field_values"] = {}
    return values


def collect_snapshot(ctx: Any, state: Any, window_id: str) -> MotifOverlaySnapshot:
    widget_values, widget_focus = collect_qt_widget_values(ctx, window_id)
    try:
        owner = _owner_from_context(ctx)
        active_tool = str(getattr(owner, "active_tool", "") or "") if owner is not None else ""
    except Exception:
        active_tool = ""
    try:
        window = ctx.overlay.window(str(window_id))
        overlay_visible = bool(getattr(window, "visible", False)) if window is not None else False
    except Exception:
        overlay_visible = False
    return MotifOverlaySnapshot(
        state_values=state_value_snapshot(state),
        manager_values=collect_overlay_manager_values(ctx, window_id),
        widget_values=widget_values,
        widget_focus=widget_focus,
        active_tool=active_tool,
        overlay_visible=overlay_visible,
    )


def record_motif_overlay_event(
    ctx: Any,
    state: Any,
    event: str,
    *,
    window_id: str,
    field_id: str | None = None,
    raw_value: Any | None = None,
    button_id: str | None = None,
    source: str = "tool",
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one JSONL diagnostic event and mirror cheap counters to profiler."""

    if not _debug_enabled(ctx):
        return
    try:
        seq = int(getattr(state, "motif_diag_sequence", 0) or 0) + 1
        setattr(state, "motif_diag_sequence", seq)
    except Exception:
        seq = 0
    snapshot = collect_snapshot(ctx, state, window_id)
    entry = {
        "ts": datetime.now().isoformat(timespec="milliseconds"),
        "seq": seq,
        "event": str(event),
        "source": str(source),
        "window_id": str(window_id),
        "field_id": None if field_id is None else str(field_id),
        "raw_value": None if raw_value is None else _safe_text(raw_value),
        "button_id": None if button_id is None else str(button_id),
        "active_tool": snapshot.active_tool,
        "overlay_visible": snapshot.overlay_visible,
        "state_values": snapshot.state_values,
        "manager_values": snapshot.manager_values,
        "widget_values": snapshot.widget_values,
        "widget_focus": snapshot.widget_focus,
        "extra": dict(extra or {}),
    }
    try:
        motif_diagnostics_path().open("a", encoding="utf-8").write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass
    try:
        profiler = getattr(ctx, "profiler", None)
        increment = getattr(profiler, "increment", None)
        set_value = getattr(profiler, "set_value", None)
        if callable(increment):
            increment(f"plan_trace.motif_overlay.{event}")
        if callable(set_value):
            set_value("plan_trace.motif_overlay.last_event", str(event))
            if field_id is not None:
                set_value("plan_trace.motif_overlay.last_field_id", str(field_id))
            if raw_value is not None:
                set_value("plan_trace.motif_overlay.last_raw_value", _safe_text(raw_value))
    except Exception:
        pass
    try:
        setattr(state, "motif_diag_last_event", f"#{seq} {event}")
    except Exception:
        pass


__all__ = [
    "MotifOverlaySnapshot",
    "collect_overlay_manager_values",
    "collect_qt_widget_values",
    "collect_snapshot",
    "motif_diagnostics_path",
    "record_motif_overlay_event",
    "state_value_snapshot",
]

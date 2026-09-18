# -*- coding: utf-8 -*-
"""Deep diagnostics for Plan Tracer selected-length propagation.

The trace is intentionally isolated from the normal application log and is
strictly gated by LaserProg's global debug mode.  It follows the full runtime
pipeline from Shift-click hit testing to the text shown by the live Qt
inspector, so a future report can identify the first failing stage instead of
inferring it from headless tests.
"""
from __future__ import annotations

from collections import Counter, deque
import json
import os
import time
from pathlib import Path
from typing import Any

_DIAG_FILE = "plan_trace_selection_length_debug.jsonl"
_SUMMARY_FILE = "plan_trace_selection_length_debug.md"
_MAX_EVENTS = int(os.environ.get("LASERPROG_PLAN_TRACE_SELECTION_DIAG_MAX", "20000") or "20000")
_RECENT_LIMIT = 80
_seq = 0
_started = False
_stage_counts: Counter[str] = Counter()
_recent: deque[dict[str, Any]] = deque(maxlen=_RECENT_LIMIT)
_last_by_stage: dict[str, dict[str, Any]] = {}


def _debug_enabled(owner: Any | None = None) -> bool:
    try:
        from laserprog_studio.services.debug_mode import should_record_diagnostics

        return bool(should_record_diagnostics(owner))
    except Exception:
        return False


def _diagnostics_dir() -> Path:
    try:
        from laserprog_studio.bootstrap import compute_paths

        path = compute_paths().diagnostics_dir
    except Exception:
        path = Path.cwd() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def selection_length_diagnostics_path() -> Path:
    return _diagnostics_dir() / _DIAG_FILE


def selection_length_summary_path() -> Path:
    return _diagnostics_dir() / _SUMMARY_FILE


def _safe(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth >= 4:
        return repr(value)
    if isinstance(value, dict):
        return {str(key): _safe(item, depth=depth + 1) for key, item in list(value.items())[:100]}
    if isinstance(value, (list, tuple, set, frozenset, deque)):
        return [_safe(item, depth=depth + 1) for item in list(value)[:100]]
    try:
        return str(value.value)
    except Exception:
        pass
    try:
        return int(value)
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        pass
    return repr(value)


def actor_snapshot(actor: Any | None) -> dict[str, Any]:
    if actor is None:
        return {"exists": False}
    metadata = getattr(actor, "metadata", {}) or {}
    kind = getattr(actor, "kind", "")
    kind = getattr(kind, "value", kind)
    interaction = getattr(actor, "interaction", "")
    interaction = getattr(interaction, "value", interaction)
    return {
        "exists": True,
        "id": str(getattr(actor, "id", "")),
        "owner_tool": str(getattr(actor, "owner_tool", "") or ""),
        "kind": str(kind),
        "interaction": str(interaction),
        "selectable": bool(getattr(actor, "selectable", False)),
        "hit_radius_px": _safe(getattr(actor, "hit_radius_px", None)),
        "point_count": len(tuple(getattr(actor, "points", ()) or ())),
        "role": str(metadata.get("plan_trace_role", "") or ""),
        "line_id": _safe(metadata.get("plan_trace_sketch_line_id")),
        "arc_id": _safe(metadata.get("plan_trace_sketch_arc_id")),
        "circle_id": _safe(metadata.get("plan_trace_sketch_circle_id")),
        "face_id": _safe(metadata.get("plan_trace_sketch_face_id")),
        "selection_priority": _safe(metadata.get("selection_priority")),
        "api_ui_visible": _safe(metadata.get("api_ui_visible")),
    }


def selection_snapshot(selection: Any | None) -> dict[str, Any]:
    if selection is None:
        return {"available": False, "ids": [], "actors": []}
    try:
        ids = tuple(str(value) for value in selection.ids())
    except Exception as exc:
        return {"available": False, "error": repr(exc), "ids": [], "actors": []}
    actors = []
    for actor_id in ids:
        try:
            actor = selection.actor(actor_id)
        except Exception:
            actor = None
        snap = actor_snapshot(actor)
        snap["selected_id"] = actor_id
        actors.append(snap)
    return {"available": True, "ids": list(ids), "count": len(ids), "actors": actors}


def inspector_snapshot(ctx: Any | None) -> dict[str, Any]:
    if ctx is None:
        return {"available": False}
    manager = getattr(ctx, "inspector", None)
    if manager is None:
        return {"available": False}
    try:
        value = manager.value("plan_trace_2d.selection_length", "<missing>")
    except Exception as exc:
        value = f"<error:{exc!r}>"
    panel = getattr(manager, "panel", None)
    return {
        "available": True,
        "panel_id": str(getattr(panel, "id", "") or ""),
        "owner_tool": str(getattr(panel, "owner_tool", "") or ""),
        "value": _safe(value),
        "revision": _safe(getattr(manager, "revision", None)),
        "layout_revision": _safe(getattr(manager, "layout_revision", None)),
        "value_revision": _safe(getattr(manager, "value_revision", None)),
        "state_revision": _safe(getattr(manager, "state_revision", None)),
    }


def qt_field_snapshot(root: Any | None, field_id: str = "plan_trace_2d.selection_length") -> dict[str, Any]:
    if root is None:
        return {"available": False, "reason": "no_root"}
    try:
        from PySide6.QtWidgets import QWidget
    except Exception as exc:
        return {"available": False, "reason": "pyside_unavailable", "error": repr(exc)}
    try:
        widgets = list(root.findChildren(QWidget))
    except Exception as exc:
        return {"available": False, "reason": "find_children_failed", "error": repr(exc)}
    matches: list[dict[str, Any]] = []
    for widget in widgets:
        try:
            widget_field_id = str(widget.property("inspector_field_id") or "")
        except Exception:
            widget_field_id = ""
        if widget_field_id != field_id:
            continue
        text = None
        for accessor in ("text", "currentText", "value"):
            try:
                method = getattr(widget, accessor, None)
                if callable(method):
                    text = method()
                    break
            except Exception:
                pass
        matches.append(
            {
                "class": type(widget).__name__,
                "object_name": str(getattr(widget, "objectName", lambda: "")() or ""),
                "text": _safe(text),
                "visible": bool(getattr(widget, "isVisible", lambda: False)()),
                "enabled": bool(getattr(widget, "isEnabled", lambda: False)()),
            }
        )
    return {"available": True, "match_count": len(matches), "matches": matches}


def reset_selection_length_diagnostics(
    reason: str = "reset",
    *,
    owner: Any | None = None,
    ctx: Any | None = None,
    sketch: Any | None = None,
) -> None:
    global _seq, _started
    _seq = 0
    _started = False
    _stage_counts.clear()
    _recent.clear()
    _last_by_stage.clear()
    if not _debug_enabled(owner):
        return
    try:
        selection_length_diagnostics_path().write_text("", encoding="utf-8")
    except Exception:
        return
    _started = True
    record_selection_length_event(
        "session.start",
        owner=owner,
        ctx=ctx,
        reason=reason,
        sketch_counts={
            "points": len(getattr(sketch, "points", {}) or {}) if sketch is not None else None,
            "lines": len(getattr(sketch, "lines", {}) or {}) if sketch is not None else None,
            "arcs": len(getattr(sketch, "arcs", {}) or {}) if sketch is not None else None,
            "circles": len(getattr(sketch, "circles", {}) or {}) if sketch is not None else None,
        },
    )


def record_selection_length_event(
    stage: str,
    *,
    owner: Any | None = None,
    ctx: Any | None = None,
    include_selection: bool = False,
    include_inspector: bool = False,
    **payload: Any,
) -> None:
    global _seq, _started
    if not _debug_enabled(owner):
        return
    if _seq >= _MAX_EVENTS:
        return
    if not _started:
        try:
            selection_length_diagnostics_path().write_text("", encoding="utf-8")
        except Exception:
            pass
        _started = True
    _seq += 1
    entry: dict[str, Any] = {
        "seq": _seq,
        "at_s": round(time.monotonic(), 6),
        "stage": str(stage),
    }
    if include_selection and ctx is not None:
        entry["selection"] = selection_snapshot(getattr(ctx, "selection", None))
    if include_inspector and ctx is not None:
        entry["inspector"] = inspector_snapshot(ctx)
    for key, value in payload.items():
        entry[str(key)] = _safe(value)
    _stage_counts[str(stage)] += 1
    _recent.append(entry)
    _last_by_stage[str(stage)] = entry
    try:
        with selection_length_diagnostics_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _infer_breakpoint(ctx: Any | None = None) -> str:
    if "selection.event.begin" not in _last_by_stage:
        return "selection_event_not_received"
    hit = _last_by_stage.get("selection.hit_test.done", {})
    if not hit.get("winner"):
        return "hit_test_no_winner"
    mutation = _last_by_stage.get("selection.mutation.done", {})
    selection = mutation.get("selection") if isinstance(mutation, dict) else None
    actors = selection.get("actors", []) if isinstance(selection, dict) else []
    roles = {str(item.get("role") or "") for item in actors if isinstance(item, dict)}
    if actors and not roles.intersection({"edge", "arc", "circle"}):
        return "selected_actor_is_not_measurable_edge"
    measure = _last_by_stage.get("measurement.done", {})
    if measure.get("result") in (None, {}, ""):
        return "measurement_returned_none"
    manager = _last_by_stage.get("inspector.manager.write", {})
    manager_value = manager.get("validated")
    if manager_value in (None, "—", "-"):
        return "inspector_manager_received_empty_value"
    qt_sync = _last_by_stage.get("inspector.qt.sync_field", {})
    qt_refresh = _last_by_stage.get("inspector.qt.refresh.end", {})
    if not qt_refresh:
        return "qt_live_panel_refresh_not_observed"
    qt_after = qt_sync.get("after") if isinstance(qt_sync, dict) else None
    matches = qt_after.get("matches", []) if isinstance(qt_after, dict) else []
    texts = [str(item.get("text")) for item in matches if isinstance(item, dict)]
    if texts and all(text in {"—", "-", "None", ""} for text in texts):
        return "qt_label_not_updated"
    return "pipeline_completed_or_requires_timeline_review"


def export_selection_length_summary(
    *,
    ctx: Any | None = None,
    sketch: Any | None = None,
    reason: str = "snapshot",
) -> Path | None:
    if not _debug_enabled(getattr(ctx, "owner", None) if ctx is not None else None):
        return None
    selection = selection_snapshot(getattr(ctx, "selection", None) if ctx is not None else None)
    inspector = inspector_snapshot(ctx)
    lines = [
        "# Plan Tracer selected-length diagnostic",
        "",
        f"- reason: {reason}",
        f"- generated_at: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- jsonl: {selection_length_diagnostics_path()}",
        f"- event_count: {_seq}",
        f"- likely_breakpoint: {_infer_breakpoint(ctx)}",
        "",
        "## Current selection",
        "",
        f"- ids: {selection.get('ids', [])}",
        f"- actors: {selection.get('actors', [])}",
        "",
        "## Inspector manager",
        "",
        f"- snapshot: {inspector}",
        "",
        "## Sketch counts",
        "",
        f"- points: {len(getattr(sketch, 'points', {}) or {}) if sketch is not None else 'unknown'}",
        f"- lines: {len(getattr(sketch, 'lines', {}) or {}) if sketch is not None else 'unknown'}",
        f"- arcs: {len(getattr(sketch, 'arcs', {}) or {}) if sketch is not None else 'unknown'}",
        f"- circles: {len(getattr(sketch, 'circles', {}) or {}) if sketch is not None else 'unknown'}",
        "",
        "## Stage counts",
        "",
    ]
    for stage, count in sorted(_stage_counts.items()):
        lines.append(f"- `{stage}`: {count}")
    lines.extend(["", "## Last event by important stage", ""])
    for stage in (
        "selection.event.begin",
        "selection.hit_test.done",
        "selection.mutation.done",
        "measurement.done",
        "overlay.selection_length.computed",
        "inspector.manager.write",
        "inspector.qt.refresh.begin",
        "inspector.qt.sync_field",
        "inspector.qt.refresh.end",
    ):
        lines.append(f"### `{stage}`")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(_last_by_stage.get(stage, {}), ensure_ascii=False, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
    lines.extend(["## Recent timeline", "", "```jsonl"])
    for entry in _recent:
        lines.append(json.dumps(entry, ensure_ascii=False, sort_keys=True))
    lines.extend(["```", ""])
    path = selection_length_summary_path()
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
        record_selection_length_event("summary.exported", path=str(path), reason=reason)
        return path
    except Exception:
        return None


__all__ = [
    "actor_snapshot",
    "export_selection_length_summary",
    "inspector_snapshot",
    "qt_field_snapshot",
    "record_selection_length_event",
    "reset_selection_length_diagnostics",
    "selection_length_diagnostics_path",
    "selection_length_summary_path",
    "selection_snapshot",
]

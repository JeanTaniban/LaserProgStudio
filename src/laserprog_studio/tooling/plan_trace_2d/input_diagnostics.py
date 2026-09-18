# -*- coding: utf-8 -*-
"""Structured pointer-input diagnostics for Plan Tracer 2D.

This diagnostic is intentionally verbose in the v46 debug build: it records the
full path of a mouse move from the Qt event filter, through the Creator API
bridge, into Plan Tracer and finally through cursor projection/snap.  The file is
JSONL so a bad frame can be inspected without parsing the whole app log.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_DIAG_FILE = "plan_trace_input_debug.jsonl"
_MAX_EVENTS = int(os.environ.get("LASERPROG_PLAN_TRACE_INPUT_DIAG_MAX", "50000") or "50000")
_seq = 0
_started = False


def _debug_enabled(owner: Any | None = None) -> bool:
    try:
        from laserprog_studio.services.debug_mode import should_record_diagnostics
        return bool(should_record_diagnostics(owner))
    except Exception:
        return False


def _diagnostics_dir() -> Path:
    path = Path.cwd() / "diagnostics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def plan_trace_input_diagnostics_path() -> Path:
    return _diagnostics_dir() / _DIAG_FILE


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        if isinstance(value, (list, tuple)):
            return [_safe_scalar(v) for v in value[:12]]
        if isinstance(value, dict):
            return {str(k): _safe_scalar(v) for k, v in list(value.items())[:50]}
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


def _qflag_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        pass
    try:
        return int(value.value)  # PySide6 enum flag wrapper
    except Exception:
        pass
    try:
        return int(value.toInt()[0])
    except Exception:
        pass
    return None


def _qbutton_names(value: Any, Qt: Any | None = None) -> list[str]:
    names: list[str] = []
    if Qt is None:
        return names
    for attr, label in (
        ("LeftButton", "left"),
        ("MiddleButton", "middle"),
        ("RightButton", "right"),
    ):
        try:
            flag = getattr(Qt, attr)
            if bool(value & flag):
                names.append(label)
        except Exception:
            pass
    if not names:
        try:
            if value == getattr(Qt, "NoButton"):
                names.append("none")
        except Exception:
            pass
    return names


def _event_type_name(etype: Any, QEvent: Any | None = None) -> str:
    if QEvent is not None:
        for attr in ("MouseButtonPress", "MouseMove", "MouseButtonRelease", "MouseButtonDblClick", "Wheel"):
            try:
                if etype == getattr(QEvent, attr):
                    return attr
            except Exception:
                pass
    return repr(etype)


def _button_name(button: Any, Qt: Any | None = None) -> str:
    if Qt is not None:
        for attr, label in (
            ("LeftButton", "left"),
            ("MiddleButton", "middle"),
            ("RightButton", "right"),
            ("NoButton", "none"),
        ):
            try:
                if button == getattr(Qt, attr):
                    return label
            except Exception:
                pass
    try:
        return str(button.name).lower()
    except Exception:
        return repr(button)


def _owner_snapshot(owner: Any) -> dict[str, Any]:
    if owner is None:
        return {}
    keys = (
        "active_tool",
        "_viewport_pointer_buttons_down",
        "_creator_camera_navigation_active",
        "_creator_camera_navigation_mode",
        "_creator_camera_navigation_candidate_mode",
        "_creator_camera_navigation_generation",
        "_right_pan_active",
        "_drag_axis",
        "_gizmo_pressed_axis",
    )
    data: dict[str, Any] = {}
    for key in keys:
        try:
            data[key] = _safe_scalar(getattr(owner, key, None))
        except Exception:
            pass
    try:
        data["plotter_has_focus"] = bool(owner.plotter.hasFocus())
    except Exception:
        pass
    return data


def _ctx_snapshot(ctx: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    try:
        selection = getattr(ctx, "selection", None)
        state = getattr(selection, "state", None)
        data["selection_grab_active"] = bool(getattr(state, "grab_active", False))
        data["selection_grabbed_ids"] = list(getattr(state, "grabbed_ids", ()) or ())[:8]
        data["selection_ids"] = list(selection.ids())[:8] if callable(getattr(selection, "ids", None)) else []
    except Exception:
        pass
    try:
        pd = getattr(ctx, "projected_drawing", None)
        snap = pd.snapshot("plan_trace") if pd is not None else None
        if snap is not None:
            data["projected_revision"] = int(getattr(snap, "revision", -1))
            data["projected_primitives"] = len(tuple(getattr(snap, "primitives", ()) or ()))
    except Exception:
        pass
    return data


def _tool_state_snapshot(tool: Any) -> dict[str, Any]:
    state = getattr(tool, "_state", None)
    if state is None:
        return {}
    data: dict[str, Any] = {}
    for key in (
        "active_tool",
        "camera_interaction_active",
        "camera_interaction_mode",
        "camera_interaction_screen_pos",
        "plan_trace_last_cursor_screen_pos",
        "plan_trace_last_cursor_world",
        "pending_preview_ids",
        "last_snap_kind",
        "last_snap_label",
        "active_drag_snapshot",
        "motif_offset_drag_axis",
    ):
        try:
            value = getattr(state, key, None)
            if isinstance(value, tuple):
                value = list(value[:8])
            data[key] = _safe_scalar(value)
        except Exception:
            pass
    try:
        data["plane_locked"] = getattr(state, "plane", None) is not None
        data["display_plane_locked"] = getattr(state, "display_plane", None) is not None
        sketch = getattr(state, "sketch", None)
        if sketch is not None:
            data["sketch_points"] = len(getattr(sketch, "points", {}) or {})
            data["sketch_lines"] = len(getattr(sketch, "lines", {}) or {})
    except Exception:
        pass
    return data


def reset_plan_trace_input_diagnostics(reason: str = "reset", *, owner: Any = None, ctx: Any = None, tool: Any = None) -> None:
    global _seq, _started
    if not _debug_enabled(owner):
        _seq = 0
        _started = False
        return
    _seq = 0
    _started = True
    path = plan_trace_input_diagnostics_path()
    try:
        path.write_text("", encoding="utf-8")
    except Exception:
        return
    record_plan_trace_input_event(
        "session.start",
        reason=reason,
        owner=_owner_snapshot(owner),
        ctx=_ctx_snapshot(ctx),
        tool_state=_tool_state_snapshot(tool),
        cwd=str(Path.cwd()),
        file=str(path),
    )


def record_plan_trace_input_event(stage: str, **payload: Any) -> None:
    global _seq, _started
    owner = payload.get("owner") if isinstance(payload, dict) else None
    if isinstance(owner, dict):
        owner = None
    if not _debug_enabled(owner):
        return
    if _seq >= _MAX_EVENTS:
        return
    if not _started:
        _started = True
        try:
            # Start a fresh file on the first diagnostic event of the process,
            # but do not recurse through reset_plan_trace_input_diagnostics().
            plan_trace_input_diagnostics_path().write_text("", encoding="utf-8")
        except Exception:
            pass
    _seq += 1
    entry = {
        "seq": _seq,
        "at_s": round(time.monotonic(), 6),
        "stage": str(stage),
    }
    for key, value in payload.items():
        entry[str(key)] = _safe_scalar(value)
    try:
        plan_trace_input_diagnostics_path().open("a", encoding="utf-8").write(
            json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        )
    except Exception:
        pass


def record_controller_event(stage: str, owner: Any, etype: Any, event: Any, qx: float, qy: float, buttons: Any, *, Qt: Any, QEvent: Any, source: str = "controller", **payload: Any) -> None:
    try:
        button = event.button() if hasattr(event, "button") else None
    except Exception:
        button = None
    record_plan_trace_input_event(
        stage,
        source=str(source),
        event_type=_event_type_name(etype, QEvent),
        q=(float(qx), float(qy)),
        buttons_repr=repr(buttons),
        buttons_int=_qflag_int(buttons),
        buttons_names=_qbutton_names(buttons, Qt),
        button_repr=repr(button),
        button_int=_qflag_int(button),
        button_name=_button_name(button, Qt),
        accepted=bool(getattr(event, "isAccepted", lambda: False)()),
        owner=_owner_snapshot(owner),
        **payload,
    )


def record_creator_bridge_event(stage: str, owner: Any, ctx: Any, tool: Any, etype: Any, event: Any, qx: float, qy: float, buttons: Any, *, Qt: Any, QEvent: Any, **payload: Any) -> None:
    record_controller_event(
        stage,
        owner,
        etype,
        event,
        qx,
        qy,
        buttons,
        Qt=Qt,
        QEvent=QEvent,
        source="creator_bridge",
        ctx=_ctx_snapshot(ctx),
        tool_id=getattr(tool, "id", None),
        tool_state=_tool_state_snapshot(getattr(tool, "creator", tool)),
        **payload,
    )


def record_tool_event(stage: str, tool: Any, ctx: Any, event: Any, *, source: str = "plan_trace_tool", **payload: Any) -> None:
    try:
        screen = getattr(event, "screen_pos", None)
    except Exception:
        screen = None
    record_plan_trace_input_event(
        stage,
        source=str(source),
        event_type=str(getattr(getattr(event, "type", None), "value", getattr(event, "type", "unknown"))),
        button=str(getattr(getattr(event, "button", None), "value", getattr(event, "button", "unknown"))),
        screen_pos=screen,
        world_pos=getattr(event, "world_pos", None),
        ctx=_ctx_snapshot(ctx),
        tool_state=_tool_state_snapshot(tool),
        **payload,
    )


def record_cursor_event(stage: str, service: Any, ctx: Any, event: Any, **payload: Any) -> None:
    record_tool_event(
        stage,
        getattr(service, "owner", None),
        ctx,
        event,
        source="plan_trace_cursor",
        **payload,
    )


__all__ = [
    "plan_trace_input_diagnostics_path",
    "record_controller_event",
    "record_creator_bridge_event",
    "record_cursor_event",
    "record_plan_trace_input_event",
    "record_tool_event",
    "reset_plan_trace_input_diagnostics",
]

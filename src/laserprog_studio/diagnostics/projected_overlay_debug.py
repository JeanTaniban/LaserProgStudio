# -*- coding: utf-8 -*-
"""Structured diagnostics for the Projected Drawing 2D live renderer.

This trace is intentionally gated behind the global debug mode because it writes
JSONL events from the rendering path.  It answers one precise question that the
normal Plan Tracer timing report cannot answer: did projected geometry disappear
before reaching VTK, while creating VTK actors, or during world->screen
projection?
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

_DIAG_FILE = "projected_overlay_debug.jsonl"
_MAX_EVENTS = int(os.environ.get("LASERPROG_PROJECTED_OVERLAY_DIAG_MAX", "20000") or "20000")
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


def projected_overlay_diagnostics_path() -> Path:
    return _diagnostics_dir() / _DIAG_FILE


def _safe(value: Any, *, max_list: int = 24, max_dict: int = 60) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        if isinstance(value, Path):
            return str(value)
    except Exception:
        pass
    try:
        if isinstance(value, (list, tuple)):
            return [_safe(item, max_list=max_list, max_dict=max_dict) for item in list(value)[:max_list]]
        if isinstance(value, set):
            return [_safe(item, max_list=max_list, max_dict=max_dict) for item in sorted(value, key=str)[:max_list]]
        if isinstance(value, dict):
            return {str(key): _safe(val, max_list=max_list, max_dict=max_dict) for key, val in list(value.items())[:max_dict]}
    except Exception:
        pass
    try:
        return float(value)
    except Exception:
        pass
    try:
        return int(value)
    except Exception:
        pass
    return repr(value)


def _owner_snapshot(owner: Any) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if owner is None:
        return data
    for key in ("active_tool", "_performance_mode", "_diagnostic_verbose"):
        try:
            data[key] = _safe(getattr(owner, key, None))
        except Exception:
            pass
    try:
        plotter = getattr(owner, "plotter", None)
        data["plotter_type"] = type(plotter).__name__ if plotter is not None else None
        renderer = getattr(plotter, "renderer", None) if plotter is not None else None
        data["renderer_type"] = type(renderer).__name__ if renderer is not None else None
        if renderer is not None:
            data["renderer_id"] = id(renderer)
            for method_name in ("GetSize", "GetOrigin", "GetNumberOfPropsRendered"):
                method = getattr(renderer, method_name, None)
                if callable(method):
                    try:
                        data[method_name] = _safe(method())
                    except Exception as exc:
                        data[method_name] = f"error:{type(exc).__name__}"
        if plotter is not None:
            for name in ("width", "height"):
                method = getattr(plotter, name, None)
                if callable(method):
                    try:
                        data[f"plotter_{name}"] = int(method())
                    except Exception as exc:
                        data[f"plotter_{name}"] = f"error:{type(exc).__name__}"
    except Exception:
        pass
    return data



def _safe_count_items(provider: Any, *, owner_tool: str = "") -> dict[str, Any]:
    data: dict[str, Any] = {}
    try:
        items_method = getattr(provider, "items", None)
        handles_method = getattr(provider, "handles", None)
        if callable(items_method):
            try:
                values = tuple(items_method(owner_tool=owner_tool)) if owner_tool and owner_tool != "*" else tuple(items_method())
            except TypeError:
                values = tuple(items_method())
            data["items_count"] = len(values)
            counts: dict[str, int] = {}
            samples: list[dict[str, Any]] = []
            for item in values:
                kind = str(getattr(item, "kind", type(item).__name__))
                counts[kind] = counts.get(kind, 0) + 1
                if len(samples) < 8:
                    samples.append({
                        "id": str(getattr(item, "id", "")),
                        "kind": kind,
                        "visible": bool(getattr(item, "visible", True)),
                        "points": len(tuple(getattr(item, "points", ()) or ())) if hasattr(item, "points") else None,
                    })
            data["items_by_kind"] = counts
            data["item_samples"] = samples
        if callable(handles_method):
            try:
                values = tuple(handles_method(owner_tool=owner_tool)) if owner_tool and owner_tool != "*" else tuple(handles_method())
            except TypeError:
                values = tuple(handles_method())
            data["handles_count"] = len(values)
            data["handle_samples"] = [
                {
                    "id": str(getattr(item, "id", "")),
                    "kind": str(getattr(item, "kind", type(item).__name__)),
                    "visible": bool(getattr(item, "visible", True)),
                    "position": _safe(getattr(item, "position", None)),
                    "radius_px": _safe(getattr(item, "radius_px", None)),
                }
                for item in values[:8]
            ]
    except Exception as exc:
        data["error"] = type(exc).__name__
    return data


def _context_snapshot(ctx: Any, owner_tool: str = "") -> dict[str, Any]:
    data: dict[str, Any] = {}
    if ctx is None:
        return data
    try:
        data["ctx_type"] = type(ctx).__name__
        data["ctx_owner_id"] = id(getattr(ctx, "owner", None)) if getattr(ctx, "owner", None) is not None else None
    except Exception:
        pass
    try:
        preview = getattr(ctx, "preview", None)
        if preview is not None:
            data["preview"] = _safe_count_items(preview, owner_tool=str(owner_tool or ""))
    except Exception:
        pass
    try:
        gizmos = getattr(ctx, "gizmos", None)
        if gizmos is not None:
            data["gizmos"] = _safe_count_items(gizmos, owner_tool=str(owner_tool or ""))
    except Exception:
        pass
    try:
        projected = getattr(ctx, "projected_drawing", None)
        if projected is not None and owner_tool and owner_tool != "*":
            data["projected"] = _manager_snapshot(projected, str(owner_tool))
    except Exception:
        pass
    try:
        selection = getattr(ctx, "selection", None)
        state = getattr(selection, "state", None) if selection is not None else None
        if state is not None:
            data["selection"] = {
                "hover_id": _safe(getattr(state, "hover_id", None)),
                "grabbed_ids": _safe(tuple(getattr(state, "grabbed_ids", ()) or ())),
            }
    except Exception:
        pass
    return data


def _plotter_live_snapshot(owner: Any, owner_tool: str = "") -> dict[str, Any]:
    data: dict[str, Any] = {}
    if owner is None:
        return data
    try:
        plotter = getattr(owner, "plotter", None)
        data["plotter_type"] = type(plotter).__name__ if plotter is not None else None
        if plotter is None:
            return data
        actors = getattr(plotter, "actors", None)
        if isinstance(actors, dict):
            keys = [str(key) for key in actors.keys()]
            data["plotter_actor_count"] = len(keys)
            prefix = ""
            if owner_tool and owner_tool != "*":
                safe = "".join(ch if ch.isalnum() else "_" for ch in str(owner_tool))
                prefix = f"creator_ui_{safe}_"
            if prefix:
                matching = sorted(key for key in keys if key.startswith(prefix))
                data["creator_prefix"] = prefix
                data["creator_actor_count"] = len(matching)
                data["creator_actor_sample"] = matching[:16]
            data["plotter_actor_sample"] = sorted(keys)[:16]
        renderer = getattr(plotter, "renderer", None)
        data["renderer_type"] = type(renderer).__name__ if renderer is not None else None
        if renderer is not None:
            data["renderer_id"] = id(renderer)
            for method_name in ("GetSize", "GetOrigin", "GetNumberOfPropsRendered"):
                method = getattr(renderer, method_name, None)
                if callable(method):
                    try:
                        data[method_name] = _safe(method())
                    except Exception as exc:
                        data[method_name] = f"error:{type(exc).__name__}"
            get_view_props = getattr(renderer, "GetViewProps", None)
            if callable(get_view_props):
                try:
                    props = get_view_props()
                    get_count = getattr(props, "GetNumberOfItems", None)
                    if callable(get_count):
                        data["view_props_count"] = int(get_count())
                except Exception as exc:
                    data["view_props_count"] = f"error:{type(exc).__name__}"
    except Exception as exc:
        data["error"] = type(exc).__name__
    return data

def _manager_snapshot(manager: Any, owner_tool: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    try:
        snapshot = manager.snapshot(str(owner_tool))
        primitives = tuple(getattr(snapshot, "primitives", ()) or ())
        counts: dict[str, int] = {}
        samples: list[dict[str, Any]] = []
        for primitive in primitives:
            kind = str(getattr(getattr(primitive, "kind", None), "value", getattr(primitive, "kind", type(primitive).__name__)))
            counts[kind] = counts.get(kind, 0) + 1
            if len(samples) < 8:
                samples.append(
                    {
                        "id": str(getattr(primitive, "id", "")),
                        "type": type(primitive).__name__,
                        "kind": kind,
                        "visible": bool(getattr(primitive, "visible", True)),
                        "position": _safe(getattr(primitive, "position", None)),
                        "points": len(tuple(getattr(primitive, "points", ()) or ())) if hasattr(primitive, "points") else None,
                        "vertices": len(tuple(getattr(primitive, "vertices", ()) or ())) if hasattr(primitive, "vertices") else None,
                    }
                )
        data.update(
            {
                "owner_tool": str(owner_tool),
                "revision": int(getattr(snapshot, "revision", -1)),
                "visible": bool(getattr(snapshot, "visible", False)),
                "primitive_count": len(primitives),
                "primitive_counts": counts,
                "primitive_samples": samples,
            }
        )
    except Exception as exc:
        data["error"] = type(exc).__name__
    return data


def reset_projected_overlay_diagnostics(reason: str = "reset", *, owner: Any = None, ctx: Any = None, owner_tool: str = "") -> None:
    global _seq, _started
    if not _debug_enabled(owner):
        _seq = 0
        _started = False
        return
    _seq = 0
    _started = True
    path = projected_overlay_diagnostics_path()
    try:
        path.write_text("", encoding="utf-8")
    except Exception:
        return
    record_projected_overlay_event(
        "session.start",
        owner=owner,
        ctx=ctx,
        owner_tool=owner_tool,
        reason=reason,
        file=str(path),
        cwd=str(Path.cwd()),
    )


def record_projected_overlay_event(stage: str, *, owner: Any = None, ctx: Any = None, owner_tool: str = "", manager: Any = None, renderer: Any = None, error: BaseException | None = None, **payload: Any) -> None:
    global _seq, _started
    if not _debug_enabled(owner):
        return
    if _seq >= _MAX_EVENTS:
        return
    if not _started:
        _started = True
        try:
            projected_overlay_diagnostics_path().write_text("", encoding="utf-8")
        except Exception:
            pass
    _seq += 1
    entry: dict[str, Any] = {
        "seq": _seq,
        "at_s": round(time.monotonic(), 6),
        "stage": str(stage),
    }
    if owner_tool:
        entry["owner_tool"] = str(owner_tool)
    if owner is not None:
        entry["owner"] = _owner_snapshot(owner)
        entry["plotter_live"] = _plotter_live_snapshot(owner, str(owner_tool or ""))
    if ctx is not None:
        try:
            entry["ctx_owner_id"] = id(getattr(ctx, "owner", None)) if getattr(ctx, "owner", None) is not None else None
            entry["ctx_id"] = id(ctx)
        except Exception:
            pass
        try:
            entry["context"] = _context_snapshot(ctx, str(owner_tool or ""))
        except Exception:
            pass
        try:
            pd = getattr(ctx, "projected_drawing", None)
            if pd is not None and owner_tool:
                entry["manager"] = _manager_snapshot(pd, str(owner_tool))
        except Exception:
            pass
    if manager is not None and owner_tool:
        entry["manager"] = _manager_snapshot(manager, str(owner_tool))
    if renderer is not None:
        try:
            snapshot = getattr(renderer, "diagnostic_snapshot", None)
            if callable(snapshot):
                entry["renderer"] = _safe(snapshot())
            else:
                entry["renderer"] = {"type": type(renderer).__name__, "id": id(renderer)}
        except Exception as exc:
            entry["renderer"] = {"error": type(exc).__name__}
    if error is not None:
        entry["error"] = {"type": type(error).__name__, "message": str(error)[:500]}
    for key, value in payload.items():
        entry[str(key)] = _safe(value)
    try:
        projected_overlay_diagnostics_path().open("a", encoding="utf-8").write(
            json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        )
    except Exception:
        pass


def projected_overlay_renderer_snapshot(owner: Any, owner_tool: str) -> dict[str, Any]:
    try:
        store = getattr(owner, "_laserprog_projected_drawing_2d_renderers", None)
        if not isinstance(store, dict):
            return {"store": "missing", "owner_tool": str(owner_tool)}
        renderer = store.get(str(owner_tool))
        if renderer is None:
            return {"store": "present", "renderer": "missing", "keys": sorted(str(key) for key in store), "owner_tool": str(owner_tool)}
        snapshot = getattr(renderer, "diagnostic_snapshot", None)
        return dict(snapshot()) if callable(snapshot) else {"renderer": type(renderer).__name__, "owner_tool": str(owner_tool)}
    except Exception as exc:
        return {"error": type(exc).__name__, "owner_tool": str(owner_tool)}


__all__ = [
    "projected_overlay_diagnostics_path",
    "projected_overlay_renderer_snapshot",
    "record_projected_overlay_event",
    "reset_projected_overlay_diagnostics",
]

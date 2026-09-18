# -*- coding: utf-8 -*-
"""Debug-only diagnostics for global 3D boolean operations.

Normal editing performs no disk writes.  When the global diagnostics mode is
active, every boolean request records indexed topology, manifold3d status,
automatic repair attempts and the final result.  This prevents the UI from
collapsing unrelated failures into the old generic "solids are not closed"
message.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


def _enabled() -> bool:
    try:
        from laserprog_studio.services.debug_mode import should_record_diagnostics

        return bool(should_record_diagnostics())
    except Exception:
        return False


def boolean_diagnostics_path() -> Path:
    try:
        from laserprog_studio.bootstrap import compute_paths

        directory = compute_paths().diagnostics_dir
    except Exception:
        directory = Path.cwd() / "diagnostics"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / "boolean_debug.jsonl"


def _safe(value: Any, *, depth: int = 0) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if depth >= 4:
        return repr(value)
    if isinstance(value, dict):
        return {str(key): _safe(item, depth=depth + 1) for key, item in list(value.items())[:100]}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_safe(item, depth=depth + 1) for item in list(value)[:100]]
    try:
        return str(value.value)
    except Exception:
        return repr(value)


def record_boolean_event(stage: str, **payload: Any) -> None:
    if not _enabled():
        return
    event = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "perf_s": round(time.perf_counter(), 6),
        "stage": str(stage),
    }
    event.update({str(key): _safe(value) for key, value in payload.items()})
    try:
        with boolean_diagnostics_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


__all__ = ["boolean_diagnostics_path", "record_boolean_event"]

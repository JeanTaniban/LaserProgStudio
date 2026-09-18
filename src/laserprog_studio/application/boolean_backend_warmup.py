# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from typing import Any

_started = False
_lock = threading.Lock()
_last_error: str | None = None
_state = "idle"


def _cube_mesh(name: str, x0: float, x1: float):
    from laserprog_studio.domain.work_model import WorkMesh

    vertices = [
        (x0, 0.0, 0.0), (x1, 0.0, 0.0), (x1, 1.0, 0.0), (x0, 1.0, 0.0),
        (x0, 0.0, 1.0), (x1, 0.0, 1.0), (x1, 1.0, 1.0), (x0, 1.0, 1.0),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    return WorkMesh(name=name, vertices=vertices, triangles=triangles, color="#B8B8B8")


def warm_boolean_backend() -> None:
    """Load and lightly exercise the boolean backend before first user action.

    The first call into manifold/boolean code can pay a one-time import and C++
    initialization cost on some machines.  Running tiny closed-mesh booleans on a
    daemon thread moves that cost out of the first visible user operation while
    avoiding the heavy trimesh/PyVista repair path.
    """
    global _last_error, _state
    _state = "warming"
    try:
        # Import the same public path used by tools.cube_boolean.
        from laserprog_studio.boolean_ops import boolean_mesh_3d

        a = _cube_mesh("warmup_a", 0.0, 1.0)
        b = _cube_mesh("warmup_b", 0.5, 1.5)
        for operation in ("union", "difference"):
            try:
                boolean_mesh_3d(a, b, operation=operation)
            except Exception:
                # A failing backend should not break app startup.  The real operation
                # will still show the normal user-facing boolean error later.
                pass
        _last_error = None
        _state = "ready"
    except Exception as exc:  # pragma: no cover - defensive optional dependency path
        _last_error = str(exc)
        _state = "failed"


def start_boolean_backend_warmup(owner: Any | None = None) -> bool:
    """Start the one-shot warmup thread. Return True only for the first call."""
    global _started
    with _lock:
        if _started:
            return False
        _started = True
    thread = threading.Thread(target=warm_boolean_backend, name="LPSBooleanWarmup", daemon=True)
    thread.start()
    try:
        if owner is not None and bool(getattr(owner, "_diagnostic_verbose", False)):
            owner.ui_log("[PERF] Boolean backend warmup scheduled")
    except Exception:
        pass
    return True


def boolean_backend_warmup_status() -> tuple[bool, str | None]:
    return _started, _last_error


def boolean_backend_warmup_state() -> str:
    return _state


__all__ = ["start_boolean_backend_warmup", "warm_boolean_backend", "boolean_backend_warmup_status", "boolean_backend_warmup_state"]

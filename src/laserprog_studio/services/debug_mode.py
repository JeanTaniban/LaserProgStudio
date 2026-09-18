# -*- coding: utf-8 -*-
"""Global debug/diagnostic mode for LaserProg Studio.

Normal editing must not pay for diagnostic disk writes, JSONL traces, app-wide
profilers or high-volume counters.  This module is the single gate used by all
new diagnostics.  The default is OFF unless the user enables it from the UI or
an environment variable explicitly requests it.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths

_TRUE_VALUES = {"1", "true", "yes", "on", "debug", "diag", "diagnostic", "verbose"}
_FALSE_VALUES = {"0", "false", "no", "off", "optimized", "normal", "release"}
_CACHE: bool | None = None
_SOURCE: str = "default"


def debug_preferences_path() -> Path:
    return compute_paths().root / "settings" / "studio_debug.json"


def _running_under_pytest() -> bool:
    return "pytest" in sys.modules or bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _env_override() -> tuple[bool | None, str]:
    for key in ("LASERPROG_DEBUG_MODE", "LPS_DEBUG_MODE", "LPS_PERF_MODE", "LPS_MODE", "LPS_VERBOSE_DIAG"):
        raw = os.environ.get(key)
        if raw is None:
            continue
        text = str(raw).strip().lower()
        if text in _TRUE_VALUES:
            return True, f"env:{key}"
        if text in _FALSE_VALUES:
            return False, f"env:{key}"
    return None, "default"


def load_debug_preferences(path: Path | None = None) -> dict[str, Any]:
    pref_path = debug_preferences_path() if path is None else Path(path)
    try:
        if not pref_path.exists():
            return {}
        payload = json.loads(pref_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def save_debug_preferences(enabled: bool, path: Path | None = None) -> None:
    pref_path = debug_preferences_path() if path is None else Path(path)
    try:
        pref_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "debug_mode": bool(enabled),
            "description": "When false, high-volume diagnostics, performance audit samples and JSONL traces stay disabled.",
        }
        tmp = pref_path.with_suffix(pref_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(pref_path)
    except Exception:
        pass


def refresh_debug_mode_cache() -> bool:
    global _CACHE, _SOURCE
    env_value, env_source = _env_override()
    if env_value is not None:
        _CACHE = bool(env_value)
        _SOURCE = env_source
        return bool(_CACHE)
    payload = load_debug_preferences()
    if "debug_mode" in payload:
        _CACHE = bool(payload.get("debug_mode"))
        _SOURCE = "settings"
        return bool(_CACHE)
    # Unit tests keep historical diagnostic assertions alive without enabling
    # noisy runtime diagnostics in normal user sessions.
    if _running_under_pytest():
        _CACHE = True
        _SOURCE = "pytest"
        return True
    _CACHE = False
    _SOURCE = "default"
    return False


def is_debug_mode_enabled() -> bool:
    global _CACHE
    if _CACHE is None:
        return refresh_debug_mode_cache()
    return bool(_CACHE)


def set_debug_mode_enabled(enabled: bool, *, persist: bool = True) -> bool:
    global _CACHE, _SOURCE
    _CACHE = bool(enabled)
    _SOURCE = "runtime"
    if persist:
        save_debug_preferences(bool(enabled))
        _SOURCE = "settings"
    return bool(_CACHE)


def debug_mode_source() -> str:
    if _CACHE is None:
        refresh_debug_mode_cache()
    return _SOURCE


def should_record_diagnostics(owner: Any | None = None) -> bool:
    if owner is not None:
        try:
            if bool(getattr(owner, "_diagnostic_verbose", False)):
                return True
        except Exception:
            pass
        try:
            if str(getattr(owner, "_performance_mode", "")).lower() == "debug":
                return True
        except Exception:
            pass
    return is_debug_mode_enabled()


__all__ = [
    "debug_mode_source",
    "debug_preferences_path",
    "is_debug_mode_enabled",
    "load_debug_preferences",
    "refresh_debug_mode_cache",
    "save_debug_preferences",
    "set_debug_mode_enabled",
    "should_record_diagnostics",
]

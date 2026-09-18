# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths


def _persistence_disabled() -> bool:
    value = os.environ.get("LASERPROG_DISABLE_TOOL_PARAMETER_PERSISTENCE", "")
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def preferences_dir() -> Path:
    override = os.environ.get("LASERPROG_TOOL_PARAMETER_PREFERENCES")
    if override:
        path = Path(override).expanduser().resolve().parent
    else:
        path = compute_paths().root / "settings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tool_parameter_preferences_path() -> Path:
    override = os.environ.get("LASERPROG_TOOL_PARAMETER_PREFERENCES")
    if override:
        return Path(override).expanduser().resolve()
    return preferences_dir() / "studio_tool_parameters.json"


def _read_payload(path: Path | None = None) -> dict[str, Any]:
    path = tool_parameter_preferences_path() if path is None else Path(path)
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_payload(payload: dict[str, Any], path: Path | None = None) -> None:
    path = tool_parameter_preferences_path() if path is None else Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # Tool parameter persistence is a comfort feature: never break the tool.
        pass


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    return str(value)


def load_tool_parameters(tool_key: str, *, path: Path | None = None) -> dict[str, Any]:
    if path is None and _persistence_disabled():
        return {}
    key = str(tool_key or "").strip()
    if not key:
        return {}
    payload = _read_payload(path)
    tools = payload.get("tools", {})
    if not isinstance(tools, dict):
        return {}
    values = tools.get(key, {})
    return dict(values) if isinstance(values, dict) else {}


def save_tool_parameters(tool_key: str, values: dict[str, Any], *, path: Path | None = None) -> None:
    if path is None and _persistence_disabled():
        return
    key = str(tool_key or "").strip()
    if not key:
        return
    payload = _read_payload(path)
    tools = payload.get("tools", {})
    if not isinstance(tools, dict):
        tools = {}
    current = tools.get(key, {})
    if not isinstance(current, dict):
        current = {}
    for field_id, value in dict(values or {}).items():
        current[str(field_id)] = _json_safe(value)
    tools[key] = current
    payload["schema_version"] = 1
    payload["tools"] = tools
    _write_payload(payload, path)


__all__ = [
    "load_tool_parameters",
    "save_tool_parameters",
    "tool_parameter_preferences_path",
]

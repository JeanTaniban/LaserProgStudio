# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths


_FALSE_VALUES = {"0", "false", "no", "off", "disabled"}
_TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}


@dataclass(frozen=True)
class AppearancePreferences:
    """Application-wide appearance settings.

    ``force_dark_mode`` defaults to ``True`` on purpose: LaserProg keeps a
    deterministic dark Qt UI even when Windows asks applications to use a light
    color scheme.  Native system file dialogs default to enabled because they
    are roomier and more familiar for Open, Save and Export workflows.
    """

    force_dark_mode: bool = True
    use_native_dialogs: bool = True


def preferences_dir() -> Path:
    path = compute_paths().root / "settings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def appearance_preferences_path() -> Path:
    return preferences_dir() / "studio_appearance.json"


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in _TRUE_VALUES:
        return True
    if text in _FALSE_VALUES:
        return False
    return bool(default)


def _environment_override(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return bool(default)
    return _coerce_bool(value, default)


def load_appearance_preferences(path: Path | None = None) -> AppearancePreferences:
    path = appearance_preferences_path() if path is None else Path(path)
    payload: dict[str, Any] = {}
    try:
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload = raw
    except Exception:
        payload = {}

    force_dark = _coerce_bool(payload.get("force_dark_mode"), True)
    native_dialogs = _coerce_bool(payload.get("use_native_dialogs"), True)

    # Explicit process overrides are useful for diagnostics and automated tests.
    force_dark = _environment_override("LPS_FORCE_DARK_MODE", force_dark)
    native_dialogs = _environment_override("LPS_USE_NATIVE_DIALOGS", native_dialogs)

    preferences = AppearancePreferences(
        force_dark_mode=force_dark,
        use_native_dialogs=native_dialogs,
    )
    ensure_appearance_preferences_file(preferences, path=path)
    return preferences


def save_appearance_preferences(preferences: AppearancePreferences, path: Path | None = None) -> None:
    """Persist application appearance preferences.

    File dialog mode is read before QApplication is created, so changing the
    native-dialog preference usually takes effect after restart.
    """

    path = appearance_preferences_path() if path is None else Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "force_dark_mode": bool(preferences.force_dark_mode),
            "use_native_dialogs": bool(preferences.use_native_dialogs),
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        pass


def ensure_appearance_preferences_file(
    preferences: AppearancePreferences | None = None,
    *,
    path: Path | None = None,
) -> None:
    path = appearance_preferences_path() if path is None else Path(path)
    preferences = preferences or AppearancePreferences()
    try:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "force_dark_mode": bool(preferences.force_dark_mode),
            "use_native_dialogs": bool(preferences.use_native_dialogs),
        }
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # Appearance persistence must never prevent the editor from starting.
        pass


__all__ = [
    "AppearancePreferences",
    "appearance_preferences_path",
    "ensure_appearance_preferences_file",
    "load_appearance_preferences",
    "save_appearance_preferences",
]

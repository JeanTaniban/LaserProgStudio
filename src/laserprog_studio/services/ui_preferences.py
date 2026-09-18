# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths


def preferences_dir() -> Path:
    path = compute_paths().root / "settings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ui_layout_preferences_path() -> Path:
    return preferences_dir() / "studio_ui_layout.json"


def load_ui_layout_preferences(path: Path | None = None) -> dict[str, Any]:
    path = ui_layout_preferences_path() if path is None else Path(path)
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def save_ui_layout_preferences(state: Any, path: Path | None = None) -> None:
    path = ui_layout_preferences_path() if path is None else Path(path)
    try:
        if is_dataclass(state):
            payload = asdict(state)
        else:
            payload = dict(getattr(state, "__dict__", {}) or {})
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # Layout persistence is a comfort feature; never break the editor for it.
        pass

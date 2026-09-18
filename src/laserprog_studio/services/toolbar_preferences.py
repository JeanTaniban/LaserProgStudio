# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths


def preferences_dir() -> Path:
    path = compute_paths().root / "settings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def toolbar_preferences_path() -> Path:
    return preferences_dir() / "studio_toolbar.json"


def load_toolbar_preferences(path: Path | None = None) -> dict[str, Any]:
    path = toolbar_preferences_path() if path is None else Path(path)
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def save_toolbar_preferences(
    item_ids: list[str] | tuple[str, ...],
    *,
    registry_version: int,
    max_items: int,
    path: Path | None = None,
) -> None:
    path = toolbar_preferences_path() if path is None else Path(path)
    try:
        payload = {
            "toolbar_item_ids": [str(v) for v in list(item_ids or [])],
            "toolbar_registry_version": int(registry_version),
            "toolbar_max_items": int(max_items),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        # Toolbar persistence is a comfort feature; never break the editor for it.
        pass

# -*- coding: utf-8 -*-
"""Persistent user prefabs for Plan Tracer 2D Duplicate."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from laserprog_studio.bootstrap import compute_paths

from .selection_edit import SketchPayload

PREFAB_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class PlanTracePrefab:
    id: str
    name: str
    payload: SketchPayload


def prefab_store_path() -> Path:
    path = compute_paths().root / "settings" / "plan_trace_2d_prefabs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _clean_name(value: Any) -> str:
    return " ".join(str(value or "").strip().split())[:80]


def _prefab_id(name: str) -> str:
    return "user:" + _clean_name(name).casefold()


def load_prefabs(path: Path | None = None) -> tuple[PlanTracePrefab, ...]:
    target = prefab_store_path() if path is None else Path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except Exception:
        return ()
    rows = raw.get("prefabs", ()) if isinstance(raw, dict) else ()
    result: dict[str, PlanTracePrefab] = {}
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict):
            continue
        name = _clean_name(row.get("name"))
        payload = SketchPayload.from_dict(row.get("payload") if isinstance(row.get("payload"), Mapping) else {})
        if not name or payload.is_empty:
            continue
        item = PlanTracePrefab(_prefab_id(name), name, payload)
        result[item.id] = item
    return tuple(sorted(result.values(), key=lambda item: item.name.casefold()))


def save_prefab(name: str, payload: SketchPayload, path: Path | None = None) -> PlanTracePrefab:
    clean_name = _clean_name(name)
    if not clean_name:
        raise ValueError("Prefab name is required.")
    if payload.is_empty:
        raise ValueError("Prefab geometry is empty.")
    target = prefab_store_path() if path is None else Path(path)
    item = PlanTracePrefab(_prefab_id(clean_name), clean_name, payload)
    by_id = {existing.id: existing for existing in load_prefabs(target)}
    by_id[item.id] = item
    _write_prefabs(tuple(by_id.values()), target)
    return item


def rename_prefab(prefab_id: str, new_name: str, path: Path | None = None) -> PlanTracePrefab:
    """Rename one stored prefab atomically without changing its geometry.

    Prefab ids are derived from their display name for backward compatibility
    with the existing schema.  Renaming therefore updates both the visible name
    and id while refusing to silently overwrite a different catalog entry.
    """

    target = prefab_store_path() if path is None else Path(path)
    clean_name = _clean_name(new_name)
    if not clean_name:
        raise ValueError("Prefab name is required.")
    existing = list(load_prefabs(target))
    source = next((item for item in existing if item.id == str(prefab_id)), None)
    if source is None:
        raise ValueError("The selected prefab no longer exists.")
    renamed = PlanTracePrefab(_prefab_id(clean_name), clean_name, source.payload)
    conflict = next((item for item in existing if item.id == renamed.id and item.id != source.id), None)
    if conflict is not None:
        raise ValueError(f"A prefab named '{clean_name}' already exists.")
    remaining = [item for item in existing if item.id != source.id]
    remaining.append(renamed)
    _write_prefabs(tuple(remaining), target)
    return renamed


def delete_prefab(prefab_id: str, path: Path | None = None) -> bool:
    target = prefab_store_path() if path is None else Path(path)
    existing = list(load_prefabs(target))
    remaining = [item for item in existing if item.id != str(prefab_id)]
    if len(remaining) == len(existing):
        return False
    _write_prefabs(tuple(remaining), target)
    return True


def _write_prefabs(items: tuple[PlanTracePrefab, ...], path: Path) -> None:
    payload = {
        "schema_version": PREFAB_SCHEMA_VERSION,
        "prefabs": [
            {"name": item.name, "payload": item.payload.to_dict()}
            for item in sorted(items, key=lambda value: value.name.casefold())
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


__all__ = [
    "PlanTracePrefab",
    "delete_prefab",
    "load_prefabs",
    "rename_prefab",
    "prefab_store_path",
    "save_prefab",
]

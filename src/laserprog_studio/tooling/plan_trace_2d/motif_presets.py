# -*- coding: utf-8 -*-
"""Persistent named presets for the Plan Tracer 2D Pattern editor."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

from laserprog_studio.bootstrap import compute_paths


PRESET_SCHEMA_VERSION = 1
CUSTOM_PRESET_ID = "__custom__"
_PATTERN_PARAMETER_KEYS: tuple[str, ...] = (
    "cell_size",
    "wall",
    "margin",
    "keep_form",
    "angle",
    "aspect",
    "seed",
    "offset_x",
    "offset_y",
)


@dataclass(frozen=True, slots=True)
class MotifPreset:
    """One user-authored Pattern preset."""

    id: str
    name: str
    kind: str
    parameters: dict[str, float | int | bool]


def motif_presets_path() -> Path:
    path = compute_paths().root / "settings" / "plan_trace_2d_pattern_presets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _preset_id(name: str) -> str:
    # Case-insensitive identity means saving "Grille fine" again updates the
    # existing preset instead of creating visually indistinguishable duplicates.
    return "user:" + " ".join(str(name).strip().split()).casefold()


def _clean_name(name: Any) -> str:
    return " ".join(str(name or "").strip().split())[:80]


def _clean_parameters(values: Mapping[str, Any] | None) -> dict[str, float | int | bool]:
    source = dict(values or {})
    cleaned: dict[str, float | int | bool] = {}
    for key in _PATTERN_PARAMETER_KEYS:
        if key not in source:
            continue
        value = source[key]
        try:
            if key == "keep_form":
                cleaned[key] = bool(value)
            elif key == "seed":
                cleaned[key] = max(0, int(float(value)))
            else:
                cleaned[key] = float(value)
        except Exception:
            continue
    return cleaned


def load_motif_presets(path: Path | None = None) -> tuple[MotifPreset, ...]:
    target = motif_presets_path() if path is None else Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return ()
    except Exception:
        return ()
    rows = payload.get("presets", ()) if isinstance(payload, dict) else ()
    result: dict[str, MotifPreset] = {}
    for row in rows if isinstance(rows, list) else ():
        if not isinstance(row, dict):
            continue
        name = _clean_name(row.get("name"))
        kind = str(row.get("kind") or "").strip()
        if not name or not kind:
            continue
        preset_id = _preset_id(name)
        result[preset_id] = MotifPreset(
            id=preset_id,
            name=name,
            kind=kind,
            parameters=_clean_parameters(row.get("parameters") if isinstance(row.get("parameters"), dict) else {}),
        )
    return tuple(sorted(result.values(), key=lambda item: item.name.casefold()))


def save_motif_preset(
    name: str,
    *,
    kind: str,
    parameters: Mapping[str, Any],
    path: Path | None = None,
) -> MotifPreset:
    target = motif_presets_path() if path is None else Path(path)
    clean_name = _clean_name(name)
    if not clean_name:
        raise ValueError("Preset name is required.")
    clean_kind = str(kind or "").strip()
    if not clean_kind:
        raise ValueError("Pattern kind is required.")
    preset = MotifPreset(
        id=_preset_id(clean_name),
        name=clean_name,
        kind=clean_kind,
        parameters=_clean_parameters(parameters),
    )
    by_id = {item.id: item for item in load_motif_presets(target)}
    by_id[preset.id] = preset
    _write_presets(tuple(by_id.values()), target)
    return preset


def delete_motif_preset(preset_id: str, path: Path | None = None) -> bool:
    target = motif_presets_path() if path is None else Path(path)
    requested = str(preset_id or "")
    presets = list(load_motif_presets(target))
    remaining = [preset for preset in presets if preset.id != requested]
    if len(remaining) == len(presets):
        return False
    _write_presets(tuple(remaining), target)
    return True


def _write_presets(presets: tuple[MotifPreset, ...], path: Path) -> None:
    payload = {
        "schema_version": PRESET_SCHEMA_VERSION,
        "presets": [
            {
                "name": preset.name,
                "kind": preset.kind,
                "parameters": dict(preset.parameters),
            }
            for preset in sorted(presets, key=lambda item: item.name.casefold())
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


__all__ = [
    "CUSTOM_PRESET_ID",
    "MotifPreset",
    "delete_motif_preset",
    "load_motif_presets",
    "motif_presets_path",
    "save_motif_preset",
]

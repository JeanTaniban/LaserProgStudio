# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths


@dataclass(frozen=True)
class LaserEngravingPreferences:
    """Workshop defaults used by the scene and context actions."""

    default_board_thickness_mm: float = 3.0
    machine_area_x_mm: float = 358.0
    machine_area_y_mm: float = 268.0
    show_machine_area: bool = True
    primitive_board_x_mm: float = 200.0
    primitive_board_y_mm: float = 100.0
    boolean_subtract_margin_mm: float = 0.0
    plan_tracer_pattern_max_segments: int = 120000


@dataclass(frozen=True)
class KeyboardShortcutsPreferences:
    """Configurable high-frequency shortcuts used in the modeling viewport."""

    toolbar_modifier: str = "shift"
    transform_cycle_key: str = "tab"
    preview_apply_key: str = "left_alt"
    hold_threshold_s: float = 0.5
    multi_press_window_s: float = 0.65


@dataclass(frozen=True)
class ProjectPreferences:
    schema_version: int = 1
    laser: LaserEngravingPreferences = LaserEngravingPreferences()
    shortcuts: KeyboardShortcutsPreferences = KeyboardShortcutsPreferences()
    autosave_enabled: bool = True
    autosave_interval_s: int = 10
    default_floor_grid_step_mm: float = 10.0


def preferences_dir() -> Path:
    path = compute_paths().root / "settings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_preferences_path() -> Path:
    return preferences_dir() / "studio_project_preferences.json"


def _float(value: Any, default: float, *, minimum: float = 0.001, maximum: float = 100_000.0) -> float:
    try:
        v = float(value)
        if not (minimum <= v <= maximum):
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _int(value: Any, default: int, *, minimum: int = 1, maximum: int = 86_400) -> int:
    try:
        v = int(float(value))
        if not (minimum <= v <= maximum):
            return int(default)
        return int(v)
    except Exception:
        return int(default)


def _choice(value: Any, default: str, choices: set[str]) -> str:
    text = str(value or "").strip().lower()
    return text if text in choices else str(default)


def _bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled"}:
        return False
    return bool(default)


def _read_payload(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    return {}


def coerce_project_preferences(payload: dict[str, Any] | None) -> ProjectPreferences:
    payload = payload if isinstance(payload, dict) else {}
    laser_raw = payload.get("laser", {})
    if not isinstance(laser_raw, dict):
        laser_raw = {}
    defaults = ProjectPreferences()
    laser_defaults = defaults.laser
    laser = LaserEngravingPreferences(
        default_board_thickness_mm=_float(
            laser_raw.get("default_board_thickness_mm"),
            laser_defaults.default_board_thickness_mm,
            minimum=0.05,
            maximum=2000.0,
        ),
        machine_area_x_mm=_float(laser_raw.get("machine_area_x_mm"), laser_defaults.machine_area_x_mm, minimum=1.0),
        machine_area_y_mm=_float(laser_raw.get("machine_area_y_mm"), laser_defaults.machine_area_y_mm, minimum=1.0),
        show_machine_area=_bool(laser_raw.get("show_machine_area"), laser_defaults.show_machine_area),
        primitive_board_x_mm=_float(laser_raw.get("primitive_board_x_mm"), laser_defaults.primitive_board_x_mm, minimum=1.0),
        primitive_board_y_mm=_float(laser_raw.get("primitive_board_y_mm"), laser_defaults.primitive_board_y_mm, minimum=1.0),
        boolean_subtract_margin_mm=_float(
            laser_raw.get("boolean_subtract_margin_mm"),
            laser_defaults.boolean_subtract_margin_mm,
            minimum=-1000.0,
            maximum=1000.0,
        ),
        plan_tracer_pattern_max_segments=_int(
            laser_raw.get("plan_tracer_pattern_max_segments"),
            laser_defaults.plan_tracer_pattern_max_segments,
            minimum=1000,
            maximum=1_000_000,
        ),
    )
    shortcuts_raw = payload.get("shortcuts", {})
    if not isinstance(shortcuts_raw, dict):
        shortcuts_raw = {}
    shortcut_defaults = defaults.shortcuts
    shortcuts = KeyboardShortcutsPreferences(
        toolbar_modifier=_choice(shortcuts_raw.get("toolbar_modifier"), shortcut_defaults.toolbar_modifier, {"shift"}),
        transform_cycle_key=_choice(shortcuts_raw.get("transform_cycle_key"), shortcut_defaults.transform_cycle_key, {"tab", "space"}),
        preview_apply_key=_choice(shortcuts_raw.get("preview_apply_key"), shortcut_defaults.preview_apply_key, {"left_alt", "space"}),
        hold_threshold_s=_float(shortcuts_raw.get("hold_threshold_s"), shortcut_defaults.hold_threshold_s, minimum=0.2, maximum=2.0),
        multi_press_window_s=_float(shortcuts_raw.get("multi_press_window_s"), shortcut_defaults.multi_press_window_s, minimum=0.1, maximum=2.0),
    )
    return ProjectPreferences(
        schema_version=1,
        laser=laser,
        shortcuts=shortcuts,
        autosave_enabled=_bool(payload.get("autosave_enabled"), defaults.autosave_enabled),
        autosave_interval_s=_int(payload.get("autosave_interval_s"), defaults.autosave_interval_s, minimum=3, maximum=3600),
        default_floor_grid_step_mm=_float(payload.get("default_floor_grid_step_mm"), defaults.default_floor_grid_step_mm, minimum=0.5, maximum=1000.0),
    )


def _payload_from_preferences(preferences: ProjectPreferences) -> dict[str, Any]:
    payload = asdict(preferences)
    payload["schema_version"] = 1
    return payload


def save_project_preferences(preferences: ProjectPreferences, path: Path | None = None) -> None:
    pref_path = project_preferences_path() if path is None else Path(path)
    try:
        pref_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = pref_path.with_suffix(pref_path.suffix + ".tmp")
        tmp.write_text(json.dumps(_payload_from_preferences(preferences), indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(pref_path)
    except Exception:
        pass


def load_project_preferences(path: Path | None = None) -> ProjectPreferences:
    pref_path = project_preferences_path() if path is None else Path(path)
    prefs = coerce_project_preferences(_read_payload(pref_path))
    ensure_project_preferences_file(prefs, path=pref_path)
    return prefs


def ensure_project_preferences_file(preferences: ProjectPreferences | None = None, *, path: Path | None = None) -> None:
    pref_path = project_preferences_path() if path is None else Path(path)
    try:
        if pref_path.exists():
            return
        save_project_preferences(preferences or ProjectPreferences(), path=pref_path)
    except Exception:
        pass


__all__ = [
    "KeyboardShortcutsPreferences",
    "LaserEngravingPreferences",
    "ProjectPreferences",
    "coerce_project_preferences",
    "ensure_project_preferences_file",
    "load_project_preferences",
    "project_preferences_path",
    "save_project_preferences",
]

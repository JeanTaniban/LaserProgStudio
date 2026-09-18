# -*- coding: utf-8 -*-
"""Product presets for the built-in Creator UI/Gizmo catalog."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from laserprog_studio.tool_api.ui_motifs import OFFICIAL_CREATOR_UI_MOTIF_FAMILIES

CUSTOM_PRESET_ID = "custom"
ALL_PRESET_ID = "all"
HIDDEN_PRESET_ID = "hidden"


@dataclass(frozen=True, slots=True)
class GizmoCatalogViewPreset:
    """One user-facing catalog view preset."""

    id: str
    label: str
    description: str
    families: tuple[str, ...] | None = None

    def visible_by_family(self, families: Iterable[str] = OFFICIAL_CREATOR_UI_MOTIF_FAMILIES) -> dict[str, bool]:
        if self.families is None:
            return {str(family): True for family in families}
        visible = set(self.families)
        return {str(family): str(family) in visible for family in families}


_GIZMO_CATALOG_PRESETS: tuple[GizmoCatalogViewPreset, ...] = (
    GizmoCatalogViewPreset(
        ALL_PRESET_ID,
        "All motifs",
        "Show every official Creator UI family.",
        None,
    ),
    GizmoCatalogViewPreset(
        "tool_author",
        "Tool author essentials",
        "Focus on actors, interactions, point styles, line styles and previews used by most tools.",
        ("actor_kinds", "actor_interactions", "point_styles", "line_styles", "previews"),
    ),
    GizmoCatalogViewPreset(
        "interaction_tuning",
        "Interaction tuning",
        "Inspect hover, selected, grabbed and manipulator behaviour without preview/overlay noise.",
        ("actor_interactions", "visual_states", "point_styles", "line_styles", "manipulators"),
    ),
    GizmoCatalogViewPreset(
        "viewport_feedback",
        "Viewport feedback",
        "Review preview primitives and overlay windows for user-facing tool feedback.",
        ("previews", "overlays"),
    ),
    GizmoCatalogViewPreset(
        HIDDEN_PRESET_ID,
        "Clean viewport",
        "Hide all families without destroying the catalog scene; useful before a focused toggle test.",
        (),
    ),
    GizmoCatalogViewPreset(
        CUSTOM_PRESET_ID,
        "Custom",
        "Manual family selection.",
        (),
    ),
)


def iter_gizmo_catalog_view_presets() -> tuple[GizmoCatalogViewPreset, ...]:
    """Return user-facing catalog view presets in display order."""

    return _GIZMO_CATALOG_PRESETS


def gizmo_catalog_view_preset_choices() -> tuple[tuple[str, str], ...]:
    """Return inspector-ready choices for the catalog view selector."""

    return tuple((preset.id, preset.label) for preset in _GIZMO_CATALOG_PRESETS)


def get_gizmo_catalog_view_preset(preset_id: str) -> GizmoCatalogViewPreset:
    """Return a catalog view preset, falling back to Custom."""

    cleaned = str(preset_id).strip() or CUSTOM_PRESET_ID
    for preset in _GIZMO_CATALOG_PRESETS:
        if preset.id == cleaned:
            return preset
    return get_gizmo_catalog_view_preset(CUSTOM_PRESET_ID)


def detect_gizmo_catalog_view_preset(visible_by_family: dict[str, bool]) -> GizmoCatalogViewPreset:
    """Return the exact preset matching the current visibility, or Custom.

    Accept both raw family ids (``previews``) and inspector field ids
    (``show_previews``) so tests/tools can pass the whole inspector values map.
    """

    official = tuple(str(family) for family in OFFICIAL_CREATOR_UI_MOTIF_FAMILIES)
    normalized = {
        family: bool(visible_by_family.get(family, visible_by_family.get(f"show_{family}", False)))
        for family in official
    }
    for preset in _GIZMO_CATALOG_PRESETS:
        if preset.id == CUSTOM_PRESET_ID:
            continue
        if preset.visible_by_family(official) == normalized:
            return preset
    return get_gizmo_catalog_view_preset(CUSTOM_PRESET_ID)


__all__ = [
    "ALL_PRESET_ID",
    "CUSTOM_PRESET_ID",
    "GizmoCatalogViewPreset",
    "HIDDEN_PRESET_ID",
    "detect_gizmo_catalog_view_preset",
    "get_gizmo_catalog_view_preset",
    "gizmo_catalog_view_preset_choices",
    "iter_gizmo_catalog_view_presets",
]

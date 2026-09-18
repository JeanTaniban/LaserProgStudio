"""Shared contract for official Creator UI motifs.

This module contains stable identifiers and tiny data structures shared by the
public :mod:`tool_api.ui_motifs` facade and the private motif runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .ui_catalog import CreatorUiFamilyId, iter_creator_ui_families

Point3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class CreatorUiMotifSnapshot:
    """Counts produced by the public Tool Core Analysis motif builder."""

    owner_tool: str
    families: tuple[str, ...]
    actors: int
    handles: int
    previews: int
    labels: int
    overlay_windows: int


FAMILY_ACTOR_KINDS = CreatorUiFamilyId.ACTOR_KINDS.value
FAMILY_ACTOR_INTERACTIONS = CreatorUiFamilyId.ACTOR_INTERACTIONS.value
FAMILY_VISUAL_STATES = CreatorUiFamilyId.VISUAL_STATES.value
FAMILY_POINT_STYLES = CreatorUiFamilyId.POINT_STYLES.value
FAMILY_LINE_STYLES = CreatorUiFamilyId.LINE_STYLES.value
FAMILY_MANIPULATORS = CreatorUiFamilyId.MANIPULATORS.value
FAMILY_PREVIEWS = CreatorUiFamilyId.PREVIEWS.value
FAMILY_OVERLAYS = CreatorUiFamilyId.OVERLAYS.value

OFFICIAL_CREATOR_UI_MOTIF_FAMILIES: tuple[str, ...] = tuple(family.id for family in iter_creator_ui_families())
API_UI_VISIBLE_METADATA_KEY = "api_ui_visible"


def normalize_creator_ui_motif_families(families: Iterable[str] | None = None) -> tuple[str, ...]:
    """Return official motif family ids, preserving requested order."""

    if families is None:
        return OFFICIAL_CREATOR_UI_MOTIF_FAMILIES
    official = set(OFFICIAL_CREATOR_UI_MOTIF_FAMILIES)
    result: list[str] = []
    for family in families:
        value = str(getattr(family, "value", family)).strip().lower()
        if value in official and value not in result:
            result.append(value)
    return tuple(result)


__all__ = [
    "API_UI_VISIBLE_METADATA_KEY",
    "CreatorUiMotifSnapshot",
    "FAMILY_ACTOR_INTERACTIONS",
    "FAMILY_ACTOR_KINDS",
    "FAMILY_LINE_STYLES",
    "FAMILY_MANIPULATORS",
    "FAMILY_OVERLAYS",
    "FAMILY_POINT_STYLES",
    "FAMILY_PREVIEWS",
    "FAMILY_VISUAL_STATES",
    "OFFICIAL_CREATOR_UI_MOTIF_FAMILIES",
    "Point3",
    "normalize_creator_ui_motif_families",
]

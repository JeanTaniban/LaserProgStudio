# -*- coding: utf-8 -*-
"""Small reporting helpers for the built-in Creator UI/Gizmo catalog."""
from __future__ import annotations

from typing import Iterable

from laserprog_studio.tool_api.ui_catalog import CreatorUiFamily


def catalog_family_count_report(families: Iterable[CreatorUiFamily]) -> str:
    """Return a compact product-facing count report for all UI families."""

    parts = [f"{family.label}: {len(family.items)}" for family in families]
    return " · ".join(parts)


def catalog_visibility_report(families: Iterable[CreatorUiFamily], visible_by_family: dict[str, bool]) -> str:
    """Return a readable list of visible families."""

    visible = [family.label for family in families if visible_by_family.get(family.id, False)]
    return "Visible: " + (", ".join(visible) if visible else "none")


def catalog_focus_report(families: Iterable[CreatorUiFamily], visible_by_family: dict[str, bool]) -> str:
    """Return a concise active/hidden family count summary."""

    all_families = tuple(families)
    active = sum(1 for family in all_families if visible_by_family.get(family.id, False))
    hidden = max(0, len(all_families) - active)
    return f"{active} active families · {hidden} hidden"


__all__ = ["catalog_family_count_report", "catalog_focus_report", "catalog_visibility_report"]

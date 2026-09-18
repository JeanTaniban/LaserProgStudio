# -*- coding: utf-8 -*-
"""Canonical action identifiers for Cloth's single-overlay workflow."""
from __future__ import annotations

from enum import Enum


class ClothAction(str, Enum):
    TAKE_FACE = "take_face"
    OPEN_CLOSURE = "open_closure"
    OPEN_DRAW = "open_draw"
    OPEN_PROPERTIES = "open_properties"
    APPLY_OUTPUT = "apply_output"
    APPLY_CLOSURE = "apply_closure"
    PREVIOUS_CLOSURE = "previous_closure"
    NEXT_CLOSURE = "next_closure"
    RESET_CLOSURE = "reset_closure"


_ALIASES = {
    "create_source_textile": ClothAction.TAKE_FACE.value,
    "open_close": ClothAction.OPEN_CLOSURE.value,
    "draw_join_textile_faces": ClothAction.OPEN_CLOSURE.value,
    "draw_join_faces": ClothAction.OPEN_CLOSURE.value,
    "workspace_draw": ClothAction.OPEN_DRAW.value,
    "workspace_properties": ClothAction.OPEN_PROPERTIES.value,
    "apply_continue": ClothAction.APPLY_OUTPUT.value,
    "apply_close": ClothAction.APPLY_CLOSURE.value,
    "accept_join": ClothAction.APPLY_CLOSURE.value,
    "previous_close": ClothAction.PREVIOUS_CLOSURE.value,
    "previous_join": ClothAction.PREVIOUS_CLOSURE.value,
    "next_close": ClothAction.NEXT_CLOSURE.value,
    "next_join": ClothAction.NEXT_CLOSURE.value,
    "reset_close": ClothAction.RESET_CLOSURE.value,
    "clear_join": ClothAction.RESET_CLOSURE.value,
}


def canonical_cloth_action(action_id: str | None) -> str:
    value = str(action_id or "")
    return _ALIASES.get(value, value)


def is_apply_action(action_id: str | None) -> bool:
    value = canonical_cloth_action(action_id)
    return value in {ClothAction.APPLY_OUTPUT.value, ClothAction.APPLY_CLOSURE.value}


__all__ = ["ClothAction", "canonical_cloth_action", "is_apply_action"]

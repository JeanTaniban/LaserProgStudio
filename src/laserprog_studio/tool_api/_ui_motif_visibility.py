"""Visibility helpers for official Creator UI motifs."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from laserprog_studio.tool_core.selection import ToolActor

from ._ui_motif_contract import (
    API_UI_VISIBLE_METADATA_KEY,
    FAMILY_OVERLAYS,
    OFFICIAL_CREATOR_UI_MOTIF_FAMILIES,
)


def _actor_belongs_to_family(actor: ToolActor, owner: str, family: str) -> bool:
    if actor.owner_tool != owner:
        return False
    motif_family = str(actor.metadata.get("motif_family", ""))
    if motif_family == family:
        return True
    return str(actor.id).startswith(f"{owner}:{family}:")


def _set_actor_api_visible(ctx: Any, actor: ToolActor, visible: bool) -> None:
    metadata = {**actor.metadata, API_UI_VISIBLE_METADATA_KEY: bool(visible)}
    if metadata == actor.metadata:
        return
    ctx.actor_registry(actor.owner_tool).add(replace(actor, metadata=metadata), replace=True)


def set_creator_ui_motif_family_visible(ctx: Any, *, owner_tool: str, family_id: str, visible: bool) -> None:
    """Show/hide one official motif family without inventing alternate visuals.

    Visibility is semantic, not cosmetic only: hidden motif actors are marked in
    their ``ToolActor`` metadata so the native hit-test path ignores them.  This
    keeps "Hide all" safe and makes "Show all" instant because motifs stay
    registered and only their visible/interactive flag changes.
    """

    owner = str(owner_tool)
    family = str(getattr(family_id, "value", family_id)).strip().lower()
    visible_bool = bool(visible)
    id_prefix = f"{owner}:{family}:"
    overlay_id_prefix = f"{owner}:overlay:" if family == FAMILY_OVERLAYS else id_prefix
    kind_prefix = f"catalog:{family}:"

    for actor in list(ctx.selection.actors(owner_tool=owner)):
        if _actor_belongs_to_family(actor, owner, family):
            _set_actor_api_visible(ctx, actor, visible_bool)
            if not visible_bool:
                ctx.selection.deselect(actor.id)
                if ctx.selection.state.hover_id == actor.id:
                    ctx.selection.set_hover(None)
                if actor.id in ctx.selection.state.grabbed_ids:
                    ctx.selection.end_grab()

    ctx.gizmos.begin_interactive_update()
    try:
        for handle in ctx.gizmos.handles(owner_tool=owner):
            handle_id = str(handle.id)
            handle_kind = str(handle.kind)
            # Public manipulators produce native kinds such as ``translate:x``;
            # owner-scoped ids keep them family-addressable without changing the
            # optimized native GizmoManager helpers.
            if handle_id.startswith(id_prefix) or handle_kind.startswith(kind_prefix):
                ctx.gizmos.set_visible(handle.id, visible_bool)
    finally:
        ctx.gizmos.end_interactive_update()
    for item in ctx.preview.items(owner_tool=owner):
        if str(item.id).startswith(id_prefix):
            item.visible = visible_bool
            item.dirty = True
    if family == FAMILY_OVERLAYS:
        for window_id, window in list(ctx.overlay.windows.items()):
            if window.owner_tool == owner and str(window_id).startswith(overlay_id_prefix):
                ctx.overlay.windows[window_id] = replace(window, visible=visible_bool)

def apply_creator_ui_motif_visibility(ctx: Any, *, owner_tool: str, visible_by_family: Mapping[str, bool]) -> None:
    """Apply toggle state for all public motif families."""

    for family in OFFICIAL_CREATOR_UI_MOTIF_FAMILIES:
        set_creator_ui_motif_family_visible(ctx, owner_tool=owner_tool, family_id=family, visible=bool(visible_by_family.get(family, True)))


__all__ = ["apply_creator_ui_motif_visibility", "set_creator_ui_motif_family_visible"]

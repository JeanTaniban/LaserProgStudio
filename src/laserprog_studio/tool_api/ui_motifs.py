"""Public facade for official Creator UI motifs.

This module is the executable side of the Creator UI contract.  Tool Core
Analysis remains the laboratory where visual motifs are tested and optimized;
this public module exposes the approved motifs to tool authors.

Important boundary:

* ``tool_api.ui_catalog`` lists and documents the official vocabulary.
* ``tool_api.ui_motifs`` exposes stable public builders/refresher functions.
* Private ``tool_api._ui_motif_*`` modules own the runtime implementation.
* The built-in Gizmo catalog only displays these motifs and toggles visibility.

Visibility uses the public metadata key ``api_ui_visible``.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from ._ui_motif_builder import CreatorUiMotifBuilder
from ._ui_motif_contract import (
    API_UI_VISIBLE_METADATA_KEY,
    OFFICIAL_CREATOR_UI_MOTIF_FAMILIES,
    CreatorUiMotifSnapshot,
    Point3,
)
from ._ui_motif_visibility import (
    apply_creator_ui_motif_visibility,
    set_creator_ui_motif_family_visible,
)
from .ui_catalog import iter_creator_ui_families


def build_creator_ui_motifs(ctx: Any, *, owner_tool: str, families: Iterable[str] | None = None) -> CreatorUiMotifSnapshot:
    """Build official Tool Core Analysis UI motifs for one creator tool owner."""

    return CreatorUiMotifBuilder(ctx, owner_tool=owner_tool).build(families)


def refresh_creator_ui_interaction(
    ctx: Any,
    *,
    owner_tool: str,
    render: bool = False,
    changed_actor_ids: Iterable[str] | None = None,
    position_only: bool = False,
    return_snapshot: bool = True,
) -> CreatorUiMotifSnapshot | None:
    """Refresh hover/select/grab visuals using the persistent interaction path.

    Unlike :func:`refresh_creator_ui_motifs`, this function does not clear
    previews, handles or overlays.  It updates only actor-backed motifs in
    place and is therefore the correct API call during hover and drag events.

    ``return_snapshot=False`` lets viewport-side hover/drag refreshes skip the
    final count-summary build that walks every preview, handle, actor and
    overlay window of the owner tool. The snapshot is only needed for tests
    and diagnostics; the visuals are already updated by the inner refresh.
    """

    snapshot = CreatorUiMotifBuilder(ctx, owner_tool=owner_tool).refresh_interaction_visuals(
        changed_actor_ids=changed_actor_ids,
        position_only=position_only,
        return_snapshot=return_snapshot,
    )
    if render:
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import render_creator_viewport_ui

                render_creator_viewport_ui(owner, ctx, owner_tool, render=True, sync_overlays=False)
            except Exception:
                try:
                    ctx.request_full_render()
                except Exception:
                    pass
        else:
            try:
                ctx.request_full_render()
            except Exception:
                pass
    return snapshot


def refresh_creator_ui_drag(
    ctx: Any,
    *,
    owner_tool: str,
    changed_actor_ids: Iterable[str] | None = None,
    extra_preview_ids: Iterable[str] | None = None,
    render: bool = True,
    return_snapshot: bool = True,
) -> CreatorUiMotifSnapshot | None:
    """Refresh a Creator UI drag with the Tool Core Analysis fast path.

    This is the API-level equivalent of the diagnostic handle-demo drag path:
    update only moved actors and their dependent primitives, then mutate cached
    viewport mesh ranges when a live owner is available.  Tool authors should
    call this for mouse-move drag events instead of forcing a full motif refresh.
    """

    snapshot = refresh_creator_ui_interaction(
        ctx,
        owner_tool=owner_tool,
        render=False,
        changed_actor_ids=changed_actor_ids,
        position_only=True,
        return_snapshot=return_snapshot,
    )
    extras = tuple(str(value) for value in (extra_preview_ids or ()) if str(value))
    if extras:
        try:
            state = ctx.selection.state
            merged = tuple(dict.fromkeys((*tuple(getattr(state, "dirty_visual_preview_ids", ()) or ()), *extras)))
            state.dirty_visual_preview_ids = merged
        except Exception:
            pass
    if render:
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            state = getattr(ctx.selection, "state", None)
            handle_ids = tuple(getattr(state, "dirty_visual_handle_ids", ()) or ())
            preview_ids = tuple(getattr(state, "dirty_visual_preview_ids", ()) or ())
            try:
                from laserprog_studio.application.creator_viewport_ui import fast_update_creator_viewport_ui, render_creator_viewport_ui

                if not fast_update_creator_viewport_ui(
                    owner,
                    ctx,
                    owner_tool,
                    handle_ids=handle_ids,
                    preview_ids=preview_ids,
                    render=True,
                ):
                    render_creator_viewport_ui(owner, ctx, owner_tool, render=True, sync_overlays=False)
            except Exception:
                try:
                    ctx.request_light_render()
                except Exception:
                    pass
        else:
            try:
                ctx.request_light_render()
            except Exception:
                pass
    return snapshot

def refresh_creator_ui_motifs(ctx: Any, *, owner_tool: str, families: Iterable[str] | None = None) -> CreatorUiMotifSnapshot:
    """Refresh official motif visuals after hover, grab or selection changes.

    This is the native Creator API interaction path: it redraws handles and
    previews from current ToolActor state without resetting the actors.
    """

    return CreatorUiMotifBuilder(ctx, owner_tool=owner_tool).refresh(families)


def refresh_creator_ui_camera(ctx: Any, *, owner_tool: str, render: bool = True) -> bool:
    """Refresh camera-oriented/scaled Creator UI without involving tool code.

    The shared Tool Core Analysis painter snaps GUI guide planes to the nearest
    camera axis and converts pixel-sized guides to world units from the active
    field of view.  Calling this after a camera drag or wheel burst is enough;
    individual tools do not compute axes, billboards or scale factors.
    """

    owner = getattr(ctx, "owner", None)
    if owner is None:
        return False
    try:
        from laserprog_studio.application.creator_viewport_ui import render_creator_viewport_ui

        render_creator_viewport_ui(owner, ctx, owner_tool, render=render)
        return True
    except Exception:
        return False


def clear_creator_ui_motifs(ctx: Any, *, owner_tool: str) -> None:
    """Clear all public UI motifs owned by ``owner_tool``."""

    CreatorUiMotifBuilder(ctx, owner_tool=owner_tool).clear()


def iter_creator_ui_motif_families():
    """Return the public UI families that can be rendered as official motifs."""

    return iter_creator_ui_families()


# Stable aliases with the wording used by earlier passes/docs.
build_gizmo_ui_motifs = build_creator_ui_motifs
clear_gizmo_ui_motifs = clear_creator_ui_motifs
iter_gizmo_ui_motif_families = iter_creator_ui_motif_families
apply_gizmo_ui_motif_visibility = apply_creator_ui_motif_visibility
refresh_gizmo_ui_interaction = refresh_creator_ui_interaction
refresh_gizmo_ui_drag = refresh_creator_ui_drag
refresh_gizmo_ui_motifs = refresh_creator_ui_motifs
refresh_gizmo_ui_camera = refresh_creator_ui_camera

__all__ = [
    "API_UI_VISIBLE_METADATA_KEY",
    "CreatorUiMotifBuilder",
    "CreatorUiMotifSnapshot",
    "OFFICIAL_CREATOR_UI_MOTIF_FAMILIES",
    "Point3",
    "apply_creator_ui_motif_visibility",
    "apply_gizmo_ui_motif_visibility",
    "build_creator_ui_motifs",
    "build_gizmo_ui_motifs",
    "clear_creator_ui_motifs",
    "clear_gizmo_ui_motifs",
    "iter_creator_ui_motif_families",
    "iter_gizmo_ui_motif_families",
    "refresh_creator_ui_camera",
    "refresh_creator_ui_drag",
    "refresh_creator_ui_interaction",
    "refresh_creator_ui_motifs",
    "refresh_gizmo_ui_camera",
    "refresh_gizmo_ui_drag",
    "refresh_gizmo_ui_interaction",
    "refresh_gizmo_ui_motifs",
    "set_creator_ui_motif_family_visible",
]

"""Shared private helpers for Creator UI motif construction."""
from __future__ import annotations

from dataclasses import replace
from math import cos, hypot, pi, sin

from laserprog_studio.tool_core.gizmos import DEFAULT_POINT_STYLES, GizmoHandle
from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind, ToolActor

from . import actors
from ._ui_motif_contract import (
    API_UI_VISIBLE_METADATA_KEY,
    FAMILY_ACTOR_INTERACTIONS,
    FAMILY_ACTOR_KINDS,
    FAMILY_LINE_STYLES,
    FAMILY_MANIPULATORS,
    FAMILY_OVERLAYS,
    FAMILY_POINT_STYLES,
    FAMILY_PREVIEWS,
    FAMILY_VISUAL_STATES,
    Point3,
)
from .styles import (
    InteractionVisualState,
    LineStyleId,
    PointStyleId,
    list_line_styles,
    resolve_actor_visual,
)
from .visual import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

def _register_actor_motif(self, actor: ToolActor) -> ToolActor:
    """Register a motif actor once and preserve its runtime position/state.

    ``refresh()`` calls must not replace actors that the user just selected
    or dragged.  The template is used only when the actor does not exist yet.
    """

    existing = self.ctx.selection.actor(actor.id)
    if existing is not None and existing.owner_tool == self.owner_tool:
        return existing
    # Pattern actors are also part of the public visibility contract.  Hidden
    # families must not be hit-testable; the selection manager reads this
    # metadata directly.
    metadata = {**actor.metadata}
    metadata.setdefault("motif_family", self._family_from_actor_id(actor.id))
    metadata.setdefault(API_UI_VISIBLE_METADATA_KEY, True)
    if metadata != actor.metadata:
        actor = replace(actor, metadata=metadata)
    return self.ctx.actor_registry(self.owner_tool).add(actor, replace=True)


def _register_handle_actor(
    self,
    family: str,
    local_id: str,
    position: Point3,
    *,
    interaction: str | ActorInteraction = ActorInteraction.GRABBABLE,
    point_style: str = PointStyleId.SOLID.value,
    line_style: str = LineStyleId.GRABBABLE.value,
    visual_state: str | InteractionVisualState = InteractionVisualState.AUTO.value,
    radius_px: int = 11,
    kind_suffix: str | None = None,
) -> ToolActor:
    """Register a handle as a public ToolActor and preserve its drag state.

    Tool Core Analysis allowed users to grab real UI motifs, not just the
    decorative point actor.  Creator API motifs therefore expose grabbable
    handles as owner-scoped ``ToolActor`` entries with the same id as the
    handle.  Interaction code can move them through the standard selection
    manager; the visual handle is then synchronized from that actor.
    """

    actor_id = self._id(family, local_id)
    metadata = {
        "motif_family": family,
        "motif_kind": "handle",
        "point_style": str(point_style),
        "line_style": str(line_style),
        "visual_state": str(getattr(visual_state, "value", visual_state)),
        "base_radius_px": int(radius_px),
        "kind_suffix": str(kind_suffix or local_id),
        API_UI_VISIBLE_METADATA_KEY: True,
    }
    existing_for_visibility = self.ctx.selection.actor(actor_id)
    if existing_for_visibility is not None and existing_for_visibility.owner_tool == self.owner_tool:
        metadata[API_UI_VISIBLE_METADATA_KEY] = bool(existing_for_visibility.metadata.get(API_UI_VISIBLE_METADATA_KEY, True))
    template = ToolActor(
        id=actor_id,
        kind=ActorKind.POINT,
        owner_tool=self.owner_tool,
        points=(tuple(float(v) for v in position),),
        interaction=interaction,
        hit_radius_px=max(float(radius_px), 8.0),
        metadata=metadata,
    )
    existing = self.ctx.selection.actor(actor_id)
    if existing is not None and existing.owner_tool == self.owner_tool:
        if existing.metadata != metadata or existing.interaction != interaction:
            return self.ctx.actor_registry(self.owner_tool).add(
                ToolActor(
                    id=existing.id,
                    kind=existing.kind,
                    owner_tool=existing.owner_tool,
                    points=existing.points,
                    interaction=interaction,
                    hit_radius_px=max(float(radius_px), float(existing.hit_radius_px)),
                    metadata=metadata,
                ),
                replace=True,
            )
        return existing
    return self.ctx.actor_registry(self.owner_tool).add(template, replace=True)


def _sync_handle_actor_visual(self, actor: ToolActor, *, position_only: bool = False) -> None:
    """Synchronize one grabbable handle visual from its ToolActor state."""

    if not actor.points:
        return
    family = str(actor.metadata.get("motif_family", ""))
    if not family:
        return
    selected = self.ctx.selection.is_selected(actor.id)
    hover = actor.id == self.ctx.selection.state.hover_id
    grabbed = actor.id in self.ctx.selection.state.grabbed_ids
    point_style = str(actor.metadata.get("point_style", PointStyleId.SOLID.value))
    line_style = str(actor.metadata.get("line_style", LineStyleId.GRABBABLE.value))
    visual_state = str(actor.metadata.get("visual_state", InteractionVisualState.AUTO.value))
    base_radius = int(actor.metadata.get("base_radius_px", 11))
    api_visible = bool(actor.metadata.get(API_UI_VISIBLE_METADATA_KEY, True))
    direct_handle = getattr(self.ctx.gizmos, "handle", None)
    existing = direct_handle(actor.id, owner_tool=self.owner_tool) if callable(direct_handle) else next((handle for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool) if handle.id == actor.id), None)
    if position_only and existing is not None:
        self.ctx.gizmos.update_positions_only({actor.id: actor.points[0]})
        self._dirty_handle_ids.add(actor.id)
        return
    visual = resolve_actor_visual(
        interaction=actor.interaction_mode,
        point_style_id=point_style,
        line_style_id=line_style,
        visual_state=visual_state,
        base_radius_px=base_radius,
        selected=selected,
        hover=hover,
        grabbed=grabbed,
        visible=api_visible,
    )
    self.ctx.gizmos.create_handle(
        GizmoHandle(
            id=actor.id,
            owner_tool=self.owner_tool,
            position=actor.points[0],
            radius_px=visual.radius_px,
            color=visual.point_color,
            selected=selected,
            hover=hover,
            grabbed=grabbed,
            visible=api_visible,
            selectable=actor.selectable and api_visible,
            kind=self._kind(family, actor.metadata.get("kind_suffix", actor.id)),
            style_id=visual.point_style_id,
            base_radius_px=base_radius,
            screen_locked=True,
        )
    )
    self._dirty_handle_ids.add(actor.id)


def _register_existing_family_handles_as_actors(self, family: str) -> None:
    """Expose native GizmoManager manipulator handles to interaction API."""

    id_prefix = f"{self.owner_tool}:{family}:"
    for handle in self.ctx.gizmos.handles(owner_tool=self.owner_tool):
        if not str(handle.id).startswith(id_prefix) or not bool(handle.selectable):
            continue
        self._register_handle_actor(
            family,
            str(handle.id)[len(id_prefix):],
            handle.position,
            interaction=ActorInteraction.GRABBABLE,
            point_style=str(getattr(handle, "style_id", PointStyleId.SOLID.value)),
            line_style=LineStyleId.GRABBABLE.value,
            visual_state=InteractionVisualState.AUTO.value,
            radius_px=int(getattr(handle, "base_radius_px", None) or getattr(handle, "radius_px", 11) or 11),
            kind_suffix=str(getattr(handle, "kind", handle.id)),
        )


def _label(self, family: str, local_id: str, text: str, position: Point3, *, size_px: int = 12) -> None:
    self.ctx.preview.show_text(self._id(family, "label", local_id), self.owner_tool, text, position, size_px=size_px)


def _show_handle(
    self,
    family: str,
    local_id: str,
    position: Point3,
    *,
    interaction: str | ActorInteraction = ActorInteraction.GRABBABLE,
    point_style: str = PointStyleId.SOLID.value,
    line_style: str = LineStyleId.GRABBABLE.value,
    visual_state: str | InteractionVisualState = InteractionVisualState.AUTO.value,
    selected: bool = False,
    hover: bool = False,
    grabbed: bool = False,
    visible: bool = True,
    selectable: bool = True,
    radius_px: int = 11,
    kind_suffix: str | None = None,
    interactive: bool = True,
) -> None:
    actor = None
    if selectable and interactive:
        actor = self._register_handle_actor(
            family,
            local_id,
            position,
            interaction=interaction,
            point_style=point_style,
            line_style=line_style,
            visual_state=visual_state,
            radius_px=radius_px,
            kind_suffix=kind_suffix or local_id,
        )
        position = actor.points[0]
        visible = bool(actor.metadata.get(API_UI_VISIBLE_METADATA_KEY, visible))
        selectable = bool(selectable and visible)
        selected = self.ctx.selection.is_selected(actor.id)
        hover = actor.id == self.ctx.selection.state.hover_id
        grabbed = actor.id in self.ctx.selection.state.grabbed_ids
    visual = resolve_actor_visual(
        interaction=interaction,
        point_style_id=point_style,
        line_style_id=line_style,
        visual_state=visual_state,
        base_radius_px=radius_px,
        selected=selected,
        hover=hover,
        grabbed=grabbed,
        visible=True,
    )
    self.ctx.gizmos.create_handle(
        GizmoHandle(
            id=self._id(family, local_id),
            owner_tool=self.owner_tool,
            position=position,
            radius_px=visual.radius_px,
            color=visual.point_color,
            selected=selected,
            hover=hover,
            grabbed=grabbed,
            visible=visible,
            selectable=selectable,
            kind=self._kind(family, kind_suffix or local_id),
            style_id=visual.point_style_id,
            base_radius_px=radius_px,
            screen_locked=True,
        )
    )

__all__ = ['_register_actor_motif', '_register_handle_actor', '_sync_handle_actor_visual', '_register_existing_family_handles_as_actors', '_label', '_show_handle']

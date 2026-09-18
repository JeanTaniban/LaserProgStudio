"""Public actor factories for tool creators.

The low-level :mod:`laserprog_studio.tool_core.selection` module owns hit tests,
selection and grab state.  Tool creators should prefer the helpers in this file:
they make the interaction contract explicit and keep actor declarations short.
"""
from __future__ import annotations

from math import dist
from typing import Any, Iterable, Literal

from laserprog_studio.tool_core.selection import ActorInteraction, ActorKind, Point3, ToolActor

from .errors import ToolApiUsageError, ToolApiValidationError
from .styles import normalize_line_style, normalize_point_style, normalize_visual_state

InteractionName = Literal["fixed", "selectable", "grabbable"] | ActorInteraction


def _interaction(value: InteractionName) -> ActorInteraction:
    if isinstance(value, ActorInteraction):
        return value
    try:
        return ActorInteraction(str(value))
    except ValueError as exc:  # pragma: no cover - defensive path
        allowed = ", ".join(item.value for item in ActorInteraction)
        raise ToolApiValidationError(f"Invalid actor interaction {value!r}. Expected one of: {allowed}.") from exc


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


def make_actor(
    *,
    id: str,
    kind: ActorKind | str,
    points: Iterable[Iterable[float]],
    interaction: InteractionName = ActorInteraction.SELECTABLE,
    owner_tool: str | None = None,
    hit_radius_px: float = 10.0,
    metadata: dict[str, Any] | None = None,
    point_style: str | None = None,
    line_style: str | None = None,
    visual_state: str | None = None,
) -> ToolActor:
    """Create a validated :class:`ToolActor`.

    ``interaction`` is the creator-facing contract:

    - ``fixed``: no user interaction;
    - ``selectable``: can be selected but not moved;
    - ``grabbable``: can be selected, then moved.
    """

    actor_id = str(id).strip()
    if not actor_id:
        raise ToolApiValidationError("ToolActor id must be non-empty.")
    actor_kind = kind if isinstance(kind, ActorKind) else ActorKind(str(kind)) if str(kind) in ActorKind._value2member_map_ else str(kind)
    actor_points = tuple(_point3(value) for value in points)
    _validate_actor_geometry(actor_id, actor_kind, actor_points)
    if float(hit_radius_px) <= 0:
        raise ToolApiValidationError(f"Actor {actor_id!r} hit_radius_px must be greater than 0.")
    actor_metadata = dict(metadata or {})
    if point_style is not None:
        actor_metadata["point_style"] = normalize_point_style(point_style)
    if line_style is not None:
        actor_metadata["line_style"] = normalize_line_style(line_style)
    if visual_state is not None:
        actor_metadata["visual_state"] = normalize_visual_state(visual_state).value
    return ToolActor(
        id=actor_id,
        kind=actor_kind,
        owner_tool=owner_tool,
        points=actor_points,
        interaction=_interaction(interaction),
        hit_radius_px=float(hit_radius_px),
        metadata=actor_metadata,
    )


def _validate_actor_geometry(actor_id: str, kind: ActorKind | str, points: tuple[Point3, ...]) -> None:
    kind_value = kind.value if isinstance(kind, ActorKind) else str(kind)
    if kind_value == ActorKind.POINT.value and len(points) != 1:
        raise ToolApiValidationError(f"Actor {actor_id!r} is a point but received {len(points)} points. Expected exactly 1.")
    if kind_value == ActorKind.LINE.value and len(points) != 2:
        raise ToolApiValidationError(f"Actor {actor_id!r} is a line but received {len(points)} points. Expected exactly 2.")
    if kind_value == ActorKind.CIRCLE.value:
        if len(points) != 2:
            raise ToolApiValidationError(f"Actor {actor_id!r} is a circle but received {len(points)} points. Expected center and radius point.")
        if dist(points[0], points[1]) <= 1.0e-9:
            raise ToolApiValidationError(f"Actor {actor_id!r} is a circle but its radius is zero.")
    if kind_value == ActorKind.ARC.value and len(points) < 3:
        raise ToolApiValidationError(f"Actor {actor_id!r} is an arc but received {len(points)} points. Expected at least 3.")
    if kind_value == ActorKind.POLYLINE.value and len(points) < 2:
        raise ToolApiValidationError(f"Actor {actor_id!r} is a polyline but received {len(points)} points. Expected at least 2.")


def point(
    id: str,
    position: Iterable[float],
    *,
    interaction: InteractionName = ActorInteraction.GRABBABLE,
    owner_tool: str | None = None,
    hit_radius_px: float = 10.0,
    metadata: dict[str, Any] | None = None,
    point_style: str | None = None,
    line_style: str | None = None,
    visual_state: str | None = None,
) -> ToolActor:
    """Create a point actor, grabbable by default."""

    return make_actor(
        id=id,
        kind=ActorKind.POINT,
        points=(position,),
        interaction=interaction,
        owner_tool=owner_tool,
        hit_radius_px=hit_radius_px,
        metadata=metadata,
        point_style=point_style,
        line_style=line_style,
        visual_state=visual_state,
    )


def line(
    id: str,
    start: Iterable[float],
    end: Iterable[float],
    *,
    interaction: InteractionName = ActorInteraction.SELECTABLE,
    owner_tool: str | None = None,
    hit_radius_px: float = 10.0,
    metadata: dict[str, Any] | None = None,
    point_style: str | None = None,
    line_style: str | None = None,
    visual_state: str | None = None,
) -> ToolActor:
    """Create a line actor between ``start`` and ``end``."""

    return make_actor(
        id=id,
        kind=ActorKind.LINE,
        points=(start, end),
        interaction=interaction,
        owner_tool=owner_tool,
        hit_radius_px=hit_radius_px,
        metadata=metadata,
        point_style=point_style,
        line_style=line_style,
        visual_state=visual_state,
    )


def circle(
    id: str,
    center: Iterable[float],
    radius_point: Iterable[float],
    *,
    interaction: InteractionName = ActorInteraction.SELECTABLE,
    owner_tool: str | None = None,
    hit_radius_px: float = 10.0,
    metadata: dict[str, Any] | None = None,
    point_style: str | None = None,
    line_style: str | None = None,
    visual_state: str | None = None,
) -> ToolActor:
    """Create a circle actor from a center and one point on the radius."""

    return make_actor(
        id=id,
        kind=ActorKind.CIRCLE,
        points=(center, radius_point),
        interaction=interaction,
        owner_tool=owner_tool,
        hit_radius_px=hit_radius_px,
        metadata=metadata,
        point_style=point_style,
        line_style=line_style,
        visual_state=visual_state,
    )


def arc(
    id: str,
    points: Iterable[Iterable[float]],
    *,
    interaction: InteractionName = ActorInteraction.SELECTABLE,
    owner_tool: str | None = None,
    hit_radius_px: float = 10.0,
    metadata: dict[str, Any] | None = None,
    point_style: str | None = None,
    line_style: str | None = None,
    visual_state: str | None = None,
) -> ToolActor:
    """Create an arc actor represented by a sampled point chain."""

    return make_actor(
        id=id,
        kind=ActorKind.ARC,
        points=points,
        interaction=interaction,
        owner_tool=owner_tool,
        hit_radius_px=hit_radius_px,
        metadata=metadata,
        point_style=point_style,
        line_style=line_style,
        visual_state=visual_state,
    )


def polyline(
    id: str,
    points: Iterable[Iterable[float]],
    *,
    interaction: InteractionName = ActorInteraction.SELECTABLE,
    owner_tool: str | None = None,
    hit_radius_px: float = 10.0,
    metadata: dict[str, Any] | None = None,
    point_style: str | None = None,
    line_style: str | None = None,
    visual_state: str | None = None,
) -> ToolActor:
    """Create a polyline actor represented by a sampled point chain."""

    return make_actor(
        id=id,
        kind=ActorKind.POLYLINE,
        points=points,
        interaction=interaction,
        owner_tool=owner_tool,
        hit_radius_px=hit_radius_px,
        metadata=metadata,
        point_style=point_style,
        line_style=line_style,
        visual_state=visual_state,
    )


class ActorRegistry:
    """Owner-scoped actor registry exposed as ``ctx.actors``.

    The ``ctx.selection.register_actor`` path remains available, but this
    wrapper is safer for creator tools: it can enforce duplicate policies, attach
    ownership automatically and keep scene-cache invalidation consistent.
    """

    def __init__(self, ctx, owner_tool: str | None = None) -> None:
        self._ctx = ctx
        self.owner_tool = str(owner_tool) if owner_tool is not None else None

    def for_tool(self, owner_tool: str) -> "ActorRegistry":
        return ActorRegistry(self._ctx, owner_tool)

    def add(self, actor: ToolActor, *, replace: bool = False, owner_tool: str | None = None) -> ToolActor:
        owner = str(owner_tool) if owner_tool is not None else self.owner_tool
        if owner is not None and actor.owner_tool is None:
            from dataclasses import replace as dataclass_replace

            actor = dataclass_replace(actor, owner_tool=owner)
        existing = self._ctx.selection.actor(actor.id)
        if existing is not None and not replace:
            raise ToolApiValidationError(
                f"Actor {actor.id!r} is already registered. Pass replace=True to update it explicitly."
            )
        self._ctx.selection.register_actor(actor)
        scene_cache = getattr(self._ctx, "scene_cache", None)
        invalidate = getattr(scene_cache, "invalidate", None)
        if callable(invalidate):
            invalidate()
        return actor

    def add_many(self, actors: Iterable[ToolActor], *, replace: bool = False, owner_tool: str | None = None) -> tuple[ToolActor, ...]:
        return tuple(self.add(actor, replace=replace, owner_tool=owner_tool) for actor in actors)

    def update(self, actor: ToolActor) -> ToolActor:
        if not self._ctx.selection.update_actor(actor):
            raise ToolApiUsageError(f"Cannot update unknown actor {actor.id!r}.")
        scene_cache = getattr(self._ctx, "scene_cache", None)
        invalidate = getattr(scene_cache, "invalidate", None)
        if callable(invalidate):
            invalidate()
        return actor

    def remove(self, actor_id: str) -> None:
        self._ctx.selection.unregister(str(actor_id))
        scene_cache = getattr(self._ctx, "scene_cache", None)
        invalidate = getattr(scene_cache, "invalidate", None)
        if callable(invalidate):
            invalidate()

    def clear(self, *, owner_tool: str | None = None) -> None:
        owner = str(owner_tool) if owner_tool is not None else self.owner_tool
        if owner is None:
            for actor in self._ctx.selection.actors():
                self._ctx.selection.unregister(actor.id)
        else:
            self._ctx.selection.clear_tool(owner)
        scene_cache = getattr(self._ctx, "scene_cache", None)
        invalidate = getattr(scene_cache, "invalidate", None)
        if callable(invalidate):
            invalidate()

    def get(self, actor_id: str) -> ToolActor | None:
        return self._ctx.selection.actor(str(actor_id))

    def all(self, *, owner_tool: str | None = None) -> tuple[ToolActor, ...]:
        owner = str(owner_tool) if owner_tool is not None else self.owner_tool
        return self._ctx.selection.actors(owner_tool=owner)

    def selected(self) -> tuple[ToolActor, ...]:
        return self._ctx.selection.selected_actors()


def registry(ctx, owner_tool: str | None = None) -> ActorRegistry:
    """Return a safe actor registry for a context or owner tool."""

    return ActorRegistry(ctx, owner_tool)


fixed = ActorInteraction.FIXED
selectable = ActorInteraction.SELECTABLE
grabbable = ActorInteraction.GRABBABLE

__all__ = [
    "ActorInteraction",
    "ActorRegistry",
    "ActorKind",
    "InteractionName",
    "ToolActor",
    "arc",
    "circle",
    "fixed",
    "grabbable",
    "line",
    "make_actor",
    "point",
    "polyline",
    "registry",
    "selectable",
]

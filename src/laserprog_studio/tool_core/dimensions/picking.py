"""Dimension reference picking helpers.

Dimension tools often need a slightly different picking policy from normal
selection.  Normal CAD selection gives vertices priority over edges/faces; a
measurement workflow may intentionally prefer a circle when the user is asking
for a radius, or a line when the user is building an angle.  Keeping that policy
here avoids duplicating hit-test loops inside every sketch tool.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
WorldToScreen = Callable[[Point3], Point2]


@dataclass(frozen=True, slots=True)
class DimensionReferenceHit:
    actor: Any
    actor_id: str
    role: str
    distance_px: float
    priority: int = 0


def find_dimension_reference_hit(
    ctx: Any,
    *,
    owner_tool: str,
    screen_pos: Point2,
    world_to_screen: WorldToScreen | None = None,
    preferred_roles: Iterable[str] = (),
    selectable_only: bool = True,
) -> DimensionReferenceHit | None:
    """Pick the best sketch actor to use as a dimension reference.

    This is intentionally API-owned, not Plan-Tracer-owned: normal selection and
    dimension-reference picking are related but not identical.  A radius gesture
    can prefer circles over center points, while an angle gesture can prefer
    edges over vertices under the same cursor.
    """

    if world_to_screen is None:
        world_to_screen = lambda point: (float(point[0]), float(point[1]))
    preferred = {str(role) for role in preferred_roles}
    sx, sy = float(screen_pos[0]), float(screen_pos[1])
    distance_fn = getattr(ctx.selection, "_distance_to_actor_px", None)
    if not callable(distance_fn):
        return None
    best: DimensionReferenceHit | None = None
    for actor in tuple(ctx.selection.actors(owner_tool=owner_tool)):
        if actor.metadata.get("api_ui_visible") is False:
            continue
        if selectable_only and not bool(getattr(actor, "selectable", False)):
            continue
        role = str(actor.metadata.get("plan_trace_role", "") or "")
        if role not in {"point", "edge", "arc", "circle", "face", "dimension"}:
            continue
        try:
            distance = distance_fn(actor, (sx, sy), world_to_screen)
        except Exception:
            continue
        if distance is None or float(distance) > float(actor.hit_radius_px):
            continue
        priority = _dimension_role_priority(role) + (1000 if role in preferred else 0)
        hit = DimensionReferenceHit(actor=actor, actor_id=str(actor.id), role=role, distance_px=float(distance), priority=priority)
        if best is None or _hit_is_better(hit, best):
            best = hit
    return best


def _dimension_role_priority(role: str) -> int:
    # Dimension references prefer explicit geometry over generated faces and text
    # labels, but the caller can boost a role for contextual gestures.
    if role == "point":
        return 90
    if role == "edge":
        return 80
    if role in {"circle", "arc"}:
        return 75
    if role == "face":
        return 10
    if role == "dimension":
        return 5
    return 0


def _hit_is_better(candidate: DimensionReferenceHit, current: DimensionReferenceHit) -> bool:
    if candidate.priority != current.priority:
        return candidate.priority > current.priority
    return candidate.distance_px < current.distance_px

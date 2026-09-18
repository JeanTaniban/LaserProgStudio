"""Creator-facing smart-snap helpers."""
from __future__ import annotations

from typing import Any, Iterable

from laserprog_studio.tool_core.snap import SnapKind, SnapManager, SnapResult, SnapSource, SnapTarget
from laserprog_studio.tool_core.snap.types import Point2, Point3, snap_label_for_kind


def point(
    id: str,
    position: Point3,
    *,
    screen_pos: Point2 | None = None,
    source: SnapSource = SnapSource.CUSTOM_POINT,
    radius_px: float = 14.0,
    priority: int = 50,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
) -> SnapTarget:
    """Create an extra world point target for ``ctx.snap.smart``."""

    return SnapTarget.point(id, position, screen_pos=screen_pos, source=source, radius_px=radius_px, priority=priority, metadata=metadata, kind=kind)


def tool_point(
    id: str,
    position: Point3,
    *,
    screen_pos: Point2 | None = None,
    radius_px: float = 14.0,
    priority: int = 35,
    owner_tool: str | None = None,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
) -> SnapTarget:
    """Create a temporary tool-construction point target.

    Use this for helper geometry created by a tool. It is different from
    ``ui_point``: the target is a world-space snap target, not a screen-space GUI
    target.
    """

    data = dict(metadata or {})
    if owner_tool is not None:
        data.setdefault("owner_tool", str(owner_tool))
    return SnapTarget.point(id, position, screen_pos=screen_pos, source=SnapSource.TOOL_TEMP_POINT, radius_px=radius_px, priority=priority, metadata=data, kind=kind)


def ui_point(
    id: str,
    screen_pos: Point2,
    *,
    world_pos: Point3 | None = None,
    radius_px: float = 14.0,
    priority: int = 15,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
) -> SnapTarget:
    """Create a screen-space UI snap target.

    Use this for overlay handles, temporary GUI guide points or projected gizmo
    anchors.  When ``world_pos`` is omitted, the snap result keeps the queried
    world position while still reporting this target as the source.
    """

    return SnapTarget.ui_point(id, screen_pos, world_pos=world_pos, radius_px=radius_px, priority=priority, metadata=metadata, kind=kind)


def segment(
    id: str,
    start: Point3,
    end: Point3,
    *,
    source: SnapSource = SnapSource.CUSTOM_EDGE,
    radius_px: float = 14.0,
    priority: int = 70,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
) -> SnapTarget:
    """Create an extra segment target for ``ctx.snap.smart``."""

    return SnapTarget.segment(id, start, end, source=source, radius_px=radius_px, priority=priority, metadata=metadata, kind=kind)


def tool_segment(
    id: str,
    start: Point3,
    end: Point3,
    *,
    radius_px: float = 14.0,
    priority: int = 55,
    owner_tool: str | None = None,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
) -> SnapTarget:
    """Create a temporary tool-construction segment target."""

    data = dict(metadata or {})
    if owner_tool is not None:
        data.setdefault("owner_tool", str(owner_tool))
    return SnapTarget.segment(id, start, end, source=SnapSource.TOOL_TEMP_EDGE, radius_px=radius_px, priority=priority, metadata=data, kind=kind)




def arc(
    id: str,
    start: Point3,
    end: Point3,
    control: Point3,
    *,
    source: SnapSource = SnapSource.CUSTOM_CURVE,
    radius_px: float = 14.0,
    priority: int = 65,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
) -> SnapTarget:
    """Create a circular-arc snap target for exact curve intersections."""

    return SnapTarget.arc(id, start, end, control, source=source, radius_px=radius_px, priority=priority, metadata=metadata, kind=kind)


def tool_arc(
    id: str,
    start: Point3,
    end: Point3,
    control: Point3,
    *,
    radius_px: float = 14.0,
    priority: int = 62,
    owner_tool: str | None = None,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
) -> SnapTarget:
    """Create a temporary tool-construction circular arc snap target."""

    data = dict(metadata or {})
    if owner_tool is not None:
        data.setdefault("owner_tool", str(owner_tool))
    return SnapTarget.arc(id, start, end, control, source=SnapSource.TOOL_TEMP_CURVE, radius_px=radius_px, priority=priority, metadata=data, kind=kind)


def circle(
    id: str,
    center: Point3,
    radius: float,
    *,
    source: SnapSource = SnapSource.CUSTOM_CURVE,
    radius_px: float = 14.0,
    priority: int = 65,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
    basis_u: Point3 | None = None,
    basis_v: Point3 | None = None,
) -> SnapTarget:
    """Create a circular curve snap target.

    The snap API expands this into center, quadrant/angle and curve snap
    candidates.  Tool code only declares the curve geometry.
    """

    return SnapTarget.circle(id, center, radius, source=source, radius_px=radius_px, priority=priority, metadata=metadata, kind=kind, basis_u=basis_u, basis_v=basis_v)


def tool_circle(
    id: str,
    center: Point3,
    radius: float,
    *,
    radius_px: float = 14.0,
    priority: int = 60,
    owner_tool: str | None = None,
    metadata: dict[str, Any] | None = None,
    kind: SnapKind | str | None = None,
    basis_u: Point3 | None = None,
    basis_v: Point3 | None = None,
) -> SnapTarget:
    """Create a temporary tool-construction circular snap target."""

    data = dict(metadata or {})
    if owner_tool is not None:
        data.setdefault("owner_tool", str(owner_tool))
    return SnapTarget.circle(id, center, radius, source=SnapSource.TOOL_TEMP_CURVE, radius_px=radius_px, priority=priority, metadata=data, kind=kind, basis_u=basis_u, basis_v=basis_v)


def label_for_kind(kind: SnapKind | str | None) -> str:
    """Return the stable user-facing label for a semantic snap kind."""

    return snap_label_for_kind(kind)

def smart(
    manager: SnapManager,
    world_pos: Point3,
    screen_pos: Point2,
    ctx: Any,
    *,
    extra_targets: Iterable[SnapTarget] = (),
    exclude_ids: Iterable[str] = (),
    exclude_sources: Iterable[SnapSource | str] = (),
    allowed_sources: Iterable[SnapSource | str] = (),
    allowed_kinds: Iterable[str] = (),
    max_distance_px: float | None = None,
    rebuild_cache: bool | None = None,
) -> SnapResult:
    """Small functional wrapper around ``SnapManager.smart``."""

    return manager.smart(
        world_pos,
        screen_pos,
        ctx,
        extra_targets=extra_targets,
        exclude_ids=exclude_ids,
        exclude_sources=exclude_sources,
        allowed_sources=allowed_sources,
        allowed_kinds=allowed_kinds,
        max_distance_px=max_distance_px,
        rebuild_cache=rebuild_cache,
    )


__all__ = [
    "SnapKind",
    "SnapManager",
    "SnapResult",
    "SnapSource",
    "SnapTarget",
    "arc",
    "circle",
    "label_for_kind",
    "point",
    "segment",
    "smart",
    "tool_arc",
    "tool_circle",
    "tool_point",
    "tool_segment",
    "ui_point",
]

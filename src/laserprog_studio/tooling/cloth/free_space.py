"""Free-space point placement for the Cloth 3D tracer.

A screen click does not mathematically identify one 3D point.  Cloth resolves
that ambiguity with a predictable CAD-like priority order:

1. exact smart snap to existing Cloth or scene vertices/edges;
2. the visible mesh surface under the cursor;
3. a camera-facing construction plane through the previous draft point;
4. for the first point, a camera-facing plane through the camera target.

The construction plane is transient and never becomes a document constraint.
Orbiting the camera before the next click is therefore the normal way to choose
another depth while drawing a genuinely three-dimensional wireframe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from laserprog_studio.tool_api import snap as snap_api
from laserprog_studio.tool_api.tracing import plane_from_origin_normal

from .models import ClothDocument, Point3
from .picking import ClothSnapTargetCache, cloth_snap_targets, point_id_from_snap_source

Point2 = tuple[float, float]


@dataclass(frozen=True, slots=True)
class ClothPointPlacement:
    position: Point3 | None
    existing_point_id: str | None = None
    label: str = "Free 3D"
    source: str = "none"
    construction_plane: Any | None = None
    snapped: bool = False
    snap_kind: str = "free"
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return self.position is not None


def resolve_cloth_point(
    ctx: Any,
    screen_pos: Point2,
    *,
    document: ClothDocument,
    owner_tool: str,
    pending_points: Iterable[Point3] = (),
    event_world_pos: Point3 | None = None,
    smart_snap: bool = True,
    snap_tolerance_px: float = 16.0,
    snap_target_cache: ClothSnapTargetCache | None = None,
    construction_snap: bool = True,
) -> ClothPointPlacement:
    """Resolve one Cloth point directly in the 3D viewport."""

    pending = tuple(_point3(point) for point in pending_points)
    surface_pick = _safe_pick_face(ctx, screen_pos)
    surface_point = _pick_world(surface_pick)

    anchor = pending[-1] if pending else _camera_target(ctx)
    normal = _camera_direction(ctx)
    construction_plane = None
    free_point: Point3 | None = surface_point
    source = "surface" if surface_point is not None else "free"
    label = "Mesh surface" if surface_point is not None else "Free 3D"

    if free_point is None:
        try:
            construction_plane = plane_from_origin_normal(anchor, normal)
        except Exception:
            construction_plane = None
        if construction_plane is not None:
            try:
                hit = ctx.pick.plane_intersection(screen_pos, construction_plane)
                free_point = _pick_world(hit)
            except Exception:
                free_point = None
        if free_point is None and event_world_pos is not None:
            free_point = _point3(event_world_pos)
        if free_point is None:
            # Headless/limited hosts often expose a simple viewport projection
            # without the picking facade.  Keep this as the last production-safe
            # fallback rather than requiring each tool to duplicate it.
            viewport = getattr(ctx, "viewport", None)
            method = getattr(viewport, "screen_to_world_on_plane", None)
            if callable(method):
                try:
                    value = method(screen_pos, construction_plane)
                except TypeError:
                    try:
                        value = method(screen_pos)
                    except Exception:
                        value = None
                except Exception:
                    value = None
                if value is not None:
                    free_point = _point3(value)

    if free_point is None:
        return ClothPointPlacement(None, label="No 3D point", source="none", construction_plane=construction_plane)

    if smart_snap:
        try:
            extra_targets = (
                snap_target_cache.near(
                    ctx,
                    document,
                    screen_pos,
                    owner_tool=owner_tool,
                    max_distance_px=float(snap_tolerance_px),
                )
                if snap_target_cache is not None
                else cloth_snap_targets(document, owner_tool=owner_tool, plane=None)
            )
            snap = ctx.snap.smart(
                free_point,
                screen_pos,
                ctx,
                extra_targets=extra_targets,
                max_distance_px=float(snap_tolerance_px),
            )
        except Exception:
            snap = None
        if snap is not None and bool(getattr(snap, "snapped", False)):
            position = _point3(getattr(snap, "position"))
            metadata = dict(getattr(snap, "metadata", {}) or {})
            existing_id = point_id_from_snap_source(getattr(snap, "source_id", None), metadata)
            kind = str(getattr(getattr(snap, "kind", None), "value", getattr(snap, "kind", "free")) or "free")
            snap_label = snap_api.label_for_kind(kind)
            if kind in {"edge", "free"}:
                snap_label = str(metadata.get("snap_label") or getattr(snap, "label", None) or snap_label)
            return ClothPointPlacement(
                position,
                existing_point_id=existing_id,
                label=snap_label,
                source=str(getattr(getattr(snap, "source", None), "value", getattr(snap, "source", "snap"))),
                construction_plane=construction_plane,
                snapped=True,
                snap_kind=kind,
                source_id=str(getattr(snap, "source_id", "") or "") or None,
                metadata=metadata,
            )

    if construction_snap and pending and source == "free":
        aligned = _construction_snap(ctx, free_point, screen_pos, pending, max_distance_px=min(float(snap_tolerance_px), 12.0))
        if aligned is not None:
            position, aligned_label, aligned_kind = aligned
            return ClothPointPlacement(
                position,
                label=aligned_label,
                source="construction",
                construction_plane=construction_plane,
                snapped=True,
                snap_kind=aligned_kind,
                metadata={"snap_label": aligned_label, "snap_kind": aligned_kind},
            )

    return ClothPointPlacement(
        _point3(free_point),
        existing_point_id=None,
        label=label,
        source=source,
        construction_plane=construction_plane,
        snapped=False,
        snap_kind="free",
    )



def _construction_snap(
    ctx: Any,
    free_point: Point3,
    screen_pos: Point2,
    pending: tuple[Point3, ...],
    *,
    max_distance_px: float,
) -> tuple[Point3, str, str] | None:
    """Return lightweight axis/extension/perpendicular alignment snaps."""

    anchor = pending[-1]
    directions: list[tuple[Point3, str, str]] = [
        ((1.0, 0.0, 0.0), "Axis X", "angle"),
        ((0.0, 1.0, 0.0), "Axis Y", "angle"),
        ((0.0, 0.0, 1.0), "Axis Z", "angle"),
    ]
    if len(pending) >= 2:
        previous = pending[-2]
        extension = _normalized((anchor[0] - previous[0], anchor[1] - previous[1], anchor[2] - previous[2]))
        directions.insert(0, (extension, "Extension", "angle"))
        view_normal = _camera_direction(ctx)
        perpendicular = _cross(view_normal, extension)
        if _length(perpendicular) > 1.0e-9:
            directions.insert(1, (_normalized(perpendicular), "Perpendicular", "perpendicular"))

    projector = getattr(getattr(ctx, "viewport", None), "world_to_screen", None)
    if not callable(projector):
        return None
    best: tuple[float, Point3, str, str] | None = None
    delta = (free_point[0] - anchor[0], free_point[1] - anchor[1], free_point[2] - anchor[2])
    for direction, label, kind in directions:
        t = delta[0] * direction[0] + delta[1] * direction[1] + delta[2] * direction[2]
        candidate = (anchor[0] + direction[0] * t, anchor[1] + direction[1] * t, anchor[2] + direction[2] * t)
        try:
            projected = projector(candidate)
            distance = ((float(projected[0]) - float(screen_pos[0])) ** 2 + (float(projected[1]) - float(screen_pos[1])) ** 2) ** 0.5
        except Exception:
            continue
        if distance <= max_distance_px and (best is None or distance < best[0]):
            best = (distance, candidate, label, kind)
    return None if best is None else (best[1], best[2], best[3])


def _cross(a: Point3, b: Point3) -> Point3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _length(value: Point3) -> float:
    return (value[0] * value[0] + value[1] * value[1] + value[2] * value[2]) ** 0.5


def camera_facing_plane(ctx: Any, origin: Point3) -> Any | None:
    """Return a transient screen-facing edit plane through ``origin``.

    This is a depth-resolution aid only; it is never serialized into Cloth.
    """

    try:
        return plane_from_origin_normal(_point3(origin), _camera_direction(ctx))
    except Exception:
        return None

def _safe_pick_face(ctx: Any, screen_pos: Point2) -> Any | None:
    try:
        pick = ctx.pick.face_at(screen_pos)
    except Exception:
        return None
    return pick if bool(getattr(pick, "hit", False)) else None


def _pick_world(pick: Any | None) -> Point3 | None:
    value = getattr(pick, "world_pos", None) if pick is not None else None
    if value is None:
        return None
    try:
        return _point3(value)
    except Exception:
        return None


def _camera_target(ctx: Any) -> Point3:
    viewport = getattr(ctx, "viewport", None)
    for name in ("camera_target", "focal_point", "camera_focal_point"):
        value = getattr(viewport, name, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value is not None:
            try:
                return _point3(value)
            except Exception:
                pass
    owner = getattr(ctx, "owner", None)
    for candidate in (
        getattr(owner, "plotter", None),
        getattr(getattr(owner, "plotter", None), "camera", None),
        getattr(owner, "camera", None),
    ):
        camera = getattr(candidate, "camera", candidate)
        getter = getattr(camera, "GetFocalPoint", None)
        if callable(getter):
            try:
                return _point3(getter())
            except Exception:
                pass
    return (0.0, 0.0, 0.0)


def _camera_direction(ctx: Any) -> Point3:
    viewport = getattr(ctx, "viewport", None)
    for name in ("camera_direction", "view_direction"):
        value = getattr(viewport, name, None)
        if callable(value):
            try:
                value = value()
            except Exception:
                value = None
        if value is not None:
            try:
                return _normalized(_point3(value))
            except Exception:
                pass
    try:
        ray = ctx.pick.ray((0.0, 0.0))
        direction = dict(getattr(ray, "metadata", {}) or {}).get("direction")
        if direction is not None:
            return _normalized(_point3(direction))
    except Exception:
        pass
    owner = getattr(ctx, "owner", None)
    for candidate in (
        getattr(owner, "plotter", None),
        getattr(getattr(owner, "plotter", None), "camera", None),
        getattr(owner, "camera", None),
    ):
        camera = getattr(candidate, "camera", candidate)
        get_position = getattr(camera, "GetPosition", None)
        get_focal = getattr(camera, "GetFocalPoint", None)
        if callable(get_position) and callable(get_focal):
            try:
                position = _point3(get_position())
                focal = _point3(get_focal())
                return _normalized((focal[0] - position[0], focal[1] - position[1], focal[2] - position[2]))
            except Exception:
                pass
    return (0.0, 0.0, 1.0)


def _point3(value: Iterable[float]) -> Point3:
    x, y, z = tuple(value)
    return (float(x), float(y), float(z))


def _normalized(value: Point3) -> Point3:
    import math

    length = math.sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2])
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return (value[0] / length, value[1] / length, value[2] / length)


__all__ = ["ClothPointPlacement", "camera_facing_plane", "resolve_cloth_point"]

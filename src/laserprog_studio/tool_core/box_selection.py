"""Native screen-rectangle selection service for creator tools.

The manager is UI-neutral: it tracks the drag rectangle in screen-space and
selects typed targets through ToolContext services. Qt code may subscribe to the
state to draw a translucent rubber-band, but creator tools only interact with
``ctx.selection_box``.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from math import hypot
from typing import Any, Callable, Iterable

from .events import MouseButton, ToolEvent, ToolEventType, screen_distance
from .selection import ActorKind, Point2, Point3, ToolActor, WorldToScreen


class BoxSelectionTarget(str, Enum):
    TOOL_ACTORS = "tool_actors"
    SCENE_OBJECTS = "scene_objects"
    SCENE_FACES = "scene_faces"
    SCENE_EDGES = "scene_edges"
    SCENE_VERTICES = "scene_vertices"


class BoxSelectionMode(str, Enum):
    REPLACE = "replace"
    ADD = "add"
    SUBTRACT = "subtract"
    TOGGLE = "toggle"


class BoxSelectionInsidePolicy(str, Enum):
    PARTIAL = "partial"
    FULL = "full"


class BoxSelectionActivationModifier(str, Enum):
    NONE = "none"
    SHIFT = "shift"
    CTRL = "ctrl"
    ALT = "alt"


@dataclass(frozen=True, slots=True)
class ScreenRect:
    left: float
    top: float
    right: float
    bottom: float

    @classmethod
    def from_points(cls, a: Point2, b: Point2) -> "ScreenRect":
        ax, ay = float(a[0]), float(a[1])
        bx, by = float(b[0]), float(b[1])
        return cls(min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    @property
    def width(self) -> float:
        return max(0.0, self.right - self.left)

    @property
    def height(self) -> float:
        return max(0.0, self.bottom - self.top)

    def contains(self, point: Point2) -> bool:
        x, y = float(point[0]), float(point[1])
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def intersects_bbox(self, points: Iterable[Point2]) -> bool:
        pts = tuple(points)
        if not pts:
            return False
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        return not (max(xs) < self.left or min(xs) > self.right or max(ys) < self.top or min(ys) > self.bottom)

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.left, self.top, self.right, self.bottom)


@dataclass(frozen=True, slots=True)
class SceneFaceRef:
    object_id: str
    object_index: int
    face_index: int


@dataclass(frozen=True, slots=True)
class SceneEdgeRef:
    object_id: str
    object_index: int
    edge_index: int


@dataclass(frozen=True, slots=True)
class SceneVertexRef:
    object_id: str
    object_index: int
    vertex_index: int


@dataclass(frozen=True, slots=True)
class BoxSelectionResult:
    rect: ScreenRect | None = None
    mode: BoxSelectionMode = BoxSelectionMode.REPLACE
    targets: tuple[BoxSelectionTarget, ...] = ()
    tool_actor_ids: tuple[str, ...] = ()
    scene_object_ids: tuple[str, ...] = ()
    scene_object_indices: tuple[int, ...] = ()
    scene_faces: tuple[SceneFaceRef, ...] = ()
    scene_edges: tuple[SceneEdgeRef, ...] = ()
    scene_vertices: tuple[SceneVertexRef, ...] = ()
    completed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        return not (self.tool_actor_ids or self.scene_object_ids or self.scene_faces or self.scene_edges or self.scene_vertices)


@dataclass(frozen=True, slots=True)
class BoxSelectionConfig:
    enabled: bool = False
    targets: tuple[BoxSelectionTarget, ...] = (BoxSelectionTarget.TOOL_ACTORS,)
    mode: BoxSelectionMode = BoxSelectionMode.REPLACE
    inside_policy: BoxSelectionInsidePolicy = BoxSelectionInsidePolicy.PARTIAL
    owner_tool: str | None = None
    min_drag_px: float = 6.0
    selectable_only: bool = True
    clear_on_empty: bool = True
    require_empty_press: bool = True
    activation_modifier: BoxSelectionActivationModifier = BoxSelectionActivationModifier.SHIFT
    on_complete: Callable[[BoxSelectionResult, Any], None] | None = None


@dataclass(slots=True)
class BoxSelectionState:
    pending: bool = False
    active: bool = False
    start_screen_pos: Point2 | None = None
    current_screen_pos: Point2 | None = None
    mode_override: BoxSelectionMode | None = None
    last_result: BoxSelectionResult = field(default_factory=BoxSelectionResult)

    @property
    def rect(self) -> ScreenRect | None:
        if self.start_screen_pos is None or self.current_screen_pos is None:
            return None
        return ScreenRect.from_points(self.start_screen_pos, self.current_screen_pos)


class BoxSelectionManager:
    """Screen-space rectangle selection owned by ToolContext."""

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self.config = BoxSelectionConfig()
        self.state = BoxSelectionState()

    def bind_context(self, ctx: Any) -> "BoxSelectionManager":
        self._ctx = ctx
        return self

    def configure(
        self,
        *,
        enabled: bool | None = None,
        targets: Iterable[BoxSelectionTarget | str] | None = None,
        mode: BoxSelectionMode | str | None = None,
        inside_policy: BoxSelectionInsidePolicy | str | None = None,
        owner_tool: str | None = None,
        min_drag_px: float | None = None,
        selectable_only: bool | None = None,
        clear_on_empty: bool | None = None,
        require_empty_press: bool | None = None,
        activation_modifier: BoxSelectionActivationModifier | str | None = None,
        on_complete: Callable[[BoxSelectionResult, Any], None] | None | object = ...,  # ellipsis means keep previous
    ) -> BoxSelectionConfig:
        cfg = self.config
        kwargs: dict[str, Any] = {}
        if enabled is not None:
            kwargs["enabled"] = bool(enabled)
        if targets is not None:
            kwargs["targets"] = tuple(_target(value) for value in targets)
        if mode is not None:
            kwargs["mode"] = _mode(mode)
        if inside_policy is not None:
            kwargs["inside_policy"] = _inside_policy(inside_policy)
        if owner_tool is not None:
            kwargs["owner_tool"] = str(owner_tool)
        if min_drag_px is not None:
            kwargs["min_drag_px"] = max(0.0, float(min_drag_px))
        if selectable_only is not None:
            kwargs["selectable_only"] = bool(selectable_only)
        if clear_on_empty is not None:
            kwargs["clear_on_empty"] = bool(clear_on_empty)
        if require_empty_press is not None:
            kwargs["require_empty_press"] = bool(require_empty_press)
        if activation_modifier is not None:
            kwargs["activation_modifier"] = _activation_modifier(activation_modifier)
        if on_complete is not ...:
            kwargs["on_complete"] = on_complete
        self.config = replace(cfg, **kwargs)
        return self.config

    @property
    def active(self) -> bool:
        return bool(self.state.active)

    @property
    def pending(self) -> bool:
        return bool(self.state.pending)

    def begin(self, screen_pos: Point2, *, mode: BoxSelectionMode | str | None = None) -> None:
        point = _point2(screen_pos)
        self.state.pending = True
        self.state.active = False
        self.state.start_screen_pos = point
        self.state.current_screen_pos = point
        self.state.mode_override = _mode(mode) if mode is not None else None

    def update(self, screen_pos: Point2) -> bool:
        if not self.state.pending:
            return False
        point = _point2(screen_pos)
        self.state.current_screen_pos = point
        start = self.state.start_screen_pos
        if start is None:
            return False
        if screen_distance(start, point) >= float(self.config.min_drag_px):
            self.state.active = True
        return bool(self.state.active)

    def finish(self, screen_pos: Point2 | None = None, *, world_to_screen: WorldToScreen | None = None, apply: bool = True) -> BoxSelectionResult:
        if screen_pos is not None and self.state.pending:
            self.update(screen_pos)
        if not self.state.pending or not self.state.active:
            self.cancel()
            return BoxSelectionResult(completed=False)
        rect = self.state.rect
        if rect is None:
            self.cancel()
            return BoxSelectionResult(completed=False)
        ctx = self._require_ctx()
        mode = self.state.mode_override or self.config.mode
        result = self._collect(rect, world_to_screen=world_to_screen, mode=mode)
        if apply:
            self.apply_result(result)
        self.state.last_result = result
        callback = self.config.on_complete
        self.cancel(keep_last_result=True)
        if callable(callback):
            callback(result, ctx)
        return result

    def cancel(self, *, keep_last_result: bool = False) -> None:
        last = self.state.last_result
        self.state = BoxSelectionState(last_result=last if keep_last_result else last)

    def last_result(self) -> BoxSelectionResult:
        return self.state.last_result

    def handle_event(self, event: ToolEvent, *, world_to_screen: WorldToScreen | None = None) -> bool:
        if not self.config.enabled:
            return False
        if event.type == ToolEventType.CANCEL or event.is_escape:
            self.cancel()
            return True
        if event.type == ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT and event.screen_pos is not None:
            if not self._event_has_activation_modifier(event):
                return False
            if self.config.require_empty_press and self._press_hits_tool_actor(event.screen_pos, world_to_screen):
                return False
            mode = self._mode_from_event(event)
            self.begin(event.screen_pos, mode=mode)
            return False
        if event.type == ToolEventType.MOUSE_MOVE and event.screen_pos is not None and self.state.pending:
            return self.update(event.screen_pos)
        if event.type == ToolEventType.MOUSE_RELEASE and event.screen_pos is not None and self.state.pending:
            result = self.finish(event.screen_pos, world_to_screen=world_to_screen)
            return bool(result.completed)
        return False

    def apply_result(self, result: BoxSelectionResult) -> None:
        ctx = self._require_ctx()
        mode = result.mode
        if BoxSelectionTarget.TOOL_ACTORS in result.targets:
            self._apply_tool_actor_selection(result.tool_actor_ids, mode)
        if BoxSelectionTarget.SCENE_OBJECTS in result.targets:
            self._apply_scene_object_selection(result.scene_object_indices, mode)
        if not result.empty or self.config.clear_on_empty:
            invalidate = getattr(getattr(ctx, "scene_cache", None), "invalidate", None)
            if callable(invalidate):
                invalidate()

    def _collect(self, rect: ScreenRect, *, world_to_screen: WorldToScreen | None, mode: BoxSelectionMode) -> BoxSelectionResult:
        targets = self.config.targets
        tool_actor_ids: tuple[str, ...] = ()
        scene_object_ids: tuple[str, ...] = ()
        scene_object_indices: tuple[int, ...] = ()
        if BoxSelectionTarget.TOOL_ACTORS in targets:
            if world_to_screen is None:
                world_to_screen = _identity_world_to_screen
            tool_actor_ids = self._tool_actor_ids_in_rect(rect, world_to_screen)
        if BoxSelectionTarget.SCENE_OBJECTS in targets:
            if world_to_screen is None:
                world_to_screen = _identity_world_to_screen
            scene_object_ids, scene_object_indices = self._scene_objects_in_rect(rect, world_to_screen)
        return BoxSelectionResult(
            rect=rect,
            mode=mode,
            targets=targets,
            tool_actor_ids=tool_actor_ids,
            scene_object_ids=scene_object_ids,
            scene_object_indices=scene_object_indices,
            completed=True,
            metadata={"inside_policy": self.config.inside_policy.value, "owner_tool": self.config.owner_tool},
        )

    def _tool_actor_ids_in_rect(self, rect: ScreenRect, world_to_screen: WorldToScreen) -> tuple[str, ...]:
        ctx = self._require_ctx()
        hits: list[str] = []
        for actor in ctx.selection.actors(owner_tool=self.config.owner_tool):
            if self.config.selectable_only and not actor.selectable:
                continue
            if _actor_intersects_rect(actor, rect, world_to_screen, self.config.inside_policy):
                hits.append(actor.id)
        return tuple(hits)

    def _scene_objects_in_rect(self, rect: ScreenRect, world_to_screen: WorldToScreen) -> tuple[tuple[str, ...], tuple[int, ...]]:
        ctx = self._require_ctx()
        ids: list[str] = []
        indices: list[int] = []
        try:
            objects = ctx.document.objects()
        except Exception:
            return (), ()
        for obj in objects:
            bounds = _bounds_for_mesh(getattr(obj, "mesh", None))
            if bounds is None:
                continue
            points = tuple(world_to_screen(corner) for corner in _bounds_corners(bounds))
            hit = all(rect.contains(point) for point in points) if self.config.inside_policy == BoxSelectionInsidePolicy.FULL else rect.intersects_bbox(points)
            if hit:
                ids.append(str(obj.id))
                indices.append(int(obj.index))
        return tuple(ids), tuple(indices)

    def _apply_tool_actor_selection(self, actor_ids: Iterable[str], mode: BoxSelectionMode) -> None:
        ctx = self._require_ctx()
        ids = tuple(str(value) for value in actor_ids)
        owner = self.config.owner_tool
        if mode == BoxSelectionMode.REPLACE:
            for selected_id in list(ctx.selection.ids()):
                actor = ctx.selection.actor(selected_id)
                if owner is None or (actor is not None and actor.owner_tool == owner):
                    ctx.selection.deselect(selected_id)
            for actor_id in ids:
                ctx.selection.select(actor_id, replace=False)
            if not ids and self.config.clear_on_empty:
                # Replace + empty means clear matching tool actors only.
                for selected_id in list(ctx.selection.ids()):
                    actor = ctx.selection.actor(selected_id)
                    if owner is None or (actor is not None and actor.owner_tool == owner):
                        ctx.selection.deselect(selected_id)
            return
        if mode == BoxSelectionMode.ADD:
            for actor_id in ids:
                ctx.selection.select(actor_id, replace=False)
            return
        if mode == BoxSelectionMode.SUBTRACT:
            for actor_id in ids:
                ctx.selection.deselect(actor_id)
            return
        if mode == BoxSelectionMode.TOGGLE:
            for actor_id in ids:
                if ctx.selection.is_selected(actor_id):
                    ctx.selection.deselect(actor_id)
                else:
                    ctx.selection.select(actor_id, replace=False)

    def _apply_scene_object_selection(self, indices: Iterable[int], mode: BoxSelectionMode) -> None:
        ctx = self._require_ctx()
        hits = tuple(int(index) for index in indices)
        current = list(ctx.scene_selection.selected_indices())
        if mode == BoxSelectionMode.REPLACE:
            new_indices = list(hits) if hits or self.config.clear_on_empty else current
        elif mode == BoxSelectionMode.ADD:
            new_indices = [*current]
            for index in hits:
                if index not in new_indices:
                    new_indices.append(index)
        elif mode == BoxSelectionMode.SUBTRACT:
            new_indices = [index for index in current if index not in hits]
        else:
            new_indices = [*current]
            for index in hits:
                if index in new_indices:
                    new_indices.remove(index)
                else:
                    new_indices.append(index)
        try:
            ctx.scene_selection.set_selected(new_indices)
        except Exception:
            pass

    def _event_has_activation_modifier(self, event: ToolEvent) -> bool:
        modifier = self.config.activation_modifier
        if modifier == BoxSelectionActivationModifier.NONE:
            return True
        if modifier == BoxSelectionActivationModifier.SHIFT:
            return bool(event.shift)
        if modifier == BoxSelectionActivationModifier.CTRL:
            return bool(event.ctrl)
        if modifier == BoxSelectionActivationModifier.ALT:
            return bool(event.alt)
        return False

    def _mode_from_event(self, event: ToolEvent) -> BoxSelectionMode:
        # When Shift is the activation gesture for the rectangle, it must not
        # silently force additive mode; the configured/panel mode remains the
        # source of truth.  If the tool chooses another activation modifier,
        # Shift can still be used as the classic additive override.
        if event.ctrl and self.config.activation_modifier != BoxSelectionActivationModifier.CTRL:
            return BoxSelectionMode.SUBTRACT
        if event.shift and self.config.activation_modifier != BoxSelectionActivationModifier.SHIFT:
            return BoxSelectionMode.ADD
        return self.config.mode

    def _press_hits_tool_actor(self, screen_pos: Point2, world_to_screen: WorldToScreen | None) -> bool:
        if BoxSelectionTarget.TOOL_ACTORS not in self.config.targets:
            return False
        if world_to_screen is None:
            world_to_screen = _identity_world_to_screen
        ctx = self._require_ctx()
        hit = ctx.selection.hit_test(screen_pos, world_to_screen, owner_tool=self.config.owner_tool, selectable_only=True)
        return hit is not None

    def _require_ctx(self) -> Any:
        if self._ctx is None:
            raise RuntimeError("BoxSelectionManager is not bound to a ToolContext.")
        return self._ctx


def _activation_modifier(value: BoxSelectionActivationModifier | str) -> BoxSelectionActivationModifier:
    if isinstance(value, BoxSelectionActivationModifier):
        return value
    return BoxSelectionActivationModifier(str(value))


def _target(value: BoxSelectionTarget | str) -> BoxSelectionTarget:
    return value if isinstance(value, BoxSelectionTarget) else BoxSelectionTarget(str(value))


def _mode(value: BoxSelectionMode | str) -> BoxSelectionMode:
    return value if isinstance(value, BoxSelectionMode) else BoxSelectionMode(str(value))


def _inside_policy(value: BoxSelectionInsidePolicy | str) -> BoxSelectionInsidePolicy:
    return value if isinstance(value, BoxSelectionInsidePolicy) else BoxSelectionInsidePolicy(str(value))


def _point2(value: Point2) -> Point2:
    return (float(value[0]), float(value[1]))


def _identity_world_to_screen(point: Point3) -> Point2:
    return (float(point[0]), float(point[1]))


def _actor_intersects_rect(actor: ToolActor, rect: ScreenRect, world_to_screen: WorldToScreen, policy: BoxSelectionInsidePolicy) -> bool:
    if not actor.points:
        return False
    kind = actor.kind.value if isinstance(actor.kind, ActorKind) else str(actor.kind)
    projected = tuple(world_to_screen(point) for point in actor.points)
    if policy == BoxSelectionInsidePolicy.FULL:
        return all(rect.contains(point) for point in projected)
    if any(rect.contains(point) for point in projected):
        return True
    if kind == ActorKind.LINE.value and len(projected) >= 2:
        return _segment_intersects_rect(projected[0], projected[1], rect)
    if kind in {ActorKind.POLYLINE.value, ActorKind.ARC.value, ActorKind.CUSTOM.value} and len(projected) >= 2:
        return any(_segment_intersects_rect(a, b, rect) for a, b in zip(projected, projected[1:])) or rect.intersects_bbox(projected)
    if kind == ActorKind.CIRCLE.value and len(projected) >= 2:
        cx, cy = projected[0]
        rx, ry = projected[1]
        radius = hypot(float(rx) - float(cx), float(ry) - float(cy))
        circle_bbox = ((cx - radius, cy - radius), (cx + radius, cy + radius))
        return rect.intersects_bbox(circle_bbox)
    return rect.intersects_bbox(projected)


def _segment_intersects_rect(a: Point2, b: Point2, rect: ScreenRect) -> bool:
    if rect.contains(a) or rect.contains(b):
        return True
    corners = ((rect.left, rect.top), (rect.right, rect.top), (rect.right, rect.bottom), (rect.left, rect.bottom))
    edges = tuple(zip(corners, (*corners[1:], corners[0])))
    return any(_segments_intersect(a, b, edge_a, edge_b) for edge_a, edge_b in edges)


def _segments_intersect(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    def orient(p: Point2, q: Point2, r: Point2) -> float:
        return (float(q[0]) - float(p[0])) * (float(r[1]) - float(p[1])) - (float(q[1]) - float(p[1])) * (float(r[0]) - float(p[0]))

    def on_segment(p: Point2, q: Point2, r: Point2) -> bool:
        return min(float(p[0]), float(r[0])) <= float(q[0]) <= max(float(p[0]), float(r[0])) and min(float(p[1]), float(r[1])) <= float(q[1]) <= max(float(p[1]), float(r[1]))

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    eps = 1.0e-9
    if abs(o1) <= eps and on_segment(a, c, b):
        return True
    if abs(o2) <= eps and on_segment(a, d, b):
        return True
    if abs(o3) <= eps and on_segment(c, a, d):
        return True
    if abs(o4) <= eps and on_segment(c, b, d):
        return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _bounds_for_mesh(mesh: Any) -> tuple[float, float, float, float, float, float] | None:
    if mesh is None:
        return None
    for attr in ("bounds", "GetBounds"):
        value = getattr(mesh, attr, None)
        try:
            raw = value() if callable(value) else value
        except Exception:
            raw = None
        if raw is not None and len(raw) >= 6:
            return tuple(float(v) for v in raw[:6])  # type: ignore[return-value]
    points = getattr(mesh, "points", None)
    if points is None:
        points = getattr(mesh, "vertices", None)
    if points is None:
        return None
    pts = [tuple(float(v) for v in point[:3]) for point in points]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    zs = [p[2] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _bounds_corners(bounds: tuple[float, float, float, float, float, float]) -> tuple[Point3, ...]:
    xmin, xmax, ymin, ymax, zmin, zmax = bounds
    return tuple((x, y, z) for x in (xmin, xmax) for y in (ymin, ymax) for z in (zmin, zmax))


__all__ = [
    "BoxSelectionConfig",
    "BoxSelectionInsidePolicy",
    "BoxSelectionManager",
    "BoxSelectionMode",
    "BoxSelectionResult",
    "BoxSelectionState",
    "BoxSelectionTarget",
    "SceneEdgeRef",
    "SceneFaceRef",
    "SceneVertexRef",
    "ScreenRect",
]

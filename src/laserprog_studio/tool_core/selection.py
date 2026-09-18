"""Shared selection layer for handles, sketch entities and scene items.

The selection layer deliberately separates three ideas that were previously
mixed in tool code:

* the actor geometry that can be hit-tested (point, line, circle, arc, ...);
* the interaction contract exposed by the tool creator (fixed, selectable,
  grabbable);
* the transient state while the user is selecting or dragging.

Tool authors should register ``ToolActor`` objects here instead of writing a
private pick/selection/grab state machine in their own controller.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
from math import hypot
from typing import Any, Callable

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
WorldToScreen = Callable[[Point3], Point2]


class ActorKind(str, Enum):
    POINT = "point"
    LINE = "line"
    CIRCLE = "circle"
    ARC = "arc"
    POLYLINE = "polyline"
    CUSTOM = "custom"


class ActorInteraction(str, Enum):
    FIXED = "fixed"
    SELECTABLE = "selectable"
    GRABBABLE = "grabbable"


@dataclass(frozen=True, slots=True)
class Selectable:
    id: str
    kind: str
    owner_tool: str | None = None
    world_position: Point3 | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolActor:
    """Declarative viewport actor registered by a tool.

    ``interaction`` is the public contract:
    ``FIXED`` means no click/hover/grab action, ``SELECTABLE`` means the actor
    can enter the current selection, and ``GRABBABLE`` means it can be moved only
    after it is selected.  ``GRABBABLE`` intentionally implies selectable.
    """

    id: str
    kind: ActorKind | str
    owner_tool: str | None = None
    points: tuple[Point3, ...] = ()
    interaction: ActorInteraction | str = ActorInteraction.SELECTABLE
    hit_radius_px: float = 10.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def interaction_mode(self) -> ActorInteraction:
        value = self.interaction.value if isinstance(self.interaction, ActorInteraction) else str(self.interaction)
        if value in ActorInteraction._value2member_map_:
            return ActorInteraction(value)
        return ActorInteraction.SELECTABLE

    @property
    def selectable(self) -> bool:
        return self.interaction_mode in {ActorInteraction.SELECTABLE, ActorInteraction.GRABBABLE}

    @property
    def grabbable(self) -> bool:
        return self.interaction_mode == ActorInteraction.GRABBABLE

    @property
    def primary_position(self) -> Point3 | None:
        if self.points:
            return self.points[0]
        return None

    def moved_by(self, delta: Point3) -> "ToolActor":
        dx, dy, dz = (float(delta[0]), float(delta[1]), float(delta[2]))
        return replace(
            self,
            points=tuple((float(x) + dx, float(y) + dy, float(z) + dz) for x, y, z in self.points),
        )


@dataclass(frozen=True, slots=True)
class SelectionHit:
    actor_id: str
    distance_px: float
    kind: str
    interaction: ActorInteraction
    priority: int = 0


@dataclass(slots=True)
class SelectionInteractionState:
    hover_id: str | None = None
    pressed_id: str | None = None
    grabbed_ids: tuple[str, ...] = ()
    grab_active: bool = False
    start_screen_pos: Point2 | None = None
    last_screen_pos: Point2 | None = None
    current_screen_pos: Point2 | None = None
    last_world_pos: Point3 | None = None
    current_world_pos: Point3 | None = None
    empty_press_owner: str | None = None
    empty_press_start: Point2 | None = None
    empty_press_had_selection: bool = False
    empty_press_cleared: bool = False
    last_moved_ids: tuple[str, ...] = ()
    last_move_delta: Point3 | None = None
    dirty_visual_handle_ids: tuple[str, ...] = ()
    dirty_visual_preview_ids: tuple[str, ...] = ()


@dataclass(slots=True)
class _ProjectedHitShape:
    actor: ToolActor
    kind: str
    projected: tuple[Point2, ...]
    bbox: tuple[float, float, float, float]
    projected_holes: tuple[tuple[Point2, ...], ...] = ()
    hole_cells: dict[tuple[int, int], tuple[int, ...]] = field(default_factory=dict)
    hole_fallback: tuple[int, ...] = ()


@dataclass(slots=True)
class _ProjectedHitIndex:
    shapes: tuple[_ProjectedHitShape, ...]
    cells: dict[tuple[int, int], tuple[int, ...]]
    fallback: tuple[int, ...]
    cell_size_px: float


_HIT_INDEX_CELL_SIZE_PX = 96.0
_HIT_INDEX_MAX_CELLS_PER_ACTOR = 512
_HIT_INDEX_MAX_CELLS_PER_HOLE = 128
_HIT_INDEX_CACHE_LIMIT = 8


class SelectionManager:
    def __init__(self) -> None:
        self._items: dict[str, Selectable] = {}
        self._actors: dict[str, ToolActor] = {}
        self._selected: list[str] = []
        self.state = SelectionInteractionState()
        # Screen-space broad phase for dense Creator/Plan Tracer actors.  Cache
        # revisions are scoped by owner so moving a cursor or another tool does
        # not invalidate an unrelated sketch's hover index.
        self._hit_revision_by_owner: dict[str | None, int] = {}
        self._projected_hit_indices: dict[tuple[Any, ...], _ProjectedHitIndex] = {}

    def _touch_hit_geometry(self, owner_tool: str | None) -> None:
        owner = None if owner_tool is None else str(owner_tool)
        self._hit_revision_by_owner[owner] = int(self._hit_revision_by_owner.get(owner, 0)) + 1
        # Bound memory while keeping the common current-camera/current-owner index.
        if len(self._projected_hit_indices) > _HIT_INDEX_CACHE_LIMIT:
            self._projected_hit_indices.clear()

    def _hit_revision(self, owner_tool: str | None) -> int:
        owner = None if owner_tool is None else str(owner_tool)
        return int(self._hit_revision_by_owner.get(owner, 0))

    def register(self, item: Selectable | ToolActor) -> None:
        if isinstance(item, ToolActor):
            self.register_actor(item)
            return
        self._items[item.id] = item

    def register_actor(self, actor: ToolActor) -> ToolActor:
        previous = self._actors.get(actor.id)
        hit_owners: set[str | None] = set()
        if actor.selectable:
            hit_owners.add(actor.owner_tool)
        if previous is not None and previous.selectable:
            hit_owners.add(previous.owner_tool)
        for hit_owner in hit_owners:
            self._touch_hit_geometry(hit_owner)
        self._actors[actor.id] = actor
        # Keep the selected-item API useful for reports and old tools.
        self._items[actor.id] = Selectable(
            id=actor.id,
            kind=str(actor.kind.value if isinstance(actor.kind, ActorKind) else actor.kind),
            owner_tool=actor.owner_tool,
            world_position=actor.primary_position,
            metadata={**actor.metadata, "interaction": actor.interaction_mode.value},
        )
        # Re-registering an existing id with a stricter interaction mode must not
        # leave stale selection/grab state behind.  Fixed actors are inert by
        # contract: no hover, no selection, no grab, even if the id used to be
        # selectable/grabbable in a previous diagnostic step.
        if not actor.selectable:
            self.deselect(actor.id)
            if self.state.hover_id == actor.id:
                self.state.hover_id = None
        if not actor.grabbable and actor.id in self.state.grabbed_ids:
            self.state.grabbed_ids = tuple(value for value in self.state.grabbed_ids if value != actor.id)
            self.state.grab_active = bool(self.state.grabbed_ids)
            if self.state.pressed_id == actor.id:
                self.state.pressed_id = None
        return actor

    def update_actor(self, actor: ToolActor) -> bool:
        if actor.id not in self._actors:
            return False
        self.register_actor(actor)
        return True

    def unregister(self, item_id: str) -> None:
        previous_actor = self._actors.get(item_id)
        if previous_actor is not None and previous_actor.selectable:
            self._touch_hit_geometry(previous_actor.owner_tool)
        self._items.pop(item_id, None)
        self._actors.pop(item_id, None)
        self.deselect(item_id)
        if self.state.hover_id == item_id:
            self.state.hover_id = None
        if self.state.pressed_id == item_id:
            self.state.pressed_id = None
        if item_id in self.state.grabbed_ids:
            self.state.grabbed_ids = tuple(value for value in self.state.grabbed_ids if value != item_id)
            self.state.grab_active = bool(self.state.grabbed_ids)

    def clear_tool(self, owner_tool: str) -> None:
        for item_id, actor in list(self._actors.items()):
            if actor.owner_tool == owner_tool:
                self.unregister(item_id)
        for item_id, item in list(self._items.items()):
            if item.owner_tool == owner_tool:
                self.unregister(item_id)

    def select(self, item_id: str, *, replace: bool = True) -> bool:
        if item_id not in self._items:
            return False
        actor = self._actors.get(item_id)
        if actor is not None and not actor.selectable:
            return False
        if replace:
            self._selected.clear()
        if item_id not in self._selected:
            self._selected.append(item_id)
        return True

    def select_at(
        self,
        screen_pos: Point2,
        world_to_screen: WorldToScreen,
        *,
        owner_tool: str | None = None,
        additive: bool = False,
    ) -> SelectionHit | None:
        hit = self.hit_test(screen_pos, world_to_screen, owner_tool=owner_tool, selectable_only=True)
        if hit is None:
            if not additive:
                self.clear()
            return None
        self.select(hit.actor_id, replace=not additive)
        return hit

    def deselect(self, item_id: str) -> None:
        self._selected = [value for value in self._selected if value != item_id]

    def clear(self) -> None:
        self.clear_selection()

    def clear_selection(self, *, owner_tool: str | None = None) -> int:
        """Clear selected ids without unregistering actors.

        ``owner_tool`` scopes the operation to one Creator tool.  This is the
        semantic empty-click path used by the public interaction API: clicking
        on empty viewport space clears the tool selection but must not destroy
        registered actors or gizmos.
        """

        if owner_tool is None:
            removed = len(self._selected)
            self._selected.clear()
            self.end_grab()
            return removed
        owner = str(owner_tool)
        before = len(self._selected)
        self._selected = [
            item_id
            for item_id in self._selected
            if (self._actors.get(item_id) is None or self._actors[item_id].owner_tool != owner)
            and (self._items.get(item_id) is None or self._items[item_id].owner_tool != owner)
        ]
        if not any(self._actors.get(item_id) is not None and self._actors[item_id].owner_tool == owner for item_id in self.state.grabbed_ids):
            self.end_grab()
        if self.state.hover_id is not None:
            actor = self._actors.get(self.state.hover_id)
            if actor is not None and actor.owner_tool == owner:
                self.state.hover_id = None
        return before - len(self._selected)

    def has_selection(self, *, owner_tool: str | None = None) -> bool:
        if owner_tool is None:
            return bool(self._selected)
        owner = str(owner_tool)
        return any(
            (self._actors.get(item_id) is not None and self._actors[item_id].owner_tool == owner)
            or (self._items.get(item_id) is not None and self._items[item_id].owner_tool == owner)
            for item_id in self._selected
        )

    def ids(self) -> tuple[str, ...]:
        return tuple(self._selected)

    def is_selected(self, item_id: str) -> bool:
        return item_id in self._selected

    def get_selected(self) -> tuple[Selectable, ...]:
        return tuple(self._items[item_id] for item_id in self._selected if item_id in self._items)

    def selected_actors(self) -> tuple[ToolActor, ...]:
        return tuple(self._actors[item_id] for item_id in self._selected if item_id in self._actors)

    def get(self, item_id: str) -> Selectable | None:
        return self._items.get(item_id)

    def actor(self, actor_id: str) -> ToolActor | None:
        return self._actors.get(actor_id)

    def actors(self, *, owner_tool: str | None = None) -> tuple[ToolActor, ...]:
        values = self._actors.values()
        if owner_tool is not None:
            values = [actor for actor in values if actor.owner_tool == owner_tool]
        return tuple(values)

    def set_hover(self, actor_id: str | None) -> None:
        if actor_id is not None and actor_id not in self._actors:
            actor_id = None
        self.state.hover_id = actor_id

    def begin_grab(self, actor_id: str | None, screen_pos: Point2, world_pos: Point3 | None = None) -> tuple[str, ...]:
        """Begin moving the currently selected grabbable actors.

        The actor under the pointer must already be selected and grabbable.  This
        keeps the policy explicit: fixed actors never react, selectable-only
        actors can be picked but not moved, and grabbable actors move only from a
        valid selection.
        """
        if actor_id is None or actor_id not in self._selected:
            self.end_grab()
            return ()
        actor = self._actors.get(actor_id)
        if actor is None or not actor.grabbable:
            self.end_grab()
            return ()
        grabbed = tuple(actor.id for actor in self.selected_actors() if actor.grabbable)
        self.state.last_moved_ids = ()
        self.state.last_move_delta = None
        self.state.dirty_visual_handle_ids = ()
        self.state.dirty_visual_preview_ids = ()
        self.state.pressed_id = actor_id
        self.state.grabbed_ids = grabbed
        self.state.grab_active = bool(grabbed)
        self.state.start_screen_pos = (float(screen_pos[0]), float(screen_pos[1]))
        self.state.last_screen_pos = self.state.start_screen_pos
        self.state.current_screen_pos = self.state.start_screen_pos
        self.state.last_world_pos = _point3(world_pos) if world_pos is not None else None
        self.state.current_world_pos = self.state.last_world_pos
        return grabbed

    def update_grab_screen(self, screen_pos: Point2) -> None:
        if self.state.grab_active:
            self.state.last_screen_pos = self.state.current_screen_pos
            self.state.current_screen_pos = (float(screen_pos[0]), float(screen_pos[1]))

    def update_grab_world(self, world_pos: Point3) -> Point3 | None:
        if not self.state.grab_active:
            return None
        current = _point3(world_pos)
        previous = self.state.current_world_pos
        self.state.last_world_pos = previous
        self.state.current_world_pos = current
        if previous is None:
            return None
        return (current[0] - previous[0], current[1] - previous[1], current[2] - previous[2])

    def end_grab(self) -> tuple[str, ...]:
        grabbed = self.state.grabbed_ids
        self.state.last_moved_ids = ()
        self.state.last_move_delta = None
        self.state.dirty_visual_handle_ids = ()
        self.state.dirty_visual_preview_ids = ()
        self.state.pressed_id = None
        self.state.grabbed_ids = ()
        self.state.grab_active = False
        self.state.start_screen_pos = None
        self.state.last_screen_pos = None
        self.state.current_screen_pos = None
        self.state.last_world_pos = None
        self.state.current_world_pos = None
        return grabbed

    def move_selected(self, delta: Point3, *, grabbable_only: bool = True) -> int:
        changed = 0
        moved_ids: list[str] = []
        for actor in self.selected_actors():
            if grabbable_only and not actor.grabbable:
                continue
            self.register_actor(actor.moved_by(delta))
            moved_ids.append(actor.id)
            changed += 1
        self.state.last_moved_ids = tuple(moved_ids)
        self.state.last_move_delta = _point3(delta) if moved_ids else None
        return changed

    def move_actors_to(self, actor_positions: dict[str, Point3 | ToolActor], *, grabbable_only: bool = True) -> int:
        """Move selected actors to absolute positions or replacement actors.

        This is the snap-aware drag path used by Creator API tools that need a
        screen-projected absolute target instead of a raw world delta.  The
        method still enforces the same selection/grabbable contract as
        :meth:`move_selected`, so fixed actors cannot be moved by a resolver.
        """

        changed = 0
        moved_ids: list[str] = []
        for actor in self.selected_actors():
            if actor.id not in actor_positions:
                continue
            if grabbable_only and not actor.grabbable:
                continue
            replacement = actor_positions[actor.id]
            if isinstance(replacement, ToolActor):
                if replacement.id != actor.id:
                    continue
                new_actor = replacement
            else:
                position = _point3(replacement)
                if not actor.points:
                    continue
                dx = position[0] - float(actor.points[0][0])
                dy = position[1] - float(actor.points[0][1])
                dz = position[2] - float(actor.points[0][2])
                new_actor = actor.moved_by((dx, dy, dz))
            if new_actor.points == actor.points and new_actor.metadata == actor.metadata:
                continue
            self.register_actor(new_actor)
            moved_ids.append(actor.id)
            changed += 1
        self.state.last_moved_ids = tuple(moved_ids)
        self.state.last_move_delta = None
        return changed

    def hit_test(
        self,
        screen_pos: Point2,
        world_to_screen: WorldToScreen,
        *,
        owner_tool: str | None = None,
        selectable_only: bool = False,
        projection_key: Any | None = None,
    ) -> SelectionHit | None:
        # Native Creator interaction supplies a stable camera/projection key.
        # In that path use a cached screen-space broad phase instead of projecting
        # every point of every actor on every mouse move.  Direct low-level callers
        # that do not have a projection key retain the historical exact scan.
        # Keep the diagnostic path exact/verbose when explicitly enabled: its
        # candidate dump is intended to explain every actor considered, whereas
        # the indexed path deliberately visits only nearby candidates.
        if projection_key is not None and str(owner_tool or "") == "plan_trace":
            try:
                from laserprog_studio.services.debug_mode import should_record_diagnostics

                if should_record_diagnostics(None):
                    projection_key = None
            except Exception:
                pass
        if projection_key is not None:
            try:
                return self._hit_test_indexed(
                    screen_pos,
                    world_to_screen,
                    owner_tool=owner_tool,
                    selectable_only=selectable_only,
                    projection_key=projection_key,
                )
            except Exception:
                # Correctness beats the optimization if a custom projector/cache
                # key is malformed.
                pass
        sx, sy = float(screen_pos[0]), float(screen_pos[1])
        best: SelectionHit | None = None
        diagnostic_candidates: list[dict[str, Any]] | None = None
        if str(owner_tool or "") == "plan_trace":
            # Building a diagnostic dictionary for every selectable actor is an
            # O(N) allocation on every hover/click.  The previous code paid that
            # cost even when diagnostics were disabled, which made dense Plan
            # Tracer sketches feel slow in normal mode.
            try:
                from laserprog_studio.services.debug_mode import should_record_diagnostics

                if should_record_diagnostics(None):
                    diagnostic_candidates = []
            except Exception:
                diagnostic_candidates = None
        for actor in self.actors(owner_tool=owner_tool):
            # Public Creator UI visibility is semantic: a hidden API motif must
            # not remain hoverable/selectable just because its ToolActor is kept
            # alive for fast Show all / Hide all toggles.  The metadata key is
            # intentionally namespaced to avoid changing normal tool actors.
            if actor.metadata.get("api_ui_visible") is False:
                continue
            if selectable_only and not actor.selectable:
                continue
            distance = self._distance_to_actor_px(actor, (sx, sy), world_to_screen)
            kind = str(actor.kind.value if isinstance(actor.kind, ActorKind) else actor.kind)
            if diagnostic_candidates is not None:
                metadata = getattr(actor, "metadata", {}) or {}
                diagnostic_candidates.append(
                    {
                        "actor_id": str(actor.id),
                        "kind": kind,
                        "role": str(metadata.get("plan_trace_role", "") or ""),
                        "distance_px": None if distance is None else float(distance),
                        "hit_radius_px": float(actor.hit_radius_px),
                        "inside_hit_radius": bool(distance is not None and distance <= float(actor.hit_radius_px)),
                        "priority": _actor_selection_priority(actor, kind),
                        "selectable": bool(actor.selectable),
                        "selected": bool(self.is_selected(actor.id)),
                        "line_id": metadata.get("plan_trace_sketch_line_id"),
                        "arc_id": metadata.get("plan_trace_sketch_arc_id"),
                        "circle_id": metadata.get("plan_trace_sketch_circle_id"),
                        "face_id": metadata.get("plan_trace_sketch_face_id"),
                    }
                )
            if distance is None or distance > float(actor.hit_radius_px):
                continue
            hit = SelectionHit(
                actor_id=actor.id,
                distance_px=float(distance),
                kind=kind,
                interaction=actor.interaction_mode,
                priority=_actor_selection_priority(actor, kind),
            )
            if best is None or _hit_is_better(hit, best):
                best = hit
        if diagnostic_candidates is not None:
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import record_selection_length_event

                record_selection_length_event(
                    "selection.hit_test.done",
                    screen_pos=(sx, sy),
                    owner_tool=owner_tool,
                    selectable_only=bool(selectable_only),
                    selected_ids=list(self.ids()),
                    winner=(
                        {
                            "actor_id": str(best.actor_id),
                            "distance_px": float(best.distance_px),
                            "kind": str(best.kind),
                            "priority": int(best.priority),
                        }
                        if best is not None
                        else None
                    ),
                    candidates=sorted(
                        diagnostic_candidates,
                        key=lambda item: (
                            item.get("distance_px") is None,
                            float(item.get("distance_px") or 1.0e12),
                            -int(item.get("priority") or 0),
                            str(item.get("actor_id") or ""),
                        ),
                    )[:80],
                )
            except Exception:
                pass
        return best

    def _hit_test_indexed(
        self,
        screen_pos: Point2,
        world_to_screen: WorldToScreen,
        *,
        owner_tool: str | None,
        selectable_only: bool,
        projection_key: Any,
    ) -> SelectionHit | None:
        owner = None if owner_tool is None else str(owner_tool)
        key = (owner, bool(selectable_only), self._hit_revision(owner), projection_key)
        index = self._projected_hit_indices.get(key)
        if index is None:
            index = self._build_projected_hit_index(
                world_to_screen,
                owner_tool=owner,
                selectable_only=selectable_only,
            )
            if len(self._projected_hit_indices) >= _HIT_INDEX_CACHE_LIMIT:
                self._projected_hit_indices.clear()
            self._projected_hit_indices[key] = index

        sx, sy = float(screen_pos[0]), float(screen_pos[1])
        cell = float(index.cell_size_px)
        cell_key = (int(sx // cell), int(sy // cell))
        candidate_indices = set(index.fallback)
        candidate_indices.update(index.cells.get(cell_key, ()))

        best: SelectionHit | None = None
        for shape_index in candidate_indices:
            if shape_index < 0 or shape_index >= len(index.shapes):
                continue
            shape = index.shapes[shape_index]
            actor = shape.actor
            if actor.metadata.get("api_ui_visible") is False:
                continue
            if selectable_only and not actor.selectable:
                continue
            distance = self._distance_to_projected_shape_px(shape, (sx, sy))
            if distance is None or distance > float(actor.hit_radius_px):
                continue
            hit = SelectionHit(
                actor_id=actor.id,
                distance_px=float(distance),
                kind=shape.kind,
                interaction=actor.interaction_mode,
                priority=_actor_selection_priority(actor, shape.kind),
            )
            if best is None or _hit_is_better(hit, best):
                best = hit
        return best

    def _build_projected_hit_index(
        self,
        world_to_screen: WorldToScreen,
        *,
        owner_tool: str | None,
        selectable_only: bool,
    ) -> _ProjectedHitIndex:
        cell_size = float(_HIT_INDEX_CELL_SIZE_PX)
        shapes: list[_ProjectedHitShape] = []
        cells_mut: dict[tuple[int, int], list[int]] = {}
        fallback: list[int] = []

        for actor in self.actors(owner_tool=owner_tool):
            if actor.metadata.get("api_ui_visible") is False:
                continue
            if selectable_only and not actor.selectable:
                continue
            shape = self._project_actor_hit_shape(actor, world_to_screen, cell_size=cell_size)
            if shape is None:
                continue
            shape_index = len(shapes)
            shapes.append(shape)
            if not self._add_bbox_to_cells(
                cells_mut,
                shape.bbox,
                shape_index,
                cell_size=cell_size,
                max_cells=_HIT_INDEX_MAX_CELLS_PER_ACTOR,
            ):
                fallback.append(shape_index)

        return _ProjectedHitIndex(
            shapes=tuple(shapes),
            cells={key: tuple(values) for key, values in cells_mut.items()},
            fallback=tuple(fallback),
            cell_size_px=cell_size,
        )

    @staticmethod
    def _add_bbox_to_cells(
        cells: dict[tuple[int, int], list[int]],
        bbox: tuple[float, float, float, float],
        item_index: int,
        *,
        cell_size: float,
        max_cells: int,
    ) -> bool:
        min_x, min_y, max_x, max_y = bbox
        if not all(_is_finite_number(value) for value in bbox):
            return False
        min_cx = int(float(min_x) // cell_size)
        max_cx = int(float(max_x) // cell_size)
        min_cy = int(float(min_y) // cell_size)
        max_cy = int(float(max_y) // cell_size)
        count = (max_cx - min_cx + 1) * (max_cy - min_cy + 1)
        if count <= 0 or count > int(max_cells):
            return False
        for cx in range(min_cx, max_cx + 1):
            for cy in range(min_cy, max_cy + 1):
                cells.setdefault((cx, cy), []).append(int(item_index))
        return True

    @classmethod
    def _project_actor_hit_shape(
        cls,
        actor: ToolActor,
        world_to_screen: WorldToScreen,
        *,
        cell_size: float,
    ) -> _ProjectedHitShape | None:
        if not actor.points:
            return None
        try:
            projected = tuple(_point2_screen(world_to_screen(point)) for point in actor.points)
        except Exception:
            return None
        if not projected:
            return None
        kind = str(actor.kind.value if isinstance(actor.kind, ActorKind) else actor.kind)
        radius = max(float(actor.hit_radius_px), 0.0)

        if kind == ActorKind.POINT.value or len(projected) == 1:
            x, y = projected[0]
            bbox = (x - radius, y - radius, x + radius, y + radius)
        elif kind == ActorKind.CIRCLE.value and len(projected) >= 2:
            center, radius_point = projected[0], projected[1]
            circle_radius = _distance(center, radius_point)
            pad = circle_radius + radius
            bbox = (center[0] - pad, center[1] - pad, center[0] + pad, center[1] + pad)
        elif actor.metadata.get("filled_polygon_hit") and len(projected) >= 3:
            bbox = _points_bbox(projected, padding=0.0)
        else:
            bbox = _points_bbox(projected, padding=radius)

        projected_holes: list[tuple[Point2, ...]] = []
        hole_cells_mut: dict[tuple[int, int], list[int]] = {}
        hole_fallback: list[int] = []
        if actor.metadata.get("filled_polygon_hit"):
            for hole in actor.metadata.get("filled_polygon_holes") or ():
                try:
                    projected_hole = tuple(_point2_screen(world_to_screen(_point3(point))) for point in hole)
                except Exception:
                    projected_hole = ()
                if len(projected_hole) < 3:
                    continue
                hole_index = len(projected_holes)
                projected_holes.append(projected_hole)
                if not cls._add_bbox_to_cells(
                    hole_cells_mut,
                    _points_bbox(projected_hole, padding=0.0),
                    hole_index,
                    cell_size=cell_size,
                    max_cells=_HIT_INDEX_MAX_CELLS_PER_HOLE,
                ):
                    hole_fallback.append(hole_index)

        return _ProjectedHitShape(
            actor=actor,
            kind=kind,
            projected=projected,
            bbox=bbox,
            projected_holes=tuple(projected_holes),
            hole_cells={key: tuple(values) for key, values in hole_cells_mut.items()},
            hole_fallback=tuple(hole_fallback),
        )

    @staticmethod
    def _distance_to_projected_shape_px(shape: _ProjectedHitShape, screen_pos: Point2) -> float | None:
        actor = shape.actor
        projected = shape.projected
        if not projected:
            return None
        kind = shape.kind
        if kind == ActorKind.POINT.value or len(projected) == 1:
            return _distance(screen_pos, projected[0])
        if kind == ActorKind.LINE.value and len(projected) >= 2:
            return _distance_to_segment(screen_pos, projected[0], projected[1])
        if kind == ActorKind.CIRCLE.value and len(projected) >= 2:
            center, radius_point = projected[0], projected[1]
            radius = _distance(center, radius_point)
            return abs(_distance(screen_pos, center) - radius)
        if actor.metadata.get("filled_polygon_hit") and len(projected) >= 3:
            if not _bbox_contains(shape.bbox, screen_pos) or not _point_in_polygon(screen_pos, projected):
                return None
            if shape.projected_holes:
                cell = float(_HIT_INDEX_CELL_SIZE_PX)
                key = (int(float(screen_pos[0]) // cell), int(float(screen_pos[1]) // cell))
                hole_indices = set(shape.hole_fallback)
                hole_indices.update(shape.hole_cells.get(key, ()))
                for hole_index in hole_indices:
                    if 0 <= hole_index < len(shape.projected_holes):
                        hole = shape.projected_holes[hole_index]
                        if _point_in_polygon(screen_pos, hole):
                            return None
            return max(float(actor.hit_radius_px) * 0.75, 50.0)
        if len(projected) >= 2:
            return min(_distance_to_segment(screen_pos, a, b) for a, b in zip(projected, projected[1:]))
        return None

    @staticmethod
    def _distance_to_actor_px(actor: ToolActor, screen_pos: Point2, world_to_screen: WorldToScreen) -> float | None:
        points = actor.points
        if not points:
            return None
        kind = actor.kind.value if isinstance(actor.kind, ActorKind) else str(actor.kind)
        projected = [world_to_screen(point) for point in points]
        if kind == ActorKind.POINT.value or len(projected) == 1:
            return _distance(screen_pos, projected[0])
        if kind == ActorKind.LINE.value and len(projected) >= 2:
            return _distance_to_segment(screen_pos, projected[0], projected[1])
        if kind == ActorKind.CIRCLE.value and len(projected) >= 2:
            center, radius_point = projected[0], projected[1]
            radius = _distance(center, radius_point)
            return abs(_distance(screen_pos, center) - radius)
        if actor.metadata.get("filled_polygon_hit") and len(projected) >= 3:
            if _point_in_polygon(screen_pos, projected):
                hole_polygons = actor.metadata.get("filled_polygon_holes") or ()
                for hole in hole_polygons:
                    try:
                        projected_hole = [world_to_screen(_point3(point)) for point in hole]
                    except Exception:
                        projected_hole = []
                    if len(projected_hole) >= 3 and _point_in_polygon(screen_pos, projected_hole):
                        return None
                # Return a deliberately large in-hit distance so vertices/edges win
                # when they are under the cursor, but the filled face is still
                # selectable from its interior.
                return max(float(actor.hit_radius_px) * 0.75, 50.0)
            return None
        # Arc/polyline/custom actors use their segment chain as the hit area.
        if len(projected) >= 2:
            return min(_distance_to_segment(screen_pos, a, b) for a, b in zip(projected, projected[1:]))
        return None


def _point2_screen(value: Any) -> Point2:
    return (float(value[0]), float(value[1]))


def _is_finite_number(value: Any) -> bool:
    try:
        from math import isfinite

        return bool(isfinite(float(value)))
    except Exception:
        return False


def _points_bbox(points: tuple[Point2, ...], *, padding: float = 0.0) -> tuple[float, float, float, float]:
    xs = tuple(float(point[0]) for point in points)
    ys = tuple(float(point[1]) for point in points)
    pad = max(float(padding), 0.0)
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def _bbox_contains(bbox: tuple[float, float, float, float], point: Point2) -> bool:
    x, y = float(point[0]), float(point[1])
    return float(bbox[0]) <= x <= float(bbox[2]) and float(bbox[1]) <= y <= float(bbox[3])


def _actor_selection_priority(actor: ToolActor, kind: str) -> int:
    """Return semantic hit priority for overlapping actors.

    CAD/sketch tools expect vertices to win over edges, and edges/curves to win
    over generated filled faces.  Distance is still used inside the same semantic
    class, but priority avoids ambiguous clicks on corners or face interiors from
    selecting the wrong topology level.
    """

    raw = actor.metadata.get("selection_priority")
    if raw is not None:
        try:
            return int(raw)
        except (TypeError, ValueError):
            pass
    role = str(actor.metadata.get("plan_trace_role", "") or "")
    if role == "point":
        return 100
    if role in {"edge", "arc", "circle"}:
        return 70
    if role == "face" or actor.metadata.get("filled_polygon_hit"):
        return 10
    # Generic tools keep the historical nearest-hit behavior unless they opt into
    # semantic priorities through metadata.  This avoids point handles stealing
    # line drags in existing creator UI demos.
    return 0


def _hit_is_better(candidate: SelectionHit, current: SelectionHit) -> bool:
    candidate_distance = float(candidate.distance_px)
    current_distance = float(current.distance_px)
    if int(candidate.priority) != int(current.priority):
        # Semantic priority only resolves genuinely ambiguous hits.  When two
        # topology levels are within this small screen-space band, a vertex wins
        # over an edge and an edge wins over a face.  Outside the band, the
        # geometrically nearest actor must win.  The previous asymmetric test
        # allowed a point several pixels away to keep an exact line hit from ever
        # replacing it, which made Shift-clicking short polyline segments select
        # their endpoints and left Selected length at an em dash.
        priority_band_px = 3.0
        if abs(candidate_distance - current_distance) <= priority_band_px:
            return int(candidate.priority) > int(current.priority)
        return candidate_distance < current_distance
    if candidate_distance != current_distance:
        return candidate_distance < current_distance
    # Stable tie-breaker: deterministic ids prevent flicker when two actors are
    # exactly coincident in screen space.
    return str(candidate.actor_id) < str(current.actor_id)


def _point3(value: Point3) -> Point3:
    return (float(value[0]), float(value[1]), float(value[2]))


def _distance(a: Point2, b: Point2) -> float:
    return hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))


def _distance_to_segment(p: Point2, a: Point2, b: Point2) -> float:
    px, py = float(p[0]), float(p[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    dx, dy = bx - ax, by - ay
    denom = dx * dx + dy * dy
    if denom <= 1.0e-12:
        return hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
    hx, hy = ax + t * dx, ay + t * dy
    return hypot(px - hx, py - hy)


def _point_in_polygon(point: Point2, polygon: list[Point2] | tuple[Point2, ...]) -> bool:
    px, py = float(point[0]), float(point[1])
    inside = False
    pts = list(polygon)
    if len(pts) < 3:
        return False
    j = len(pts) - 1
    for i, current in enumerate(pts):
        xi, yi = float(current[0]), float(current[1])
        xj, yj = float(pts[j][0]), float(pts[j][1])
        # Boundary should behave like a hit too; this avoids a face becoming
        # impossible to select when projected edges are numerically exact.
        if _distance_to_segment((px, py), (xi, yi), (xj, yj)) <= 1.0e-6:
            return True
        intersects = (yi > py) != (yj > py)
        if intersects:
            x_cross = (xj - xi) * (py - yi) / ((yj - yi) or 1.0e-12) + xi
            if px < x_cross:
                inside = not inside
        j = i
    return inside

"""Declarative world-to-screen drawing storage for Creator tools.

This module deliberately contains no VTK, PyVista or Qt dependency. Tools
store immutable world-space primitives here; the application renderer projects
those primitives into persistent ``vtkActor2D`` batches when a live viewport is
available. Small interactive handles share the same owner-scoped registry and
are mirrored into Tool Core selection actors by the manager.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Callable, Iterable, Iterator, TypeAlias
import math

Point3: TypeAlias = tuple[float, float, float]


class ProjectedPrimitiveKind(str, Enum):
    POINT = "point"
    LINE = "line"
    FACE = "face"
    HANDLE = "handle"
    TEXT = "text"
    MESH = "mesh"


class ProjectedInteraction(str, Enum):
    FIXED = "fixed"
    SELECTABLE = "selectable"
    GRABBABLE = "grabbable"


class ProjectedActorKind(str, Enum):
    POINT = "point"
    LINE = "line"
    CIRCLE = "circle"
    ARC = "arc"
    POLYLINE = "polyline"
    FACE = "face"
    HANDLE = "handle"
    CUSTOM = "custom"


class ProjectedHandleShape(str, Enum):
    SOLID = "solid"
    RING = "ring"
    TARGET = "target"
    DIAMOND = "diamond"
    SQUARE = "square"
    ARROW = "arrow"
    AXIS = "axis"
    CHEVRON = "chevron"
    TRIAD = "triad"
    MINIMAL = "minimal"
    TRANSLATE_ARROW = "translate_arrow"


class ProjectedDragConstraint(str, Enum):
    FREE = "free"
    PLANE_XY = "plane_xy"
    AXIS_X = "axis_x"
    AXIS_Y = "axis_y"
    AXIS_Z = "axis_z"


class ProjectedVisualState(str, Enum):
    NORMAL = "normal"
    HOVER = "hover"
    SELECTED = "selected"
    GRABBED = "grabbed"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ProjectedPointStyle:
    color: str = "#DCE7F2"
    size_px: float = 7.0
    opacity: float = 1.0


@dataclass(frozen=True, slots=True)
class ProjectedLineStyle:
    color: str = "#7FC8FF"
    width_px: float = 2.0
    opacity: float = 1.0


@dataclass(frozen=True, slots=True)
class ProjectedFaceStyle:
    fill_color: str = "#4C8EB8"
    fill_opacity: float = 0.24
    outline_color: str | None = "#8FD4FF"
    outline_width_px: float = 1.5
    outline_opacity: float = 0.9


@dataclass(frozen=True, slots=True)
class ProjectedTextStyle:
    color: str = "#E8F1F8"
    size_px: int = 14
    opacity: float = 1.0
    bold: bool = False
    italic: bool = False


@dataclass(frozen=True, slots=True)
class ProjectedHandleStyle:
    size_px: float = 18.0
    line_width_px: float = 2.0
    normal_color: str = "#4AA7FF"
    hover_color: str = "#7AD8FF"
    selected_color: str = "#FFD36B"
    grabbed_color: str = "#FF6E32"
    disabled_color: str = "#697386"
    opacity: float = 1.0

    def color_for(self, state: ProjectedVisualState | str) -> str:
        value = state.value if isinstance(state, ProjectedVisualState) else str(state)
        return {
            ProjectedVisualState.HOVER.value: self.hover_color,
            ProjectedVisualState.SELECTED.value: self.selected_color,
            ProjectedVisualState.GRABBED.value: self.grabbed_color,
            ProjectedVisualState.DISABLED.value: self.disabled_color,
        }.get(value, self.normal_color)


@dataclass(frozen=True, slots=True)
class ProjectedPoint:
    id: str
    position: Point3
    style: ProjectedPointStyle = ProjectedPointStyle()
    layer: int = 20
    visible: bool = True
    interaction: ProjectedInteraction = ProjectedInteraction.FIXED
    hit_radius_px: float = 10.0
    actor_kind: ProjectedActorKind = ProjectedActorKind.POINT
    metadata: tuple[tuple[str, Any], ...] = ()
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.POINT


@dataclass(frozen=True, slots=True)
class ProjectedLine:
    id: str
    points: tuple[Point3, ...]
    style: ProjectedLineStyle = ProjectedLineStyle()
    layer: int = 10
    closed: bool = False
    visible: bool = True
    interaction: ProjectedInteraction = ProjectedInteraction.FIXED
    hit_radius_px: float = 10.0
    actor_kind: ProjectedActorKind = ProjectedActorKind.POLYLINE
    metadata: tuple[tuple[str, Any], ...] = ()
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.LINE


@dataclass(frozen=True, slots=True)
class ProjectedFace:
    id: str
    vertices: tuple[Point3, ...]
    holes: tuple[tuple[Point3, ...], ...] = ()
    style: ProjectedFaceStyle = ProjectedFaceStyle()
    layer: int = 0
    visible: bool = True
    interaction: ProjectedInteraction = ProjectedInteraction.FIXED
    hit_radius_px: float = 8.0
    actor_kind: ProjectedActorKind = ProjectedActorKind.FACE
    metadata: tuple[tuple[str, Any], ...] = ()
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.FACE


@dataclass(frozen=True, slots=True)
class ProjectedText:
    """Persistent text label anchored to one world position."""

    id: str
    text: str
    position: Point3
    style: ProjectedTextStyle = ProjectedTextStyle()
    anchor: str = "center"
    offset_px: tuple[float, float] = (0.0, 0.0)
    layer: int = 40
    visible: bool = True
    metadata: tuple[tuple[str, Any], ...] = ()
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.TEXT


@dataclass(frozen=True, slots=True)
class ProjectedTriangleMesh:
    """Renderer-neutral indexed triangle mesh projected into the 2D overlay."""

    id: str
    vertices: tuple[Point3, ...]
    triangles: tuple[tuple[int, int, int], ...]
    style: ProjectedFaceStyle = ProjectedFaceStyle()
    layer: int = 0
    visible: bool = True
    metadata: tuple[tuple[str, Any], ...] = ()
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.MESH


@dataclass(frozen=True, slots=True)
class ProjectedHandle:
    """Small persistent screen-space handle anchored to one world position."""

    id: str
    position: Point3
    shape: ProjectedHandleShape = ProjectedHandleShape.SOLID
    style: ProjectedHandleStyle = ProjectedHandleStyle()
    direction: Point3 = (1.0, 0.0, 0.0)
    layer: int = 30
    visible: bool = True
    interaction: ProjectedInteraction = ProjectedInteraction.GRABBABLE
    constraint: ProjectedDragConstraint = ProjectedDragConstraint.PLANE_XY
    hit_radius_px: float = 14.0
    visual_state: ProjectedVisualState = ProjectedVisualState.NORMAL
    metadata: tuple[tuple[str, Any], ...] = ()
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.HANDLE


@dataclass(frozen=True, slots=True)
class ProjectedPointCloud:
    """Packed same-style point collection for large static/dense scenes."""

    id: str
    positions: tuple[Point3, ...]
    item_ids: tuple[str, ...] = ()
    style: ProjectedPointStyle = ProjectedPointStyle()
    layer: int = 20
    visible: bool = True
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.POINT


@dataclass(frozen=True, slots=True)
class ProjectedSegmentBatch:
    """Packed same-style independent line segments."""

    id: str
    segments: tuple[tuple[Point3, Point3], ...]
    item_ids: tuple[str, ...] = ()
    style: ProjectedLineStyle = ProjectedLineStyle()
    layer: int = 10
    visible: bool = True
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.LINE


@dataclass(frozen=True, slots=True)
class ProjectedFaceBatch:
    """Packed same-style polygon collection."""

    id: str
    polygons: tuple[tuple[Point3, ...], ...]
    item_ids: tuple[str, ...] = ()
    style: ProjectedFaceStyle = ProjectedFaceStyle()
    layer: int = 0
    visible: bool = True
    kind: ProjectedPrimitiveKind = ProjectedPrimitiveKind.FACE


ProjectedPrimitive: TypeAlias = (
    ProjectedPoint | ProjectedLine | ProjectedFace | ProjectedHandle |
    ProjectedText | ProjectedTriangleMesh |
    ProjectedPointCloud | ProjectedSegmentBatch | ProjectedFaceBatch
)


@dataclass(frozen=True, slots=True)
class ProjectedManipulator:
    """Named group of projected primitives forming one high-level gizmo."""

    id: str
    kind: str
    origin: Point3
    primitives: tuple[ProjectedPrimitive, ...]
    handle_ids: tuple[str, ...]
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectedCoordinatePatch:
    """Exact local-coordinate changes for one already compiled primitive.

    ``chunks`` follows the renderer span order. Each entry contains
    ``(local_point_index, new_world_point)`` pairs, allowing dense batches to
    change a handful of coordinates without comparing or rebuilding the full
    declaration.
    """

    primitive_id: str
    chunks: tuple[tuple[tuple[int, Point3], ...], ...]


@dataclass(frozen=True, slots=True)
class ProjectedDrawingChange:
    """Internal mutation journal consumed by the application-side renderer."""

    owner_tool: str
    revision: int
    operation: str
    # Revision visible to the renderer before this journal entry.  A batch can
    # contain several storage revisions while still representing one atomic
    # incremental renderer update.
    base_revision: int | None = None
    before: tuple[ProjectedPrimitive, ...] = ()
    after: tuple[ProjectedPrimitive, ...] = ()
    patches: tuple[ProjectedCoordinatePatch, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectedDrawingSnapshot:
    owner_tool: str
    revision: int
    visible: bool
    primitives: tuple[ProjectedPrimitive, ...]

    @property
    def points(self) -> tuple[ProjectedPoint, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedPoint))

    @property
    def lines(self) -> tuple[ProjectedLine, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedLine))

    @property
    def faces(self) -> tuple[ProjectedFace, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedFace))

    @property
    def handles(self) -> tuple[ProjectedHandle, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedHandle))

    @property
    def texts(self) -> tuple[ProjectedText, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedText))

    @property
    def meshes(self) -> tuple[ProjectedTriangleMesh, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedTriangleMesh))

    @property
    def point_clouds(self) -> tuple[ProjectedPointCloud, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedPointCloud))

    @property
    def segment_batches(self) -> tuple[ProjectedSegmentBatch, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedSegmentBatch))

    @property
    def face_batches(self) -> tuple[ProjectedFaceBatch, ...]:
        return tuple(item for item in self.primitives if isinstance(item, ProjectedFaceBatch))


class ProjectedDrawingRegistry:
    """Owner-scoped view returned by ``ctx.projected_drawing.for_tool(...)``."""

    def __init__(self, manager: "ProjectedDrawingManager", owner_tool: str) -> None:
        self._manager = manager
        self.owner_tool = str(owner_tool).strip()
        if not self.owner_tool:
            raise ValueError("owner_tool must be non-empty")

    def replace_all(self, primitives: Iterable[ProjectedPrimitive], *, render: bool = True) -> ProjectedDrawingSnapshot:
        return self._manager.replace_all(self.owner_tool, primitives, render=render)

    def add(self, primitive: ProjectedPrimitive, *, replace: bool = False, render: bool = True) -> ProjectedPrimitive:
        return self._manager.add(self.owner_tool, primitive, replace=replace, render=render)

    def add_many(
        self,
        primitives: Iterable[ProjectedPrimitive],
        *,
        replace: bool = False,
        render: bool = True,
    ) -> tuple[ProjectedPrimitive, ...]:
        return self._manager.add_many(self.owner_tool, primitives, replace=replace, render=render)

    def batch(self) -> Any:
        """Coalesce renderer notifications until the surrounding block exits.

        Storage revisions and selection actors are still updated immediately, so
        code inside the block can query the registry normally.  Only the
        application-side world-to-screen synchronisation is deferred.  Nested
        batches are supported and the outermost block performs one final sync.
        """

        return self._manager.batch(self.owner_tool)

    def update(self, primitive: ProjectedPrimitive, *, render: bool = True) -> ProjectedPrimitive:
        return self._manager.update(self.owner_tool, primitive, render=render)

    def update_many(
        self,
        primitives: Iterable[ProjectedPrimitive],
        *,
        render: bool = True,
    ) -> tuple[ProjectedPrimitive, ...]:
        """Update several existing primitives with one revision and one sync."""

        return self._manager.update_many(self.owner_tool, primitives, render=render)

    def patch_point_cloud(
        self,
        primitive_id: str,
        updates: Iterable[tuple[int | str, Iterable[float]]],
        *,
        render: bool = True,
    ) -> ProjectedPointCloud:
        """Change selected points in one packed cloud without rebuilding it."""

        return self._manager.patch_point_cloud(self.owner_tool, primitive_id, updates, render=render)

    def patch_segment_batch(
        self,
        primitive_id: str,
        updates: Iterable[tuple[int | str, Iterable[Iterable[float]]]],
        *,
        render: bool = True,
    ) -> ProjectedSegmentBatch:
        """Replace selected packed segments while preserving batch topology."""

        return self._manager.patch_segment_batch(self.owner_tool, primitive_id, updates, render=render)

    def patch_face(
        self,
        primitive_id: str,
        updates: Iterable[tuple[int, Iterable[float]]],
        *,
        render: bool = True,
    ) -> ProjectedFace:
        """Move selected vertices of one face without retriangulation."""

        return self._manager.patch_face(self.owner_tool, primitive_id, updates, render=render)

    def patch_face_batch(
        self,
        primitive_id: str,
        updates: Iterable[tuple[int | str, Iterable[Iterable[float]]]],
        *,
        render: bool = True,
    ) -> ProjectedFaceBatch:
        """Replace selected polygons of a packed face batch with equal-size polygons."""

        return self._manager.patch_face_batch(self.owner_tool, primitive_id, updates, render=render)

    def get(self, primitive_id: str) -> ProjectedPrimitive | None:
        return self._manager.get(self.owner_tool, primitive_id)

    def items(self) -> tuple[ProjectedPrimitive, ...]:
        return self.snapshot().primitives

    def add_manipulator(
        self,
        manipulator: ProjectedManipulator,
        *,
        replace: bool = False,
        render: bool = True,
    ) -> tuple[ProjectedPrimitive, ...]:
        return self.add_many(manipulator.primitives, replace=replace, render=render)

    def update_positions(
        self,
        updates: dict[str, Iterable[float]] | Iterable[tuple[str, Iterable[float]]],
        *,
        render: bool = True,
        sync_selection: bool = True,
    ) -> int:
        """Move point/handle primitives with one revision and one renderer sync."""

        return self._manager.update_positions(
            self.owner_tool, updates, render=render, sync_selection=sync_selection
        )

    def set_primitive_visible(self, primitive_id: str, visible: bool, *, render: bool = True) -> bool:
        return self._manager.set_primitive_visible(self.owner_tool, primitive_id, visible, render=render)

    def hide(self, primitive_id: str, *, render: bool = True) -> bool:
        return self.set_primitive_visible(primitive_id, False, render=render)

    def show(self, primitive_id: str, *, render: bool = True) -> bool:
        return self.set_primitive_visible(primitive_id, True, render=render)

    def remove(self, primitive_id: str, *, render: bool = True) -> bool:
        return self._manager.remove(self.owner_tool, primitive_id, render=render)

    def remove_many(self, primitive_ids: Iterable[str], *, render: bool = True) -> int:
        return self._manager.remove_many(self.owner_tool, primitive_ids, render=render)

    def clear(self, *, render: bool = True) -> None:
        self._manager.clear_tool(self.owner_tool, render=render)

    def set_visible(self, visible: bool, *, render: bool = True) -> bool:
        return self._manager.set_visible(self.owner_tool, visible, render=render)

    def snapshot(self) -> ProjectedDrawingSnapshot:
        return self._manager.snapshot(self.owner_tool)

    def render(self, *, render: bool = True) -> bool:
        return self._manager.render_tool(self.owner_tool, render=render)

    def sync_interaction_state(self, *, render: bool = True) -> int:
        return self._manager.sync_interaction_state(self.owner_tool, render=render)

    def sync_moved_actors(self, actor_ids: Iterable[str], *, render: bool = True) -> int:
        return self._manager.sync_moved_actors(self.owner_tool, actor_ids, render=render)

    def resolve_drag_positions(self, event: Any) -> dict[str, Point3] | None:
        return self._manager.resolve_drag_positions(self.owner_tool, event)


class ProjectedDrawingManager:
    """Context-owned storage for projected drawings and interactive handles.

    Storage and rendering are intentionally separated.  The manager is useful in
    headless tests by itself; when bound to a live :class:`ToolContext`, mutations
    notify the application-side 2D renderer lazily.
    """

    def __init__(self) -> None:
        self._context: Any | None = None
        self._items: dict[str, dict[str, ProjectedPrimitive]] = {}
        self._revisions: dict[str, int] = {}
        self._visible: dict[str, bool] = {}
        self._changes: dict[str, ProjectedDrawingChange] = {}
        self._batch_depth: dict[str, int] = {}
        self._batch_dirty: dict[str, bool] = {}
        self._batch_render: dict[str, bool] = {}
        self._batch_base_revision: dict[str, int] = {}
        self._batch_before: dict[str, dict[str, ProjectedPrimitive]] = {}
        self._batch_after: dict[str, dict[str, ProjectedPrimitive]] = {}
        self._batch_operations: dict[str, list[str]] = {}
        self._batch_patches: dict[str, list[ProjectedCoordinatePatch]] = {}
        self._sync_renderer: Callable[..., bool] | None = None
        self._dispose_renderer_backend: Callable[..., None] | None = None

    def bind_context(self, context: Any) -> None:
        self._context = context

    def bind_renderer_backend(
        self,
        sync_renderer: Callable[..., bool] | None,
        dispose_renderer: Callable[..., None] | None,
    ) -> None:
        """Bind the application-side renderer without importing it from Tool Core.

        ``tool_core`` owns declarative state only. The live Qt/VTK renderer is
        installed by the application layer when a ``ToolContext`` is attached to
        a real window. Headless tests and pure tool logic can leave the backend
        unbound.
        """

        self._sync_renderer = sync_renderer
        self._dispose_renderer_backend = dispose_renderer

    def for_tool(self, owner_tool: str) -> ProjectedDrawingRegistry:
        return ProjectedDrawingRegistry(self, owner_tool)

    def state_token(self, owner_tool: str) -> tuple[int, bool]:
        """Return the cheap renderer-observable state for one owner.

        Camera frames frequently ask the projected renderer to synchronise even
        when no primitive changed.  Building a full snapshot in that case means
        allocating a tuple of every primitive and rescanning all handles/texts.
        The renderer only needs the revision and owner visibility to decide
        whether a snapshot is necessary.
        """

        owner = self._owner(owner_tool)
        return (
            int(self._revisions.get(owner, 0)),
            bool(self._visible.get(owner, True)),
        )

    @contextmanager
    def batch(self, owner_tool: str) -> Iterator[None]:
        """Defer renderer synchronisation for one owner-scoped mutation group."""

        owner = self._owner(owner_tool)
        depth = int(self._batch_depth.get(owner, 0))
        if depth == 0:
            self._batch_dirty[owner] = False
            self._batch_render[owner] = False
            self._batch_base_revision[owner] = int(self._revisions.get(owner, 0))
            self._batch_before[owner] = {}
            self._batch_after[owner] = {}
            self._batch_operations[owner] = []
            self._batch_patches[owner] = []
        self._batch_depth[owner] = depth + 1
        try:
            yield
        finally:
            remaining = max(0, int(self._batch_depth.get(owner, 1)) - 1)
            if remaining > 0:
                self._batch_depth[owner] = remaining
            else:
                self._batch_depth.pop(owner, None)
                dirty = bool(self._batch_dirty.pop(owner, False))
                render = bool(self._batch_render.pop(owner, False))
                if dirty:
                    self._finalize_batch_change(owner)
                    self._render_tool_now(owner, render=render)
                else:
                    self._discard_batch_journal(owner)

    def _discard_batch_journal(self, owner: str) -> None:
        self._batch_base_revision.pop(owner, None)
        self._batch_before.pop(owner, None)
        self._batch_after.pop(owner, None)
        self._batch_operations.pop(owner, None)
        self._batch_patches.pop(owner, None)

    def _finalize_batch_change(self, owner: str) -> None:
        base_revision = int(self._batch_base_revision.get(owner, self._revisions.get(owner, 0)))
        revision = int(self._revisions.get(owner, base_revision))
        before_map = self._batch_before.get(owner, {})
        after_map = self._batch_after.get(owner, {})
        operations = tuple(self._batch_operations.get(owner, ()))
        patches = tuple(self._batch_patches.get(owner, ()))
        self._discard_batch_journal(owner)
        if revision == base_revision or not operations:
            return

        before_ids = set(before_map)
        after_ids = set(after_map)
        update_ops = {"update", "update_many", "patch"}
        incremental_update = bool(operations) and set(operations).issubset(update_ops) and before_ids == after_ids
        patch_only = incremental_update and set(operations) == {"patch"} and bool(patches)
        operation = "patch" if patch_only else ("update_many" if incremental_update else "batch")
        self._changes[owner] = ProjectedDrawingChange(
            owner_tool=owner,
            revision=revision,
            operation=operation,
            base_revision=base_revision,
            before=tuple(before_map.values()),
            after=tuple(after_map.values()),
            patches=patches if patch_only else (),
        )

    @staticmethod
    def _owner(owner_tool: str) -> str:
        owner = str(owner_tool).strip()
        if not owner:
            raise ValueError("owner_tool must be non-empty")
        return owner

    @staticmethod
    def _validate_primitive(primitive: ProjectedPrimitive) -> ProjectedPrimitive:
        if not isinstance(primitive, (ProjectedPoint, ProjectedLine, ProjectedFace, ProjectedHandle, ProjectedText, ProjectedTriangleMesh, ProjectedPointCloud, ProjectedSegmentBatch, ProjectedFaceBatch)):
            raise TypeError("Projected drawing entries must be projected point, line, face, handle, text, triangle mesh or packed batch instances.")
        if not str(primitive.id).strip():
            raise ValueError("Projected primitive id must be non-empty")
        return primitive

    def _diag_event(self, stage: str, owner: str, **payload: Any) -> None:
        try:
            from laserprog_studio.diagnostics.projected_overlay_debug import record_projected_overlay_event

            context = self._context
            record_projected_overlay_event(
                f"manager.{stage}",
                owner=getattr(context, "owner", None) if context is not None else None,
                ctx=context,
                owner_tool=str(owner),
                manager=self,
                **payload,
            )
        except Exception:
            pass

    def _bump(self, owner: str) -> int:
        revision = int(self._revisions.get(owner, 0)) + 1
        self._revisions[owner] = revision
        return revision

    def _record_change(
        self,
        owner: str,
        revision: int,
        operation: str,
        *,
        before: Iterable[ProjectedPrimitive] = (),
        after: Iterable[ProjectedPrimitive] = (),
        patches: Iterable[ProjectedCoordinatePatch] = (),
    ) -> None:
        before_tuple = tuple(before)
        after_tuple = tuple(after)
        patch_tuple = tuple(patches)
        self._diag_event(
            "record_change",
            owner,
            revision=int(revision),
            operation=str(operation),
            before_count=len(before_tuple),
            after_count=len(after_tuple),
            patch_count=len(patch_tuple),
            after_ids=[str(getattr(item, "id", "")) for item in after_tuple[:12]],
            after_types=[type(item).__name__ for item in after_tuple[:12]],
        )
        if int(self._batch_depth.get(owner, 0)) > 0:
            before_map = self._batch_before.setdefault(owner, {})
            after_map = self._batch_after.setdefault(owner, {})
            for item in before_tuple:
                item_id = str(item.id)
                before_map.setdefault(item_id, item)
                # A remove has no final declaration unless a later operation
                # recreates it in the same atomic batch.
                if str(operation) in {"remove", "remove_many", "clear"}:
                    after_map.pop(item_id, None)
            for item in after_tuple:
                item_id = str(item.id)
                after_map[item_id] = item
                # For a new primitive there is intentionally no before entry.
            self._batch_operations.setdefault(owner, []).append(str(operation))
            self._batch_patches.setdefault(owner, []).extend(patch_tuple)

        self._changes[owner] = ProjectedDrawingChange(
            owner_tool=owner,
            revision=int(revision),
            operation=str(operation),
            base_revision=int(revision) - 1,
            before=before_tuple,
            after=after_tuple,
            patches=patch_tuple,
        )

    def _change_for(self, owner_tool: str, revision: int) -> ProjectedDrawingChange | None:
        owner = self._owner(owner_tool)
        change = self._changes.get(owner)
        if change is None or int(change.revision) != int(revision):
            return None
        return change

    def replace_all(self, owner_tool: str, primitives: Iterable[ProjectedPrimitive], *, render: bool = True) -> ProjectedDrawingSnapshot:
        owner = self._owner(owner_tool)
        ordered: dict[str, ProjectedPrimitive] = {}
        for primitive in primitives:
            item = self._validate_primitive(primitive)
            item_id = str(item.id)
            if item_id in ordered:
                raise ValueError(f"Duplicate projected primitive id {item_id!r}.")
            ordered[item_id] = item
        before = tuple(self._items.get(owner, {}).values())
        self._items[owner] = ordered
        self._visible.setdefault(owner, True)
        revision = self._bump(owner)
        self._record_change(owner, revision, "replace_all", before=before, after=ordered.values())
        self._sync_selection_actors(owner)
        self._notify(owner, render=render)
        return self.snapshot(owner)

    def add(self, owner_tool: str, primitive: ProjectedPrimitive, *, replace: bool = False, render: bool = True) -> ProjectedPrimitive:
        owner = self._owner(owner_tool)
        item = self._validate_primitive(primitive)
        bucket = self._items.setdefault(owner, {})
        if item.id in bucket and not replace:
            raise ValueError(f"Projected primitive {item.id!r} already exists. Pass replace=True to overwrite it.")
        previous = bucket.get(item.id)
        bucket[item.id] = item
        self._visible.setdefault(owner, True)
        revision = self._bump(owner)
        operation = "update" if previous is not None else "add"
        self._record_change(owner, revision, operation, before=(() if previous is None else (previous,)), after=(item,))
        self._sync_selection_delta(owner, (item,))
        self._notify(owner, render=render)
        return item

    def add_many(
        self,
        owner_tool: str,
        primitives: Iterable[ProjectedPrimitive],
        *,
        replace: bool = False,
        render: bool = True,
    ) -> tuple[ProjectedPrimitive, ...]:
        owner = self._owner(owner_tool)
        incoming = tuple(self._validate_primitive(item) for item in primitives)
        bucket = self._items.setdefault(owner, {})
        seen: set[str] = set()
        for item in incoming:
            if item.id in seen:
                raise ValueError(f"Duplicate projected primitive id {item.id!r} in one add_many call.")
            seen.add(item.id)
            if item.id in bucket and not replace:
                raise ValueError(f"Projected primitive {item.id!r} already exists. Pass replace=True to overwrite it.")
        previous = tuple(bucket[item.id] for item in incoming if item.id in bucket)
        for item in incoming:
            bucket[item.id] = item
        if incoming:
            self._visible.setdefault(owner, True)
            revision = self._bump(owner)
            operation = "update_many" if len(previous) == len(incoming) else "add_many"
            self._record_change(owner, revision, operation, before=previous, after=incoming)
            self._sync_selection_delta(owner, incoming)
            self._notify(owner, render=render)
        return incoming

    def update(self, owner_tool: str, primitive: ProjectedPrimitive, *, render: bool = True) -> ProjectedPrimitive:
        owner = self._owner(owner_tool)
        item = self._validate_primitive(primitive)
        bucket = self._items.get(owner, {})
        if item.id not in bucket:
            raise KeyError(f"Unknown projected primitive {item.id!r}.")
        previous = bucket[item.id]
        bucket[item.id] = item
        revision = self._bump(owner)
        self._record_change(owner, revision, "update", before=(previous,), after=(item,))
        self._sync_selection_delta(owner, (item,))
        self._notify(owner, render=render)
        return item

    def update_many(
        self,
        owner_tool: str,
        primitives: Iterable[ProjectedPrimitive],
        *,
        render: bool = True,
    ) -> tuple[ProjectedPrimitive, ...]:
        owner = self._owner(owner_tool)
        incoming = tuple(self._validate_primitive(item) for item in primitives)
        if not incoming:
            return ()
        bucket = self._items.get(owner, {})
        seen: set[str] = set()
        previous: list[ProjectedPrimitive] = []
        for item in incoming:
            if item.id in seen:
                raise ValueError(f"Duplicate projected primitive id {item.id!r} in one update_many call.")
            seen.add(item.id)
            if item.id not in bucket:
                raise KeyError(f"Unknown projected primitive {item.id!r}.")
            previous.append(bucket[item.id])
        for item in incoming:
            bucket[item.id] = item
        revision = self._bump(owner)
        self._record_change(owner, revision, "update_many", before=previous, after=incoming)
        self._sync_selection_delta(owner, incoming)
        self._notify(owner, render=render)
        return incoming

    @staticmethod
    def _coerce_patch_point(value: Iterable[float], *, field: str) -> Point3:
        try:
            numbers = tuple(float(component) for component in value)
        except Exception as exc:
            raise ValueError(f"{field} must contain exactly three finite numbers.") from exc
        if len(numbers) != 3 or not all(math.isfinite(component) for component in numbers):
            raise ValueError(f"{field} must contain exactly three finite numbers.")
        return (numbers[0], numbers[1], numbers[2])

    @staticmethod
    def _resolve_packed_index(reference: int | str, item_ids: tuple[str, ...], count: int, *, field: str) -> int:
        if isinstance(reference, bool):
            raise TypeError(f"{field} index must be an integer or item id, not bool.")
        if isinstance(reference, int):
            index = int(reference)
        else:
            if not item_ids:
                raise KeyError(f"{field} uses item ids, but this packed primitive has no item_ids.")
            try:
                index = item_ids.index(str(reference))
            except ValueError as exc:
                raise KeyError(f"Unknown packed item id {reference!r} in {field}.") from exc
        if index < 0 or index >= int(count):
            raise IndexError(f"{field} index {index} is outside 0..{max(0, int(count) - 1)}.")
        return index

    def _commit_coordinate_patch(
        self,
        owner: str,
        before: ProjectedPrimitive,
        after: ProjectedPrimitive,
        chunks: tuple[tuple[tuple[int, Point3], ...], ...],
        *,
        render: bool,
    ) -> ProjectedPrimitive:
        if not any(chunks):
            return before
        self._items[owner][str(after.id)] = after
        revision = self._bump(owner)
        patch = ProjectedCoordinatePatch(str(after.id), chunks)
        self._record_change(owner, revision, "patch", before=(before,), after=(after,), patches=(patch,))
        self._sync_selection_delta(owner, (after,))
        self._notify(owner, render=render)
        return after

    def patch_point_cloud(
        self,
        owner_tool: str,
        primitive_id: str,
        updates: Iterable[tuple[int | str, Iterable[float]]],
        *,
        render: bool = True,
    ) -> ProjectedPointCloud:
        owner = self._owner(owner_tool)
        primitive = self._items.get(owner, {}).get(str(primitive_id))
        if not isinstance(primitive, ProjectedPointCloud):
            raise TypeError(f"Projected primitive {primitive_id!r} is not a point cloud.")
        positions = list(primitive.positions)
        changed: dict[int, Point3] = {}
        for reference, value in updates:
            index = self._resolve_packed_index(reference, primitive.item_ids, len(positions), field="point_cloud")
            point = self._coerce_patch_point(value, field=f"point_cloud[{reference!r}]")
            if positions[index] != point:
                positions[index] = point
                changed[index] = point
        after = replace(primitive, positions=tuple(positions)) if changed else primitive
        chunk = tuple(sorted(changed.items()))
        return self._commit_coordinate_patch(owner, primitive, after, (chunk,), render=render)  # type: ignore[return-value]

    def patch_segment_batch(
        self,
        owner_tool: str,
        primitive_id: str,
        updates: Iterable[tuple[int | str, Iterable[Iterable[float]]]],
        *,
        render: bool = True,
    ) -> ProjectedSegmentBatch:
        owner = self._owner(owner_tool)
        primitive = self._items.get(owner, {}).get(str(primitive_id))
        if not isinstance(primitive, ProjectedSegmentBatch):
            raise TypeError(f"Projected primitive {primitive_id!r} is not a segment batch.")
        segments = list(primitive.segments)
        changed: dict[int, Point3] = {}
        for reference, value in updates:
            pair = tuple(value)
            if len(pair) != 2:
                raise ValueError(f"segment_batch[{reference!r}] must contain exactly two world points.")
            index = self._resolve_packed_index(reference, primitive.item_ids, len(segments), field="segment_batch")
            segment = (
                self._coerce_patch_point(pair[0], field=f"segment_batch[{reference!r}][0]"),
                self._coerce_patch_point(pair[1], field=f"segment_batch[{reference!r}][1]"),
            )
            if segments[index] != segment:
                segments[index] = segment
                changed[index * 2] = segment[0]
                changed[index * 2 + 1] = segment[1]
        after = replace(primitive, segments=tuple(segments)) if changed else primitive
        chunk = tuple(sorted(changed.items()))
        return self._commit_coordinate_patch(owner, primitive, after, (chunk,), render=render)  # type: ignore[return-value]

    def patch_face(
        self,
        owner_tool: str,
        primitive_id: str,
        updates: Iterable[tuple[int, Iterable[float]]],
        *,
        render: bool = True,
    ) -> ProjectedFace:
        owner = self._owner(owner_tool)
        primitive = self._items.get(owner, {}).get(str(primitive_id))
        if not isinstance(primitive, ProjectedFace):
            raise TypeError(f"Projected primitive {primitive_id!r} is not a face.")
        vertices = list(primitive.vertices)
        changed: dict[int, Point3] = {}
        for reference, value in updates:
            index = self._resolve_packed_index(reference, (), len(vertices), field="face")
            point = self._coerce_patch_point(value, field=f"face[{reference}]")
            if vertices[index] != point:
                vertices[index] = point
                changed[index] = point
        after = replace(primitive, vertices=tuple(vertices)) if changed else primitive
        chunk = tuple(sorted(changed.items()))
        chunks = (chunk, chunk) if primitive.style.outline_color is not None else (chunk,)
        return self._commit_coordinate_patch(owner, primitive, after, chunks, render=render)  # type: ignore[return-value]

    def patch_face_batch(
        self,
        owner_tool: str,
        primitive_id: str,
        updates: Iterable[tuple[int | str, Iterable[Iterable[float]]]],
        *,
        render: bool = True,
    ) -> ProjectedFaceBatch:
        owner = self._owner(owner_tool)
        primitive = self._items.get(owner, {}).get(str(primitive_id))
        if not isinstance(primitive, ProjectedFaceBatch):
            raise TypeError(f"Projected primitive {primitive_id!r} is not a face batch.")
        polygons = list(primitive.polygons)
        offsets: list[int] = []
        running = 0
        for polygon in polygons:
            offsets.append(running)
            running += len(polygon)
        changed: dict[int, Point3] = {}
        for reference, value in updates:
            index = self._resolve_packed_index(reference, primitive.item_ids, len(polygons), field="face_batch")
            polygon = tuple(
                self._coerce_patch_point(point, field=f"face_batch[{reference!r}][{vertex_index}]")
                for vertex_index, point in enumerate(value)
            )
            if len(polygon) != len(polygons[index]):
                raise ValueError(
                    f"face_batch[{reference!r}] must keep {len(polygons[index])} vertices for an incremental patch."
                )
            if polygons[index] != polygon:
                polygons[index] = polygon
                offset = offsets[index]
                for local_index, point in enumerate(polygon):
                    changed[offset + local_index] = point
        after = replace(primitive, polygons=tuple(polygons)) if changed else primitive
        chunk = tuple(sorted(changed.items()))
        chunks = (chunk, chunk) if primitive.style.outline_color is not None else (chunk,)
        return self._commit_coordinate_patch(owner, primitive, after, chunks, render=render)  # type: ignore[return-value]

    @staticmethod
    def _metadata_dict(value: tuple[tuple[str, Any], ...]) -> dict[str, Any]:
        try:
            return {str(key): item for key, item in value}
        except Exception:
            return {}

    @staticmethod
    def _selection_actor_for(owner: str, primitive: ProjectedPrimitive):
        from .selection import ActorInteraction, ActorKind, ToolActor

        interaction_value = getattr(primitive, "interaction", ProjectedInteraction.FIXED)
        interaction_text = interaction_value.value if isinstance(interaction_value, ProjectedInteraction) else str(interaction_value)
        interaction = ActorInteraction(interaction_text) if interaction_text in ActorInteraction._value2member_map_ else ActorInteraction.FIXED
        metadata = dict(ProjectedDrawingManager._metadata_dict(getattr(primitive, "metadata", ())))
        if bool(metadata.get("projected_no_selection_actor", False)):
            return None
        metadata["projected_drawing_id"] = str(primitive.id)
        metadata["projected_drawing_visible"] = bool(getattr(primitive, "visible", True))
        metadata["api_ui_visible"] = bool(getattr(primitive, "visible", True))
        hit_radius = float(getattr(primitive, "hit_radius_px", 10.0))
        actor_kind_value = getattr(primitive, "actor_kind", ProjectedActorKind.POINT)
        actor_kind_text = actor_kind_value.value if isinstance(actor_kind_value, ProjectedActorKind) else str(actor_kind_value)
        if isinstance(primitive, ProjectedHandle):
            metadata["projected_handle_shape"] = primitive.shape.value
            metadata["projected_drag_constraint"] = primitive.constraint.value
            return ToolActor(str(primitive.id), ActorKind.POINT, owner, (primitive.position,), interaction, hit_radius, metadata)
        if isinstance(primitive, ProjectedPoint):
            return ToolActor(str(primitive.id), ActorKind.POINT, owner, (primitive.position,), interaction, hit_radius, metadata)
        if isinstance(primitive, ProjectedLine):
            kind_map = {
                ProjectedActorKind.LINE.value: ActorKind.LINE,
                ProjectedActorKind.CIRCLE.value: ActorKind.CIRCLE,
                ProjectedActorKind.ARC.value: ActorKind.ARC,
                ProjectedActorKind.POLYLINE.value: ActorKind.POLYLINE,
            }
            kind = kind_map.get(actor_kind_text, ActorKind.POLYLINE)
            actor_points = primitive.points
            if kind == ActorKind.CIRCLE:
                circle_hit = metadata.get("circle_hit_points")
                try:
                    values = tuple(tuple(float(component) for component in point) for point in circle_hit)
                except Exception:
                    values = ()
                if len(values) == 2 and all(len(point) == 3 for point in values):
                    actor_points = values
            return ToolActor(str(primitive.id), kind, owner, actor_points, interaction, hit_radius, metadata)
        if isinstance(primitive, ProjectedFace):
            metadata["filled_polygon_hit"] = True
            if primitive.holes:
                metadata["filled_polygon_holes"] = primitive.holes
            metadata.setdefault("selection_priority", 10)
            # Filled polygon hit testing returns a semantic interior distance;
            # keep a generous threshold without enlarging the exterior hit area.
            return ToolActor(str(primitive.id), ActorKind.CUSTOM, owner, primitive.vertices, interaction, max(hit_radius, 64.0), metadata)
        return None

    def _sync_selection_actors(self, owner: str) -> None:
        context = self._context
        selection = getattr(context, "selection", None) if context is not None else None
        if selection is None:
            return
        wanted: set[str] = set()
        for primitive in self._items.get(owner, {}).values():
            actor = self._selection_actor_for(owner, primitive)
            if actor is None:
                continue
            wanted.add(actor.id)
            selection.register_actor(actor)
        for actor in tuple(selection.actors(owner_tool=owner)):
            if actor.id not in wanted:
                selection.unregister(actor.id)

    def _sync_selection_delta(
        self,
        owner: str,
        primitives: Iterable[ProjectedPrimitive] = (),
        *,
        removed_ids: Iterable[str] = (),
    ) -> None:
        """Mirror only changed declarations into Tool Core selection.

        The original implementation rebuilt every selection actor after every
        primitive mutation.  That is acceptable for a tiny gizmo, but Plan
        Tracer can own hundreds or thousands of projected entities and updates
        several of them during every drag event.  Delta mirroring keeps add /
        update operations O(changed) while ``replace_all`` retains the full
        reconciliation path.
        """

        context = self._context
        selection = getattr(context, "selection", None) if context is not None else None
        if selection is None:
            return
        for primitive_id in dict.fromkeys(str(value) for value in removed_ids):
            selection.unregister(primitive_id)
        for primitive in primitives:
            actor = self._selection_actor_for(owner, primitive)
            if actor is None:
                selection.unregister(str(primitive.id))
            else:
                selection.register_actor(actor)

    def sync_interaction_state(
        self,
        owner_tool: str,
        *,
        render: bool = True,
        actor_ids: Iterable[str] | None = None,
    ) -> int:
        owner = self._owner(owner_tool)
        context = self._context
        selection = getattr(context, "selection", None) if context is not None else None
        if selection is None:
            return 0
        bucket = self._items.get(owner, {})
        before: list[ProjectedPrimitive] = []
        changed: list[ProjectedPrimitive] = []
        grabbed = set(getattr(selection.state, "grabbed_ids", ()) or ())
        hover_id = getattr(selection.state, "hover_id", None)
        if actor_ids is None:
            primitives = tuple(bucket.values())
        else:
            # Hover/select/grab changes normally affect only the old/new hover,
            # selection and grabbed actors.  Restricting the visual-state sync to
            # those ids avoids another O(all projected primitives) pass whenever
            # the pointer crosses from one face to the next.
            primitives = tuple(
                bucket[primitive_id]
                for primitive_id in dict.fromkeys(str(value) for value in actor_ids)
                if primitive_id in bucket
            )
        for primitive in primitives:
            if not primitive.visible:
                state = ProjectedVisualState.DISABLED
            elif primitive.id in grabbed:
                state = ProjectedVisualState.GRABBED
            elif primitive.id == hover_id:
                state = ProjectedVisualState.HOVER
            elif selection.is_selected(primitive.id):
                state = ProjectedVisualState.SELECTED
            else:
                state = ProjectedVisualState.NORMAL
            updated: ProjectedPrimitive | None = None
            if isinstance(primitive, ProjectedHandle):
                if primitive.visual_state != state:
                    updated = replace(primitive, visual_state=state)
            elif isinstance(primitive, ProjectedLine):
                metadata = self._metadata_dict(primitive.metadata)
                base = metadata.get("projected_base_line_style")
                if isinstance(base, (tuple, list)) and len(base) == 3:
                    try:
                        normal_color, normal_width, normal_opacity = str(base[0]), float(base[1]), float(base[2])
                        if state == ProjectedVisualState.GRABBED:
                            color, width, opacity = "#e85f18", max(normal_width, 7.0), 1.0
                        elif state == ProjectedVisualState.SELECTED:
                            color, width, opacity = "#f0a805", max(normal_width, 6.0), 1.0
                        elif state == ProjectedVisualState.HOVER:
                            color, width, opacity = "#7357ff", max(normal_width, 5.0), 1.0
                        elif state == ProjectedVisualState.DISABLED:
                            color, width, opacity = normal_color, normal_width, min(normal_opacity, 0.35)
                        else:
                            color, width, opacity = normal_color, normal_width, normal_opacity
                        style = ProjectedLineStyle(color=color, width_px=width, opacity=opacity)
                        if primitive.style != style:
                            updated = replace(primitive, style=style)
                    except Exception:
                        pass
            elif isinstance(primitive, ProjectedFace):
                metadata = self._metadata_dict(primitive.metadata)
                base = metadata.get("projected_base_face_style")
                if isinstance(base, (tuple, list)) and len(base) == 5:
                    try:
                        base_style = ProjectedFaceStyle(
                            fill_color=str(base[0]),
                            fill_opacity=float(base[1]),
                            outline_color=None if base[2] is None else str(base[2]),
                            outline_width_px=float(base[3]),
                            outline_opacity=float(base[4]),
                        )
                        if state in {ProjectedVisualState.HOVER, ProjectedVisualState.SELECTED, ProjectedVisualState.GRABBED}:
                            width = 7.0 if state == ProjectedVisualState.GRABBED else 6.0 if state == ProjectedVisualState.SELECTED else 5.0
                            style = ProjectedFaceStyle(
                                fill_color="#f0a805" if state != ProjectedVisualState.GRABBED else "#e85f18",
                                fill_opacity=0.34,
                                outline_color="#f0a805" if state != ProjectedVisualState.GRABBED else "#e85f18",
                                outline_width_px=max(base_style.outline_width_px, width),
                                outline_opacity=1.0,
                            )
                        elif state == ProjectedVisualState.DISABLED:
                            style = replace(base_style, fill_opacity=min(base_style.fill_opacity, 0.10), outline_opacity=min(base_style.outline_opacity, 0.30))
                        else:
                            style = base_style
                        if primitive.style != style:
                            updated = replace(primitive, style=style)
                    except Exception:
                        pass
            if updated is not None:
                before.append(primitive)
                bucket[primitive.id] = updated
                changed.append(updated)
        if not changed:
            return 0
        revision = self._bump(owner)
        self._record_change(owner, revision, "update_many", before=before, after=changed)
        self._notify(owner, render=render)
        return len(changed)

    def sync_moved_actors(self, owner_tool: str, actor_ids: Iterable[str], *, render: bool = True) -> int:
        owner = self._owner(owner_tool)
        context = self._context
        selection = getattr(context, "selection", None) if context is not None else None
        if selection is None:
            return 0
        bucket = self._items.get(owner, {})
        before: list[ProjectedPrimitive] = []
        after: list[ProjectedPrimitive] = []
        for actor_id in dict.fromkeys(str(value) for value in actor_ids):
            primitive = bucket.get(actor_id)
            actor = selection.actor(actor_id)
            if primitive is None or actor is None or not actor.points:
                continue
            updated: ProjectedPrimitive | None = None
            if isinstance(primitive, ProjectedHandle):
                updated = replace(primitive, position=actor.points[0])
            elif isinstance(primitive, ProjectedPoint):
                updated = replace(primitive, position=actor.points[0])
            elif isinstance(primitive, ProjectedLine) and primitive.actor_kind == ProjectedActorKind.CIRCLE:
                metadata = self._metadata_dict(primitive.metadata)
                try:
                    hit_points = tuple(tuple(float(component) for component in point) for point in metadata.get("circle_hit_points", ()))
                except Exception:
                    hit_points = ()
                if len(hit_points) == 2 and len(actor.points) >= 2:
                    dx = float(actor.points[0][0]) - float(hit_points[0][0])
                    dy = float(actor.points[0][1]) - float(hit_points[0][1])
                    dz = float(actor.points[0][2]) - float(hit_points[0][2])
                    shifted = tuple((point[0] + dx, point[1] + dy, point[2] + dz) for point in primitive.points)
                    shifted_hit = tuple((point[0] + dx, point[1] + dy, point[2] + dz) for point in hit_points)
                    metadata["circle_hit_points"] = shifted_hit
                    updated = replace(primitive, points=shifted, metadata=tuple(metadata.items()))
            elif isinstance(primitive, ProjectedLine) and len(actor.points) == len(primitive.points):
                updated = replace(primitive, points=tuple(actor.points))
            elif isinstance(primitive, ProjectedFace) and len(actor.points) == len(primitive.vertices):
                updated = replace(primitive, vertices=tuple(actor.points))
            if updated is not None and updated != primitive:
                before.append(primitive)
                after.append(updated)
                bucket[actor_id] = updated
        if not after:
            return 0
        revision = self._bump(owner)
        self._record_change(owner, revision, "update_many", before=before, after=after)
        self._notify(owner, render=render)
        return len(after)

    def resolve_drag_positions(self, owner_tool: str, event: Any) -> dict[str, Point3] | None:
        """Resolve projected handle movement with screen-stable axis constraints.

        Axis handles use the projected direction of the corresponding world
        axis.  This keeps X/Y/Z arrows usable even when the pointer's fallback
        world position is constrained to the ground plane.  Plane/free handles
        retain the native incremental world-delta behaviour.
        """

        owner = self._owner(owner_tool)
        context = self._context
        selection = getattr(context, "selection", None) if context is not None else None
        if selection is None:
            return None
        grabbed_ids = tuple(str(actor_id) for actor_id in tuple(getattr(selection.state, "grabbed_ids", ()) or ()))
        grabbed_handles = tuple(
            actor_id
            for actor_id in grabbed_ids
            if isinstance(self._items.get(owner, {}).get(actor_id), ProjectedHandle)
        )
        # Returning None delegates regular grabbable points/lines/faces to the
        # native free-drag path. Do not advance SelectionManager's world cursor
        # here, otherwise the fallback would observe a zero delta.
        if not grabbed_handles:
            return None

        state = selection.state
        previous_world = getattr(state, "current_world_pos", None)
        raw_world = getattr(event, "world_pos", None)
        current_world = tuple(float(value) for value in raw_world) if raw_world is not None else None
        if current_world is not None and previous_world is None:
            state.current_world_pos = current_world
            return None
        world_delta: Point3 | None = None
        if current_world is not None and previous_world is not None:
            world_delta = (
                current_world[0] - float(previous_world[0]),
                current_world[1] - float(previous_world[1]),
                current_world[2] - float(previous_world[2]),
            )

        previous_screen = getattr(state, "last_screen_pos", None)
        current_screen = getattr(state, "current_screen_pos", None)
        screen_delta: tuple[float, float] | None = None
        if previous_screen is not None and current_screen is not None:
            screen_delta = (
                float(current_screen[0]) - float(previous_screen[0]),
                float(current_screen[1]) - float(previous_screen[1]),
            )

        def axis_delta(primitive: ProjectedHandle, actor_point: Point3, axis: Point3) -> Point3 | None:
            if screen_delta is None:
                return None
            projector = getattr(getattr(context, "viewport", None), "world_to_screen", None)
            if not callable(projector):
                return None
            try:
                length = math.sqrt(axis[0] * axis[0] + axis[1] * axis[1] + axis[2] * axis[2])
                if length <= 1.0e-12:
                    return None
                unit_axis = (axis[0] / length, axis[1] / length, axis[2] / length)
                start = projector(actor_point)
                end = projector(
                    (
                        actor_point[0] + unit_axis[0],
                        actor_point[1] + unit_axis[1],
                        actor_point[2] + unit_axis[2],
                    )
                )
                sx = float(end[0]) - float(start[0])
                sy = float(end[1]) - float(start[1])
                pixels_per_world = math.hypot(sx, sy)
                if not math.isfinite(pixels_per_world) or pixels_per_world <= 1.0e-7:
                    return None
                projected_pixels = (screen_delta[0] * sx + screen_delta[1] * sy) / pixels_per_world
                distance_world = projected_pixels / pixels_per_world
                return (
                    unit_axis[0] * distance_world,
                    unit_axis[1] * distance_world,
                    unit_axis[2] * distance_world,
                )
            except Exception:
                return None

        result: dict[str, Point3] = {}
        for actor_id in grabbed_handles:
            primitive = self._items.get(owner, {}).get(str(actor_id))
            actor = selection.actor(str(actor_id))
            if not isinstance(primitive, ProjectedHandle) or actor is None or not actor.points:
                continue
            point = actor.points[0]
            constraint = primitive.constraint
            delta: Point3 | None = None
            if constraint == ProjectedDragConstraint.AXIS_X:
                delta = axis_delta(primitive, point, (1.0, 0.0, 0.0))
            elif constraint == ProjectedDragConstraint.AXIS_Y:
                delta = axis_delta(primitive, point, (0.0, 1.0, 0.0))
            elif constraint == ProjectedDragConstraint.AXIS_Z:
                delta = axis_delta(primitive, point, (0.0, 0.0, 1.0))
            elif world_delta is not None:
                if constraint == ProjectedDragConstraint.PLANE_XY:
                    delta = (world_delta[0], world_delta[1], 0.0)
                else:
                    delta = world_delta

            # Deterministic fallback for headless adapters whose world-to-screen
            # projection cannot represent one of the axes.
            if delta is None and world_delta is not None:
                delta = {
                    ProjectedDragConstraint.AXIS_X: (world_delta[0], 0.0, 0.0),
                    ProjectedDragConstraint.AXIS_Y: (0.0, world_delta[1], 0.0),
                    ProjectedDragConstraint.AXIS_Z: (0.0, 0.0, world_delta[2]),
                    ProjectedDragConstraint.PLANE_XY: (world_delta[0], world_delta[1], 0.0),
                }.get(constraint, world_delta)
            if delta is None:
                continue
            result[str(actor_id)] = (point[0] + delta[0], point[1] + delta[1], point[2] + delta[2])

        # A Shift-selection may contain regular projected actors together with
        # constrained handles. Keep those actors on the native free world-delta
        # path instead of silently freezing them while a handle is grabbed.
        if world_delta is not None:
            for actor_id in grabbed_ids:
                if actor_id in grabbed_handles:
                    continue
                actor = selection.actor(actor_id)
                if actor is None or not actor.points:
                    continue
                point = actor.points[0]
                result[actor_id] = (
                    point[0] + world_delta[0],
                    point[1] + world_delta[1],
                    point[2] + world_delta[2],
                )

        if current_world is not None:
            state.last_world_pos = previous_world
            state.current_world_pos = current_world
        return result or None

    def get(self, owner_tool: str, primitive_id: str) -> ProjectedPrimitive | None:
        owner = self._owner(owner_tool)
        return self._items.get(owner, {}).get(str(primitive_id))

    def update_positions(
        self,
        owner_tool: str,
        updates: dict[str, Iterable[float]] | Iterable[tuple[str, Iterable[float]]],
        *,
        render: bool = True,
        sync_selection: bool = True,
    ) -> int:
        owner = self._owner(owner_tool)
        values = updates.items() if isinstance(updates, dict) else updates
        before: list[ProjectedPrimitive] = []
        changed: list[ProjectedPrimitive] = []
        bucket = self._items.get(owner, {})
        for primitive_id, position in values:
            primitive = bucket.get(str(primitive_id))
            if not isinstance(primitive, (ProjectedPoint, ProjectedHandle, ProjectedText)):
                continue
            try:
                point = tuple(float(component) for component in position)
            except Exception:
                continue
            if len(point) != 3 or not all(math.isfinite(component) for component in point):
                continue
            next_position = (point[0], point[1], point[2])
            if primitive.position == next_position:
                continue
            before.append(primitive)
            updated = replace(primitive, position=next_position)
            bucket[str(primitive.id)] = updated
            changed.append(updated)
        if not changed:
            return 0
        revision = self._bump(owner)
        self._record_change(owner, revision, "update_many", before=before, after=changed)
        if sync_selection:
            self._sync_selection_delta(owner, changed)
        self._notify(owner, render=render)
        return len(changed)

    def set_primitive_visible(self, owner_tool: str, primitive_id: str, visible: bool, *, render: bool = True) -> bool:
        owner = self._owner(owner_tool)
        primitive = self._items.get(owner, {}).get(str(primitive_id))
        if primitive is None or not hasattr(primitive, "visible"):
            return False
        value = bool(visible)
        if bool(getattr(primitive, "visible", True)) == value:
            if render:
                self.render_tool(owner, render=True)
            return False
        self.update(owner, replace(primitive, visible=value), render=render)
        return True

    def remove_many(self, owner_tool: str, primitive_ids: Iterable[str], *, render: bool = True) -> int:
        owner = self._owner(owner_tool)
        bucket = self._items.get(owner)
        if not bucket:
            return 0
        ids = tuple(dict.fromkeys(str(value) for value in primitive_ids))
        before = tuple(bucket[item_id] for item_id in ids if item_id in bucket)
        if not before:
            return 0
        for primitive in before:
            bucket.pop(str(primitive.id), None)
        revision = self._bump(owner)
        self._record_change(owner, revision, "remove_many", before=before)
        self._sync_selection_delta(owner, removed_ids=(primitive.id for primitive in before))
        self._notify(owner, render=render)
        return len(before)

    def remove(self, owner_tool: str, primitive_id: str, *, render: bool = True) -> bool:
        owner = self._owner(owner_tool)
        item_id = str(primitive_id)
        bucket = self._items.get(owner)
        if not bucket or item_id not in bucket:
            return False
        previous = bucket[item_id]
        del bucket[item_id]
        revision = self._bump(owner)
        self._record_change(owner, revision, "remove", before=(previous,))
        self._sync_selection_delta(owner, removed_ids=(item_id,))
        self._notify(owner, render=render)
        return True

    def clear_tool(self, owner_tool: str, *, render: bool = False) -> None:
        owner = self._owner(owner_tool)
        existed = owner in self._items or owner in self._revisions or owner in self._visible
        self._items.pop(owner, None)
        self._revisions.pop(owner, None)
        self._visible.pop(owner, None)
        self._changes.pop(owner, None)
        context = self._context
        if context is not None:
            try:
                context.selection.clear_tool(owner)
            except Exception:
                pass
        self._dispose_renderer(owner, render=render)
        if existed and render and self._context is not None and getattr(self._context, "owner", None) is None:
            try:
                self._context.request_full_render()
            except Exception:
                pass

    def clear(self, *, render: bool = False) -> None:
        owners = tuple(set(self._items) | set(self._revisions) | set(self._visible))
        for owner in owners:
            self.clear_tool(owner, render=False)
        if render and self._context is not None:
            try:
                self._context.request_full_render()
            except Exception:
                pass

    def set_visible(self, owner_tool: str, visible: bool, *, render: bool = True) -> bool:
        owner = self._owner(owner_tool)
        value = bool(visible)
        previous = bool(self._visible.get(owner, True))
        if previous == value:
            if render:
                self.render_tool(owner, render=True)
            return False
        self._visible[owner] = value
        context = self._context
        selection = getattr(context, "selection", None) if context is not None else None
        if selection is not None:
            for actor in tuple(selection.actors(owner_tool=owner)):
                metadata = dict(actor.metadata)
                metadata["api_ui_visible"] = bool(value and metadata.get("projected_drawing_visible", True))
                selection.register_actor(replace(actor, metadata=metadata))
            if not value:
                if getattr(selection.state, "hover_id", None) in {actor.id for actor in selection.actors(owner_tool=owner)}:
                    selection.set_hover(None)
                selection.clear_selection(owner_tool=owner)
        revision = self._bump(owner)
        self._record_change(owner, revision, "visibility")
        self._notify(owner, render=render)
        return True

    def snapshot(self, owner_tool: str) -> ProjectedDrawingSnapshot:
        owner = self._owner(owner_tool)
        return ProjectedDrawingSnapshot(
            owner_tool=owner,
            revision=int(self._revisions.get(owner, 0)),
            visible=bool(self._visible.get(owner, True)),
            primitives=tuple(self._items.get(owner, {}).values()),
        )

    def primitives(self, *, owner_tool: str | None = None) -> tuple[ProjectedPrimitive, ...]:
        if owner_tool is not None:
            return self.snapshot(owner_tool).primitives
        return tuple(item for owner in self._items.values() for item in owner.values())

    def render_tool(self, owner_tool: str, *, render: bool = True) -> bool:
        owner = self._owner(owner_tool)
        if int(self._batch_depth.get(owner, 0)) > 0:
            self._batch_dirty[owner] = True
            self._batch_render[owner] = bool(self._batch_render.get(owner, False) or render)
            return False
        return self._render_tool_now(owner, render=render)

    def _render_tool_now(self, owner: str, *, render: bool) -> bool:
        context = self._context
        host = getattr(context, "owner", None) if context is not None else None
        self._diag_event(
            "render_tool.enter",
            owner,
            render=bool(render),
            has_context=context is not None,
            has_host=host is not None,
            has_sync_backend=callable(self._sync_renderer),
            revision=int(self._revisions.get(owner, 0)),
            item_count=len(self._items.get(owner, {})),
        )
        if host is None:
            self._diag_event("render_tool.no_host", owner, render=bool(render))
            if render and context is not None:
                try:
                    context.request_full_render()
                except Exception as exc:
                    self._diag_event("render_tool.no_host.request_exception", owner, error_type=type(exc).__name__)
            return False
        sync_renderer = self._sync_renderer
        if not callable(sync_renderer):
            self._diag_event("render_tool.no_backend.before_repair", owner, render=bool(render))
            # ``ToolContext`` can be created headlessly and receive its live Qt
            # owner later.  If the runtime forgot to use ``attach_owner()``, try
            # one last owner-aware repair before falling back to a generic render
            # request.  This preserves the Tool Core boundary: the manager calls
            # only a context hook, never the application renderer directly.
            ensure_backend = getattr(context, "ensure_live_projected_drawing_backend", None) if context is not None else None
            if callable(ensure_backend):
                try:
                    repaired = bool(ensure_backend())
                    self._diag_event("render_tool.no_backend.repair_result", owner, repaired=bool(repaired), has_sync_backend=callable(self._sync_renderer))
                except Exception as exc:
                    self._diag_event("render_tool.no_backend.repair_exception", owner, error_type=type(exc).__name__, message=str(exc)[:300])
                sync_renderer = self._sync_renderer
        if not callable(sync_renderer):
            self._diag_event("render_tool.no_backend.final", owner, render=bool(render))
            if render and context is not None:
                try:
                    context.request_full_render()
                except Exception as exc:
                    self._diag_event("render_tool.no_backend.request_exception", owner, error_type=type(exc).__name__)
            return False
        try:
            result = bool(sync_renderer(host, self, owner, render=render))
            self._diag_event("render_tool.sync_result", owner, result=bool(result), render=bool(render))
            return result
        except Exception as exc:
            self._diag_event("render_tool.sync_exception", owner, error_type=type(exc).__name__, message=str(exc)[:500])
            return False

    def _notify(self, owner: str, *, render: bool) -> None:
        self._diag_event("notify", owner, render=bool(render), revision=int(self._revisions.get(owner, 0)), item_count=len(self._items.get(owner, {})))
        result = self.render_tool(owner, render=render)
        self._diag_event("notify.done", owner, result=bool(result), render=bool(render), revision=int(self._revisions.get(owner, 0)))

    def _dispose_renderer(self, owner: str, *, render: bool) -> None:
        context = self._context
        host = getattr(context, "owner", None) if context is not None else None
        if host is None:
            return
        dispose_renderer = self._dispose_renderer_backend
        if not callable(dispose_renderer):
            return
        try:
            dispose_renderer(host, owner, render=render)
        except Exception:
            pass


__all__ = [
    "Point3",
    "ProjectedActorKind",
    "ProjectedDragConstraint",
    "ProjectedHandle",
    "ProjectedHandleShape",
    "ProjectedHandleStyle",
    "ProjectedInteraction",
    "ProjectedVisualState",
    "ProjectedCoordinatePatch",
    "ProjectedDrawingChange",
    "ProjectedDrawingManager",
    "ProjectedDrawingRegistry",
    "ProjectedDrawingSnapshot",
    "ProjectedFace",
    "ProjectedFaceBatch",
    "ProjectedFaceStyle",
    "ProjectedLine",
    "ProjectedManipulator",
    "ProjectedPointCloud",
    "ProjectedSegmentBatch",
    "ProjectedLineStyle",
    "ProjectedPoint",
    "ProjectedPointStyle",
    "ProjectedPrimitive",
    "ProjectedPrimitiveKind",
    "ProjectedText",
    "ProjectedTextStyle",
    "ProjectedTriangleMesh",
]

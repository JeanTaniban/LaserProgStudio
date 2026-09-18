# -*- coding: utf-8 -*-
"""High-throughput persistent ``vtkActor2D`` renderer.

The public API stores immutable world-space primitives.  This backend groups
those primitives by style, keeps VTK actors/topology alive, coalesces camera
projection into NumPy matrix operations, and applies exact coordinate patches
only to affected point ranges.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import math
import time

from laserprog_studio.mesh_ops import parse_hex_color
from laserprog_studio.application.camera_motion_diagnostics import capture_camera_state, classify_camera_motion
from laserprog_studio.application.projected_face_triangulation import (
    triangulate_polygon_cells,
    triangulate_polygon_with_holes_cells,
    triangulation_cache_snapshot,
)
from laserprog_studio.diagnostics.projected_overlay_debug import (
    record_projected_overlay_event,
)

from laserprog_studio.tool_core.projected_drawing import (
    Point3,
    ProjectedCoordinatePatch,
    ProjectedDrawingChange,
    ProjectedDrawingManager,
    ProjectedFace,
    ProjectedFaceBatch,
    ProjectedHandle,
    ProjectedHandleShape,
    ProjectedVisualState,
    ProjectedLine,
    ProjectedPoint,
    ProjectedPointCloud,
    ProjectedSegmentBatch,
    ProjectedText,
    ProjectedTriangleMesh,
    ProjectedPrimitive,
)


@dataclass(frozen=True, slots=True)
class _BatchKey:
    layer: int
    kind: str
    color: str
    opacity: float
    size_px: float


@dataclass(frozen=True, slots=True)
class _CompiledBatch:
    key: _BatchKey
    world_points: tuple[Point3, ...]
    cells: tuple[tuple[int, ...], ...]


@dataclass(frozen=True, slots=True)
class _PrimitiveSpan:
    key: _BatchKey
    start: int
    count: int
    local_cells: tuple[tuple[int, ...], ...]


@dataclass(slots=True)
class _BatchVisual:
    key: _BatchKey
    actor: Any
    mapper: Any
    polydata: Any
    points: Any
    cells: Any
    world_points: tuple[Point3, ...] = ()
    topology: tuple[tuple[int, ...], ...] = ()
    world_array: Any | None = None
    display_array: Any | None = None
    vtk_display_data: Any | None = None
    dirty_all: bool = True
    dirty_indices: set[int] = field(default_factory=set)


@dataclass(slots=True)
class _TextVisual:
    primitive: ProjectedText
    actor: Any
    dirty: bool = True
    display_anchor: tuple[float, float] | None = None
    display_position: tuple[float, float] | None = None


@dataclass(slots=True)
class _HandleVisual:
    primitive: ProjectedHandle
    actor: Any
    mapper: Any
    polydata: Any
    points: Any
    line_cells: Any
    poly_cells: Any
    local_points: tuple[tuple[float, float], ...] = ()
    local_array: Any | None = None
    display_array: Any | None = None
    vtk_display_data: Any | None = None
    dirty: bool = True
    display_center: tuple[float, float] | None = None


def _circle_template(segments: int = 20) -> tuple[tuple[float, float], ...]:
    return tuple((math.cos(2.0 * math.pi * index / segments), math.sin(2.0 * math.pi * index / segments)) for index in range(segments))


def _handle_template(shape: ProjectedHandleShape | str) -> tuple[tuple[tuple[float, float], ...], tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
    """Return normalized display-space points, line cells and polygon cells."""

    value = shape.value if isinstance(shape, ProjectedHandleShape) else str(shape)
    circle = _circle_template(24)
    ring = ((*tuple(range(len(circle))), 0),)
    if value == ProjectedHandleShape.MINIMAL.value:
        pts = _circle_template(10)
        return pts, ((*tuple(range(len(pts))), 0),), (tuple(range(len(pts))),)
    if value == ProjectedHandleShape.SOLID.value:
        return circle, ring, (tuple(range(len(circle))),)
    if value == ProjectedHandleShape.RING.value:
        return circle, ring, ()
    if value == ProjectedHandleShape.TARGET.value:
        pts = (*circle, (-1.35, 0.0), (1.35, 0.0), (0.0, -1.35), (0.0, 1.35))
        return pts, ((*tuple(range(len(circle))), 0), (len(circle), len(circle)+1), (len(circle)+2, len(circle)+3)), ()
    if value == ProjectedHandleShape.DIAMOND.value:
        pts = ((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))
        return pts, ((0, 1, 2, 3, 0),), ((0, 1, 2, 3),)
    if value == ProjectedHandleShape.SQUARE.value:
        pts = ((-0.82, -0.82), (0.82, -0.82), (0.82, 0.82), (-0.82, 0.82))
        return pts, ((0, 1, 2, 3, 0),), ((0, 1, 2, 3),)
    if value == ProjectedHandleShape.CHEVRON.value:
        pts = ((-0.75, -0.75), (0.15, 0.0), (-0.75, 0.75), (0.15, 0.0), (0.85, 0.0))
        return pts, ((0, 1, 2), (3, 4)), ()
    if value == ProjectedHandleShape.TRIAD.value:
        pts: list[tuple[float, float]] = [(0.0, 0.0)]
        lines: list[tuple[int, ...]] = []
        polys: list[tuple[int, ...]] = []
        for angle in (0.0, 2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0):
            ux, uy = math.cos(angle), math.sin(angle)
            px, py = -uy, ux
            start = len(pts)
            pts.extend(((ux * 0.95, uy * 0.95), (ux * 0.60 + px * 0.18, uy * 0.60 + py * 0.18), (ux * 0.60 - px * 0.18, uy * 0.60 - py * 0.18)))
            lines.append((0, start))
            polys.append((start, start + 1, start + 2))
        return tuple(pts), tuple(lines), tuple(polys)
    if value in {ProjectedHandleShape.ARROW.value, ProjectedHandleShape.AXIS.value, ProjectedHandleShape.TRANSLATE_ARROW.value}:
        long = value == ProjectedHandleShape.TRANSLATE_ARROW.value
        axis = value == ProjectedHandleShape.AXIS.value
        tail = -1.15 if long else -0.85
        shoulder = 0.38 if long else 0.25
        tip = 1.15 if long else 0.9
        half = 0.42 if long else 0.34
        pts = ((tail, 0.0), (shoulder, 0.0), (shoulder, half), (tip, 0.0), (shoulder, -half))
        lines = ((0, 1), (2, 3, 4, 2))
        polys = ((2, 3, 4),)
        if axis:
            pts = (*pts, (tail, -0.35), (tail, 0.35))
            lines = (*lines, (5, 6))
        return pts, lines, polys
    return circle, ring, (tuple(range(len(circle))),)


def _kind_rank(kind: str) -> int:
    return {"faces": 0, "lines": 1, "points": 2}.get(str(kind), 9)


def _primitive_chunks(primitive: ProjectedPrimitive) -> tuple[tuple[_BatchKey, tuple[Point3, ...], tuple[tuple[int, ...], ...]], ...]:
    if not bool(getattr(primitive, "visible", True)):
        return ()
    if isinstance(primitive, ProjectedPoint):
        style = primitive.style
        key = _BatchKey(int(primitive.layer), "points", style.color, float(style.opacity), float(style.size_px))
        return ((key, (primitive.position,), ((0,),)),)
    if isinstance(primitive, ProjectedLine):
        style = primitive.style
        key = _BatchKey(int(primitive.layer), "lines", style.color, float(style.opacity), float(style.width_px))
        indexes = tuple(range(len(primitive.points)))
        if primitive.closed and indexes:
            indexes = (*indexes, indexes[0])
        return ((key, primitive.points, (indexes,)),)
    if isinstance(primitive, ProjectedFace):
        style = primitive.style
        chunks: list[tuple[_BatchKey, tuple[Point3, ...], tuple[tuple[int, ...], ...]]] = []
        fill_key = _BatchKey(int(primitive.layer), "faces", style.fill_color, float(style.fill_opacity), 1.0)
        world_points = tuple(primitive.vertices) + tuple(point for ring in primitive.holes for point in ring)
        fill_cells = triangulate_polygon_with_holes_cells(primitive.vertices, primitive.holes)
        chunks.append((fill_key, world_points, fill_cells))
        if style.outline_color is not None:
            outline_key = _BatchKey(
                int(primitive.layer) + 1,
                "lines",
                style.outline_color,
                float(style.outline_opacity),
                float(style.outline_width_px),
            )
            cells: list[tuple[int, ...]] = []
            offset = 0
            for ring in (primitive.vertices, *primitive.holes):
                indexes = tuple(range(offset, offset + len(ring)))
                cells.append((*indexes, indexes[0]))
                offset += len(ring)
            chunks.append((outline_key, world_points, tuple(cells)))
        return tuple(chunks)
    if isinstance(primitive, ProjectedTriangleMesh):
        style = primitive.style
        chunks: list[tuple[_BatchKey, tuple[Point3, ...], tuple[tuple[int, ...], ...]]] = []
        fill_key = _BatchKey(int(primitive.layer), "faces", style.fill_color, float(style.fill_opacity), 1.0)
        chunks.append((fill_key, primitive.vertices, tuple(tuple(cell) for cell in primitive.triangles)))
        if style.outline_color is not None:
            outline_key = _BatchKey(
                int(primitive.layer) + 1,
                "lines",
                style.outline_color,
                float(style.outline_opacity),
                float(style.outline_width_px),
            )
            edges: list[tuple[int, int]] = []
            seen: set[tuple[int, int]] = set()
            for a, b, c in primitive.triangles:
                for u, v in ((a, b), (b, c), (c, a)):
                    edge = (min(u, v), max(u, v))
                    if edge not in seen:
                        seen.add(edge)
                        edges.append((u, v))
            chunks.append((outline_key, primitive.vertices, tuple(edges)))
        return tuple(chunks)
    if isinstance(primitive, ProjectedPointCloud):
        style = primitive.style
        key = _BatchKey(int(primitive.layer), "points", style.color, float(style.opacity), float(style.size_px))
        # Point topology is implicit in the packed batch count; no O(n) cell
        # signature is needed to validate a coordinate-only update.
        return ((key, primitive.positions, ()),)
    if isinstance(primitive, ProjectedSegmentBatch):
        style = primitive.style
        key = _BatchKey(int(primitive.layer), "lines", style.color, float(style.opacity), float(style.width_px))
        points: list[Point3] = []
        cells: list[tuple[int, ...]] = []
        for segment in primitive.segments:
            offset = len(points)
            points.extend(segment)
            cells.append((offset, offset + 1))
        return ((key, tuple(points), tuple(cells)),)
    if isinstance(primitive, ProjectedFaceBatch):
        style = primitive.style
        fill_key = _BatchKey(int(primitive.layer), "faces", style.fill_color, float(style.fill_opacity), 1.0)
        fill_points: list[Point3] = []
        fill_cells: list[tuple[int, ...]] = []
        outline_points: list[Point3] = []
        outline_cells: list[tuple[int, ...]] = []
        for polygon in primitive.polygons:
            fill_offset = len(fill_points)
            fill_points.extend(polygon)
            fill_cells.extend(
                tuple(fill_offset + index for index in cell)
                for cell in triangulate_polygon_cells(polygon)
            )
            if style.outline_color is not None:
                outline_offset = len(outline_points)
                outline_points.extend(polygon)
                outline_cells.append(tuple(outline_offset + index for index in (*tuple(range(len(polygon))), 0)))
        chunks = [(fill_key, tuple(fill_points), tuple(fill_cells))]
        if style.outline_color is not None:
            outline_key = _BatchKey(
                int(primitive.layer) + 1,
                "lines",
                style.outline_color,
                float(style.outline_opacity),
                float(style.outline_width_px),
            )
            chunks.append((outline_key, tuple(outline_points), tuple(outline_cells)))
        return tuple(chunks)
    return ()


def _compile_scene(
    primitives: Iterable[ProjectedPrimitive],
) -> tuple[tuple[_CompiledBatch, ...], dict[str, tuple[_PrimitiveSpan, ...]]]:
    """Compile declarations while avoiding per-primitive temporary chunks.

    Point batches use one VTK poly-vertex cell instead of one cell object per
    point.  Style keys are interned for the duration of the compile.
    """

    grouped: dict[_BatchKey, tuple[list[Point3], list[tuple[int, ...]]]] = {}
    spans: dict[str, tuple[_PrimitiveSpan, ...]] = {}
    key_cache: dict[tuple[Any, ...], _BatchKey] = {}

    def key(layer: int, kind: str, color: str, opacity: float, size_px: float) -> _BatchKey:
        signature = (int(layer), str(kind), str(color), float(opacity), float(size_px))
        cached = key_cache.get(signature)
        if cached is None:
            cached = _BatchKey(*signature)
            key_cache[signature] = cached
        return cached

    for primitive in primitives:
        primitive_id = str(primitive.id)
        if not bool(getattr(primitive, "visible", True)):
            spans[primitive_id] = ()
            continue

        if isinstance(primitive, ProjectedPoint):
            style = primitive.style
            batch_key = key(primitive.layer, "points", style.color, style.opacity, style.size_px)
            points, _cells = grouped.setdefault(batch_key, ([], []))
            offset = len(points)
            points.append(primitive.position)
            spans[primitive_id] = (_PrimitiveSpan(batch_key, offset, 1, ((0,),)),)
            continue

        if isinstance(primitive, ProjectedLine):
            style = primitive.style
            batch_key = key(primitive.layer, "lines", style.color, style.opacity, style.width_px)
            points, cells = grouped.setdefault(batch_key, ([], []))
            offset = len(points)
            points.extend(primitive.points)
            indexes = tuple(range(len(primitive.points)))
            if primitive.closed and indexes:
                indexes = (*indexes, indexes[0])
            cells.append(tuple(offset + index for index in indexes))
            spans[primitive_id] = (_PrimitiveSpan(batch_key, offset, len(primitive.points), (indexes,)),)
            continue

        if isinstance(primitive, ProjectedFace):
            style = primitive.style
            face_spans: list[_PrimitiveSpan] = []
            world_points = tuple(primitive.vertices) + tuple(point for ring in primitive.holes for point in ring)
            fill_key = key(primitive.layer, "faces", style.fill_color, style.fill_opacity, 1.0)
            fill_points, fill_cells = grouped.setdefault(fill_key, ([], []))
            fill_offset = len(fill_points)
            fill_points.extend(world_points)
            polygon_cells = triangulate_polygon_with_holes_cells(primitive.vertices, primitive.holes)
            fill_cells.extend(tuple(fill_offset + index for index in cell) for cell in polygon_cells)
            face_spans.append(_PrimitiveSpan(fill_key, fill_offset, len(world_points), polygon_cells))
            if style.outline_color is not None:
                outline_key = key(
                    int(primitive.layer) + 1,
                    "lines",
                    style.outline_color,
                    style.outline_opacity,
                    style.outline_width_px,
                )
                outline_points, outline_cells = grouped.setdefault(outline_key, ([], []))
                outline_offset = len(outline_points)
                outline_points.extend(world_points)
                rings: list[tuple[int, ...]] = []
                local_offset = 0
                for ring_points in (primitive.vertices, *primitive.holes):
                    indexes = tuple(range(local_offset, local_offset + len(ring_points)))
                    ring = (*indexes, indexes[0])
                    outline_cells.append(tuple(outline_offset + index for index in ring))
                    rings.append(ring)
                    local_offset += len(ring_points)
                face_spans.append(_PrimitiveSpan(outline_key, outline_offset, len(world_points), tuple(rings)))
            spans[primitive_id] = tuple(face_spans)
            continue

        packed_spans: list[_PrimitiveSpan] = []
        for chunk_key, world_points, local_cells in _primitive_chunks(primitive):
            interned = key(chunk_key.layer, chunk_key.kind, chunk_key.color, chunk_key.opacity, chunk_key.size_px)
            points, cells = grouped.setdefault(interned, ([], []))
            offset = len(points)
            points.extend(world_points)
            if interned.kind != "points":
                cells.extend(tuple(offset + index for index in cell) for cell in local_cells)
            packed_spans.append(_PrimitiveSpan(interned, offset, len(world_points), local_cells))
        spans[primitive_id] = tuple(packed_spans)

    result: list[_CompiledBatch] = []
    for batch_key, (points, cells) in grouped.items():
        if batch_key.kind == "points":
            compiled_cells = (tuple(range(len(points))),) if points else ()
        else:
            compiled_cells = tuple(cells)
        result.append(_CompiledBatch(key=batch_key, world_points=tuple(points), cells=compiled_cells))
    ordered = tuple(
        sorted(result, key=lambda batch: (batch.key.layer, _kind_rank(batch.key.kind), batch.key.color, batch.key.size_px))
    )
    return ordered, spans


def _compile_batches(primitives: Iterable[ProjectedPrimitive]) -> tuple[_CompiledBatch, ...]:
    """Compatibility helper used by tests and diagnostic tooling."""

    return _compile_scene(primitives)[0]


class ProjectedDrawingOverlay2D:
    """One owner-tool renderer backed by persistent foreground actors."""

    def __init__(self, owner: Any, manager: ProjectedDrawingManager, owner_tool: str) -> None:
        self.owner = owner
        self.manager = manager
        self.owner_tool = str(owner_tool)
        self.renderer: Any | None = None
        self._observer_id: int | None = None
        self._visuals: dict[_BatchKey, _BatchVisual] = {}
        self._handle_visuals: dict[str, _HandleVisual] = {}
        self._text_visuals: dict[str, _TextVisual] = {}
        self._compiled: tuple[_CompiledBatch, ...] = ()
        self._primitive_spans: dict[str, tuple[_PrimitiveSpan, ...]] = {}
        self._ordered_keys: tuple[_BatchKey, ...] = ()
        self._revision = -1
        self._visible = True
        self._last_projection_signature: tuple[Any, ...] | None = None
        self._last_camera_state: Any | None = None
        self._last_projection_viewport: tuple[float, float, float, float] | None = None
        self._last_sync_camera_mode = "static"
        # Renderer membership only needs auditing after a real scene rebuild.
        # Scanning every VTK prop during each cursor/camera frame dominated the
        # no-op path in Plan Tracer.
        self._attached_scene_generation: int | None = None
        self._diagnostic_metrics: dict[str, Any] = {
            "sync_count": 0,
            "compile_count": 0,
            "projection_count": 0,
            "cache_hit_count": 0,
            "incremental_update_count": 0,
            "vector_projection_count": 0,
            "scalar_projection_count": 0,
            "scalar_fallback_count": 0,
            "last_projection_backend": "none",
            "last_projection_invalid_points": 0,
            "last_projection_outside_points": 0,
        }

    def _main_renderer(self) -> Any | None:
        try:
            return self.owner.plotter.renderer
        except Exception:
            return None

    def _foreground_renderer(self) -> Any | None:
        """Return the layered foreground renderer used for visible 2D overlays.

        The diagnostics from v85 showed a failure mode where projected drawing
        actors were correctly created, present in the live VTK renderer and
        marked visible, yet they were not composed into the Qt/PyVista viewport
        on the user's Windows/VTK stack.  The transform gizmo already avoids
        that class of bugs by rendering helper visuals in a dedicated layer-1
        renderer.  Projected Drawing 2D should use the same foreground layer
        for display props while still using the main renderer camera for world
        -> display projection.
        """

        ensure_overlay = getattr(self.owner, "_ensure_gizmo_overlay_renderer", None)
        if callable(ensure_overlay):
            try:
                overlay = ensure_overlay()
            except Exception as exc:
                record_projected_overlay_event(
                    "renderer.foreground.exception",
                    owner=self.owner,
                    owner_tool=self.owner_tool,
                    renderer=self,
                    error=exc,
                )
                overlay = None
            if overlay is not None:
                try:
                    overlay.SetLayer(1)
                except Exception:
                    pass
                try:
                    overlay.SetInteractive(False)
                except Exception:
                    pass
                try:
                    overlay.SetPreserveDepthBuffer(False)
                except Exception:
                    pass
                try:
                    overlay.SetErase(False)
                except Exception:
                    pass
                return overlay
        return self._main_renderer()

    def _request_render(self, reason: str) -> None:
        request = getattr(self.owner, "request_render", None)
        if callable(request):
            try:
                request(reason=reason)
                return
            except Exception:
                pass
        try:
            self.owner.plotter.render()
        except Exception:
            pass

    def _ensure_renderer(self) -> Any | None:
        renderer = self._foreground_renderer()
        if renderer is None:
            record_projected_overlay_event("renderer.missing", owner=self.owner, owner_tool=self.owner_tool, renderer=self)
            return None
        if renderer is self.renderer:
            return renderer
        # A scene rebuild can replace the VTK renderer, while this Python
        # overlay object and its cached actors remain alive.  Keep the renderer
        # identity update cheap here; actor membership is repaired immediately
        # afterwards by ``_reattach_missing_actors``.
        self._detach_observer()
        self.renderer = renderer
        self._last_projection_signature = None
        self._last_projection_viewport = None
        self._last_camera_state = None
        self._attached_scene_generation = None
        record_projected_overlay_event("renderer.attach", owner=self.owner, owner_tool=self.owner_tool, renderer=self, renderer_id=id(renderer), renderer_type=type(renderer).__name__)
        add_observer = getattr(renderer, "AddObserver", None)
        if callable(add_observer):
            try:
                import vtk

                self._observer_id = int(add_observer(vtk.vtkCommand.StartEvent, self._before_render))
            except Exception:
                try:
                    self._observer_id = int(add_observer("StartEvent", self._before_render))
                except Exception:
                    self._observer_id = None
        return renderer

    def _detach_observer(self) -> None:
        if self.renderer is not None and self._observer_id is not None:
            try:
                self.renderer.RemoveObserver(self._observer_id)
            except Exception:
                pass
        self._observer_id = None

    @staticmethod
    def _add_actor(renderer: Any, actor: Any) -> bool:
        for method in ("AddActor2D", "AddViewProp", "AddActor"):
            callback = getattr(renderer, method, None)
            if callable(callback):
                try:
                    callback(actor)
                    return True
                except Exception:
                    continue
        return False

    def _remove_actor(self, actor: Any) -> None:
        renderer = self.renderer or self._main_renderer()
        if renderer is None or actor is None:
            return
        for method in ("RemoveActor2D", "RemoveViewProp", "RemoveActor"):
            callback = getattr(renderer, method, None)
            if callable(callback):
                try:
                    callback(actor)
                    return
                except Exception:
                    continue

    @staticmethod
    def _renderer_has_actor(renderer: Any, actor: Any) -> bool | None:
        """Return whether ``actor`` is still attached to ``renderer``.

        PyVista scene rebuilds may clear VTK props without going through this
        overlay backend.  In that case our cached visual objects still exist but
        their actors are no longer in the live renderer, so the normal no-op /
        camera-only fast paths keep the overlay invisible.  The helper supports
        both real VTK renderers and the lightweight fake renderers used by the
        tests.  ``None`` means the renderer could not be introspected.
        """

        if renderer is None or actor is None:
            return None
        actors = getattr(renderer, "actors", None)
        if isinstance(actors, list):
            return actor in actors
        get_view_props = getattr(renderer, "GetViewProps", None)
        if callable(get_view_props):
            try:
                props = get_view_props()
                is_present = getattr(props, "IsItemPresent", None)
                if callable(is_present):
                    return bool(is_present(actor))
                init = getattr(props, "InitTraversal", None)
                get_next = getattr(props, "GetNextProp", None)
                if callable(init) and callable(get_next):
                    init()
                    while True:
                        prop = get_next()
                        if prop is None:
                            break
                        if prop is actor:
                            return True
                    return False
            except Exception:
                return None
        return None

    def _reattach_missing_actors(self, renderer: Any, *, force: bool = False) -> int:
        """Re-add cached overlay actors removed by a global scene rebuild.

        ``force`` is used only after a lightweight sentinel check proves that
        the projected-drawing actor set vanished.  It deliberately re-adds the
        cached props without touching unrelated gizmo/selection actors.
        """

        if renderer is None:
            return 0
        visuals = getattr(self, "_visuals", {})
        handle_visuals = getattr(self, "_handle_visuals", {})
        text_visuals = getattr(self, "_text_visuals", {})
        actors: list[Any] = []
        actors.extend(visual.actor for visual in visuals.values())
        actors.extend(visual.actor for visual in handle_visuals.values())
        actors.extend(visual.actor for visual in text_visuals.values())
        reattached = 0
        for actor in actors:
            present = self._renderer_has_actor(renderer, actor)
            if force or present is False:
                if self._add_actor(renderer, actor):
                    reattached += 1
        if reattached:
            self._last_projection_signature = None
            for visual in visuals.values():
                visual.dirty_all = True
                visual.dirty_indices.clear()
            for visual in handle_visuals.values():
                visual.dirty = True
            for visual in text_visuals.values():
                visual.dirty = True
            self._diagnostic_metrics["renderer_reattach_count"] = int(
                self._diagnostic_metrics.get("renderer_reattach_count", 0)
            ) + int(reattached)
            self._diagnostic_metrics["last_renderer_reattached_actors"] = int(reattached)
            record_projected_overlay_event(
                "renderer.reattach_missing_actors",
                owner=self.owner,
                owner_tool=self.owner_tool,
                manager=self.manager,
                renderer=self,
                reattached=int(reattached),
            )
        else:
            self._diagnostic_metrics["last_renderer_reattached_actors"] = 0
        return reattached

    def _projected_actor_sentinel_missing(self, renderer: Any) -> bool:
        """Cheap global-overlay health check used on every sync.

        The foreground renderer is shared by Plan Tracer, Cloth and other
        projected-drawing tools.  A renderer rebuild can remove all props while
        leaving manager revisions and Python visual caches unchanged.  Checking
        one cached actor is enough to detect that state without rescanning the
        whole scene on every mouse move.
        """

        sentinel = None
        visuals = getattr(self, "_visuals", {})
        handles = getattr(self, "_handle_visuals", {})
        texts = getattr(self, "_text_visuals", {})
        if visuals:
            sentinel = next(iter(visuals.values())).actor
        elif handles:
            sentinel = next(iter(handles.values())).actor
        elif texts:
            sentinel = next(iter(texts.values())).actor
        if sentinel is None:
            return False
        return self._renderer_has_actor(renderer, sentinel) is False

    def _live_actor_presence_snapshot(self, renderer: Any | None = None) -> dict[str, Any]:
        """Compact live-state audit for the overlay actor pipeline.

        Building this snapshot traverses every cached and live VTK prop.  It is
        diagnostic-only work, so avoid constructing it entirely in normal mode.
        """

        try:
            from laserprog_studio.services.debug_mode import should_record_diagnostics
            if not should_record_diagnostics(self.owner):
                return {}
        except Exception:
            return {}

        stored_renderer = getattr(self, "renderer", None)
        renderer = renderer or stored_renderer or self._main_renderer()
        visuals = getattr(self, "_visuals", {})
        handle_visuals = getattr(self, "_handle_visuals", {})
        text_visuals = getattr(self, "_text_visuals", {})
        data: dict[str, Any] = {
            "renderer_id": id(renderer) if renderer is not None else None,
            "stored_renderer_id": id(stored_renderer) if stored_renderer is not None else None,
            "batch_visuals": len(visuals),
            "handle_visuals": len(handle_visuals),
            "text_visuals": len(text_visuals),
        }
        present = missing = unknown = visible = hidden = 0
        samples: list[dict[str, Any]] = []
        entries: list[tuple[str, Any, str]] = []
        entries.extend((f"batch:{key.kind}:{key.layer}:{key.color}:{key.size_px}", visual.actor, "batch") for key, visual in visuals.items())
        entries.extend((f"handle:{handle_id}", visual.actor, "handle") for handle_id, visual in handle_visuals.items())
        entries.extend((f"text:{text_id}", visual.actor, "text") for text_id, visual in text_visuals.items())
        for name, actor, kind in entries:
            is_present = self._renderer_has_actor(renderer, actor)
            if is_present is True:
                present += 1
            elif is_present is False:
                missing += 1
            else:
                unknown += 1
            vis_value: Any = None
            try:
                getter = getattr(actor, "GetVisibility", None)
                vis_value = bool(getter()) if callable(getter) else getattr(actor, "visibility", None)
                if bool(vis_value):
                    visible += 1
                else:
                    hidden += 1
            except Exception:
                pass
            if len(samples) < 12:
                samples.append({"name": name, "kind": kind, "present": is_present, "visible": vis_value, "actor_id": id(actor) if actor is not None else None})
        data.update({
            "present": present,
            "missing": missing,
            "unknown": unknown,
            "visible": visible,
            "hidden": hidden,
            "samples": samples,
        })
        try:
            get_view_props = getattr(renderer, "GetViewProps", None) if renderer is not None else None
            if callable(get_view_props):
                props = get_view_props()
                count = getattr(props, "GetNumberOfItems", None)
                if callable(count):
                    data["renderer_view_props"] = int(count())
        except Exception as exc:
            data["renderer_view_props_error"] = type(exc).__name__
        return data

    def _new_visual(self, key: _BatchKey) -> _BatchVisual | None:
        try:
            import vtk

            points = vtk.vtkPoints()
            cells = vtk.vtkCellArray()
            polydata = vtk.vtkPolyData()
            polydata.SetPoints(points)
            if key.kind == "points":
                polydata.SetVerts(cells)
            elif key.kind == "faces":
                polydata.SetPolys(cells)
            else:
                polydata.SetLines(cells)
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetInputData(polydata)
            coordinate = vtk.vtkCoordinate()
            coordinate.SetCoordinateSystemToDisplay()
            mapper.SetTransformCoordinate(coordinate)
            actor = vtk.vtkActor2D()
            actor.SetMapper(mapper)
            prop = actor.GetProperty()
            rgb = parse_hex_color(key.color)
            prop.SetColor(float(rgb[0]), float(rgb[1]), float(rgb[2]))
            prop.SetOpacity(float(key.opacity))
            if key.kind == "points":
                prop.SetPointSize(max(1.0, float(key.size_px)))
            elif key.kind == "lines":
                prop.SetLineWidth(max(1.0, float(key.size_px)))
            try:
                prop.SetDisplayLocationToForeground()
            except Exception:
                pass
            try:
                actor.SetPickable(False)
                actor.SetVisibility(self._visible)
            except Exception:
                pass
            renderer = self._ensure_renderer()
            if renderer is None:
                record_projected_overlay_event("visual.create.no_renderer", owner=self.owner, owner_tool=self.owner_tool, renderer=self, key=key)
                return None
            if not self._add_actor(renderer, actor):
                record_projected_overlay_event("visual.create.add_failed", owner=self.owner, owner_tool=self.owner_tool, renderer=self, key=key, renderer_type=type(renderer).__name__)
                return None
            record_projected_overlay_event("visual.create.ok", owner=self.owner, owner_tool=self.owner_tool, renderer=self, key=key)
            return _BatchVisual(key=key, actor=actor, mapper=mapper, polydata=polydata, points=points, cells=cells)
        except Exception as exc:
            record_projected_overlay_event("visual.create.exception", owner=self.owner, owner_tool=self.owner_tool, renderer=self, key=key, error=exc)
            return None

    def _new_handle_visual(self, primitive: ProjectedHandle) -> _HandleVisual | None:
        try:
            import vtk

            points = vtk.vtkPoints()
            line_cells = vtk.vtkCellArray()
            poly_cells = vtk.vtkCellArray()
            polydata = vtk.vtkPolyData()
            polydata.SetPoints(points)
            polydata.SetLines(line_cells)
            polydata.SetPolys(poly_cells)
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetInputData(polydata)
            coordinate = vtk.vtkCoordinate()
            coordinate.SetCoordinateSystemToDisplay()
            mapper.SetTransformCoordinate(coordinate)
            actor = vtk.vtkActor2D()
            actor.SetMapper(mapper)
            try:
                actor.SetPickable(False)
            except Exception:
                pass
            renderer = self._ensure_renderer()
            if renderer is None:
                record_projected_overlay_event("handle.create.no_renderer", owner=self.owner, owner_tool=self.owner_tool, renderer=self, primitive_id=str(primitive.id))
                return None
            if not self._add_actor(renderer, actor):
                record_projected_overlay_event("handle.create.add_failed", owner=self.owner, owner_tool=self.owner_tool, renderer=self, primitive_id=str(primitive.id), renderer_type=type(renderer).__name__)
                return None
            visual = _HandleVisual(primitive, actor, mapper, polydata, points, line_cells, poly_cells)
            self._configure_handle_visual(visual, primitive, force_topology=True)
            record_projected_overlay_event("handle.create.ok", owner=self.owner, owner_tool=self.owner_tool, renderer=self, primitive_id=str(primitive.id), shape=str(getattr(primitive.shape, "value", primitive.shape)))
            return visual
        except Exception as exc:
            record_projected_overlay_event("handle.create.exception", owner=self.owner, owner_tool=self.owner_tool, renderer=self, primitive_id=str(getattr(primitive, "id", "?")), error=exc)
            return None

    @staticmethod
    def _fill_cell_array(cells_object: Any, cells: tuple[tuple[int, ...], ...]) -> None:
        cells_object.Reset()
        for cell in cells:
            cells_object.InsertNextCell(len(cell))
            for index in cell:
                cells_object.InsertCellPoint(int(index))
        cells_object.Modified()

    def _configure_handle_visual(self, visual: _HandleVisual, primitive: ProjectedHandle, *, force_topology: bool = False) -> None:
        shape_changed = force_topology or visual.primitive.shape != primitive.shape
        if shape_changed:
            points, lines, polys = _handle_template(primitive.shape)
            visual.local_points = points
            try:
                import numpy as np
                visual.local_array = np.asarray(points, dtype=np.float64).reshape((-1, 2))
            except Exception:
                visual.local_array = None
            visual.display_array = None
            visual.vtk_display_data = None
            self._fill_cell_array(visual.line_cells, lines)
            self._fill_cell_array(visual.poly_cells, polys)
            try:
                visual.points.SetNumberOfPoints(len(points))
                visual.polydata.Modified()
            except Exception:
                pass
            visual.dirty = True
        if (
            visual.primitive.position != primitive.position
            or visual.primitive.direction != primitive.direction
            or visual.primitive.style.size_px != primitive.style.size_px
            or visual.primitive.visual_state != primitive.visual_state
        ):
            visual.dirty = True
        visual.primitive = primitive
        prop = visual.actor.GetProperty()
        rgb = parse_hex_color(primitive.style.color_for(primitive.visual_state))
        prop.SetColor(float(rgb[0]), float(rgb[1]), float(rgb[2]))
        prop.SetOpacity(float(primitive.style.opacity))
        try:
            prop.SetLineWidth(max(1.0, float(primitive.style.line_width_px)))
            prop.SetDisplayLocationToForeground()
        except Exception:
            pass
        try:
            visual.actor.SetVisibility(bool(self._visible and primitive.visible))
        except Exception:
            pass

    def _sync_handle_visuals(self, primitives: Iterable[ProjectedPrimitive]) -> bool:
        handles = {str(item.id): item for item in primitives if isinstance(item, ProjectedHandle)}
        changed = False
        for handle_id in tuple(self._handle_visuals):
            if handle_id not in handles:
                self._remove_actor(self._handle_visuals[handle_id].actor)
                del self._handle_visuals[handle_id]
                changed = True
        for handle_id, primitive in handles.items():
            visual = self._handle_visuals.get(handle_id)
            if visual is None:
                visual = self._new_handle_visual(primitive)
                if visual is None:
                    continue
                self._handle_visuals[handle_id] = visual
                changed = True
            else:
                previous = visual.primitive
                self._configure_handle_visual(visual, primitive)
                changed = changed or previous != primitive
        return changed

    @staticmethod
    def _configure_text_anchor(prop: Any, anchor: str) -> None:
        value = str(anchor).lower()
        horizontal = "left" if "left" in value else "right" if "right" in value else "center"
        vertical = "top" if "top" in value else "bottom" if "bottom" in value else "center"
        method = {
            "left": "SetJustificationToLeft",
            "right": "SetJustificationToRight",
            "center": "SetJustificationToCentered",
        }[horizontal]
        callback = getattr(prop, method, None)
        if callable(callback):
            callback()
        vertical_method = {
            "top": "SetVerticalJustificationToTop",
            "bottom": "SetVerticalJustificationToBottom",
            "center": "SetVerticalJustificationToCentered",
        }[vertical]
        callback = getattr(prop, vertical_method, None)
        if callable(callback):
            callback()

    def _new_text_visual(self, primitive: ProjectedText) -> _TextVisual | None:
        try:
            import vtk

            actor = vtk.vtkTextActor()
            try:
                actor.SetPickable(False)
            except Exception:
                pass
            renderer = self._ensure_renderer()
            if renderer is None or not self._add_actor(renderer, actor):
                return None
            visual = _TextVisual(primitive=primitive, actor=actor, dirty=True)
            self._configure_text_visual(visual, primitive, force=True)
            return visual
        except Exception:
            return None

    def _configure_text_visual(self, visual: _TextVisual, primitive: ProjectedText, *, force: bool = False) -> None:
        previous = visual.primitive
        if force or previous.position != primitive.position or previous.offset_px != primitive.offset_px:
            visual.dirty = True
        visual.primitive = primitive
        try:
            visual.actor.SetInput(str(primitive.text))
        except Exception:
            pass
        try:
            prop = visual.actor.GetTextProperty()
            rgb = parse_hex_color(primitive.style.color)
            prop.SetColor(float(rgb[0]), float(rgb[1]), float(rgb[2]))
            prop.SetOpacity(float(primitive.style.opacity))
            prop.SetFontSize(max(1, int(primitive.style.size_px)))
            if hasattr(prop, "SetBold"):
                prop.SetBold(bool(primitive.style.bold))
            elif bool(primitive.style.bold) and hasattr(prop, "BoldOn"):
                prop.BoldOn()
            if hasattr(prop, "SetItalic"):
                prop.SetItalic(bool(primitive.style.italic))
            elif bool(primitive.style.italic) and hasattr(prop, "ItalicOn"):
                prop.ItalicOn()

            # Optional renderer-side text decoration.  Keeping it in metadata
            # avoids expanding the public ProjectedTextStyle contract for a
            # capability that is currently only needed by a few labels.
            metadata = dict(primitive.metadata)
            background_color = metadata.get("text_background_color")
            background_opacity = float(metadata.get("text_background_opacity", 0.0) or 0.0)
            if background_color and hasattr(prop, "SetBackgroundColor"):
                bg_rgb = parse_hex_color(str(background_color))
                prop.SetBackgroundColor(float(bg_rgb[0]), float(bg_rgb[1]), float(bg_rgb[2]))
            if hasattr(prop, "SetBackgroundOpacity"):
                prop.SetBackgroundOpacity(max(0.0, min(1.0, background_opacity)))

            frame_enabled = bool(metadata.get("text_frame", False))
            if frame_enabled:
                callback = getattr(prop, "FrameOn", None)
                if callable(callback):
                    callback()
            else:
                callback = getattr(prop, "FrameOff", None)
                if callable(callback):
                    callback()
            frame_color = metadata.get("text_frame_color")
            if frame_color and hasattr(prop, "SetFrameColor"):
                frame_rgb = parse_hex_color(str(frame_color))
                prop.SetFrameColor(float(frame_rgb[0]), float(frame_rgb[1]), float(frame_rgb[2]))
            if hasattr(prop, "SetFrameWidth"):
                prop.SetFrameWidth(max(1, int(metadata.get("text_frame_width", 1) or 1)))

            self._configure_text_anchor(prop, primitive.anchor)
        except Exception:
            pass
        try:
            visual.actor.SetVisibility(bool(self._visible and primitive.visible))
        except Exception:
            pass

    def _sync_text_visuals(self, primitives: Iterable[ProjectedPrimitive]) -> bool:
        texts = {str(item.id): item for item in primitives if isinstance(item, ProjectedText)}
        changed = False
        for text_id in tuple(self._text_visuals):
            if text_id not in texts:
                self._remove_actor(self._text_visuals[text_id].actor)
                del self._text_visuals[text_id]
                changed = True
        for text_id, primitive in texts.items():
            visual = self._text_visuals.get(text_id)
            if visual is None:
                visual = self._new_text_visual(primitive)
                if visual is None:
                    continue
                self._text_visuals[text_id] = visual
                changed = True
            else:
                previous = visual.primitive
                self._configure_text_visual(visual, primitive)
                changed = changed or previous != primitive
        return changed

    def _update_text_projection(self, *, force_all: bool) -> bool:
        changed = False
        projected_count = 0
        for visual in self._text_visuals.values():
            if not force_all and not visual.dirty:
                continue
            projected_count += 1
            projected = self._world_to_display(visual.primitive.position)
            if projected is None:
                anchor_x = anchor_y = -1.0e6
            else:
                anchor_x = float(projected[0])
                anchor_y = float(projected[1])
            x = anchor_x + float(visual.primitive.offset_px[0])
            y = anchor_y + float(visual.primitive.offset_px[1])
            try:
                setter = getattr(visual.actor, "SetDisplayPosition", None)
                if callable(setter):
                    setter(int(round(x)), int(round(y)))
                else:
                    visual.actor.SetPosition(float(x), float(y))
                visual.display_anchor = (float(anchor_x), float(anchor_y))
                visual.display_position = (float(x), float(y))
                visual.dirty = False
                changed = True
            except Exception:
                pass
        self._diagnostic_metrics["last_projected_texts"] = projected_count
        return changed

    @staticmethod
    def _handle_state_scale(state: ProjectedVisualState | str) -> float:
        value = state.value if isinstance(state, ProjectedVisualState) else str(state)
        return {
            ProjectedVisualState.HOVER.value: 1.12,
            ProjectedVisualState.SELECTED.value: 1.08,
            ProjectedVisualState.GRABBED.value: 1.18,
        }.get(value, 1.0)

    def _update_handle_projection(self, *, force_all: bool, context: tuple[Any, float, float, float, float] | None) -> bool:
        if not self._handle_visuals:
            return False
        try:
            import numpy as np
        except Exception:
            np = None
        numpy_to_vtk = None
        if np is not None:
            try:
                from vtk.util.numpy_support import numpy_to_vtk as _numpy_to_vtk

                numpy_to_vtk = _numpy_to_vtk
            except Exception:
                numpy_to_vtk = None
        entries = [visual for visual in self._handle_visuals.values() if force_all or visual.dirty]
        if not entries:
            return False
        if np is not None:
            anchors = np.asarray(
                [point for visual in entries for point in (visual.primitive.position, tuple(visual.primitive.position[i] + visual.primitive.direction[i] for i in range(3)))],
                dtype=np.float64,
            )
            projected = self._project_array(anchors, context)
        else:
            projected = None
        for offset, visual in enumerate(entries):
            primitive = visual.primitive
            if projected is not None:
                center = projected[offset * 2]
                end = projected[offset * 2 + 1]
                cx, cy = float(center[0]), float(center[1])
                vx, vy = float(end[0] - center[0]), float(end[1] - center[1])
            else:
                center = self._world_to_display(primitive.position)
                end_world = tuple(primitive.position[i] + primitive.direction[i] for i in range(3))
                end = self._world_to_display(end_world)
                if center is None:
                    cx = cy = -1.0e6
                else:
                    cx, cy = center
                if center is None or end is None:
                    vx, vy = 1.0, 0.0
                else:
                    vx, vy = end[0] - center[0], end[1] - center[1]
            norm = math.hypot(vx, vy)
            if not math.isfinite(norm) or norm < 1.0e-7:
                cos_a, sin_a = 1.0, 0.0
            else:
                cos_a, sin_a = vx / norm, vy / norm
            radius = float(primitive.style.size_px) * 0.5 * self._handle_state_scale(primitive.visual_state)
            vector_updated = False
            if (
                np is not None
                and numpy_to_vtk is not None
                and visual.local_array is not None
                and callable(getattr(visual.points, "SetData", None))
            ):
                try:
                    count = int(visual.local_array.shape[0])
                    if visual.display_array is None or visual.display_array.shape != (count, 3):
                        visual.display_array = np.zeros((count, 3), dtype=np.float64)
                        visual.vtk_display_data = numpy_to_vtk(visual.display_array, deep=False)
                        visual.points.SetData(visual.vtk_display_data)
                    local = visual.local_array
                    output = visual.display_array
                    output[:, 0] = cx + radius * (local[:, 0] * cos_a - local[:, 1] * sin_a)
                    output[:, 1] = cy + radius * (local[:, 0] * sin_a + local[:, 1] * cos_a)
                    output[:, 2] = 0.0
                    visual.vtk_display_data.Modified()
                    visual.points.Modified()
                    vector_updated = True
                except Exception:
                    vector_updated = False
            if not vector_updated:
                for index, (lx, ly) in enumerate(visual.local_points):
                    px = cx + radius * (lx * cos_a - ly * sin_a)
                    py = cy + radius * (lx * sin_a + ly * cos_a)
                    visual.points.SetPoint(index, float(px), float(py), 0.0)
                visual.points.Modified()
            visual.polydata.Modified()
            visual.display_center = (float(cx), float(cy))
            visual.dirty = False
        self._diagnostic_metrics["last_projected_handles"] = len(entries)
        sample = []
        try:
            for visual in entries[:8]:
                primitive = visual.primitive
                sample.append({
                    "id": str(primitive.id),
                    "visible": bool(getattr(primitive, "visible", True)),
                    "position": tuple(float(value) for value in primitive.position),
                    "local_points": len(visual.local_points),
                    "actor_visible": bool(getattr(visual.actor, "GetVisibility", lambda: 0)()),
                })
        except Exception:
            sample = []
        record_projected_overlay_event(
            "projection.handles",
            owner=self.owner,
            owner_tool=self.owner_tool,
            manager=self.manager,
            renderer=self,
            force_all=bool(force_all),
            projected_handles=len(entries),
            sample=sample,
            live_actor_audit=self._live_actor_presence_snapshot(),
        )
        return True

    @staticmethod
    def _set_topology(visual: _BatchVisual, cells: tuple[tuple[int, ...], ...]) -> None:
        if visual.topology == cells:
            return
        visual.cells.Reset()
        for cell in cells:
            visual.cells.InsertNextCell(len(cell))
            for index in cell:
                visual.cells.InsertCellPoint(int(index))
        visual.cells.Modified()
        visual.polydata.Modified()
        visual.topology = cells

    @staticmethod
    def _array_from_points(points: tuple[Point3, ...]) -> Any | None:
        try:
            import numpy as np

            if not points:
                return np.empty((0, 3), dtype=np.float64)
            return np.asarray(points, dtype=np.float64).reshape((-1, 3))
        except Exception:
            return None

    @staticmethod
    def _changed_indices(old_array: Any | None, new_array: Any | None, old_points: tuple[Point3, ...], new_points: tuple[Point3, ...]) -> set[int]:
        if len(old_points) != len(new_points):
            return set(range(len(new_points)))
        if old_array is not None and new_array is not None:
            try:
                import numpy as np

                return set(np.flatnonzero(np.any(old_array != new_array, axis=1)).tolist())
            except Exception:
                pass
        return {index for index, (old, new) in enumerate(zip(old_points, new_points)) if old != new}

    def _rebuild_batches(
        self,
        compiled: tuple[_CompiledBatch, ...],
        spans: dict[str, tuple[_PrimitiveSpan, ...]],
    ) -> bool:
        metrics = self._diagnostic_metrics
        remove_started = time.perf_counter()
        wanted = {batch.key for batch in compiled}
        removed = 0
        for key in tuple(self._visuals):
            if key not in wanted:
                self._remove_actor(self._visuals[key].actor)
                del self._visuals[key]
                removed += 1
        metrics["last_rebuild_remove_ms"] = (time.perf_counter() - remove_started) * 1000.0

        actor_create_ms = 0.0
        topology_ms = 0.0
        created = 0
        created_keys: list[_BatchKey] = []
        topology_updates = 0
        for batch in compiled:
            visual = self._visuals.get(batch.key)
            visual_created = visual is None
            if visual_created:
                create_started = time.perf_counter()
                visual = self._new_visual(batch.key)
                actor_create_ms += (time.perf_counter() - create_started) * 1000.0
                if visual is None:
                    metrics["last_actor_create_ms"] = actor_create_ms
                    return False
                self._visuals[batch.key] = visual
                created += 1
                created_keys.append(batch.key)
            old_points = visual.world_points
            old_array = visual.world_array
            new_array = self._array_from_points(batch.world_points)
            topology_changed = visual.topology != batch.cells
            topology_started = time.perf_counter()
            self._set_topology(visual, batch.cells)
            topology_ms += (time.perf_counter() - topology_started) * 1000.0
            topology_updates += int(topology_changed)
            if visual_created or len(old_points) != len(batch.world_points) or topology_changed:
                visual.dirty_all = True
                visual.dirty_indices.clear()
            else:
                visual.dirty_indices.update(self._changed_indices(old_array, new_array, old_points, batch.world_points))
            visual.world_points = batch.world_points
            visual.world_array = new_array
        metrics["last_actor_create_ms"] = actor_create_ms
        metrics["last_topology_ms"] = topology_ms

        new_order = tuple(batch.key for batch in compiled)
        reorder_started = time.perf_counter()
        renderer = self._ensure_renderer()
        if renderer is not None and new_order != self._ordered_keys:
            # Newly created actors are already appended by _new_visual in
            # compile order. Removing and re-adding every actor here doubled
            # cold-scene VTK work and caused visible case-transition hitches.
            surviving_old = tuple(key for key in self._ordered_keys if key in wanted)
            current_order = surviving_old + tuple(created_keys)
            if current_order != new_order:
                for key in current_order:
                    visual = self._visuals.get(key)
                    if visual is not None:
                        self._remove_actor(visual.actor)
                for key in new_order:
                    self._add_actor(renderer, self._visuals[key].actor)
        metrics["last_actor_reorder_ms"] = (time.perf_counter() - reorder_started) * 1000.0
        metrics["last_actors_created"] = created
        metrics["last_actors_removed"] = removed
        metrics["last_topology_updates"] = topology_updates
        self._compiled = compiled
        self._primitive_spans = spans
        self._ordered_keys = new_order
        record_projected_overlay_event(
            "rebuild.done",
            owner=self.owner,
            owner_tool=self.owner_tool,
            manager=self.manager,
            renderer=self,
            compiled_batches=len(compiled),
            compiled_world_points=sum(len(batch.world_points) for batch in compiled),
            created=int(created),
            removed=int(removed),
            topology_updates=int(topology_updates),
            live_actor_audit=self._live_actor_presence_snapshot(renderer),
        )
        return True

    def _apply_coordinate_patches(self, patches: tuple[ProjectedCoordinatePatch, ...]) -> bool:
        """Apply exact local-coordinate patches without inspecting full primitives."""

        if not patches:
            return False
        prepared: list[tuple[_BatchVisual, int, Point3]] = []
        for patch in patches:
            spans = self._primitive_spans.get(str(patch.primitive_id))
            if spans is None or len(spans) != len(patch.chunks):
                return False
            for span, chunk in zip(spans, patch.chunks):
                visual = self._visuals.get(span.key)
                if visual is None or visual.world_array is None:
                    return False
                for local_index, point in chunk:
                    index = int(local_index)
                    if index < 0 or index >= span.count:
                        return False
                    prepared.append((visual, span.start + index, point))

        changed_points = 0
        try:
            import numpy as np

            by_visual: dict[int, tuple[_BatchVisual, list[int], list[Point3]]] = {}
            for visual, index, point in prepared:
                bucket = by_visual.get(id(visual))
                if bucket is None:
                    bucket = (visual, [], [])
                    by_visual[id(visual)] = bucket
                bucket[1].append(index)
                bucket[2].append(point)
            for visual, indices, points in by_visual.values():
                index_array = np.asarray(indices, dtype=np.int64)
                new_array = np.asarray(points, dtype=np.float64).reshape((-1, 3))
                old_array = visual.world_array[index_array]
                changed_mask = np.any(old_array != new_array, axis=1)
                if np.any(changed_mask):
                    changed_indices = index_array[changed_mask]
                    visual.world_array[changed_indices] = new_array[changed_mask]
                    visual.dirty_indices.update(changed_indices.tolist())
                    changed_points += int(np.count_nonzero(changed_mask))
        except Exception:
            return False

        metrics = self._diagnostic_metrics
        metrics["incremental_update_count"] = int(metrics.get("incremental_update_count", 0)) + 1
        metrics["last_incremental_points"] = changed_points
        metrics["last_patch_count"] = len(patches)
        metrics["last_compile_ms"] = 0.0
        metrics["last_rebuild_ms"] = 0.0
        metrics["last_actor_create_ms"] = 0.0
        metrics["last_topology_ms"] = 0.0
        metrics["last_actor_reorder_ms"] = 0.0
        metrics["last_actors_created"] = 0
        metrics["last_actors_removed"] = 0
        metrics["last_topology_updates"] = 0
        return True

    def _apply_incremental_change(self, change: ProjectedDrawingChange | None) -> bool:
        if change is None:
            return False
        if change.operation == "patch":
            return self._apply_coordinate_patches(change.patches)
        if change.operation not in {"update", "update_many"}:
            return False
        if len(change.before) != len(change.after) or not change.after:
            return False
        prepared: list[tuple[_BatchVisual, _PrimitiveSpan, tuple[Point3, ...]]] = []
        for before, after in zip(change.before, change.after):
            if str(before.id) != str(after.id):
                return False
            spans = self._primitive_spans.get(str(after.id))
            before_chunks = _primitive_chunks(before)
            after_chunks = _primitive_chunks(after)
            if spans is None or len(spans) != len(before_chunks) or len(spans) != len(after_chunks):
                return False
            for span, old_chunk, new_chunk in zip(spans, before_chunks, after_chunks):
                old_key, old_points, old_cells = old_chunk
                new_key, new_points, new_cells = new_chunk
                if (
                    span.key != old_key
                    or old_key != new_key
                    or span.local_cells != old_cells
                    or old_cells != new_cells
                    or len(old_points) != len(new_points)
                    or span.count != len(new_points)
                ):
                    return False
                visual = self._visuals.get(span.key)
                if visual is None or visual.world_array is None:
                    return False
                prepared.append((visual, span, new_points))

        changed_points = 0
        for visual, span, new_points in prepared:
            try:
                import numpy as np

                new_array = np.asarray(new_points, dtype=np.float64).reshape((-1, 3))
                old_slice = visual.world_array[span.start : span.start + span.count]
                local = np.flatnonzero(np.any(old_slice != new_array, axis=1))
                if local.size:
                    visual.world_array[span.start : span.start + span.count] = new_array
                    visual.dirty_indices.update((local + span.start).tolist())
                    changed_points += int(local.size)
            except Exception:
                return False
        self._diagnostic_metrics["incremental_update_count"] = int(
            self._diagnostic_metrics.get("incremental_update_count", 0)
        ) + 1
        self._diagnostic_metrics["last_incremental_points"] = changed_points
        self._diagnostic_metrics["last_compile_ms"] = 0.0
        self._diagnostic_metrics["last_rebuild_ms"] = 0.0
        self._diagnostic_metrics["last_actor_create_ms"] = 0.0
        self._diagnostic_metrics["last_topology_ms"] = 0.0
        self._diagnostic_metrics["last_actor_reorder_ms"] = 0.0
        self._diagnostic_metrics["last_actors_created"] = 0
        self._diagnostic_metrics["last_actors_removed"] = 0
        self._diagnostic_metrics["last_topology_updates"] = 0
        return True

    def _projection_signature(self) -> tuple[Any, ...] | None:
        try:
            renderer = self._main_renderer()
            camera = renderer.GetActiveCamera()
            # VTK camera MTime also changes for internal clipping/render
            # bookkeeping.  Using it as a projection signature caused full
            # overlay reprojection on nominally static frames.  Compare only
            # values that actually affect world-to-display coordinates.
            def _optional_tuple(name: str, default: tuple[float, ...]) -> tuple[float, ...]:
                callback = getattr(camera, name, None)
                if not callable(callback):
                    return default
                try:
                    return tuple(float(value) for value in callback())
                except Exception:
                    return default

            required_camera_methods = (
                "GetPosition",
                "GetFocalPoint",
                "GetViewUp",
                "GetParallelScale",
                "GetViewAngle",
                "GetParallelProjection",
            )
            if all(callable(getattr(camera, name, None)) for name in required_camera_methods):
                camera_state: tuple[Any, ...] = (
                    tuple(float(value) for value in camera.GetPosition()),
                    tuple(float(value) for value in camera.GetFocalPoint()),
                    tuple(float(value) for value in camera.GetViewUp()),
                    float(camera.GetParallelScale()),
                    float(camera.GetViewAngle()),
                    bool(camera.GetParallelProjection()),
                    _optional_tuple("GetWindowCenter", (0.0, 0.0)),
                    _optional_tuple("GetViewShear", (0.0, 0.0, 1.0)),
                )
            else:
                # Lightweight/headless renderers used by extensions may expose
                # only MTime.  Keep compatibility there; real VTK cameras always
                # take the explicit-value path above.
                get_mtime = getattr(camera, "GetMTime", None)
                camera_state = (int(get_mtime()),) if callable(get_mtime) else ()
            get_size = getattr(renderer, "GetSize", None)
            if callable(get_size):
                size = tuple(int(value) for value in get_size())
            else:
                plotter = self.owner.plotter
                width_fn = getattr(plotter, "width", None)
                height_fn = getattr(plotter, "height", None)
                size = (
                    int(width_fn()) if callable(width_fn) else 0,
                    int(height_fn()) if callable(height_fn) else 0,
                )
            origin_fn = getattr(renderer, "GetOrigin", None)
            try:
                origin = tuple(float(value) for value in origin_fn()) if callable(origin_fn) else (0.0, 0.0)
            except Exception:
                origin = (0.0, 0.0)
            aspect_fn = getattr(renderer, "GetTiledAspectRatio", None)
            try:
                aspect = float(aspect_fn()) if callable(aspect_fn) else 1.0
            except Exception:
                aspect = 1.0
            return (id(renderer), *camera_state, *size, *origin, aspect)
        except Exception:
            return None

    def _vector_projection_context(self) -> tuple[Any, float, float, float, float] | None:
        try:
            import numpy as np

            renderer = self._main_renderer()
            camera = renderer.GetActiveCamera()
            aspect_fn = getattr(renderer, "GetTiledAspectRatio", None)
            aspect = float(aspect_fn()) if callable(aspect_fn) else 1.0
            vtk_matrix = camera.GetCompositeProjectionTransformMatrix(aspect, -1.0, 1.0)
            matrix = np.empty((4, 4), dtype=np.float64)
            for row in range(4):
                for column in range(4):
                    matrix[row, column] = float(vtk_matrix.GetElement(row, column))
            origin_fn = getattr(renderer, "GetOrigin", None)
            size_fn = getattr(renderer, "GetSize", None)
            if callable(origin_fn) and callable(size_fn):
                origin = origin_fn()
                size = size_fn()
                ox, oy = float(origin[0]), float(origin[1])
                width, height = float(size[0]), float(size[1])
            else:
                ox = oy = 0.0
                plotter = self.owner.plotter
                width = float(plotter.width())
                height = float(plotter.height())
            if width <= 0.0 or height <= 0.0:
                return None
            return matrix, ox, oy, width, height
        except Exception:
            return None

    def _world_to_display(self, point: Point3) -> tuple[float, float] | None:
        try:
            x, y, _depth = self.owner._world_to_display(point)
            if not (math.isfinite(float(x)) and math.isfinite(float(y))):
                return None
            return (float(x), float(y))
        except Exception:
            return None

    def _project_array(self, world_array: Any, context: tuple[Any, float, float, float, float] | None) -> Any:
        import numpy as np

        count = int(len(world_array))
        result = np.empty((count, 3), dtype=np.float64)
        result[:, 2] = 0.0
        if count == 0:
            self._diagnostic_metrics["last_projection_backend"] = "empty"
            return result

        def _scalar_project_all() -> Any:
            fallback = np.empty((count, 3), dtype=np.float64)
            fallback[:, 2] = 0.0
            invalid = 0
            for index, point in enumerate(world_array):
                projected = self._world_to_display((float(point[0]), float(point[1]), float(point[2])))
                if projected is None:
                    fallback[index, 0] = -1.0e6
                    fallback[index, 1] = -1.0e6
                    invalid += 1
                else:
                    fallback[index, 0], fallback[index, 1] = projected
            self._diagnostic_metrics["scalar_projection_count"] = int(
                self._diagnostic_metrics.get("scalar_projection_count", 0)
            ) + 1
            self._diagnostic_metrics["last_projection_backend"] = "scalar"
            self._diagnostic_metrics["last_projection_invalid_points"] = invalid
            self._diagnostic_metrics["last_projection_outside_points"] = self._count_outside_points(fallback)
            return fallback

        if context is not None:
            matrix, ox, oy, width, height = context
            homogeneous = np.empty((count, 4), dtype=np.float64)
            homogeneous[:, :3] = world_array
            homogeneous[:, 3] = 1.0
            clip = homogeneous @ matrix.T
            w = clip[:, 3]
            valid = np.isfinite(clip).all(axis=1) & (np.abs(w) > 1.0e-14)
            result[:, 0] = -1.0e6
            result[:, 1] = -1.0e6
            if np.any(valid):
                ndc = clip[valid, :2] / w[valid, None]
                result[valid, 0] = ox + (ndc[:, 0] + 1.0) * width * 0.5
                result[valid, 1] = oy + (ndc[:, 1] + 1.0) * height * 0.5
            invalid = count - int(np.count_nonzero(valid))
            outside = self._count_outside_points(result, viewport=(ox, oy, width, height))
            self._diagnostic_metrics["vector_projection_count"] = int(
                self._diagnostic_metrics.get("vector_projection_count", 0)
            ) + 1
            self._diagnostic_metrics["last_projection_backend"] = "vector"
            self._diagnostic_metrics["last_projection_invalid_points"] = invalid
            self._diagnostic_metrics["last_projection_outside_points"] = outside
            self._diagnostic_metrics["last_projection_viewport"] = (float(ox), float(oy), float(width), float(height))
            # A real user report showed live primitives in the registry but no visible
            # overlay.  The most likely failure class is a renderer/camera matrix
            # mismatch that projects everything far outside the display while the
            # owner-provided scalar projector remains valid.  Fall back
            # automatically only when the vector result is clearly unusable.
            if invalid == count or (count <= 64 and outside == count):
                scalar = _scalar_project_all()
                scalar_invalid = int(np.count_nonzero((scalar[:, 0] <= -9.0e5) | (scalar[:, 1] <= -9.0e5)))
                scalar_outside = self._count_outside_points(scalar, viewport=(ox, oy, width, height))
                if scalar_invalid < invalid or scalar_outside < outside:
                    self._diagnostic_metrics["scalar_fallback_count"] = int(
                        self._diagnostic_metrics.get("scalar_fallback_count", 0)
                    ) + 1
                    self._diagnostic_metrics["last_projection_backend"] = "scalar_fallback"
                    self._diagnostic_metrics["last_projection_invalid_points"] = scalar_invalid
                    self._diagnostic_metrics["last_projection_outside_points"] = scalar_outside
                    record_projected_overlay_event(
                        "projection.scalar_fallback",
                        owner=self.owner,
                        owner_tool=self.owner_tool,
                        renderer=self,
                        vector_invalid=invalid,
                        vector_outside=outside,
                        scalar_invalid=scalar_invalid,
                        scalar_outside=scalar_outside,
                        viewport=(ox, oy, width, height),
                        sample_world=tuple(tuple(float(v) for v in row) for row in world_array[:4]),
                        sample_vector=tuple(tuple(float(v) for v in row[:2]) for row in result[:4]),
                        sample_scalar=tuple(tuple(float(v) for v in row[:2]) for row in scalar[:4]),
                    )
                    return scalar
            return result

        return _scalar_project_all()

    @staticmethod
    def _count_outside_points(projected: Any, *, viewport: tuple[float, float, float, float] | None = None) -> int:
        try:
            import numpy as np

            if len(projected) == 0:
                return 0
            if viewport is None:
                ox, oy, width, height = 0.0, 0.0, 0.0, 0.0
            else:
                ox, oy, width, height = (float(v) for v in viewport)
            margin = max(float(width), float(height), 100.0) * 0.25
            xs = projected[:, 0]
            ys = projected[:, 1]
            invalid = (~np.isfinite(xs)) | (~np.isfinite(ys)) | (xs <= -9.0e5) | (ys <= -9.0e5)
            if width <= 0.0 or height <= 0.0:
                return int(np.count_nonzero(invalid))
            outside = invalid | (xs < ox - margin) | (xs > ox + width + margin) | (ys < oy - margin) | (ys > oy + height + margin)
            return int(np.count_nonzero(outside))
        except Exception:
            return 0

    @staticmethod
    def _ensure_display_storage(visual: _BatchVisual, count: int) -> bool:
        try:
            import numpy as np

            if visual.display_array is not None and tuple(visual.display_array.shape) == (count, 3):
                return visual.vtk_display_data is not None
            display = np.empty((count, 3), dtype=np.float64)
            display[:, 2] = 0.0
            set_data = getattr(visual.points, "SetData", None)
            if not callable(set_data):
                visual.display_array = display
                visual.vtk_display_data = None
                visual.points.SetNumberOfPoints(count)
                return False
            from vtk.util.numpy_support import numpy_to_vtk

            vtk_data = numpy_to_vtk(display, deep=False)
            vtk_data.SetNumberOfComponents(3)
            set_data(vtk_data)
            visual.display_array = display
            visual.vtk_display_data = vtk_data
            return True
        except Exception:
            try:
                visual.points.SetNumberOfPoints(count)
            except Exception:
                pass
            visual.display_array = None
            visual.vtk_display_data = None
            return False

    def _write_display_points(self, visual: _BatchVisual, indices: Any, projected: Any) -> None:
        use_array = self._ensure_display_storage(visual, len(visual.world_array))
        if use_array and visual.display_array is not None:
            visual.display_array[indices] = projected
            try:
                visual.vtk_display_data.Modified()
            except Exception:
                pass
        else:
            try:
                index_values = list(range(len(visual.world_array))) if isinstance(indices, slice) else list(indices)
            except Exception:
                index_values = list(indices)
            for local_index, point_index in enumerate(index_values):
                row = projected[local_index]
                visual.points.SetPoint(int(point_index), float(row[0]), float(row[1]), 0.0)
        visual.points.Modified()
        visual.polydata.Modified()

    def _current_projection_viewport(self) -> tuple[float, float, float, float] | None:
        try:
            renderer = self._main_renderer()
            origin_fn = getattr(renderer, "GetOrigin", None)
            size_fn = getattr(renderer, "GetSize", None)
            if callable(origin_fn) and callable(size_fn):
                origin = origin_fn()
                size = size_fn()
                viewport = (float(origin[0]), float(origin[1]), float(size[0]), float(size[1]))
            else:
                plotter = self.owner.plotter
                viewport = (0.0, 0.0, float(plotter.width()), float(plotter.height()))
            if viewport[2] <= 0.0 or viewport[3] <= 0.0:
                return None
            return viewport
        except Exception:
            return None

    @staticmethod
    def _normalized_vec3(value: tuple[float, float, float]) -> tuple[float, float, float]:
        length = math.sqrt(float(value[0]) ** 2 + float(value[1]) ** 2 + float(value[2]) ** 2)
        if not math.isfinite(length) or length <= 1.0e-30:
            return (0.0, 0.0, 0.0)
        return (float(value[0]) / length, float(value[1]) / length, float(value[2]) / length)

    def _parallel_camera_affine(
        self,
        previous: Any | None,
        current: Any | None,
    ) -> tuple[float, float, float, float, float] | None:
        """Return an exact display-space transform for orthographic pan/zoom.

        Plan Tracer draws on one plane and locks the camera orientation.  In a
        parallel projection, changing only the focal translation and parallel
        scale maps every already-projected point through one uniform affine
        transform.  Reusing display coordinates avoids rebuilding the camera
        matrix and reprojecting every face/edge/point for each raw mouse frame.
        """

        if previous is None or current is None:
            return None
        try:
            if not bool(previous.parallel_projection) or not bool(current.parallel_projection):
                return None
            if float(previous.parallel_scale) <= 1.0e-12 or float(current.parallel_scale) <= 1.0e-12:
                return None
            previous_forward = self._normalized_vec3(
                tuple(float(previous.focal_point[i]) - float(previous.position[i]) for i in range(3))
            )
            current_forward = self._normalized_vec3(
                tuple(float(current.focal_point[i]) - float(current.position[i]) for i in range(3))
            )
            if max(abs(previous_forward[i] - current_forward[i]) for i in range(3)) > 1.0e-8:
                return None
            if max(abs(float(previous.view_up[i]) - float(current.view_up[i])) for i in range(3)) > 1.0e-8:
                return None

            renderer = self._main_renderer()
            camera = renderer.GetActiveCamera()
            window_center_fn = getattr(camera, "GetWindowCenter", None)
            if callable(window_center_fn):
                window_center = tuple(float(value) for value in window_center_fn())
                if max(abs(value) for value in window_center) > 1.0e-12:
                    return None
            view_shear_fn = getattr(camera, "GetViewShear", None)
            if callable(view_shear_fn):
                view_shear = tuple(float(value) for value in view_shear_fn())
                if len(view_shear) >= 3 and (
                    abs(view_shear[0]) > 1.0e-12
                    or abs(view_shear[1]) > 1.0e-12
                    or abs(view_shear[2] - 1.0) > 1.0e-12
                ):
                    return None

            viewport = self._current_projection_viewport()
            if viewport is None or self._last_projection_viewport != viewport:
                return None
            ox, oy, width, height = viewport
            center_x = ox + width * 0.5
            center_y = oy + height * 0.5
            ratio = float(previous.parallel_scale) / float(current.parallel_scale)
            if not math.isfinite(ratio) or ratio <= 0.0:
                return None

            up = self._normalized_vec3(tuple(float(value) for value in current.view_up))
            right = self._normalized_vec3(
                (
                    current_forward[1] * up[2] - current_forward[2] * up[1],
                    current_forward[2] * up[0] - current_forward[0] * up[2],
                    current_forward[0] * up[1] - current_forward[1] * up[0],
                )
            )
            if right == (0.0, 0.0, 0.0):
                return None
            screen_up = self._normalized_vec3(
                (
                    right[1] * current_forward[2] - right[2] * current_forward[1],
                    right[2] * current_forward[0] - right[0] * current_forward[2],
                    right[0] * current_forward[1] - right[1] * current_forward[0],
                )
            )
            focal_delta = tuple(
                float(current.focal_point[i]) - float(previous.focal_point[i]) for i in range(3)
            )
            pixels_per_world = height / (2.0 * float(current.parallel_scale))
            translate_x = -sum(focal_delta[i] * right[i] for i in range(3)) * pixels_per_world
            translate_y = -sum(focal_delta[i] * screen_up[i] for i in range(3)) * pixels_per_world
            if not all(math.isfinite(value) for value in (center_x, center_y, translate_x, translate_y)):
                return None
            return (ratio, center_x, center_y, translate_x, translate_y)
        except Exception:
            return None

    def _apply_parallel_camera_affine(
        self,
        previous: Any | None,
        current: Any | None,
    ) -> bool:
        transform = self._parallel_camera_affine(previous, current)
        if transform is None:
            return False
        try:
            import numpy as np
        except Exception:
            return False

        # Do a complete preflight so a missing legacy display buffer cannot
        # leave half the overlay transformed before falling back to projection.
        if any(
            visual.display_array is None or visual.vtk_display_data is None
            for visual in self._visuals.values()
        ):
            return False
        if any(
            visual.display_array is None
            or visual.vtk_display_data is None
            or visual.display_center is None
            for visual in self._handle_visuals.values()
        ):
            return False
        if any(visual.display_anchor is None for visual in self._text_visuals.values()):
            return False

        ratio, center_x, center_y, translate_x, translate_y = transform
        changed = False
        projected_points = 0
        for visual in self._visuals.values():
            display = visual.display_array
            if display is None or len(display) == 0:
                continue
            display[:, 0] = center_x + ratio * (display[:, 0] - center_x) + translate_x
            display[:, 1] = center_y + ratio * (display[:, 1] - center_y) + translate_y
            visual.vtk_display_data.Modified()
            visual.points.Modified()
            visual.polydata.Modified()
            projected_points += int(display.shape[0])
            changed = True

        for visual in self._handle_visuals.values():
            old_x, old_y = visual.display_center or (0.0, 0.0)
            new_x = center_x + ratio * (old_x - center_x) + translate_x
            new_y = center_y + ratio * (old_y - center_y) + translate_y
            dx = new_x - old_x
            dy = new_y - old_y
            display = visual.display_array
            if display is not None and len(display):
                # Handles keep a fixed pixel radius during zoom. Only their
                # anchor moves; their local icon geometry must not be scaled.
                display[:, 0] += dx
                display[:, 1] += dy
                visual.vtk_display_data.Modified()
                visual.points.Modified()
                visual.polydata.Modified()
                changed = True
            visual.display_center = (float(new_x), float(new_y))

        for visual in self._text_visuals.values():
            old_anchor_x, old_anchor_y = visual.display_anchor or (0.0, 0.0)
            new_anchor_x = center_x + ratio * (old_anchor_x - center_x) + translate_x
            new_anchor_y = center_y + ratio * (old_anchor_y - center_y) + translate_y
            new_x = new_anchor_x + float(visual.primitive.offset_px[0])
            new_y = new_anchor_y + float(visual.primitive.offset_px[1])
            setter = getattr(visual.actor, "SetDisplayPosition", None)
            if callable(setter):
                setter(int(round(new_x)), int(round(new_y)))
            else:
                visual.actor.SetPosition(float(new_x), float(new_y))
            visual.display_anchor = (float(new_anchor_x), float(new_anchor_y))
            visual.display_position = (float(new_x), float(new_y))
            changed = True

        metrics = self._diagnostic_metrics
        metrics["parallel_affine_projection_count"] = int(metrics.get("parallel_affine_projection_count", 0)) + 1
        metrics["last_projection_backend"] = "parallel_affine"
        metrics["last_projected_points"] = projected_points
        metrics["last_projected_batches"] = len(self._visuals)
        metrics["last_projected_handles"] = len(self._handle_visuals)
        metrics["last_projected_texts"] = len(self._text_visuals)
        return changed

    def _update_projection(self, *, force_all: bool) -> bool:
        """Project dirty coordinates, coalescing fragmented style batches.

        A camera move can dirty many tiny actors. Concatenating their coordinates
        into one matrix operation avoids one NumPy allocation/matmul per style.
        """

        try:
            import numpy as np
        except Exception:
            np = None
        context = self._vector_projection_context() if np is not None else None
        entries: list[tuple[_BatchVisual, Any, Any]] = []
        projected_points = 0
        for key in self._ordered_keys:
            visual = self._visuals.get(key)
            if visual is None:
                continue
            if visual.world_array is None:
                visual.world_array = self._array_from_points(visual.world_points)
            if visual.world_array is None:
                continue
            count = len(visual.world_array)
            if force_all or visual.dirty_all:
                indices: Any = slice(None) if np is not None else tuple(range(count))
                selected = visual.world_array
                selected_count = count
            elif visual.dirty_indices:
                indices = np.asarray(sorted(visual.dirty_indices), dtype=np.int64) if np is not None else tuple(sorted(visual.dirty_indices))
                selected = visual.world_array[indices]
                selected_count = len(indices)
            else:
                continue
            if selected_count == 0:
                visual.dirty_all = False
                visual.dirty_indices.clear()
                continue
            entries.append((visual, indices, selected))
            projected_points += selected_count

        handle_changed = self._update_handle_projection(force_all=force_all, context=context)
        text_changed = self._update_text_projection(force_all=force_all)
        if not entries:
            self._diagnostic_metrics["last_projected_points"] = 0
            self._diagnostic_metrics["last_projected_batches"] = 0
            self._last_projection_viewport = self._current_projection_viewport()
            record_projected_overlay_event(
                "projection.no_batch_entries",
                owner=self.owner,
                owner_tool=self.owner_tool,
                manager=self.manager,
                renderer=self,
                force_all=bool(force_all),
                handle_changed=bool(handle_changed),
                text_changed=bool(text_changed),
                ordered_keys=len(self._ordered_keys),
                compiled_batches=len(self._compiled),
                visual_count=len(self._visuals),
                live_actor_audit=self._live_actor_presence_snapshot(),
            )
            return handle_changed or text_changed

        if np is not None and context is not None and len(entries) > 1:
            counts = [len(selected) for _visual, _indices, selected in entries]
            combined = np.concatenate([selected for _visual, _indices, selected in entries], axis=0)
            projected_all = self._project_array(combined, context)
            offset = 0
            for (visual, indices, _selected), count in zip(entries, counts):
                self._write_display_points(visual, indices, projected_all[offset : offset + count])
                visual.dirty_all = False
                visual.dirty_indices.clear()
                offset += count
            self._diagnostic_metrics["last_projection_groups"] = 1
        else:
            for visual, indices, selected in entries:
                projected = self._project_array(selected, context)
                self._write_display_points(visual, indices, projected)
                visual.dirty_all = False
                visual.dirty_indices.clear()
            self._diagnostic_metrics["last_projection_groups"] = len(entries)

        self._diagnostic_metrics["last_projected_points"] = projected_points
        self._diagnostic_metrics["last_projected_batches"] = len(entries)
        self._last_projection_viewport = self._current_projection_viewport()
        record_projected_overlay_event(
            "projection.batches",
            owner=self.owner,
            owner_tool=self.owner_tool,
            manager=self.manager,
            renderer=self,
            force_all=bool(force_all),
            projected_points=int(projected_points),
            projected_batches=len(entries),
            projection_backend=self._diagnostic_metrics.get("last_projection_backend"),
            invalid_points=self._diagnostic_metrics.get("last_projection_invalid_points"),
            outside_points=self._diagnostic_metrics.get("last_projection_outside_points"),
            live_actor_audit=self._live_actor_presence_snapshot(),
        )
        return True

    def diagnostic_snapshot(self) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        cells = 0
        for batch in self._compiled:
            by_kind[batch.key.kind] = by_kind.get(batch.key.kind, 0) + 1
            cells += len(batch.cells)
        result = dict(self._diagnostic_metrics)
        result.update(
            {
                "owner_tool": self.owner_tool,
                "revision": int(self._revision),
                "visible": bool(self._visible),
                "batches": len(self._compiled),
                "actors": len(self._visuals) + len(self._handle_visuals) + len(self._text_visuals),
                "handles": len(self._handle_visuals),
                "texts": len(self._text_visuals),
                "batches_by_kind": by_kind,
                "world_points": sum(len(batch.world_points) for batch in self._compiled),
                "cells": int(cells),
                "renderer_reattach_count": int(result.get("renderer_reattach_count", 0) or 0),
                "last_renderer_reattached_actors": int(result.get("last_renderer_reattached_actors", 0) or 0),
            }
        )
        try:
            result["live_actor_audit"] = self._live_actor_presence_snapshot()
        except Exception as exc:
            result["live_actor_audit"] = {"error": type(exc).__name__}
        return result

    def _record_sync_audit(
        self,
        *,
        compile_ms: float | None,
        rebuild_ms: float | None,
        projection_ms: float | None,
        path: str = "full",
    ) -> None:
        """Publish one sync sample without duplicating the hot-path logic."""

        metrics = self._diagnostic_metrics
        try:
            from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

            audit.record_timing("projected_drawing_2d.sync", float(metrics["last_sync_ms"]))
            audit.record_timing(
                f"projected_drawing_2d.sync.{str(path)}",
                float(metrics["last_sync_ms"]),
            )
            audit.increment(f"projected_drawing_2d.sync_path.{str(path)}")
            if compile_ms is not None:
                audit.record_timing("projected_drawing_2d.compile_batches", compile_ms)
            if rebuild_ms is not None:
                audit.record_timing("projected_drawing_2d.rebuild_batches", rebuild_ms)
            if projection_ms is not None:
                audit.record_timing("projected_drawing_2d.projection", projection_ms)
                audit.record_timing(
                    f"projected_drawing_2d.camera.{self._last_sync_camera_mode}.projection",
                    projection_ms,
                )
            if compile_ms is not None:
                audit.increment(
                    "projected_drawing_2d.triangulation_cache_hits",
                    int(metrics.get("last_triangulation_cache_hits", 0)),
                )
                audit.increment(
                    "projected_drawing_2d.triangulation_cache_misses",
                    int(metrics.get("last_triangulation_cache_misses", 0)),
                )
                audit.increment(
                    "projected_drawing_2d.triangulation_canonical_hits",
                    int(metrics.get("last_triangulation_canonical_hits", 0)),
                )
                audit.increment(
                    "projected_drawing_2d.triangulation_canonical_misses",
                    int(metrics.get("last_triangulation_canonical_misses", 0)),
                )
                audit.set_value(
                    "projected_drawing_2d.triangulation_cache_holes_size",
                    int(metrics.get("triangulation_cache_holes_size", 0)),
                )
                audit.set_value(
                    "projected_drawing_2d.triangulation_cache_canonical_size",
                    int(metrics.get("triangulation_cache_canonical_size", 0)),
                )
            audit.record_timing(
                f"projected_drawing_2d.camera.{self._last_sync_camera_mode}.sync",
                float(metrics["last_sync_ms"]),
            )
        except Exception:
            pass
        try:
            context = getattr(self.manager, "_context", None)
            profiler = getattr(context, "profiler", None) if context is not None else None
            if profiler is not None:
                record = getattr(profiler, "record_timing", None)
                set_value = getattr(profiler, "set_value", None)
                increment = getattr(profiler, "increment", None)
                if callable(record):
                    record("projected_drawing_2d.sync", float(metrics.get("last_sync_ms", 0.0) or 0.0))
                    if compile_ms is not None:
                        record("projected_drawing_2d.compile_batches", float(compile_ms))
                    if rebuild_ms is not None:
                        record("projected_drawing_2d.rebuild_batches", float(rebuild_ms))
                    if projection_ms is not None:
                        record("projected_drawing_2d.projection", float(projection_ms))
                if callable(set_value):
                    snapshot = self.diagnostic_snapshot()
                    for key in (
                        "actors",
                        "handles",
                        "texts",
                        "batches",
                        "world_points",
                        "cells",
                        "last_projected_points",
                        "last_projected_handles",
                        "last_projected_texts",
                        "last_projected_batches",
                        "last_projection_invalid_points",
                        "last_projection_outside_points",
                        "renderer_reattach_count",
                        "last_renderer_reattached_actors",
                    ):
                        if key in snapshot:
                            set_value(f"projected_drawing_2d.{self.owner_tool}.{key}", snapshot[key])
                    set_value(f"projected_drawing_2d.{self.owner_tool}.projection_backend", str(metrics.get("last_projection_backend", "unknown")))
                if callable(increment):
                    increment(f"projected_drawing_2d.{self.owner_tool}.sync_path.{str(path)}", 1)
        except Exception:
            pass

    def sync_from_manager(self, *, force: bool = False, render: bool = False) -> bool:
        sync_started = time.perf_counter()
        metrics = self._diagnostic_metrics
        compile_ms_this_sync: float | None = None
        rebuild_ms_this_sync: float | None = None
        projection_ms_this_sync: float | None = None
        metrics["sync_count"] = int(metrics.get("sync_count", 0)) + 1
        self._last_sync_camera_mode = "static"
        live_renderer = self._ensure_renderer()
        if live_renderer is None:
            metrics["last_sync_ms"] = (time.perf_counter() - sync_started) * 1000.0
            record_projected_overlay_event("sync.no_renderer", owner=self.owner, owner_tool=self.owner_tool, manager=self.manager, renderer=self)
            return False
        scene_generation = int(getattr(self.owner, "_scene_rebuild_generation", 0) or 0)
        attached_scene_generation = getattr(self, "_attached_scene_generation", None)
        renderer_changed = attached_scene_generation is None
        scene_rebuilt = attached_scene_generation != scene_generation
        expected_actor_count = (
            len(getattr(self, "_visuals", {}))
            + len(getattr(self, "_handle_visuals", {}))
            + len(getattr(self, "_text_visuals", {}))
        )
        live_actor_list = getattr(live_renderer, "actors", None)
        lightweight_membership_mismatch = (
            isinstance(live_actor_list, list) and len(live_actor_list) < expected_actor_count
        )
        # One sentinel membership query closes a critical blind spot: the
        # renderer can lose every projected prop without changing scene
        # generation and without exposing a Python ``actors`` list.  In that
        # state all tools keep producing primitives, but cursor/lines/highlights
        # remain globally invisible.
        sentinel_missing = bool(expected_actor_count and self._projected_actor_sentinel_missing(live_renderer))
        reattached_actors = 0
        if renderer_changed or scene_rebuilt or lightweight_membership_mismatch or sentinel_missing:
            reattached_actors = self._reattach_missing_actors(live_renderer, force=sentinel_missing)
            self._attached_scene_generation = scene_generation
        state_revision, state_visible = self.manager.state_token(self.owner_tool)
        record_projected_overlay_event(
            "sync.start",
            owner=self.owner,
            owner_tool=self.owner_tool,
            manager=self.manager,
            renderer=self,
            force=bool(force),
            render=bool(render),
            state_revision=int(state_revision),
            stored_revision=int(self._revision),
            state_visible=bool(state_visible),
            stored_visible=bool(self._visible),
            reattached_actors=int(reattached_actors),
            live_actor_audit=self._live_actor_presence_snapshot(live_renderer),
        )

        # Hot path for camera frames and cursor renders with no primitive
        # mutation.  The previous implementation built a full snapshot and
        # rescanned every handle/text on every call, even when the owner
        # revision and camera were unchanged.  Dense Plan Tracer scenes call
        # this path several thousand times per session, so the avoidable
        # ~1 ms bookkeeping became one of the largest cumulative costs.
        if not force and state_revision == self._revision and state_visible == self._visible:
            signature_started = time.perf_counter()
            signature = self._projection_signature() if self._visible else self._last_projection_signature
            metrics["last_signature_ms"] = (time.perf_counter() - signature_started) * 1000.0
            camera_changed = bool(
                self._visible
                and (signature is None or signature != self._last_projection_signature)
            )
            if not camera_changed:
                metrics["fast_noop_count"] = int(metrics.get("fast_noop_count", 0)) + 1
                metrics["cache_hit_count"] = int(metrics.get("cache_hit_count", 0)) + 1
                metrics["last_projection_ms"] = 0.0
                metrics["last_projected_points"] = 0
                metrics["last_projected_batches"] = 0
                if render or reattached_actors:
                    render_request_started = time.perf_counter()
                    self._request_render("projected_drawing_2d.reattach" if reattached_actors else "projected_drawing_2d.sync")
                    metrics["last_render_request_ms"] = (time.perf_counter() - render_request_started) * 1000.0
                metrics["last_sync_ms"] = (time.perf_counter() - sync_started) * 1000.0
                self._record_sync_audit(
                    compile_ms=None,
                    rebuild_ms=None,
                    projection_ms=None,
                    path="reattach" if reattached_actors else "noop",
                )
                record_projected_overlay_event(
                    "sync.fast_noop",
                    owner=self.owner,
                    owner_tool=self.owner_tool,
                    manager=self.manager,
                    renderer=self,
                    render_requested=bool(render),
                    reattached_actors=int(reattached_actors),
                    signature=signature,
                    live_actor_audit=self._live_actor_presence_snapshot(live_renderer),
                )
                return bool(reattached_actors)

            current_camera_state = capture_camera_state(self._main_renderer())
            self._last_sync_camera_mode = str(classify_camera_motion(self._last_camera_state, current_camera_state))
            projection_started = time.perf_counter()
            changed = self._apply_parallel_camera_affine(self._last_camera_state, current_camera_state)
            if changed:
                metrics["camera_affine_fast_path_count"] = int(metrics.get("camera_affine_fast_path_count", 0)) + 1
            else:
                changed = self._update_projection(force_all=True)
            projection_ms_this_sync = (time.perf_counter() - projection_started) * 1000.0
            metrics["camera_only_fast_path_count"] = int(metrics.get("camera_only_fast_path_count", 0)) + 1
            metrics["projection_count"] = int(metrics.get("projection_count", 0)) + 1
            metrics["last_projection_ms"] = projection_ms_this_sync
            metrics["last_camera_mode"] = self._last_sync_camera_mode
            self._last_projection_signature = signature
            if current_camera_state is not None:
                self._last_camera_state = current_camera_state
            if render or reattached_actors:
                render_request_started = time.perf_counter()
                self._request_render("projected_drawing_2d.reattach" if reattached_actors else "projected_drawing_2d.sync")
                metrics["last_render_request_ms"] = (time.perf_counter() - render_request_started) * 1000.0
            metrics["last_sync_ms"] = (time.perf_counter() - sync_started) * 1000.0
            self._record_sync_audit(
                compile_ms=None,
                rebuild_ms=None,
                projection_ms=projection_ms_this_sync,
                path="camera_only",
            )
            record_projected_overlay_event(
                "sync.camera_only",
                owner=self.owner,
                owner_tool=self.owner_tool,
                manager=self.manager,
                renderer=self,
                changed=bool(changed),
                camera_mode=self._last_sync_camera_mode,
                projection_ms=projection_ms_this_sync,
                live_actor_audit=self._live_actor_presence_snapshot(live_renderer),
            )
            return bool(changed)

        snapshot_started = time.perf_counter()
        snapshot = self.manager.snapshot(self.owner_tool)
        metrics["last_snapshot_ms"] = (time.perf_counter() - snapshot_started) * 1000.0
        record_projected_overlay_event("sync.snapshot", owner=self.owner, owner_tool=self.owner_tool, manager=self.manager, renderer=self, revision=int(getattr(snapshot, "revision", -1)), primitive_count=len(tuple(getattr(snapshot, "primitives", ()) or ())))
        changed = self._sync_handle_visuals(snapshot.primitives)
        changed = self._sync_text_visuals(snapshot.primitives) or changed
        record_projected_overlay_event(
            "sync.after_handle_text",
            owner=self.owner,
            owner_tool=self.owner_tool,
            manager=self.manager,
            renderer=self,
            handle_visuals=len(self._handle_visuals),
            text_visuals=len(self._text_visuals),
            changed=bool(changed),
            live_actor_audit=self._live_actor_presence_snapshot(live_renderer),
        )
        geometry_changed = False
        revision_changed = force or snapshot.revision != self._revision
        if revision_changed:
            change = self.manager._change_for(self.owner_tool, snapshot.revision)
            base_revision = getattr(change, "base_revision", None) if change is not None else None
            sequential = (
                int(base_revision) == int(self._revision)
                if base_revision is not None
                else int(snapshot.revision) == int(self._revision) + 1
            )
            visibility_only = sequential and change is not None and change.operation == "visibility"
            incremental = False
            if not force and sequential and not visibility_only:
                incremental_started = time.perf_counter()
                incremental = self._apply_incremental_change(change)
                metrics["last_incremental_update_ms"] = (time.perf_counter() - incremental_started) * 1000.0
            if visibility_only:
                self._revision = snapshot.revision
            elif incremental:
                self._revision = snapshot.revision
                geometry_changed = True
                changed = True
            else:
                cache_before = triangulation_cache_snapshot()
                compile_started = time.perf_counter()
                compiled, spans = _compile_scene(snapshot.primitives)
                compile_ms = (time.perf_counter() - compile_started) * 1000.0
                cache_after = triangulation_cache_snapshot()
                compile_ms_this_sync = compile_ms
                metrics["compile_count"] = int(metrics.get("compile_count", 0)) + 1
                metrics["last_compile_ms"] = compile_ms
                metrics["last_triangulation_cache_hits"] = (
                    int(cache_after["simple_hits"] - cache_before["simple_hits"])
                    + int(cache_after["holes_hits"] - cache_before["holes_hits"])
                )
                metrics["last_triangulation_cache_misses"] = (
                    int(cache_after["simple_misses"] - cache_before["simple_misses"])
                    + int(cache_after["holes_misses"] - cache_before["holes_misses"])
                )
                metrics["last_triangulation_canonical_hits"] = int(
                    cache_after["holes_canonical_hits"] - cache_before["holes_canonical_hits"]
                )
                metrics["last_triangulation_canonical_misses"] = int(
                    cache_after["holes_canonical_misses"] - cache_before["holes_canonical_misses"]
                )
                metrics["triangulation_cache_simple_size"] = int(cache_after["simple_size"])
                metrics["triangulation_cache_holes_size"] = int(cache_after["holes_size"])
                metrics["triangulation_cache_canonical_size"] = int(cache_after["holes_canonical_size"])
                rebuild_started = time.perf_counter()
                if not self._rebuild_batches(compiled, spans):
                    metrics["last_rebuild_ms"] = (time.perf_counter() - rebuild_started) * 1000.0
                    metrics["last_sync_ms"] = (time.perf_counter() - sync_started) * 1000.0
                    return False
                metrics["last_rebuild_ms"] = (time.perf_counter() - rebuild_started) * 1000.0
                rebuild_ms_this_sync = float(metrics["last_rebuild_ms"])
                self._revision = snapshot.revision
                geometry_changed = True
                changed = True
        if force or snapshot.visible != self._visible:
            visibility_started = time.perf_counter()
            self._visible = bool(snapshot.visible)
            for visual in self._visuals.values():
                try:
                    visual.actor.SetVisibility(self._visible)
                except Exception:
                    pass
            for visual in self._handle_visuals.values():
                try:
                    visual.actor.SetVisibility(bool(self._visible and visual.primitive.visible))
                except Exception:
                    pass
            for visual in self._text_visuals.values():
                try:
                    visual.actor.SetVisibility(bool(self._visible and visual.primitive.visible))
                except Exception:
                    pass
            metrics["last_visibility_ms"] = (time.perf_counter() - visibility_started) * 1000.0
            changed = True
        if self._visible:
            signature_started = time.perf_counter()
            signature = self._projection_signature()
            metrics["last_signature_ms"] = (time.perf_counter() - signature_started) * 1000.0
            camera_changed = force or signature is None or signature != self._last_projection_signature
            if geometry_changed or camera_changed:
                current_camera_state = capture_camera_state(self._main_renderer())
                camera_mode = classify_camera_motion(self._last_camera_state, current_camera_state) if camera_changed else "static"
                self._last_sync_camera_mode = str(camera_mode)
                projection_started = time.perf_counter()
                projection_changed = False
                if camera_changed and not geometry_changed:
                    projection_changed = self._apply_parallel_camera_affine(self._last_camera_state, current_camera_state)
                    if projection_changed:
                        metrics["camera_affine_fast_path_count"] = int(metrics.get("camera_affine_fast_path_count", 0)) + 1
                if not projection_changed:
                    projection_changed = self._update_projection(force_all=bool(camera_changed))
                changed = projection_changed or changed
                projection_ms = (time.perf_counter() - projection_started) * 1000.0
                projection_ms_this_sync = projection_ms
                metrics["projection_count"] = int(metrics.get("projection_count", 0)) + 1
                metrics["last_projection_ms"] = projection_ms
                metrics["last_camera_mode"] = str(camera_mode)
                self._last_projection_signature = signature
                if current_camera_state is not None:
                    self._last_camera_state = current_camera_state
            else:
                metrics["cache_hit_count"] = int(metrics.get("cache_hit_count", 0)) + 1
                metrics["last_projection_ms"] = 0.0
                metrics["last_projected_points"] = 0
                metrics["last_projected_batches"] = 0
        if render:
            render_request_started = time.perf_counter()
            self._request_render("projected_drawing_2d.sync")
            metrics["last_render_request_ms"] = (time.perf_counter() - render_request_started) * 1000.0
        metrics["last_sync_ms"] = (time.perf_counter() - sync_started) * 1000.0
        self._record_sync_audit(
            compile_ms=compile_ms_this_sync,
            rebuild_ms=rebuild_ms_this_sync,
            projection_ms=projection_ms_this_sync,
            path="full",
        )
        record_projected_overlay_event("sync.done", owner=self.owner, owner_tool=self.owner_tool, manager=self.manager, renderer=self, changed=bool(changed), geometry_changed=bool(geometry_changed), projection_backend=metrics.get("last_projection_backend"), projected_points=metrics.get("last_projected_points"), projected_handles=metrics.get("last_projected_handles"), actors=metrics.get("last_actors_created"))
        return changed

    def _before_render(self, _caller: Any = None, _event: Any = None) -> None:
        started = time.perf_counter()
        try:
            self.sync_from_manager(force=False, render=False)
        finally:
            try:
                from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

                audit.record_timing("projected_drawing_2d.before_render", (time.perf_counter() - started) * 1000.0)
                audit.record_timing(
                    f"projected_drawing_2d.camera.{self._last_sync_camera_mode}.before_render",
                    (time.perf_counter() - started) * 1000.0,
                )
                audit.set_value("projected_drawing_2d.batches", len(self._visuals))
                audit.set_value("projected_drawing_2d.world_points", sum(len(batch.world_points) for batch in self._compiled))
                audit.set_value("projected_drawing_2d.camera.last_mode", self._last_sync_camera_mode)
            except Exception:
                pass

    def dispose(self, *, render: bool = False) -> None:
        for visual in tuple(self._visuals.values()):
            self._remove_actor(visual.actor)
        for visual in tuple(self._handle_visuals.values()):
            self._remove_actor(visual.actor)
        for visual in tuple(self._text_visuals.values()):
            self._remove_actor(visual.actor)
        self._visuals.clear()
        self._handle_visuals.clear()
        self._text_visuals.clear()
        self._compiled = ()
        self._primitive_spans.clear()
        self._ordered_keys = ()
        self._last_projection_signature = None
        self._last_camera_state = None
        self._last_projection_viewport = None
        self._detach_observer()
        self.renderer = None
        if render:
            self._request_render("projected_drawing_2d.dispose")


_RENDERERS_ATTR = "_laserprog_projected_drawing_2d_renderers"


def _renderer_store(owner: Any, *, create: bool) -> dict[str, ProjectedDrawingOverlay2D] | None:
    store = getattr(owner, _RENDERERS_ATTR, None)
    if isinstance(store, dict):
        return store
    if not create:
        return None
    store = {}
    try:
        setattr(owner, _RENDERERS_ATTR, store)
    except Exception:
        return None
    return store


def sync_projected_drawing_2d(
    owner: Any,
    manager: ProjectedDrawingManager,
    owner_tool: str,
    *,
    render: bool = True,
) -> bool:
    store = _renderer_store(owner, create=True)
    if store is None:
        record_projected_overlay_event("sync.store_failed", owner=owner, owner_tool=owner_tool, manager=manager)
        return False
    key = str(owner_tool)
    renderer = store.get(key)
    if renderer is None or renderer.manager is not manager:
        if renderer is not None:
            renderer.dispose(render=False)
        renderer = ProjectedDrawingOverlay2D(owner, manager, key)
        store[key] = renderer
        record_projected_overlay_event("sync.renderer_created", owner=owner, owner_tool=key, manager=manager, renderer=renderer, store_keys=tuple(store))
    result = renderer.sync_from_manager(force=False, render=render)
    record_projected_overlay_event("sync.call_result", owner=owner, owner_tool=key, manager=manager, renderer=renderer, result=bool(result), render=bool(render))
    return result



def bind_projected_drawing_2d_backend(ctx: Any) -> bool:
    """Attach the Qt/VTK renderer backend to a ToolContext.

    This keeps ``tool_core.projected_drawing`` independent from the application
    package: Tool Core owns declarations and state, while the application layer
    owns the live renderer.
    """

    manager = getattr(ctx, "projected_drawing", None)
    binder = getattr(manager, "bind_renderer_backend", None)
    if not callable(binder):
        return False
    try:
        binder(sync_projected_drawing_2d, dispose_projected_drawing_2d)
        record_projected_overlay_event("backend.bind.ok", owner=getattr(ctx, "owner", None), ctx=ctx, owner_tool="*", manager=manager)
        return True
    except Exception as exc:
        record_projected_overlay_event("backend.bind.exception", owner=getattr(ctx, "owner", None), ctx=ctx, owner_tool="*", manager=manager, error=exc)
        return False

def dispose_projected_drawing_2d(owner: Any, owner_tool: str, *, render: bool = False) -> None:
    store = _renderer_store(owner, create=False)
    if not store:
        return
    renderer = store.pop(str(owner_tool), None)
    if renderer is not None:
        renderer.dispose(render=render)


def dispose_all_projected_drawing_2d(owner: Any, *, render: bool = False) -> None:
    store = _renderer_store(owner, create=False)
    if not store:
        return
    for renderer in tuple(store.values()):
        renderer.dispose(render=False)
    store.clear()
    if render:
        try:
            owner.request_render(reason="projected_drawing_2d.dispose_all")
        except Exception:
            try:
                owner.plotter.render()
            except Exception:
                pass


__all__ = [
    "ProjectedDrawingOverlay2D",
    "bind_projected_drawing_2d_backend",
    "dispose_all_projected_drawing_2d",
    "dispose_projected_drawing_2d",
    "sync_projected_drawing_2d",
]

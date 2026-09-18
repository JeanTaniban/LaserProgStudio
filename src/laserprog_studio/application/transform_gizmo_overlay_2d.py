# -*- coding: utf-8 -*-
"""Screen-space Transform gizmo renderer.

The transform manipulator is an interface control, not scene geometry.  This
backend therefore projects its world-space declaration into persistent
``vtkActor2D`` polylines immediately before every rendered frame.

Design constraints:
- no cones, cylinders, spheres, cubes, tubes or 3D glyph meshes;
- no secondary VTK renderer and no duplicate main-scene fallback;
- all actors use ``vtkProperty2D.SetDisplayLocationToForeground``;
- visible geometry and picking share the exact same projected frame;
- actor/mapper/polydata objects are persistent and only point arrays change;
- camera-facing translation arrows can switch side with hysteresis.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Sequence
import math
import time

from laserprog_studio.mesh_ops import parse_hex_color
from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]


def _p3(value: Sequence[float]) -> Point3:
    return (float(value[0]), float(value[1]), float(value[2]))


def _add(a: Point3, b: Point3) -> Point3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a: Point3, value: float) -> Point3:
    return (a[0] * float(value), a[1] * float(value), a[2] * float(value))


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _length2(a: Point2) -> float:
    return math.hypot(float(a[0]), float(a[1]))


def _normalize3(value: Point3, fallback: Point3 = (1.0, 0.0, 0.0)) -> Point3:
    length = math.sqrt(_dot(value, value))
    if length <= 1.0e-12:
        return fallback
    return (value[0] / length, value[1] / length, value[2] / length)


def _normalize2(value: Point2, fallback: Point2 = (1.0, 0.0)) -> Point2:
    length = _length2(value)
    if length <= 1.0e-9:
        return fallback
    return (float(value[0]) / length, float(value[1]) / length)


def _mix(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    t = max(0.0, min(1.0, float(t)))
    return tuple(float(a[index]) + (float(b[index]) - float(a[index])) * t for index in range(3))  # type: ignore[return-value]


def _point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    denom = vx * vx + vy * vy
    if denom <= 1.0e-9:
        return math.hypot(wx, wy)
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / denom))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


@dataclass(slots=True)
class _OverlayVisual:
    handle: str
    actor: Any
    mapper: Any
    polydata: Any
    points: Any
    primitive: str
    base_width: float
    base_color: tuple[float, float, float]
    topology: tuple[int, ...] = ()


@dataclass(slots=True)
class ProjectedTransformFrame:
    mode: str = ""
    center_qt: Point2 = (0.0, 0.0)
    lines_qt: dict[str, tuple[tuple[Point2, ...], ...]] = field(default_factory=dict)
    axis_basis_qt: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    display_signs: dict[str, float] = field(default_factory=dict)
    updated_at: float = 0.0


class TransformGizmoOverlay2D:
    """Persistent foreground-only 2D renderer for Transform controls."""

    screen_space_overlay = True

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.renderer = None
        self._observer_id: int | None = None
        self._snapshot: Any = None
        self._mode: str | None = None
        self._translation_offset: Point3 = (0.0, 0.0, 0.0)
        self._visuals: dict[str, _OverlayVisual] = {}
        self.groups: dict[str, Any] = {}  # compatibility/debug surface
        self.projected = ProjectedTransformFrame()
        self._display_signs: dict[str, float] = {}
        self._active_handle: str | None = None
        self._pinned_handle: str | None = None
        self._grabbed_handle: str | None = None
        self._last_projection_signature: tuple[Any, ...] | None = None
        # Compatibility aliases. A 2D overlay intentionally owns no assemblies.
        self.overlay_assembly = None
        self.main_assembly = None
        self.assembly = None

    # ------------------------------------------------------------------
    # VTK lifecycle
    # ------------------------------------------------------------------
    def _main_renderer(self) -> Any | None:
        try:
            return self.owner.plotter.renderer
        except Exception:
            return None

    def _request_render(self, reason: str) -> None:
        request = getattr(self.owner, "request_render", None)
        if callable(request):
            try:
                request(reason=str(reason))
                return
            except Exception:
                pass
        try:
            self.owner.plotter.render()
        except Exception:
            pass

    def _ensure_renderer(self) -> Any | None:
        renderer = self._main_renderer()
        if renderer is None:
            return None
        if renderer is self.renderer:
            return renderer
        self._detach_observer()
        self.renderer = renderer
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
        record_transform_gizmo_event(
            self.owner,
            "overlay2d.renderer_ready",
            extra={"observer": self._observer_id is not None, "foreground": True},
        )
        return renderer

    def _detach_observer(self) -> None:
        if self.renderer is not None and self._observer_id is not None:
            try:
                self.renderer.RemoveObserver(self._observer_id)
            except Exception:
                pass
        self._observer_id = None

    def _remove_actor(self, actor: Any) -> None:
        renderer = self.renderer or self._main_renderer()
        if renderer is None or actor is None:
            return
        for method in ("RemoveActor2D", "RemoveViewProp", "RemoveActor"):
            fn = getattr(renderer, method, None)
            if callable(fn):
                try:
                    fn(actor)
                    return
                except Exception:
                    continue

    def clear(self, *, render: bool = False) -> None:
        for visual in tuple(self._visuals.values()):
            self._remove_actor(visual.actor)
        actor_count = len(self._visuals)
        self._visuals.clear()
        self.groups.clear()
        self._snapshot = None
        self._mode = None
        self._translation_offset = (0.0, 0.0, 0.0)
        self.projected = ProjectedTransformFrame()
        self._last_projection_signature = None
        self._detach_observer()
        self.renderer = None
        record_transform_gizmo_event(self.owner, "overlay2d.clear", extra={"actors_removed": actor_count}, ui_log=True)
        if render:
            self._request_render("transform.gizmo.overlay2d.clear")

    @staticmethod
    def _add_actor(renderer: Any, actor: Any) -> bool:
        for method in ("AddActor2D", "AddViewProp", "AddActor"):
            fn = getattr(renderer, method, None)
            if callable(fn):
                try:
                    fn(actor)
                    return True
                except Exception:
                    continue
        return False

    def _new_visual(self, handle: str, *, color: str, width: float, primitive: str = "line") -> _OverlayVisual | None:
        try:
            import vtk

            points = vtk.vtkPoints()
            cells = vtk.vtkCellArray()
            polydata = vtk.vtkPolyData()
            polydata.SetPoints(points)
            polydata.SetLines(cells)
            mapper = vtk.vtkPolyDataMapper2D()
            mapper.SetInputData(polydata)
            coordinate = vtk.vtkCoordinate()
            coordinate.SetCoordinateSystemToDisplay()
            mapper.SetTransformCoordinate(coordinate)
            actor = vtk.vtkActor2D()
            actor.SetMapper(mapper)
            prop = actor.GetProperty()
            rgb = parse_hex_color(str(color))
            prop.SetColor(float(rgb[0]), float(rgb[1]), float(rgb[2]))
            prop.SetOpacity(1.0)
            prop.SetLineWidth(max(1.0, float(width)))
            try:
                prop.SetDisplayLocationToForeground()
            except Exception:
                pass
            try:
                actor.SetPickable(False)
                actor.SetVisibility(True)
            except Exception:
                pass
            renderer = self._ensure_renderer()
            if renderer is None or not self._add_actor(renderer, actor):
                return None
            visual = _OverlayVisual(
                handle=str(handle),
                actor=actor,
                mapper=mapper,
                polydata=polydata,
                points=points,
                primitive=str(primitive),
                base_width=float(width),
                base_color=(float(rgb[0]), float(rgb[1]), float(rgb[2])),
            )
            self._visuals[str(handle)] = visual
            self.groups[str(handle)] = visual
            return visual
        except Exception as exc:
            record_transform_gizmo_event(self.owner, "overlay2d.actor_create_failed", extra={"handle": handle}, error=exc, ui_log=True)
            return None

    def _ensure_visuals(self, snapshot: Any) -> bool:
        mode = str(getattr(snapshot, "mode", "")).lower()
        colors = dict(getattr(snapshot, "colors", {}) or {})
        handles: list[tuple[str, str, float]] = []
        if mode in {"translate", "rotate"}:
            for axis in tuple(getattr(snapshot, "axes", ()) or ()):
                handles.append((str(axis), str(colors.get(axis, "#42A5F5")), 4.2 if mode == "translate" else 3.1))
        elif mode == "scale":
            for key in dict(getattr(snapshot, "lines", {}) or {}):
                logical = str(key)[:1] if str(key)[:1] in {"x", "y", "z"} else str(key)
                handles.append((str(key), str(colors.get(logical, colors.get(key, "#91E085"))), 3.8 if str(key) in {"x", "y", "z"} else 2.2))
        else:
            return False
        handles.append(("__center__", "#E7ECF2", 2.0))
        wanted = {handle for handle, _color, _width in handles}
        for handle in tuple(self._visuals):
            if handle not in wanted:
                self._remove_actor(self._visuals[handle].actor)
                self._visuals.pop(handle, None)
                self.groups.pop(handle, None)
        for handle, color, width in handles:
            if handle not in self._visuals and self._new_visual(handle, color=color, width=width) is None:
                return False
        return True

    # ------------------------------------------------------------------
    # Projection and geometry
    # ------------------------------------------------------------------
    def _world_to_vtk(self, point: Point3) -> Point2 | None:
        try:
            x, y, _depth = self.owner._world_to_display(point)
            return (float(x), float(y))
        except Exception:
            return None

    def _vtk_to_qt(self, point: Point2) -> Point2:
        try:
            height = float(self.owner.plotter.height())
        except Exception:
            height = 0.0
        return (float(point[0]), height - float(point[1]))

    def _camera_vector(self, center: Point3) -> Point3:
        try:
            camera = self._main_renderer().GetActiveCamera()
            position = _p3(camera.GetPosition())
            return _normalize3(_sub(position, center), (0.0, 0.0, 1.0))
        except Exception:
            return (0.0, 0.0, 1.0)

    def _choose_display_sign(self, axis: str, direction: Point3, center: Point3) -> float:
        facing = _dot(_normalize3(direction), self._camera_vector(center))
        previous = float(self._display_signs.get(str(axis), 1.0))
        if facing > 0.14:
            sign = 1.0
        elif facing < -0.14:
            sign = -1.0
        else:
            sign = previous
        self._display_signs[str(axis)] = sign
        return sign

    @staticmethod
    def _clamped_axis_endpoint(center: Point2, projected: Point2, *, axis_index: int, minimum: float = 72.0, maximum: float = 145.0) -> tuple[Point2, Point2, float]:
        delta = (float(projected[0]) - center[0], float(projected[1]) - center[1])
        raw_length = _length2(delta)
        if raw_length < 1.5:
            angle = (0.0, 2.0 * math.pi / 3.0, 4.0 * math.pi / 3.0)[axis_index % 3]
            direction = (math.cos(angle), math.sin(angle))
        else:
            direction = _normalize2(delta)
        display_length = max(float(minimum), min(float(maximum), raw_length if raw_length > 1.5 else float(minimum)))
        endpoint = (center[0] + direction[0] * display_length, center[1] + direction[1] * display_length)
        return endpoint, direction, display_length

    @staticmethod
    def _arrow_polylines(center: Point2, endpoint: Point2, direction: Point2) -> tuple[tuple[Point2, ...], ...]:
        perpendicular = (-direction[1], direction[0])
        head = 13.0
        half = 7.0
        base = (endpoint[0] - direction[0] * head, endpoint[1] - direction[1] * head)
        wing_a = (base[0] + perpendicular[0] * half, base[1] + perpendicular[1] * half)
        wing_b = (base[0] - perpendicular[0] * half, base[1] - perpendicular[1] * half)
        tail = (center[0] - direction[0] * 6.0, center[1] - direction[1] * 6.0)
        return ((tail, endpoint), (wing_a, endpoint, wing_b))

    @staticmethod
    def _square_polyline(center: Point2, half: float = 6.0) -> tuple[Point2, ...]:
        return (
            (center[0] - half, center[1] - half),
            (center[0] + half, center[1] - half),
            (center[0] + half, center[1] + half),
            (center[0] - half, center[1] + half),
            (center[0] - half, center[1] - half),
        )

    def _project_translate(self, snapshot: Any) -> tuple[Point2, dict[str, tuple[tuple[Point2, ...], ...]], dict[str, tuple[float, float, float, float]], dict[str, float]] | None:
        center_world = _add(_p3(snapshot.center), self._translation_offset)
        center = self._world_to_vtk(center_world)
        if center is None:
            return None
        lines: dict[str, tuple[tuple[Point2, ...], ...]] = {}
        basis: dict[str, tuple[float, float, float, float]] = {}
        signs: dict[str, float] = {}
        vectors = dict(getattr(snapshot, "axis_vectors", {}) or {})
        axes = tuple(getattr(snapshot, "axes", ()) or ())
        length_world = max(float(getattr(snapshot, "length", 1.0)), 1.0e-9)
        for index, axis in enumerate(axes):
            direction_world = _normalize3(_p3(vectors.get(axis, (1.0, 0.0, 0.0))))
            sign = self._choose_display_sign(str(axis), direction_world, center_world)
            signed = _mul(direction_world, sign)
            projected = self._world_to_vtk(_add(center_world, _mul(signed, length_world)))
            if projected is None:
                continue
            endpoint, direction_2d, display_length = self._clamped_axis_endpoint(center, projected, axis_index=index)
            lines[str(axis)] = self._arrow_polylines(center, endpoint, direction_2d)
            direction_qt = (direction_2d[0], -direction_2d[1])
            basis[str(axis)] = (direction_qt[0], direction_qt[1], length_world / max(display_length, 1.0), sign)
            signs[str(axis)] = sign
        center_cross = (((center[0] - 4.0, center[1]), (center[0] + 4.0, center[1])), ((center[0], center[1] - 4.0), (center[0], center[1] + 4.0)))
        lines["__center__"] = center_cross
        return center, lines, basis, signs

    def _project_rotate(self, snapshot: Any) -> tuple[Point2, dict[str, tuple[tuple[Point2, ...], ...]], dict[str, tuple[float, float, float, float]], dict[str, float]] | None:
        center = self._world_to_vtk(_p3(snapshot.center))
        if center is None:
            return None
        lines: dict[str, tuple[tuple[Point2, ...], ...]] = {}
        for axis, points in dict(getattr(snapshot, "rings", {}) or {}).items():
            projected: list[Point2] = []
            for point in points:
                value = self._world_to_vtk(_p3(point))
                if value is not None:
                    projected.append(value)
            if len(projected) >= 3:
                lines[str(axis)] = (tuple(projected),)
        lines["__center__"] = (((center[0] - 3.0, center[1]), (center[0] + 3.0, center[1])), ((center[0], center[1] - 3.0), (center[0], center[1] + 3.0)))
        return center, lines, {}, {}

    def _project_scale(self, snapshot: Any) -> tuple[Point2, dict[str, tuple[tuple[Point2, ...], ...]], dict[str, tuple[float, float, float, float]], dict[str, float]] | None:
        center_world = _p3(snapshot.center)
        center = self._world_to_vtk(center_world)
        if center is None:
            return None
        lines: dict[str, tuple[tuple[Point2, ...], ...]] = {}
        basis: dict[str, tuple[float, float, float, float]] = {}
        signs: dict[str, float] = {}
        vectors = dict(getattr(snapshot, "axis_vectors", {}) or {})
        length_world = max(float(getattr(snapshot, "length", 1.0)), 1.0e-9)
        for index, (key, line) in enumerate(dict(getattr(snapshot, "lines", {}) or {}).items()):
            p0 = self._world_to_vtk(_p3(line[0]))
            p1 = self._world_to_vtk(_p3(line[1]))
            if p0 is None or p1 is None:
                continue
            key = str(key)
            if key in {"x", "y", "z"}:
                endpoint, direction_2d, display_length = self._clamped_axis_endpoint(p0, p1, axis_index=index, minimum=68.0, maximum=180.0)
                lines[key] = ((p0, endpoint), self._square_polyline(endpoint, 6.0))
                direction_qt = (direction_2d[0], -direction_2d[1])
                basis[key] = (direction_qt[0], direction_qt[1], length_world / max(display_length, 1.0), 1.0)
                signs[key] = 1.0
            else:
                midpoint = ((p0[0] + p1[0]) * 0.5, (p0[1] + p1[1]) * 0.5)
                lines[key] = ((p0, p1), self._square_polyline(midpoint, 4.5))
        lines["__center__"] = (((center[0] - 4.0, center[1]), (center[0] + 4.0, center[1])), ((center[0], center[1] - 4.0), (center[0], center[1] + 4.0)))
        return center, lines, basis, signs

    @staticmethod
    def _flatten_polylines(polylines: Iterable[Sequence[Point2]]) -> tuple[list[Point2], tuple[int, ...]]:
        points: list[Point2] = []
        topology: list[int] = []
        for polyline in polylines:
            clean = [(float(point[0]), float(point[1])) for point in polyline]
            if len(clean) < 2:
                continue
            start = len(points)
            points.extend(clean)
            topology.extend((len(clean), *range(start, start + len(clean))))
        return points, tuple(topology)

    @staticmethod
    def _set_visual_geometry(visual: _OverlayVisual, polylines: tuple[tuple[Point2, ...], ...]) -> None:
        import vtk

        flat, topology = TransformGizmoOverlay2D._flatten_polylines(polylines)
        points = visual.points
        points.SetNumberOfPoints(len(flat))
        for index, point in enumerate(flat):
            points.SetPoint(index, float(point[0]), float(point[1]), 0.0)
        if topology != visual.topology:
            cells = vtk.vtkCellArray()
            cursor = 0
            while cursor < len(topology):
                count = int(topology[cursor])
                cells.InsertNextCell(count)
                for offset in range(count):
                    cells.InsertCellPoint(int(topology[cursor + 1 + offset]))
                cursor += count + 1
            visual.polydata.SetLines(cells)
            visual.topology = topology
        points.Modified()
        visual.polydata.Modified()
        try:
            visual.actor.SetVisibility(bool(flat))
        except Exception:
            pass

    def _projection_signature(self, snapshot: Any) -> tuple[Any, ...]:
        try:
            camera = self._main_renderer().GetActiveCamera()
            camera_sig = (
                tuple(round(float(v), 7) for v in camera.GetPosition()),
                tuple(round(float(v), 7) for v in camera.GetFocalPoint()),
                tuple(round(float(v), 7) for v in camera.GetViewUp()),
                round(float(camera.GetParallelScale()), 7),
                round(float(camera.GetViewAngle()), 7),
                bool(camera.GetParallelProjection()),
            )
        except Exception:
            camera_sig = ()
        return (
            id(self._snapshot),
            round(float(getattr(snapshot, "length", 0.0) or 0.0), 9),
            camera_sig,
            tuple(round(float(v), 7) for v in self._translation_offset),
            self._active_handle,
            self._pinned_handle,
            self._grabbed_handle,
        )


    def _camera_scaled_snapshot(self, snapshot: Any) -> Any:
        """Return ephemeral geometry sized from the *current* camera.

        The 2D backend is projected during ``vtkRenderer.StartEvent``.  Camera
        wheel handling and Qt timers can run in either order, so using the
        persisted world-space snapshot here creates a one-or-more-frame lag and
        hits the pixel clamps asymmetrically.  Rebuilding only this tiny
        immutable snapshot from the camera makes the current render authoritative.
        No actors, mappers or ToolContext items are recreated.
        """
        try:
            center = _p3(snapshot.center)
            length = max(float(self.owner._gizmo_length_at(center, self.owner.current_meshes())), 1.0e-9)
            old_length = max(float(getattr(snapshot, "length", 0.0) or 0.0), 1.0e-12)
            if abs(length - old_length) <= max(length, old_length) * 1.0e-7:
                return snapshot
            mode = str(getattr(snapshot, "mode", "")).lower()
            axes = tuple(str(axis) for axis in tuple(getattr(snapshot, "axes", ()) or ()))
            vectors = dict(getattr(snapshot, "axis_vectors", {}) or {})
            positions: dict[str, Point3] = {}
            lines: dict[str, tuple[Point3, Point3]] = {}
            rings: dict[str, tuple[Point3, ...]] = {}
            if mode == "translate":
                for axis in axes:
                    direction = _normalize3(_p3(vectors.get(axis, (1.0, 0.0, 0.0))))
                    positions[axis] = _add(center, _mul(direction, length))
                    lines[axis] = (center, _add(center, _mul(direction, length * 0.86)))
            elif mode == "rotate":
                for axis in axes:
                    normal = _normalize3(_p3(vectors.get(axis, (1.0, 0.0, 0.0))))
                    seed = (0.0, 0.0, 1.0) if abs(normal[2]) < 0.9 else (0.0, 1.0, 0.0)
                    u = _normalize3((
                        normal[1] * seed[2] - normal[2] * seed[1],
                        normal[2] * seed[0] - normal[0] * seed[2],
                        normal[0] * seed[1] - normal[1] * seed[0],
                    ))
                    v = _normalize3((
                        normal[1] * u[2] - normal[2] * u[1],
                        normal[2] * u[0] - normal[0] * u[2],
                        normal[0] * u[1] - normal[1] * u[0],
                    ))
                    radius = length * 0.92
                    ring = tuple(
                        _add(center, _add(_mul(u, math.cos(2.0 * math.pi * i / 96.0) * radius), _mul(v, math.sin(2.0 * math.pi * i / 96.0) * radius)))
                        for i in range(97)
                    )
                    rings[axis] = ring
                    positions[axis] = ring[len(ring) // 2]
            elif mode == "scale":
                old_lines = dict(getattr(snapshot, "lines", {}) or {})
                old_positions = dict(getattr(snapshot, "positions", {}) or {})
                frame_keys = [str(key) for key in old_lines if str(key) not in {"x", "y", "z"}]
                ratio = length / old_length
                for key in frame_keys:
                    a, b = old_lines[key]
                    a3, b3 = _p3(a), _p3(b)
                    lines[key] = (_add(center, _mul(_sub(a3, center), ratio)), _add(center, _mul(_sub(b3, center), ratio)))
                    if key in old_positions:
                        positions[key] = _add(center, _mul(_sub(_p3(old_positions[key]), center), ratio))
                for axis in axes:
                    direction = _normalize3(_p3(vectors.get(axis, (1.0, 0.0, 0.0))))
                    tip = _add(center, _mul(direction, length * 0.74))
                    positions[axis] = tip
                    lines[axis] = (center, tip)
            else:
                return snapshot
            return replace(snapshot, length=length, positions=positions, lines=lines, rings=rings)
        except Exception as exc:
            record_transform_gizmo_event(self.owner, "overlay2d.camera_snapshot_failed", error=exc)
            return snapshot

    def update_before_render(self, *, force: bool = False) -> bool:
        source_snapshot = self._snapshot
        if source_snapshot is None:
            return False
        snapshot = self._camera_scaled_snapshot(source_snapshot)
        signature = self._projection_signature(snapshot)
        if not force and signature == self._last_projection_signature:
            return False
        start = time.perf_counter()
        mode = str(getattr(snapshot, "mode", "")).lower()
        if mode == "translate":
            result = self._project_translate(snapshot)
        elif mode == "rotate":
            result = self._project_rotate(snapshot)
        elif mode == "scale":
            result = self._project_scale(snapshot)
        else:
            return False
        if result is None:
            return False
        center_vtk, lines_vtk, axis_basis, signs = result
        for handle, visual in self._visuals.items():
            self._set_visual_geometry(visual, lines_vtk.get(handle, ()))
        self.projected = ProjectedTransformFrame(
            mode=mode,
            center_qt=self._vtk_to_qt(center_vtk),
            lines_qt={
                handle: tuple(tuple(self._vtk_to_qt(point) for point in polyline) for polyline in polylines)
                for handle, polylines in lines_vtk.items()
            },
            axis_basis_qt=axis_basis,
            display_signs=signs,
            updated_at=time.monotonic(),
        )
        self._last_projection_signature = signature
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        try:
            from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

            audit.record_timing("transform.gizmo.overlay2d.project", elapsed_ms)
            audit.set_value("transform.gizmo.overlay2d.actors", len(self._visuals))
            audit.set_value("transform.gizmo.overlay2d.projected_handles", len(lines_vtk))
        except Exception:
            pass
        record_transform_gizmo_event(
            self.owner,
            "overlay2d.projected",
            snapshot=snapshot,
            extra={"elapsed_ms": round(elapsed_ms, 4), "handles": len(lines_vtk), "signs": signs},
        )
        return True

    def _before_render(self, _caller: Any = None, _event: Any = None) -> None:
        try:
            self.update_before_render(force=False)
        except Exception as exc:
            record_transform_gizmo_event(self.owner, "overlay2d.before_render_failed", error=exc)

    # ------------------------------------------------------------------
    # Public renderer contract
    # ------------------------------------------------------------------
    def sync(self, snapshot: Any, *, render: bool = True) -> bool:
        if self._ensure_renderer() is None:
            # Headless tests still use API picking from the world snapshot.
            self._snapshot = snapshot
            self._mode = str(getattr(snapshot, "mode", "")).lower()
            return True
        if not self._ensure_visuals(snapshot):
            return False
        self._snapshot = snapshot
        self._mode = str(getattr(snapshot, "mode", "")).lower()
        self._translation_offset = (0.0, 0.0, 0.0)
        self._last_projection_signature = None
        self.update_before_render(force=True)
        self.set_interaction(
            active_handle=self._active_handle,
            pinned_handle=self._pinned_handle,
            grabbed_handle=self._grabbed_handle,
            render=False,
        )
        record_transform_gizmo_event(
            self.owner,
            "overlay2d.sync_success",
            snapshot=snapshot,
            extra={"actors": len(self._visuals), "renderer": "vtkActor2D"},
            ui_log=True,
        )
        if render:
            self._request_render("transform.gizmo.overlay2d.sync")
        return True

    def update_geometry(self, snapshot: Any, *, render: bool = False) -> bool:
        if str(getattr(snapshot, "mode", "")).lower() != self._mode:
            return self.sync(snapshot, render=render)
        self._snapshot = snapshot
        self._translation_offset = (0.0, 0.0, 0.0)
        self._last_projection_signature = None
        self.update_before_render(force=True)
        if render:
            self._request_render("transform.gizmo.overlay2d.update")
        return True

    def move_translate(self, *, offset: Point3, render: bool = False) -> bool:
        if self._mode != "translate" or self._snapshot is None:
            return False
        self._translation_offset = _p3(offset)
        self._last_projection_signature = None
        self.update_before_render(force=True)
        if render:
            self._request_render("transform.gizmo.overlay2d.follow")
        return True

    @staticmethod
    def _logical(handle: str | None) -> str | None:
        value = (handle or "").lower().strip()
        if not value:
            return None
        return value[:1] if value[:1] in {"x", "y", "z"} else value

    def set_interaction(self, *, active_handle: str | None, pinned_handle: str | None, grabbed_handle: str | None, render: bool = False) -> bool:
        values = (
            (active_handle or "").lower().strip() or None,
            (pinned_handle or "").lower().strip() or None,
            (grabbed_handle or "").lower().strip() or None,
        )
        changed = values != (self._active_handle, self._pinned_handle, self._grabbed_handle)
        self._active_handle, self._pinned_handle, self._grabbed_handle = values
        active = self._logical(self._active_handle)
        pinned = self._logical(self._pinned_handle)
        grabbed = self._logical(self._grabbed_handle)
        for handle, visual in self._visuals.items():
            logical = self._logical(handle)
            if handle == "__center__":
                color, opacity, scale = visual.base_color, 0.78, 1.0
            elif grabbed and logical == grabbed:
                color, opacity, scale = _mix(visual.base_color, (1.0, 0.94, 0.25), 0.72), 1.0, 1.55
            elif active and logical == active:
                color, opacity, scale = _mix(visual.base_color, (1.0, 1.0, 1.0), 0.58), 1.0, 1.35
            elif pinned and logical == pinned:
                color, opacity, scale = _mix(visual.base_color, (1.0, 1.0, 1.0), 0.28), 1.0, 1.16
            else:
                color, opacity, scale = visual.base_color, 0.96, 1.0
            try:
                prop = visual.actor.GetProperty()
                prop.SetColor(*color)
                prop.SetOpacity(float(opacity))
                prop.SetLineWidth(max(1.0, visual.base_width * scale))
            except Exception:
                pass
        if changed and render:
            self._request_render("transform.gizmo.overlay2d.interaction")
        return changed

    # ------------------------------------------------------------------
    # Shared projected picking / drag basis
    # ------------------------------------------------------------------
    def pick(self, qx: float, qy: float, *, generous: bool = False) -> str | None:
        self.update_before_render(force=False)
        px, py = float(qx), float(qy)
        center = self.projected.center_qt
        if self.projected.mode == "translate" and math.hypot(px - center[0], py - center[1]) < (25.0 if generous else 18.0):
            return None
        candidates: list[tuple[str, float]] = []
        for handle, polylines in self.projected.lines_qt.items():
            if handle == "__center__":
                continue
            best = 1.0e9
            for polyline in polylines:
                for a, b in zip(polyline, polyline[1:]):
                    best = min(best, _point_segment_distance(px, py, a[0], a[1], b[0], b[1]))
            candidates.append((handle, best))
        threshold = (19.0 if generous else 10.5) if self.projected.mode != "rotate" else (20.0 if generous else 9.0)
        candidates = [candidate for candidate in candidates if candidate[1] <= threshold]
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[1], item[0]))
        sticky = self._logical(self._grabbed_handle or self._active_handle or self._pinned_handle)
        if sticky:
            for handle, distance in candidates:
                if self._logical(handle) == sticky and distance <= threshold * 1.12:
                    return handle
        return candidates[0][0]

    def drag_basis(self, handle: str, *, world_length: float | None = None) -> tuple[float, float, float, float] | None:
        self.update_before_render(force=False)
        logical = self._logical(handle)
        if logical is None:
            return None
        basis = self.projected.axis_basis_qt.get(logical)
        if basis is None:
            return None
        dx, dy, stored_world_per_pixel, sign = basis
        if world_length is not None and float(world_length) > 0.0:
            # Stored basis already derives from snapshot length and the exact
            # displayed pixel span. Keep it unless callers supplied a materially
            # different world length.
            stored_world_per_pixel = max(float(stored_world_per_pixel), 1.0e-12)
        return (float(dx), float(dy), float(stored_world_per_pixel), float(sign))

    def display_sign(self, handle: str) -> float:
        return float(self.projected.display_signs.get(self._logical(handle) or str(handle), 1.0))


__all__ = ["ProjectedTransformFrame", "TransformGizmoOverlay2D"]

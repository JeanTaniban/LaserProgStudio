# -*- coding: utf-8 -*-
"""Lightweight line/point renderer for the application Transform gizmo.

The renderer follows the Creator API visual model: transform controls are made
only from PyVista polylines and point clouds.  It deliberately avoids cones,
cylinders, spheres, cubes, tubes and every other solid helper mesh.

The v17 implementation also makes visibility robust:

* actors keep valid bounds in the foreground renderer, otherwise VTK may compute
  an invalid clipping range and silently hide a renderer containing only
  ``UseBoundsOff`` props;
* the same lightweight geometry is mirrored to the main renderer as a fallback;
* foreground and fallback assemblies are removed deterministically;
* all lifecycle stages emit structured diagnostics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence
import math
import os

from laserprog_studio.mesh_ops import parse_hex_color
from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event

Point3 = tuple[float, float, float]


@dataclass(slots=True)
class _ActorVisual:
    actor: Any
    primitive: str
    base_width: float
    layer: str


@dataclass(slots=True)
class _ActorGroup:
    handle: str
    actors: list[_ActorVisual] = field(default_factory=list)
    base_color: tuple[float, float, float] = (1.0, 1.0, 1.0)


def _mix(a: tuple[float, float, float], b: tuple[float, float, float], t: float) -> tuple[float, float, float]:
    t = max(0.0, min(1.0, float(t)))
    return (
        float(a[0]) + (float(b[0]) - float(a[0])) * t,
        float(a[1]) + (float(b[1]) - float(a[1])) * t,
        float(a[2]) + (float(b[2]) - float(a[2])) * t,
    )


def _sub(a: Point3, b: Point3) -> Point3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _add(a: Point3, b: Point3) -> Point3:
    return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))


def _mul(a: Point3, s: float) -> Point3:
    return (float(a[0]) * float(s), float(a[1]) * float(s), float(a[2]) * float(s))


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(a: Point3) -> float:
    return math.sqrt(float(a[0]) ** 2 + float(a[1]) ** 2 + float(a[2]) ** 2)


def _normalize(a: Point3, fallback: Point3 = (1.0, 0.0, 0.0)) -> Point3:
    n = _norm(a)
    if n <= 1.0e-12:
        return fallback
    return (float(a[0]) / n, float(a[1]) / n, float(a[2]) / n)


def _as_point(p: Sequence[float]) -> Point3:
    return (float(p[0]), float(p[1]), float(p[2]))


def _main_fallback_enabled() -> bool:
    value = str(os.environ.get("LPS_TRANSFORM_GIZMO_MAIN_FALLBACK", "1")).strip().lower()
    return value not in {"0", "false", "off", "no"}


class _LegacyTransformGizmoRenderer3D:
    """Persistent foreground renderer made exclusively of lines and points."""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.overlay = None
        self.overlay_assembly = None
        self.main_assembly = None
        # Compatibility alias used by earlier tests/callers. It resolves to the
        # primary visible assembly after a successful sync.
        self.assembly = None
        self.groups: dict[str, _ActorGroup] = {}
        self._all_actors: list[Any] = []
        self._signature: tuple[Any, ...] | None = None
        self._base_center: Point3 | None = None
        self._mode: str | None = None
        self._active_handle: str | None = None
        self._pinned_handle: str | None = None
        self._grabbed_handle: str | None = None

    # ------------------------------------------------------------------
    # Renderer / actor lifecycle
    # ------------------------------------------------------------------
    def _ensure_overlay(self):
        ensure = getattr(self.owner, "_ensure_gizmo_overlay_renderer", None)
        if not callable(ensure):
            record_transform_gizmo_event(self.owner, "renderer.overlay_unavailable", extra={"reason": "missing_ensure_method"})
            return None
        try:
            overlay = ensure()
        except Exception as exc:
            record_transform_gizmo_event(self.owner, "renderer.overlay_exception", error=exc, ui_log=True)
            overlay = None
        self.overlay = overlay
        if overlay is not None:
            try:
                overlay.SetLayer(1)
                overlay.SetInteractive(False)
                overlay.SetPreserveDepthBuffer(False)
                # Layer renderers must not erase the color buffer produced by
                # the main renderer. Some VTK builds ignore alpha otherwise.
                overlay.SetErase(False)
            except Exception:
                pass
        record_transform_gizmo_event(self.owner, "renderer.overlay_ready", extra={"available": overlay is not None})
        return overlay

    def _main_renderer(self):
        try:
            return self.owner.plotter.renderer
        except Exception:
            return None

    def _cleanup_transform_legacy_actors(self) -> None:
        """Remove only actors owned by historical Transform implementations.

        This renderer must never call the generic Creator-UI cleanup path.  That
        path is shared by Plan Tracer and every Creator tool; using it from the
        application Transform subsystem previously corrupted their actor state.
        The compatibility cleanup below is deliberately restricted to the known
        legacy Transform keys in ``owner.gizmo_actors``.
        """

        actors = getattr(self.owner, "gizmo_actors", None)
        plotter = getattr(self.owner, "plotter", None)
        if not isinstance(actors, dict):
            return
        exact = {
            "center",
            "label_x", "label_y", "label_z",
        }
        prefixes = (
            "x_shaft", "y_shaft", "z_shaft",
            "x_tip", "y_tip", "z_tip",
            "rotate_x_", "rotate_y_", "rotate_z_",
            "scale_x_", "scale_y_", "scale_z_", "scale_edge_",
            "creator_ui_app_transform_gizmo_",
        )
        removed = 0
        for key, actor in list(actors.items()):
            name = str(key)
            if name not in exact and not name.startswith(prefixes):
                continue
            try:
                if plotter is not None and actor is not None:
                    plotter.remove_actor(actor, render=False)
            except Exception:
                pass
            actors.pop(key, None)
            removed += 1
        if removed:
            record_transform_gizmo_event(
                self.owner,
                "renderer.transform_legacy_actors_removed",
                extra={"count": removed},
            )

    @staticmethod
    def _remove_prop(renderer: Any, prop: Any) -> bool:
        if renderer is None or prop is None:
            return False
        for method in ("RemoveViewProp", "RemoveActor"):
            fn = getattr(renderer, method, None)
            if callable(fn):
                try:
                    fn(prop)
                    return True
                except Exception:
                    continue
        return False

    def _remove_assembly(self) -> None:
        overlay = self.overlay or self._ensure_overlay()
        main = self._main_renderer()
        removed_overlay = self._remove_prop(overlay, self.overlay_assembly)
        removed_main = self._remove_prop(main, self.main_assembly)
        record_transform_gizmo_event(
            self.owner,
            "renderer.assemblies_removed",
            extra={
                "removed_overlay": removed_overlay,
                "removed_main": removed_main,
                "actors_before": len(self._all_actors),
                "groups_before": len(self.groups),
            },
        )
        self.overlay_assembly = None
        self.main_assembly = None
        self.assembly = None
        self.groups.clear()
        self._all_actors.clear()
        self._signature = None
        self._base_center = None
        self._mode = None

    def clear(self, *, render: bool = False) -> None:
        self._cleanup_transform_legacy_actors()
        self._remove_assembly()
        self._active_handle = None
        self._pinned_handle = None
        self._grabbed_handle = None
        record_transform_gizmo_event(self.owner, "renderer.clear", ui_log=True)
        if render:
            self._request_render("transform.gizmo.clear")

    def _request_render(self, reason: str) -> None:
        record_transform_gizmo_event(self.owner, "renderer.render_requested", extra={"reason": str(reason)})
        request = getattr(self.owner, "request_render", None)
        if callable(request):
            try:
                request(reason=str(reason))
                return
            except Exception as exc:
                record_transform_gizmo_event(self.owner, "renderer.request_render_failed", error=exc)
        plotter = getattr(self.owner, "plotter", None)
        render = getattr(plotter, "render", None)
        if callable(render):
            try:
                render()
            except Exception as exc:
                record_transform_gizmo_event(self.owner, "renderer.direct_render_failed", error=exc, ui_log=True)

    @staticmethod
    def _polyline_mesh(polylines: Iterable[Sequence[Point3]]):
        """Build disconnected PyVista polylines without tubing or surfaces."""

        import numpy as np
        import pyvista as pv

        points: list[Point3] = []
        cells: list[int] = []
        for line in polylines:
            clean = [_as_point(p) for p in line]
            if len(clean) < 2:
                continue
            start = len(points)
            points.extend(clean)
            cells.extend([len(clean), *range(start, start + len(clean))])
        if not points:
            return None
        mesh = pv.PolyData(np.asarray(points, dtype=float))
        mesh.lines = np.asarray(cells, dtype=np.int64)
        return mesh

    @staticmethod
    def _point_mesh(points: Iterable[Point3]):
        """Build a PyVista point cloud; points stay GL/VTK points, not spheres."""

        import numpy as np
        import pyvista as pv

        clean = [_as_point(p) for p in points]
        if not clean:
            return None
        return pv.PolyData(np.asarray(clean, dtype=float))

    def _new_actor(
        self,
        mesh: Any,
        color: str,
        *,
        primitive: str,
        opacity: float = 1.0,
        line_width: float = 3.0,
        point_size: float = 10.0,
        use_bounds: bool = True,
    ) -> Any | None:
        try:
            import vtk

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(mesh)
            try:
                mapper.Update()
            except Exception:
                pass
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            r, g, b = parse_hex_color(str(color))
            prop = actor.GetProperty()
            prop.SetColor(float(r), float(g), float(b))
            prop.SetOpacity(float(opacity))
            prop.SetAmbient(1.0)
            prop.SetDiffuse(0.0)
            prop.SetSpecular(0.0)
            try:
                prop.LightingOff()
            except Exception:
                pass
            if primitive == "line":
                prop.SetLineWidth(max(1.0, float(line_width)))
                try:
                    prop.SetRenderLinesAsTubes(False)
                except Exception:
                    pass
            elif primitive == "point":
                prop.SetPointSize(max(1.0, float(point_size)))
                try:
                    prop.SetRenderPointsAsSpheres(False)
                except Exception:
                    pass
            try:
                actor.SetVisibility(True)
                actor.SetPickable(False)  # deterministic screen-space picker
            except Exception:
                pass
            # IMPORTANT: foreground renderers containing only UseBoundsOff props
            # may obtain an invalid clipping range and render nothing at all.
            try:
                actor.SetUseBounds(bool(use_bounds))
            except Exception:
                pass
            return actor
        except Exception as exc:
            record_transform_gizmo_event(
                self.owner,
                "renderer.actor_create_failed",
                extra={"primitive": primitive, "color": color},
                error=exc,
                ui_log=True,
            )
            return None

    def _append_actor(
        self,
        handle: str,
        mesh: Any,
        color: str,
        *,
        primitive: str,
        opacity: float,
        line_width: float,
        point_size: float,
    ) -> None:
        try:
            base = tuple(float(v) for v in parse_hex_color(str(color)))
        except Exception:
            base = (1.0, 1.0, 1.0)
        group = self.groups.setdefault(str(handle), _ActorGroup(str(handle), [], base))
        group.base_color = base

        targets: list[tuple[str, Any, bool]] = []
        if self.overlay_assembly is not None:
            targets.append(("overlay", self.overlay_assembly, True))
        if self.main_assembly is not None:
            # Main fallback must not influence camera framing.
            targets.append(("main", self.main_assembly, False))

        for layer, assembly, use_bounds in targets:
            actor = self._new_actor(
                mesh,
                color,
                primitive=primitive,
                opacity=opacity,
                line_width=line_width,
                point_size=point_size,
                use_bounds=use_bounds,
            )
            if actor is None:
                continue
            try:
                assembly.AddPart(actor)
            except Exception as exc:
                record_transform_gizmo_event(self.owner, "renderer.assembly_add_part_failed", extra={"layer": layer, "handle": handle}, error=exc)
                continue
            visual = _ActorVisual(actor=actor, primitive=primitive, base_width=float(line_width if primitive == "line" else point_size), layer=layer)
            group.actors.append(visual)
            self._all_actors.append(actor)

    def _add_group_actor(
        self,
        handle: str,
        mesh: Any,
        color: str,
        *,
        primitive: str,
        opacity: float = 1.0,
        line_width: float = 3.0,
        point_size: float = 10.0,
    ) -> None:
        if mesh is None:
            return
        self._append_actor(
            handle,
            mesh,
            color,
            primitive=primitive,
            opacity=opacity,
            line_width=line_width,
            point_size=point_size,
        )

    def _add_neutral_point(self, point: Point3, *, size: float = 8.0, color: str = "#E7ECF2", opacity: float = 0.9) -> None:
        self._add_group_actor("__center__", self._point_mesh([point]), color, primitive="point", opacity=opacity, point_size=size)

    def _camera_view_direction(self) -> Point3:
        try:
            camera = self.owner.plotter.renderer.GetActiveCamera()
            direction = camera.GetDirectionOfProjection()
            return _normalize(_as_point(direction), (0.0, 0.0, -1.0))
        except Exception:
            return (0.0, 0.0, -1.0)

    def _arrow_wing_vector(self, axis: Point3) -> Point3:
        """Return a camera-facing perpendicular so arrowheads stay readable."""

        axis_n = _normalize(axis)
        side = _cross(axis_n, self._camera_view_direction())
        if _norm(side) <= 1.0e-6:
            ref = (0.0, 0.0, 1.0) if abs(axis_n[2]) < 0.9 else (0.0, 1.0, 0.0)
            side = _cross(axis_n, ref)
        return _normalize(side, (0.0, 1.0, 0.0))

    # ------------------------------------------------------------------
    # Geometry builders: line/point primitives only
    # ------------------------------------------------------------------
    def _build_translate(self, snapshot: Any) -> None:
        center = _as_point(snapshot.center)
        length = max(float(snapshot.length), 1.0e-9)
        colors = dict(getattr(snapshot, "colors", {}) or {})
        vectors = dict(getattr(snapshot, "axis_vectors", {}) or {})
        positions = dict(getattr(snapshot, "positions", {}) or {})
        for axis in tuple(snapshot.axes):
            direction = _normalize(_as_point(vectors.get(axis, (1.0, 0.0, 0.0))))
            tip = _as_point(positions.get(axis, _add(center, _mul(direction, length))))
            side = self._arrow_wing_vector(direction)
            head_len = length * 0.18
            head_half_width = length * 0.085
            head_base = _sub(tip, _mul(direction, head_len))
            wing_a = _add(head_base, _mul(side, head_half_width))
            wing_b = _sub(head_base, _mul(side, head_half_width))
            tail = _sub(center, _mul(direction, length * 0.075))
            color = colors.get(axis, "#42A5F5")
            # One lightweight polydata contains shaft, orientation tail and both
            # arrowhead strokes. Picking remains screen-space; no large tip point
            # is rendered on translation arrows.
            # Canonical arrow strokes are ((center, tip), (tip, wing_a), (tip, wing_b));
            # the extra tail segment only improves orientation around the origin.
            mesh = self._polyline_mesh(((tail, tip), (tip, wing_a), (tip, wing_b)))
            self._add_group_actor(axis, mesh, color, primitive="line", line_width=4.6)
        self._add_neutral_point(center, size=9.0)

    def _build_rotate(self, snapshot: Any) -> None:
        colors = dict(getattr(snapshot, "colors", {}) or {})
        positions = dict(getattr(snapshot, "positions", {}) or {})
        for axis, points in dict(getattr(snapshot, "rings", {}) or {}).items():
            clean = tuple(_as_point(p) for p in points)
            if len(clean) < 3:
                continue
            color = colors.get(str(axis), "#FFB23F")
            self._add_group_actor(str(axis), self._polyline_mesh((clean,)), color, primitive="line", line_width=3.4, opacity=0.96)
            marker = positions.get(str(axis))
            if marker is not None:
                # The marker is intentionally larger than the ring stroke. It is
                # the predictable grab point when projected rings overlap.
                self._add_group_actor(str(axis), self._point_mesh([_as_point(marker)]), color, primitive="point", point_size=12.0)
        self._add_neutral_point(_as_point(snapshot.center), size=7.0, opacity=0.70)

    def _build_scale(self, snapshot: Any) -> None:
        colors = dict(getattr(snapshot, "colors", {}) or {})
        lines = dict(getattr(snapshot, "lines", {}) or {})
        positions = dict(getattr(snapshot, "positions", {}) or {})
        for handle, line in lines.items():
            key = str(handle)
            p0, p1 = _as_point(line[0]), _as_point(line[1])
            logical = key[:1] if key[:1] in {"x", "y", "z"} else key
            color = colors.get(logical, colors.get(key, "#91E085"))
            width = 3.8 if key in {"x", "y", "z"} else 2.3
            opacity = 1.0 if key in {"x", "y", "z"} else 0.72
            self._add_group_actor(key, self._polyline_mesh(((p0, p1),)), color, primitive="line", line_width=width, opacity=opacity)
            tip = positions.get(key)
            if tip is not None:
                size = 12.0 if key in {"x", "y", "z"} else 9.0
                self._add_group_actor(key, self._point_mesh([_as_point(tip)]), color, primitive="point", point_size=size, opacity=opacity)
        self._add_neutral_point(_as_point(snapshot.center), size=8.0, opacity=0.78)

    def _set_group_points(self, handle: str, primitive: str, points: Sequence[Point3]) -> bool:
        """Update one lightweight actor group in place without actor churn."""

        group = self.groups.get(str(handle))
        if group is None:
            return False
        try:
            import numpy as np

            array = np.asarray([_as_point(point) for point in points], dtype=float)
        except Exception:
            return False
        updated = False
        seen_inputs: set[int] = set()
        for visual in group.actors:
            if visual.primitive != primitive:
                continue
            try:
                mapper = visual.actor.GetMapper()
                mesh = mapper.GetInput() if mapper is not None else None
                if mesh is None or id(mesh) in seen_inputs:
                    continue
                seen_inputs.add(id(mesh))
                if int(mesh.GetNumberOfPoints()) != int(len(array)):
                    return False
                if hasattr(mesh, "points"):
                    mesh.points = array
                    modified = getattr(mesh, "modified", None)
                    if callable(modified):
                        modified()
                    else:
                        mesh.Modified()
                else:
                    vtk_points = mesh.GetPoints()
                    if vtk_points is None:
                        return False
                    for index, point in enumerate(array):
                        vtk_points.SetPoint(index, float(point[0]), float(point[1]), float(point[2]))
                    vtk_points.Modified()
                    mesh.Modified()
                updated = True
            except Exception:
                return False
        return updated

    def _update_translate_geometry(self, snapshot: Any) -> bool:
        center = _as_point(snapshot.center)
        length = max(float(snapshot.length), 1.0e-9)
        vectors = dict(getattr(snapshot, "axis_vectors", {}) or {})
        positions = dict(getattr(snapshot, "positions", {}) or {})
        ok = True
        for axis in tuple(snapshot.axes):
            direction = _normalize(_as_point(vectors.get(axis, (1.0, 0.0, 0.0))))
            tip = _as_point(positions.get(axis, _add(center, _mul(direction, length))))
            side = self._arrow_wing_vector(direction)
            head_base = _sub(tip, _mul(direction, length * 0.18))
            wing_a = _add(head_base, _mul(side, length * 0.085))
            wing_b = _sub(head_base, _mul(side, length * 0.085))
            tail = _sub(center, _mul(direction, length * 0.075))
            ok = self._set_group_points(str(axis), "line", (tail, tip, tip, wing_a, tip, wing_b)) and ok
        ok = self._set_group_points("__center__", "point", (center,)) and ok
        return ok

    def _update_rotate_geometry(self, snapshot: Any) -> bool:
        ok = True
        positions = dict(getattr(snapshot, "positions", {}) or {})
        for axis, points in dict(getattr(snapshot, "rings", {}) or {}).items():
            key = str(axis)
            ok = self._set_group_points(key, "line", tuple(_as_point(p) for p in points)) and ok
            marker = positions.get(key)
            if marker is not None:
                ok = self._set_group_points(key, "point", (_as_point(marker),)) and ok
        ok = self._set_group_points("__center__", "point", (_as_point(snapshot.center),)) and ok
        return ok

    def _update_scale_geometry(self, snapshot: Any) -> bool:
        ok = True
        lines = dict(getattr(snapshot, "lines", {}) or {})
        positions = dict(getattr(snapshot, "positions", {}) or {})
        for handle, line in lines.items():
            key = str(handle)
            ok = self._set_group_points(key, "line", (_as_point(line[0]), _as_point(line[1]))) and ok
            tip = positions.get(key)
            if tip is not None:
                ok = self._set_group_points(key, "point", (_as_point(tip),)) and ok
        ok = self._set_group_points("__center__", "point", (_as_point(snapshot.center),)) and ok
        return ok

    def update_geometry(self, snapshot: Any, *, render: bool = False) -> bool:
        """Update line/point coordinates in place for camera-scaled gizmos."""

        mode = str(getattr(snapshot, "mode", "")).lower()
        if mode != self._mode:
            return False
        # Headless/test hosts keep only the API snapshot.
        if self.overlay_assembly is None and self.main_assembly is None:
            self._signature = self._snapshot_signature(snapshot)
            self._base_center = _as_point(snapshot.center)
            return True
        try:
            if mode == "translate":
                updated = self._update_translate_geometry(snapshot)
            elif mode == "rotate":
                updated = self._update_rotate_geometry(snapshot)
            elif mode == "scale":
                updated = self._update_scale_geometry(snapshot)
            else:
                return False
            if not updated:
                return False
            self._signature = self._snapshot_signature(snapshot)
            self._base_center = _as_point(snapshot.center)
            record_transform_gizmo_event(
                self.owner,
                "renderer.geometry_updated",
                snapshot=snapshot,
                extra={"render": bool(render)},
            )
            if render:
                self._request_render("transform.gizmo.camera_scale")
            return True
        except Exception as exc:
            record_transform_gizmo_event(self.owner, "renderer.geometry_update_failed", snapshot=snapshot, error=exc)
            return False

    # ------------------------------------------------------------------
    # Public updates
    # ------------------------------------------------------------------
    @staticmethod
    def _snapshot_signature(snapshot: Any) -> tuple[Any, ...]:
        def rounded_point(p: Any) -> tuple[float, float, float]:
            return tuple(round(float(v), 8) for v in tuple(p))

        lines = tuple(sorted((str(k), rounded_point(v[0]), rounded_point(v[1])) for k, v in dict(getattr(snapshot, "lines", {}) or {}).items()))
        rings = tuple(
            sorted(
                (str(k), len(v), rounded_point(v[0]) if v else (), rounded_point(v[len(v) // 2]) if v else (), rounded_point(v[-1]) if v else ())
                for k, v in dict(getattr(snapshot, "rings", {}) or {}).items()
            )
        )
        vectors = tuple(sorted((str(k), rounded_point(v)) for k, v in dict(getattr(snapshot, "axis_vectors", {}) or {}).items()))
        colors = tuple(sorted((str(k), str(v)) for k, v in dict(getattr(snapshot, "colors", {}) or {}).items()))
        return (str(snapshot.mode), rounded_point(snapshot.center), round(float(snapshot.length), 8), tuple(snapshot.axes), lines, rings, vectors, colors)

    @staticmethod
    def _add_prop(renderer: Any, prop: Any) -> bool:
        if renderer is None or prop is None:
            return False
        for method in ("AddViewProp", "AddActor"):
            fn = getattr(renderer, method, None)
            if callable(fn):
                try:
                    fn(prop)
                    return True
                except Exception:
                    continue
        return False

    def _create_assemblies(self, overlay: Any, main: Any) -> None:
        import vtk

        self.overlay_assembly = vtk.vtkAssembly() if overlay is not None else None
        self.main_assembly = vtk.vtkAssembly() if main is not None and _main_fallback_enabled() else None
        for assembly, use_bounds in ((self.overlay_assembly, True), (self.main_assembly, False)):
            if assembly is None:
                continue
            try:
                assembly.SetPickable(False)
                assembly.SetUseBounds(bool(use_bounds))
                assembly.SetVisibility(True)
            except Exception:
                pass
        self.assembly = self.overlay_assembly or self.main_assembly

    def sync(self, snapshot: Any, *, render: bool = True) -> bool:
        self._cleanup_transform_legacy_actors()
        record_transform_gizmo_event(self.owner, "renderer.sync_begin", snapshot=snapshot, extra={"render": bool(render)})
        overlay = self._ensure_overlay()
        main = self._main_renderer()

        # Headless/test hosts intentionally have no VTK renderer. API state and
        # picking still work, so rendering is a successful no-op.
        if overlay is None and main is None:
            self._signature = self._snapshot_signature(snapshot)
            self._base_center = _as_point(snapshot.center)
            self._mode = str(snapshot.mode)
            record_transform_gizmo_event(self.owner, "renderer.sync_headless", snapshot=snapshot)
            return True

        signature = self._snapshot_signature(snapshot)
        if signature == self._signature and self.assembly is not None:
            self.set_interaction(
                active_handle=self._active_handle,
                pinned_handle=self._pinned_handle,
                grabbed_handle=self._grabbed_handle,
                render=render,
            )
            record_transform_gizmo_event(self.owner, "renderer.sync_reused", snapshot=snapshot)
            return True

        self._remove_assembly()
        try:
            self._create_assemblies(overlay, main)
            mode = str(snapshot.mode).lower()
            if mode == "translate":
                self._build_translate(snapshot)
            elif mode == "rotate":
                self._build_rotate(snapshot)
            elif mode == "scale":
                self._build_scale(snapshot)
            else:
                self._remove_assembly()
                record_transform_gizmo_event(self.owner, "renderer.sync_invalid_mode", snapshot=snapshot, ui_log=True)
                return False

            overlay_added = self._add_prop(overlay, self.overlay_assembly)
            main_added = self._add_prop(main, self.main_assembly)
            if not overlay_added and not main_added:
                self._remove_assembly()
                record_transform_gizmo_event(
                    self.owner,
                    "renderer.sync_no_target",
                    snapshot=snapshot,
                    extra={"overlay_available": overlay is not None, "main_available": main is not None},
                    ui_log=True,
                )
                return False

            # The overlay owns valid bounds, so clipping computation can no
            # longer collapse to an invalid range. The main fallback keeps bounds
            # disabled to avoid changing camera framing.
            try:
                if overlay_added:
                    overlay.ResetCameraClippingRange()
                # The overlay shares the main camera. Restore a clipping range
                # that contains the complete scene, not only the gizmo props.
                if main is not None:
                    main.ResetCameraClippingRange()
            except Exception:
                pass

            self._signature = signature
            self._base_center = _as_point(snapshot.center)
            self._mode = mode
            self.assembly = self.overlay_assembly if overlay_added else self.main_assembly
            self.set_interaction(
                active_handle=self._active_handle,
                pinned_handle=self._pinned_handle,
                grabbed_handle=self._grabbed_handle,
                render=False,
            )
            record_transform_gizmo_event(
                self.owner,
                "renderer.sync_success",
                snapshot=snapshot,
                extra={
                    "overlay_added": overlay_added,
                    "main_added": main_added,
                    "actors": len(self._all_actors),
                    "groups": len(self.groups),
                    "main_fallback_enabled": _main_fallback_enabled(),
                },
                ui_log=True,
            )
            if render:
                self._request_render("transform.gizmo.sync")
            return True
        except Exception as exc:
            self._remove_assembly()
            record_transform_gizmo_event(self.owner, "renderer.sync_exception", snapshot=snapshot, error=exc, ui_log=True)
            return False

    @staticmethod
    def _logical(handle: str | None) -> str | None:
        raw = (handle or "").lower().strip()
        if not raw:
            return None
        if raw[:1] in {"x", "y", "z"}:
            return raw[:1]
        return raw

    def set_interaction(
        self,
        *,
        active_handle: str | None,
        pinned_handle: str | None,
        grabbed_handle: str | None,
        render: bool = False,
    ) -> bool:
        self._active_handle = (active_handle or "").lower().strip() or None
        self._pinned_handle = (pinned_handle or "").lower().strip() or None
        self._grabbed_handle = (grabbed_handle or "").lower().strip() or None
        changed = False
        active_logical = self._logical(self._active_handle)
        pinned_logical = self._logical(self._pinned_handle)
        grabbed_logical = self._logical(self._grabbed_handle)
        for handle, group in self.groups.items():
            logical = self._logical(handle)
            is_grabbed = bool(self._grabbed_handle and (handle == self._grabbed_handle or logical == grabbed_logical))
            is_active = bool(self._active_handle and (handle == self._active_handle or logical == active_logical)) and not is_grabbed
            is_pinned = bool(self._pinned_handle and (handle == self._pinned_handle or logical == pinned_logical)) and not is_grabbed and not is_active
            if handle == "__center__":
                color = group.base_color
                opacity = 0.82
                scale = 1.0
            elif is_grabbed:
                color = _mix(group.base_color, (1.0, 0.95, 0.35), 0.72)
                opacity = 1.0
                scale = 1.50
            elif is_active:
                color = _mix(group.base_color, (1.0, 1.0, 1.0), 0.58)
                opacity = 1.0
                scale = 1.32
            elif is_pinned:
                color = _mix(group.base_color, (1.0, 1.0, 1.0), 0.28)
                opacity = 1.0
                scale = 1.16
            else:
                color = group.base_color
                opacity = 0.96
                scale = 1.0
            for visual in group.actors:
                try:
                    prop = visual.actor.GetProperty()
                    old = tuple(float(v) for v in prop.GetColor())
                    size_changed = False
                    target_size = max(1.0, float(visual.base_width) * float(scale))
                    if visual.primitive == "line":
                        try:
                            size_changed = abs(float(prop.GetLineWidth()) - target_size) > 1.0e-5
                            if size_changed:
                                prop.SetLineWidth(target_size)
                        except Exception:
                            pass
                    else:
                        try:
                            size_changed = abs(float(prop.GetPointSize()) - target_size) > 1.0e-5
                            if size_changed:
                                prop.SetPointSize(target_size)
                        except Exception:
                            pass
                    if max(abs(old[i] - color[i]) for i in range(3)) > 1.0e-5 or abs(float(prop.GetOpacity()) - opacity) > 1.0e-5:
                        prop.SetColor(*color)
                        prop.SetOpacity(opacity)
                        changed = True
                    changed = bool(changed or size_changed)
                except Exception:
                    continue
        if changed:
            record_transform_gizmo_event(
                self.owner,
                "renderer.interaction_changed",
                extra={"active": self._active_handle, "pinned": self._pinned_handle, "grabbed": self._grabbed_handle},
            )
        if changed and render:
            self._request_render("transform.gizmo.interaction")
        return changed

    def move_translate(self, *, offset: Point3, render: bool = False) -> bool:
        if self.assembly is None or self._mode != "translate":
            record_transform_gizmo_event(self.owner, "renderer.follow_skipped", extra={"reason": "missing_translate_assembly"})
            return False
        try:
            for assembly in (self.overlay_assembly, self.main_assembly):
                if assembly is not None:
                    assembly.SetPosition(float(offset[0]), float(offset[1]), float(offset[2]))
            record_transform_gizmo_event(self.owner, "renderer.follow", extra={"offset": tuple(float(v) for v in offset)})
            if render:
                self._request_render("transform.gizmo.follow")
            return True
        except Exception as exc:
            record_transform_gizmo_event(self.owner, "renderer.follow_failed", error=exc)
            return False



class TransformGizmoRenderer:
    """Select the foreground 2D backend, with a compatibility fallback.

    Real VTK builds use :class:`TransformGizmoOverlay2D`.  The old lightweight
    3D renderer is retained only for old VTK builds/headless fakes that do not
    expose ``vtkActor2D`` and ``vtkPolyDataMapper2D``.  Plan Tracer's generic
    Creator API is not involved in either backend.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self._backend = self._create_backend(owner)

    @staticmethod
    def _create_backend(owner: Any) -> Any:
        try:
            import vtk

            if hasattr(vtk, "vtkActor2D") and hasattr(vtk, "vtkPolyDataMapper2D"):
                from laserprog_studio.application.transform_gizmo_overlay_2d import TransformGizmoOverlay2D

                return TransformGizmoOverlay2D(owner)
        except Exception:
            pass
        return _LegacyTransformGizmoRenderer3D(owner)

    @property
    def screen_space_overlay(self) -> bool:
        return bool(getattr(self._backend, "screen_space_overlay", False))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._backend, name)

    def sync(self, snapshot: Any, *, render: bool = True) -> bool:
        return bool(self._backend.sync(snapshot, render=render))

    def update_geometry(self, snapshot: Any, *, render: bool = False) -> bool:
        return bool(self._backend.update_geometry(snapshot, render=render))

    def move_translate(self, *, offset: Point3, render: bool = False) -> bool:
        return bool(self._backend.move_translate(offset=offset, render=render))

    def set_interaction(self, *, active_handle: str | None, pinned_handle: str | None, grabbed_handle: str | None, render: bool = False) -> bool:
        return bool(self._backend.set_interaction(active_handle=active_handle, pinned_handle=pinned_handle, grabbed_handle=grabbed_handle, render=render))

    def clear(self, *, render: bool = False) -> None:
        self._backend.clear(render=render)

    def pick(self, qx: float, qy: float, *, generous: bool = False) -> str | None:
        fn = getattr(self._backend, "pick", None)
        return fn(qx, qy, generous=generous) if callable(fn) else None

    def drag_basis(self, handle: str, *, world_length: float | None = None) -> tuple[float, float, float, float] | None:
        fn = getattr(self._backend, "drag_basis", None)
        return fn(handle, world_length=world_length) if callable(fn) else None


def get_transform_gizmo_renderer(owner: Any) -> TransformGizmoRenderer:
    renderer = getattr(owner, "_transform_gizmo_renderer", None)
    if not isinstance(renderer, TransformGizmoRenderer):
        renderer = TransformGizmoRenderer(owner)
        setattr(owner, "_transform_gizmo_renderer", renderer)
        record_transform_gizmo_event(
            owner,
            "renderer.created",
            extra={"backend": "overlay2d" if renderer.screen_space_overlay else "legacy3d"},
        )
    return renderer


__all__ = ["TransformGizmoRenderer", "get_transform_gizmo_renderer"]

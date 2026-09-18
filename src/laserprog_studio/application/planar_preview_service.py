# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any

from ..app_context import AppContext
from ..planar_tools import PlanTraceAddKind, PlanarEditMode, PlanarPolygonDraft, VentPathDraft, plane_to_world, plan_trace_closed_regions, sample_plan_trace_element, sample_vent_centerline, triangulate_polygon
from ..planar_tools.vent_preview_snap import clean_polyline, corridor_bounds, corridor_outline_paths, rectangular_vent_bounds, rectangular_vent_material_outline_paths, rectangular_vent_outline_paths, variable_corridor_bounds, variable_corridor_outline_paths
from ..studio_log import log_exception
from .action_controller import WindowController
from .planar_gizmo_cache import PlanarGizmoActorCache


class PlanarPreviewService(WindowController):
    """PyVista preview actors for locked-plane sketch tools.

    This keeps rendering-only code out of ``PlanarToolController`` so the
    controller can focus on tool state, pointer edits and Apply workflows.
    """

    PREVIEW_ACTOR_NAMES = (
        "planar_tool_preview_lines",
        "planar_tool_preview_points",
        "planar_tool_preview_bounds_a",
        "planar_tool_preview_bounds_b",
        *tuple(f"planar_tool_preview_bounds_{i:02d}" for i in range(24)),
        "planar_tool_preview_selected",
        "planar_tool_preview_start_handle",
        "planar_tool_preview_end_handle",
        "planar_tool_preview_raw_pointer",
        "planar_tool_preview_raw_link",
        "planar_tool_preview_snap_hint",
        "planar_tool_preview_snap_raw",
        "planar_tool_preview_snap_link",
        "planar_tool_preview_curve_handles",
        "planar_tool_preview_selected_segment",
        "planar_tool_preview_fill",
        "planar_tool_preview_fill_box",
        "planar_tool_preview_close_hint",
        "plan_trace_staged_lines",
        "plan_trace_staged_points",
        "plan_trace_selected_element",
        "plan_trace_element_lines",
        "plan_trace_element_points",
        *tuple(f"plan_trace_region_fill_{i:02d}" for i in range(32)),
        *tuple(f"plan_trace_element_lines_{i:02d}" for i in range(64)),
        *tuple(f"plan_trace_element_points_{i:02d}" for i in range(64)),
    )

    # During drags we deliberately do not tear down region fills or every
    # reserved actor on each mouse event.  Only the handles/curves that
    # can actually move are refreshed.  This is a different rendering strategy
    # from the old "clear the whole sketch overlay then rebuild" path.
    INTERACTIVE_PREVIEW_ACTOR_NAMES = tuple(
        name for name in PREVIEW_ACTOR_NAMES
        if not name.startswith("plan_trace_region_fill_")
        and name not in {
            "planar_tool_preview_fill",
            "planar_tool_preview_fill_box",
            "plan_trace_element_lines",
            "plan_trace_element_points",
        }
    )

    @classmethod
    def create(cls, context: AppContext) -> "PlanarPreviewService":
        return cls(context)

    @property
    def state(self):
        return getattr(self.owner, "planar_tool_state", None)

    @property
    def _gizmo_cache(self) -> PlanarGizmoActorCache:
        cache = getattr(self, "_planar_gizmo_actor_cache", None)
        if cache is None:
            cache = PlanarGizmoActorCache()
            setattr(self, "_planar_gizmo_actor_cache", cache)
        return cache

    def _cached_gizmo_names(self) -> set[str]:
        try:
            return self._gizmo_cache.names()
        except Exception:
            return set()

    def clear_preview_actors(self, *, render: bool = False, interactive_only: bool = False) -> None:
        try:
            plotter = getattr(self.owner, "plotter", None)
            if plotter is None:
                return
            names = self.INTERACTIVE_PREVIEW_ACTOR_NAMES if bool(interactive_only) else self.PREVIEW_ACTOR_NAMES
            # Cached VTK glyph gizmos stay in the renderer.  Clearing the
            # preview only hides them, so the next mouse move can update the
            # existing vtkPoints instead of removing/recreating actors.
            gizmo_names = self._cached_gizmo_names()
            if gizmo_names:
                self._gizmo_cache.hide_all(gizmo_names.intersection(set(str(n) for n in names)))
            try:
                existing = tuple(getattr(plotter, "actors", {}) or {})
            except Exception:
                existing = ()
            halo_names = tuple(name for name in existing if str(name).endswith("__halo"))
            for name in tuple(names) + halo_names:
                if str(name) in gizmo_names:
                    continue
                try:
                    plotter.remove_actor(name, render=False)
                except Exception:
                    pass
            if render:
                plotter.render()
        except Exception:
            log_exception("planar_clear_preview_actors")

    def _polyline_actor(self, points: list[tuple[float, float, float]], *, name: str, color: str, closed: bool = False, width: float = 4.0) -> None:
        if len(points) < 2:
            return
        try:
            import numpy as np
            import pyvista as pv

            pts = list(points)
            edges = [(i, i + 1) for i in range(len(pts) - 1)]
            if closed and len(pts) > 2:
                edges.append((len(pts) - 1, 0))
            lines: list[int] = []
            for a, b in edges:
                lines.extend([2, int(a), int(b)])
            poly = pv.PolyData(np.asarray(pts, dtype=float))
            poly.lines = np.asarray(lines, dtype=np.int64)
            self.owner.plotter.add_mesh(poly, name=name, color=color, line_width=float(width), render_lines_as_tubes=True, pickable=False)
        except Exception:
            log_exception(f"planar_polyline_actor_{name}")

    def _surface_actor(
        self,
        points: list[tuple[float, float, float]],
        triangles: list[tuple[int, int, int]],
        *,
        name: str,
        color: str,
        opacity: float = 0.20,
    ) -> None:
        if len(points) < 3 or not triangles:
            return
        try:
            import numpy as np
            import pyvista as pv

            faces: list[int] = []
            for a, b, c in triangles:
                faces.extend([3, int(a), int(b), int(c)])
            poly = pv.PolyData(np.asarray(points, dtype=float), np.asarray(faces, dtype=np.int64))
            self.owner.plotter.add_mesh(poly, name=name, color=color, opacity=float(opacity), pickable=False)
        except Exception:
            log_exception(f"planar_surface_actor_{name}")

    def _camera_towards_vector(self) -> tuple[float, float, float]:
        try:
            cam = getattr(getattr(self.owner, "plotter", None), "camera", None)
            if cam is None:
                return (0.0, 0.0, 1.0)
            pos = tuple(float(v) for v in cam.GetPosition())
            focal = tuple(float(v) for v in cam.GetFocalPoint())
            vx, vy, vz = pos[0] - focal[0], pos[1] - focal[1], pos[2] - focal[2]
            norm = math.sqrt(vx * vx + vy * vy + vz * vz)
            if norm <= 1e-9 or not math.isfinite(norm):
                return (0.0, 0.0, 1.0)
            return (vx / norm, vy / norm, vz / norm)
        except Exception:
            return (0.0, 0.0, 1.0)

    def _point_world_radius(self, size: float) -> float:
        try:
            plotter = getattr(self.owner, "plotter", None)
            cam = getattr(plotter, "camera", None)
            scale = float(cam.GetParallelScale()) if cam is not None and hasattr(cam, "GetParallelScale") else 0.0
            height = float(plotter.height()) if plotter is not None and callable(getattr(plotter, "height", None)) else 0.0
            if math.isfinite(scale) and scale > 0.0 and height > 1.0:
                radius = max(float(size), 8.0) * scale / height
                return max(min(radius, scale / 28.0), max(scale / 900.0, 0.035))
            if math.isfinite(scale) and scale > 0.0:
                return max(min(scale / 90.0, 4.0), 0.10)
        except Exception:
            pass
        return max(float(size) * 0.045, 0.22)

    def _cached_point_sphere(self, radius: float, *, lightweight: bool = False):
        """Return a cached sphere template for old-style 3D edit handles.

        Pass99 used GPU point sprites.  They were fast, but they did not read
        as real CAD gizmos.  This restores the former mesh/glyph sphere style,
        while avoiding the worst cost: constructing a new sphere primitive for
        every actor on every mouse event.
        """
        try:
            import pyvista as pv

            cache = getattr(self, "_planar_point_sphere_cache", None)
            if cache is None:
                cache = {}
                setattr(self, "_planar_point_sphere_cache", cache)
            key = (round(float(radius), 4), bool(lightweight))
            sphere = cache.get(key)
            if sphere is None:
                # Lightweight drag keeps the old spherical look, but drops
                # tessellation enough to stay fluid while the pointer moves.
                sphere = pv.Sphere(
                    radius=float(radius),
                    theta_resolution=10 if lightweight else 18,
                    phi_resolution=6 if lightweight else 10,
                )
                cache[key] = sphere
            return sphere
        except Exception:
            log_exception("planar_cached_point_sphere")
            return None

    def _point_actor(
        self,
        points: list[tuple[float, float, float]],
        *,
        name: str,
        color: str,
        size: float = 12.0,
        lightweight: bool = False,
    ) -> None:
        if not points:
            try:
                self._gizmo_cache.hide_all([name])
            except Exception:
                pass
            return
        try:
            import numpy as np
            import pyvista as pv

            # Old gizmo look, new pipeline: actual small 3D spheres are kept as
            # persistent vtkGlyph3DMapper actors.  Only vtkPoints are modified
            # in place during drag.  The old CPU fallback below still contains
            # ``cloud.glyph(geom=sphere`` for environments without direct VTK.
            point_size = max(float(size), 30.0)
            radius = self._point_world_radius(point_size)
            tx, ty, tz = self._camera_towards_vector()
            lift = radius * 0.90
            lifted = [(float(x) + tx * lift, float(y) + ty * lift, float(z) + tz * lift) for x, y, z in points]
            used_cache = self._gizmo_cache.draw_points(
                getattr(self.owner, "plotter", None),
                name=name,
                points=lifted,
                color=color,
                radius=radius,
                lightweight=lightweight,
                ambient=0.58 if lightweight else 0.50,
                diffuse=0.64 if lightweight else 0.74,
                specular=0.12 if lightweight else 0.22,
            )
            if used_cache:
                return

            # Fallback: if vtkGlyph3DMapper is unavailable, keep the former
            # batched PyVista glyph path.  This is slower, but still functional.
            lifted_np = np.asarray(lifted, dtype=float)
            cloud = pv.PolyData(lifted_np)
            sphere = self._cached_point_sphere(radius, lightweight=lightweight)
            if sphere is not None:
                try:
                    mesh = cloud.glyph(geom=sphere, orient=False, scale=False)
                except Exception:
                    mesh = cloud
            else:
                mesh = cloud
            self.owner.plotter.add_mesh(
                mesh,
                name=name,
                color=color,
                point_size=max(point_size, 24.0),
                render_points_as_spheres=True,
                ambient=0.55 if lightweight else 0.48,
                diffuse=0.68 if lightweight else 0.76,
                specular=0.16 if lightweight else 0.22,
                smooth_shading=not bool(lightweight),
                pickable=False,
            )
        except Exception:
            log_exception(f"planar_point_actor_{name}")

    def _polylines_actor(self, polylines: list[list[tuple[float, float, float]]], *, name: str, color: str, width: float = 4.0) -> None:
        clean_lines = [line for line in polylines if len(line) >= 2]
        if not clean_lines:
            return
        try:
            import numpy as np
            import pyvista as pv

            pts: list[tuple[float, float, float]] = []
            lines: list[int] = []
            for line in clean_lines:
                start_idx = len(pts)
                pts.extend(line)
                lines.append(len(line))
                lines.extend(range(start_idx, start_idx + len(line)))
            poly = pv.PolyData(np.asarray(pts, dtype=float))
            poly.lines = np.asarray(lines, dtype=np.int64)
            self.owner.plotter.add_mesh(poly, name=name, color=color, line_width=float(width), render_lines_as_tubes=False, pickable=False)
        except Exception:
            log_exception(f"planar_polylines_actor_{name}")

    def _plan_points_for_draw(self, payload: Any) -> list[tuple[float, float]]:
        pending = getattr(self.state, "pending_plane_point", None)
        if isinstance(payload, PlanarPolygonDraft):
            pts = list(payload.points)
        elif isinstance(payload, VentPathDraft):
            pts = list(payload.waypoints)
        else:
            pts = []
        if pending is not None:
            pts.append((float(pending[0]), float(pending[1])))
        return pts


    def _plan_trace_elements_signature(self, payload: PlanarPolygonDraft) -> tuple:
        elements = []
        for element in getattr(payload, "elements", []) or []:
            try:
                kind = str(getattr(getattr(element, "kind", None), "value", getattr(element, "kind", "")))
                points = tuple((round(float(u), 5), round(float(v), 5)) for u, v in getattr(element, "points", ()) or ())
                elements.append((kind, points))
            except Exception:
                continue
        return tuple(elements)

    def _draw_plan_trace_elements(self, payload: PlanarPolygonDraft, *, color: str = "#64B5F6", lightweight: bool = False) -> None:
        """Draw independent 2D sketch elements added by the Plan tracer.

        The old implementation created one line actor and one glyph actor per
        element.  During a drag this quickly became the main source of lag.
        Static element lines and control points are now batched into two actors.
        """
        try:
            signature = self._plan_trace_elements_signature(payload)
            static_signature_attr = "_plan_trace_static_elements_signature"
            static_unchanged = bool(lightweight) and getattr(self, static_signature_attr, None) == signature
            if not static_unchanged:
                line_samples = 16 if lightweight else 48
                polylines: list[list[tuple[float, float, float]]] = []
                point_cloud: list[tuple[float, float, float]] = []
                for element in list(getattr(payload, "elements", []) or [])[:256]:
                    sampled = element.sampled_points(samples=line_samples)
                    if len(sampled) >= 2:
                        line = [plane_to_world(payload.plane, u, v) for u, v in sampled]
                        if element.kind is PlanTraceAddKind.CIRCLE and line:
                            line = line + [line[0]]
                        polylines.append(line)
                    for u, v in element.normalized_points():
                        point_cloud.append(plane_to_world(payload.plane, u, v))
                self._polylines_actor(polylines, name="plan_trace_element_lines", color=color, width=3.4 if lightweight else 4.2)
                self._point_actor(point_cloud, name="plan_trace_element_points", color="#90CAF9", size=34.0 if lightweight else 40.0, lightweight=lightweight)
                setattr(self, static_signature_attr, signature)

            selected_element = getattr(payload, "selected_element_index", None)
            if selected_element is not None and 0 <= int(selected_element) < len(getattr(payload, "elements", [])):
                element = payload.elements[int(selected_element)]
                sampled = element.sampled_points(samples=24 if lightweight else 72)
                if len(sampled) >= 2:
                    line = [plane_to_world(payload.plane, u, v) for u, v in sampled]
                    self._polyline_actor(
                        line,
                        name="plan_trace_selected_element",
                        color="#FFFFFF",
                        closed=element.kind is PlanTraceAddKind.CIRCLE,
                        width=5.0 if lightweight else 7.0,
                    )
        except Exception:
            log_exception("draw_plan_trace_elements")


    def _draw_plan_trace_regions(self, payload: PlanarPolygonDraft, *, samples: int = 48, max_regions: int = 32) -> None:
        try:
            regions = plan_trace_closed_regions(payload, samples=max(8, int(samples)))[:max(0, int(max_regions))]
            for idx, region in enumerate(regions):
                pts = list(region.points)
                if len(pts) < 3:
                    continue
                tris = triangulate_polygon(pts)
                self._surface_actor(
                    [plane_to_world(payload.plane, u, v) for u, v in pts],
                    tris,
                    name=f"plan_trace_region_fill_{idx:02d}",
                    color="#81C784",
                    opacity=0.18,
                )
        except Exception:
            log_exception("draw_plan_trace_regions")

    def _draw_plan_trace_staged_element(self, payload: PlanarPolygonDraft, *, lightweight: bool = False) -> None:
        try:
            pending = getattr(self.state, "pending_plane_point", None)
            staged = payload.staged_trace_points(pending=pending)
            if not staged:
                return
            sampled = sample_plan_trace_element(payload.add_kind, staged, samples=20 if lightweight else 64)
            if len(sampled) >= 2:
                self._polyline_actor(
                    [plane_to_world(payload.plane, u, v) for u, v in sampled],
                    name="plan_trace_staged_lines",
                    color="#29B6F6",
                    closed=payload.add_kind is PlanTraceAddKind.CIRCLE and len(staged) >= 2,
                    width=4.8,
                )
            self._point_actor(
                [plane_to_world(payload.plane, u, v) for u, v in staged],
                name="plan_trace_staged_points",
                color="#E1F5FE",
                size=40.0 if lightweight else 46.0,
                lightweight=lightweight,
            )
        except Exception:
            log_exception("draw_plan_trace_staged_element")

    def _draw_snap_hint(self, payload: Any) -> None:
        try:
            # Vent Generator owns its route feedback through the Plan2D Creator
            # API.  The legacy planar snap hint below is the source of the two
            # large PyVista sphere gizmos (green snapped point + white/grey raw
            # point) reported in the viewport.  They are valid for the old
            # Plan Tracer preview, but forbidden for Vent because snap feedback
            # must be line/guide based and must not add extra point handles.
            if isinstance(payload, VentPathDraft):
                return
            state = self.state
            if state is None:
                return
            label = str(getattr(state, "snap_preview_label", "") or "")
            snap = getattr(state, "snap_preview_plane_point", None)
            raw = getattr(state, "snap_preview_raw_plane", None)
            if not label or snap is None or not hasattr(payload, "plane"):
                return
            su, sv = float(snap[0]), float(snap[1])
            snap_world = plane_to_world(payload.plane, su, sv)
            self._point_actor([snap_world], name="planar_tool_preview_snap_hint", color="#76FF03", size=46.0)
            if raw is not None:
                ru, rv = float(raw[0]), float(raw[1])
                if math.hypot(ru - su, rv - sv) > 1e-5:
                    raw_world = plane_to_world(payload.plane, ru, rv)
                    self._point_actor([raw_world], name="planar_tool_preview_snap_raw", color="#B0BEC5", size=40.0)
                    self._polyline_actor([raw_world, snap_world], name="planar_tool_preview_snap_link", color="#76FF03", closed=False, width=2.2)
        except Exception:
            log_exception("draw_planar_snap_hint")

    def _vent_cumulative_lengths(self, points: list[tuple[float, float]]) -> list[float]:
        lengths = [0.0]
        for a, b in zip(points, points[1:]):
            lengths.append(lengths[-1] + math.hypot(float(b[0]) - float(a[0]), float(b[1]) - float(a[1])))
        return lengths

    def draw_planar_preview(self, *, render: bool = False, lightweight: bool = False) -> None:
        payload = getattr(self.state, "payload", None)
        self.clear_preview_actors(render=False, interactive_only=bool(lightweight))
        if payload is None:
            return
        try:
            plane_points = self._plan_points_for_draw(payload)
            world_points = [plane_to_world(payload.plane, u, v) for u, v in plane_points]
            if isinstance(payload, PlanarPolygonDraft):
                warning = str(getattr(self.state, "last_edit_warning", "") or "")
                line_color = "#FFB74D" if warning else "#FFD54F"
                point_color = "#FF8A65" if warning else "#FF7043"
                pending = getattr(self.state, "pending_plane_point", None)
                if pending is not None and not bool(payload.closed):
                    draw_points = list(payload.points) + [(float(pending[0]), float(pending[1]))]
                    offsets = payload.curve_offsets_for_sampling(closed=False) + [0.0]
                    smooth = sample_vent_centerline(draw_points, samples_per_corner=6 if lightweight else 18, segment_curve_offsets=offsets, default_curve_offset=0.0)
                elif hasattr(payload, "sampled_boundary_points"):
                    smooth = payload.sampled_boundary_points(samples_per_segment=8 if lightweight else 24, include_closure=False)
                else:
                    smooth = list(payload.points)
                smooth_world = [plane_to_world(payload.plane, u, v) for u, v in smooth]
                self._polyline_actor(smooth_world, name="planar_tool_preview_lines", color=line_color, closed=bool(payload.closed), width=4.5)
                self._point_actor(world_points, name="planar_tool_preview_points", color=point_color, size=38.0 if lightweight else 42.0, lightweight=lightweight)
                self._draw_plan_selected_segment(payload, color="#FFFFFF")
                if not lightweight:
                    self._draw_plan_trace_regions(payload)
                self._draw_plan_trace_elements(payload, lightweight=lightweight)
                self._draw_plan_trace_staged_element(payload, lightweight=lightweight)
                if len(payload.points) >= 1:
                    self._point_actor([plane_to_world(payload.plane, payload.points[0][0], payload.points[0][1])], name="planar_tool_preview_start_handle", color="#69F0AE", size=44.0 if lightweight else 48.0, lightweight=lightweight)
                if len(payload.points) >= 2:
                    self._point_actor([plane_to_world(payload.plane, payload.points[-1][0], payload.points[-1][1])], name="planar_tool_preview_end_handle", color="#CE93D8", size=42.0 if lightweight else 46.0, lightweight=lightweight)
                if bool(payload.closed) and len(smooth) >= 3 and not lightweight:
                    tris = triangulate_polygon(smooth)
                    self._surface_actor([plane_to_world(payload.plane, u, v) for u, v in smooth], tris, name="planar_tool_preview_fill", color="#AED581", opacity=0.23)
                elif len(payload.points) >= 3 and not bool(payload.closed):
                    # A subtle closing helper makes the double-click target obvious.
                    hint = [plane_to_world(payload.plane, payload.points[-1][0], payload.points[-1][1]), plane_to_world(payload.plane, payload.points[0][0], payload.points[0][1])]
                    self._polyline_actor(hint, name="planar_tool_preview_close_hint", color="#A5D6A7", closed=False, width=1.5)
                raw = getattr(self.state, "last_pointer_raw_plane", None)
                if warning and raw is not None:
                    raw_world = plane_to_world(payload.plane, float(raw[0]), float(raw[1]))
                    self._point_actor([raw_world], name="planar_tool_preview_raw_pointer", color="#FF5252", size=32.0, lightweight=lightweight)
                    if getattr(self.state, "pending_plane_point", None) is not None:
                        pu, pv = self.state.pending_plane_point
                        self._polyline_actor([plane_to_world(payload.plane, pu, pv), raw_world], name="planar_tool_preview_raw_link", color="#FF5252", closed=False, width=1.5)
            elif isinstance(payload, VentPathDraft):
                warning = str(getattr(self.state, "last_edit_warning", "") or "")
                # Vent editable route UI is strictly owned by the public Plan2D
                # Creator API, exactly like Plan Tracer.  This legacy PyVista
                # preview layer now draws only the non-interactive duct footprint
                # on full refresh; it never draws points, handles or route lines.
                if not lightweight:
                    smooth, flare_scales = payload.sampled_centerline_with_flare_scales(samples_per_segment=28)
                    boundary_color = "#DC2626" if warning else "#0EA5E9"
                    self._draw_vent_boundaries(payload, smooth, flare_scales=flare_scales, color=boundary_color)
                    if bool(getattr(payload, "fill_area", False)):
                        self._draw_vent_fill_box(payload, smooth, flare_scales=flare_scales, color="#CE93D8")
            self._draw_snap_hint(payload)
            selected = getattr(payload, "selected_index", None)
            selected_point = None
            if selected is not None:
                source = getattr(payload, "points", getattr(payload, "waypoints", []))
                if 0 <= int(selected) < len(source):
                    selected_point = source[int(selected)]
            elif isinstance(payload, PlanarPolygonDraft):
                eidx = getattr(payload, "selected_element_index", None)
                pidx = getattr(payload, "selected_element_point_index", None)
                if eidx is not None and pidx is not None and 0 <= int(eidx) < len(payload.elements):
                    element = payload.elements[int(eidx)]
                    if 0 <= int(pidx) < len(element.points):
                        selected_point = element.points[int(pidx)]
            if selected_point is not None and not isinstance(payload, VentPathDraft):
                u, v = selected_point
                self._point_actor([plane_to_world(payload.plane, u, v)], name="planar_tool_preview_selected", color="#FFFFFF", size=48.0 if lightweight else 52.0, lightweight=lightweight)
            if render:
                self.owner.plotter.render()
        except Exception:
            log_exception("draw_planar_preview")

    def _draw_plan_selected_segment(self, payload: PlanarPolygonDraft, *, color: str = "#FFFFFF") -> None:
        try:
            segment = payload.selected_segment_index() if hasattr(payload, "selected_segment_index") else None
            if segment is None:
                return
            points = list(payload.points)
            if len(points) < 2:
                return
            i = int(segment)
            if i < len(points) - 1:
                a, b = points[i], points[i + 1]
            elif bool(payload.closed) and len(points) >= 3 and i == len(points) - 1:
                a, b = points[-1], points[0]
            else:
                return
            offsets = payload.curve_offsets_for_sampling() if hasattr(payload, "curve_offsets_for_sampling") else []
            offset = float(offsets[i]) if i < len(offsets) else 0.0
            curve = sample_vent_centerline([a, b], samples_per_corner=24, segment_curve_offsets=[offset], default_curve_offset=0.0)
            self._polyline_actor([plane_to_world(payload.plane, u, v) for u, v in curve], name="planar_tool_preview_selected_segment", color=color, closed=False, width=6.0)
        except Exception:
            log_exception("draw_plan_selected_segment")

    def _vent_preview_half_width_profiles(self, payload: VentPathDraft, centerline: list[tuple[float, float]], *, flare_scales: list[float] | None = None) -> tuple[list[float], list[float]]:
        width, _height = payload.section_dimensions()
        wall = max(float(payload.wall_thickness), 0.0)
        scales = list(flare_scales or [])
        if len(scales) != len(centerline):
            _points, scales = payload.sampled_centerline_with_flare_scales(samples_per_segment=24)
        if len(scales) != len(centerline):
            scales = [scales[min(i, len(scales) - 1)] if scales else 1.0 for i in range(len(centerline))]
        inner_halves: list[float] = []
        outer_halves: list[float] = []
        for scale in scales:
            inner = max(float(width) * float(scale) * 0.5, 1e-9)
            inner_halves.append(inner)
            outer_halves.append(inner + wall)
        return inner_halves, outer_halves


    def _draw_vent_boundaries(self, payload: VentPathDraft, centerline: list[tuple[float, float]], *, flare_scales: list[float] | None = None, color: str = "#81D4FA") -> None:
        if len(centerline) < 2:
            return
        try:
            # Draw the exact material footprint used by Apply.  This shows open
            # inlet/outlet cuts and avoids hiding Fill-area caps/holes behind
            # separate outer/inner guide rings.
            material_rings = rectangular_vent_material_outline_paths(payload, centerline, fill_area=bool(getattr(payload, "fill_area", False)))
            if material_rings:
                for i, ring in enumerate(material_rings[:24]):
                    self._polyline_actor(
                        [plane_to_world(payload.plane, u, v) for u, v in ring],
                        name=f"planar_tool_preview_bounds_{i:02d}",
                        color=color if i == 0 else "#B3E5FC",
                        closed=True,
                        width=2.5 if i == 0 else 1.5,
                    )
                return
            outer_rings, inner_rings = rectangular_vent_outline_paths(payload, centerline)
            if outer_rings:
                self._polyline_actor([plane_to_world(payload.plane, u, v) for u, v in outer_rings[0]], name="planar_tool_preview_bounds_a", color=color, closed=True, width=2.5)
            if inner_rings:
                self._polyline_actor([plane_to_world(payload.plane, u, v) for u, v in inner_rings[0]], name="planar_tool_preview_bounds_b", color="#B3E5FC", closed=True, width=1.5)
        except Exception:
            log_exception("draw_vent_boundaries")


    def _draw_vent_selected_segment(self, payload: VentPathDraft, *, color: str = "#FFFFFF") -> None:
        try:
            segment = payload.selected_segment_index()
            if segment is None or not (0 <= int(segment) < len(payload.waypoints) - 1):
                return
            a = payload.waypoints[int(segment)]
            b = payload.waypoints[int(segment) + 1]
            offsets = payload.curve_offsets_for_sampling()
            offset = float(offsets[int(segment)]) if int(segment) < len(offsets) else 0.0
            curve = sample_vent_centerline([a, b], samples_per_corner=18, segment_curve_offsets=[offset])
            self._polyline_actor([plane_to_world(payload.plane, u, v) for u, v in curve], name="planar_tool_preview_selected_segment", color=color, closed=False, width=6.0)
        except Exception:
            log_exception("draw_vent_selected_segment")

    def _draw_vent_fill_box(self, payload: VentPathDraft, centerline: list[tuple[float, float]], *, flare_scales: list[float] | None = None, color: str = "#CE93D8") -> None:
        if len(centerline) < 2:
            return
        try:
            bounds = rectangular_vent_bounds(payload, centerline)
            if bounds is None:
                return
            min_u, min_v, max_u, max_v = bounds
            box = [(min_u, min_v), (max_u, min_v), (max_u, max_v), (min_u, max_v)]
            self._polyline_actor([plane_to_world(payload.plane, u, v) for u, v in box], name="planar_tool_preview_fill_box", color=color, closed=True, width=2.5)
        except Exception:
            log_exception("draw_vent_fill_box")

# -*- coding: utf-8 -*-
from __future__ import annotations

from .planar_tool_deps import *  # noqa: F401,F403

class PlanarToolSnapLayer:

    def snap_config_from_owner(self) -> PlanarToolConfig:

        w = self.owner
        payload = getattr(self.state, "payload", None)
        base = PlanarToolConfig(
            grid_snap_enabled=bool(getattr(w, "grid_snap_enabled", False)),
            smart_snap_enabled=bool(getattr(w, "smart_snap_enabled", True)),
            grid_step=max(float(getattr(w, "grid_snap_step", 5.0)), 0.01),
            smart_snap_tolerance=max(float(getattr(w, "smart_snap_tolerance", 2.0)), 0.01),
        )
        try:
            snap_settings = getattr(w, "_snap_settings", None)
            if callable(snap_settings):
                settings = snap_settings()
                base = PlanarToolConfig(
                    grid_snap_enabled=bool(settings.grid_enabled),
                    smart_snap_enabled=bool(settings.smart_enabled),
                    grid_step=max(float(settings.grid_step), 0.01),
                    smart_snap_tolerance=max(float(settings.smart_tolerance), 0.01),
                )
        except Exception:
            pass
        if isinstance(payload, PlanarPolygonDraft):
            # PLN has its own snap buttons.  The global transform snap values are
            # still used as defaults, but sketching must be controllable without
            # opening the transform box.
            smart_enabled = bool(getattr(w, "plan_trace_smart_snap_enabled", True))
            grid_enabled = bool(getattr(w, "plan_trace_grid_snap_enabled", False))
            try:
                grid_widget = getattr(w, "plan_trace_grid_step", None)
                grid_step = float(grid_widget.value()) if grid_widget is not None else float(base.grid_step)
            except Exception:
                grid_step = float(base.grid_step)
            sketch_grid = max(float(grid_step), 0.01)
            return PlanarToolConfig(
                grid_snap_enabled=grid_enabled,
                smart_snap_enabled=smart_enabled,
                grid_step=sketch_grid,
                # Plan tracing works on explicit visible handles.  A slightly
                # larger tolerance makes endpoint reuse feel like a CAD sketcher
                # instead of pixel hunting, while smart hits still win over grid.
                smart_snap_tolerance=max(float(base.smart_snap_tolerance), min(sketch_grid * 0.8, 8.0), 5.0),
                smart_snap_priority=True,
            )
        if isinstance(payload, VentPathDraft):
            settings = getattr(w, "vent_generator_settings", None)
            values = settings if isinstance(settings, dict) else {}
            try:
                smart_enabled = bool(values.get("smart_snap", True))
            except Exception:
                smart_enabled = True
            try:
                from laserprog_studio.tooling.vent_generator.snap import VENT_ROUTE_SNAP_TOLERANCE

                tolerance = float(VENT_ROUTE_SNAP_TOLERANCE)
            except Exception:
                tolerance = 1.5
            # Vent snapping is routing-safe: no direct route point/segment snap,
            # no generated duct-offset geometry.  Existing waypoints are only
            # alignment guides; real attraction can come from projected scene data.
            # Keep this radius intentionally small so smart snap does not prevent
            # free routing between nearby scene/guide features.
            return PlanarToolConfig(
                grid_snap_enabled=False,
                smart_snap_enabled=smart_enabled,
                grid_step=1.0,
                smart_snap_tolerance=max(float(tolerance), 0.01),
                smart_snap_priority=True,
            )
        return base

    def _own_payload_anchor_points(self, *, include_active: bool = True) -> tuple[tuple[float, float], ...]:
        payload = getattr(self.state, "payload", None)
        if isinstance(payload, PlanarPolygonDraft):
            try:
                return tuple(payload.snap_anchor_points(samples_per_segment=8))
            except Exception:
                return tuple((float(u), float(v)) for u, v in getattr(payload, "points", []) or [])
        if isinstance(payload, VentPathDraft):
            # Vent never exposes its own route as direct point snap targets.
            # Waypoints are consumed by the Vent-specific resolver as alignment
            # guides only, which avoids collapsing the route onto itself.
            return ()
        return ()

    def payload_anchor_points(self, *, include_pending: bool = True) -> tuple[tuple[float, float], ...]:
        state = self.state
        payload = getattr(state, "payload", None)
        pending = getattr(state, "pending_plane_point", None)
        if state is not None and bool(getattr(state, "pointer_drag_active", False)) and getattr(state, "drag_snap_anchor_cache", None) is not None:
            points = tuple(state.drag_snap_anchor_cache or ())
        elif isinstance(payload, PlanarPolygonDraft):
            self._ensure_payload_snap_cache(payload)
            points = tuple(getattr(state, "payload_snap_anchor_cache", ()) or ()) + tuple(getattr(state, "scene_snap_anchor_cache", ()) or ())
        elif isinstance(payload, VentPathDraft):
            points = tuple(getattr(state, "scene_snap_anchor_cache", ()) or ())
        else:
            points = ()
        if bool(include_pending) and pending is not None:
            return points + ((float(pending[0]), float(pending[1])),)
        return points

    def payload_edge_segments(self) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
        state = self.state
        payload = getattr(state, "payload", None)
        if state is not None and bool(getattr(state, "pointer_drag_active", False)) and getattr(state, "drag_snap_edge_cache", None) is not None:
            return tuple(state.drag_snap_edge_cache or ())
        if isinstance(payload, PlanarPolygonDraft):
            return tuple(getattr(state, "scene_snap_edge_cache", ()) or ())
        if isinstance(payload, VentPathDraft):
            return tuple(getattr(state, "scene_snap_edge_cache", ()) or ())
        return ()


    def _round_snap_value(self, value: float) -> int:
        try:
            return int(round(float(value) * 100000.0))
        except Exception:
            return 0

    def _payload_snap_signature(self, payload: Any) -> tuple[Any, ...]:
        """Cheap geometry signature for the local sketch snap cache.

        Do not call sampled/snap collection code here: this method runs before
        deciding whether the expensive local snap anchors must be rebuilt.  Raw
        control points and curve parameters are enough to invalidate the cache
        exactly when the useful snap geometry can change.
        """
        if isinstance(payload, PlanarPolygonDraft):
            points = tuple((self._round_snap_value(u), self._round_snap_value(v)) for u, v in getattr(payload, "points", ()) or ())
            active = tuple((self._round_snap_value(u), self._round_snap_value(v)) for u, v in getattr(payload, "active_element_points", ()) or ())
            elements: list[tuple[Any, ...]] = []
            for element in getattr(payload, "elements", ()) or ():
                try:
                    kind = str(getattr(getattr(element, "kind", None), "value", getattr(element, "kind", "")))
                    pts = tuple((self._round_snap_value(u), self._round_snap_value(v)) for u, v in getattr(element, "points", ()) or ())
                    elements.append((kind, pts))
                except Exception:
                    continue
            curves = (
                tuple(self._round_snap_value(v) for v in getattr(payload, "segment_curve_offsets", ()) or ()),
                tuple(self._round_snap_value(v) for v in getattr(payload, "segment_curve_radii", ()) or ()),
                tuple(self._round_snap_value(v) for v in getattr(payload, "segment_curve_strengths", ()) or ()),
            )
            scene_sig = (
                len(getattr(self.state, "scene_snap_anchor_cache", ()) or ()),
                len(getattr(self.state, "scene_snap_edge_cache", ()) or ()),
                id(getattr(self.state, "scene_snap_compiled_cache", None)),
            )
            return ("pln", id(payload), bool(getattr(payload, "closed", False)), str(getattr(payload, "add_kind", "")), points, active, tuple(elements), curves, scene_sig)
        if isinstance(payload, VentPathDraft):
            waypoints = tuple((self._round_snap_value(u), self._round_snap_value(v)) for u, v in getattr(payload, "waypoints", ()) or ())
            scene_sig = (
                len(getattr(self.state, "scene_snap_anchor_cache", ()) or ()),
                len(getattr(self.state, "scene_snap_edge_cache", ()) or ()),
                id(getattr(self.state, "scene_snap_compiled_cache", None)),
            )
            return ("evt", id(payload), waypoints, scene_sig)
        return ("none", id(payload))

    def _invalidate_payload_snap_cache(self) -> None:
        state = self.state
        if state is None:
            return
        state.payload_snap_signature = None
        state.payload_snap_anchor_cache = ()
        state.payload_snap_compiled_cache = None

    def _ensure_payload_snap_cache(self, payload: Any):
        state = self.state
        if state is None:
            return None
        signature = self._payload_snap_signature(payload)
        cached = getattr(state, "payload_snap_compiled_cache", None)
        if getattr(state, "payload_snap_signature", None) == signature and cached is not None:
            return cached
        local_anchors: tuple[tuple[float, float], ...] = ()
        if isinstance(payload, PlanarPolygonDraft):
            try:
                local_anchors = tuple(payload.snap_anchor_points(samples_per_segment=8))
            except Exception:
                local_anchors = self._own_payload_anchor_points()
        elif isinstance(payload, VentPathDraft):
            local_anchors = ()
        scene_anchors = tuple(getattr(state, "scene_snap_anchor_cache", ()) or ())
        scene_edges = tuple(getattr(state, "scene_snap_edge_cache", ()) or ())
        compiled = compile_planar_snap_cache(scene_anchors + local_anchors, scene_edges)
        state.payload_snap_signature = signature
        state.payload_snap_anchor_cache = local_anchors
        state.payload_snap_compiled_cache = compiled
        return compiled

    def _scene_planar_snap_cache(self, plane: LockedPlaneSpec, *, max_points: int = 360, max_edges: int = 900) -> tuple[tuple[tuple[float, float], ...], tuple[tuple[tuple[float, float], tuple[float, float]], ...]]:
        """Return cached smart-snap anchors/edges projected from scene objects.

        Building this cache used to happen implicitly on every pointer move.  A
        sizeable mesh therefore made dragging feel sticky.  The cache is rebuilt
        when the Plan tracer starts and then reused during hover/drag.
        """
        anchors: list[tuple[float, float]] = []
        edges: list[tuple[tuple[float, float], tuple[float, float]]] = []
        try:
            if callable(getattr(self.owner, "committed_meshes", None)):
                meshes = self.owner.committed_meshes()
            elif callable(getattr(self.owner, "current_meshes", None)):
                meshes = self.owner.current_meshes()
            else:
                meshes = []
        except Exception:
            meshes = []
        seen_points: set[tuple[int, int]] = set()
        seen_edges: set[tuple[tuple[int, int], tuple[int, int]]] = set()

        def project(world):
            try:
                u, v = world_to_plane(plane, tuple(float(x) for x in world))
                return (float(u), float(v))
            except Exception:
                return None

        def point_key(point: tuple[float, float]) -> tuple[int, int]:
            return (round(float(point[0]) * 10000), round(float(point[1]) * 10000))

        def add_anchor(world) -> tuple[float, float] | None:
            point = project(world)
            if point is None:
                return None
            key = point_key(point)
            if key not in seen_points:
                seen_points.add(key)
                if len(anchors) < int(max_points):
                    anchors.append(point)
            return point

        def add_edge(a_world, b_world) -> None:
            if len(edges) >= int(max_edges):
                return
            a = project(a_world)
            b = project(b_world)
            if a is None or b is None:
                return
            if math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1])) <= 1e-6:
                return
            ka, kb = point_key(a), point_key(b)
            key = tuple(sorted((ka, kb)))  # type: ignore[assignment]
            if key in seen_edges:
                return
            seen_edges.add(key)
            edges.append((a, b))

        for mesh in meshes:
            vertices = list(getattr(mesh, "vertices", []) or [])
            if not vertices:
                continue
            step = max(1, int(len(vertices) / max(1, max_points // 2)))
            for vertex in vertices[::step]:
                add_anchor(vertex)
            triangles = list(getattr(mesh, "triangles", []) or [])
            tri_step = max(1, int(len(triangles) / max(1, max_edges // 3)))
            for tri in triangles[::tri_step]:
                try:
                    ia, ib, ic = int(tri[0]), int(tri[1]), int(tri[2])
                    if min(ia, ib, ic) < 0 or max(ia, ib, ic) >= len(vertices):
                        continue
                    add_edge(vertices[ia], vertices[ib])
                    add_edge(vertices[ib], vertices[ic])
                    add_edge(vertices[ic], vertices[ia])
                except Exception:
                    continue
            try:
                xs = [float(v[0]) for v in vertices]; ys = [float(v[1]) for v in vertices]; zs = [float(v[2]) for v in vertices]
                corners = [(x, y, z) for x in (min(xs), max(xs)) for y in (min(ys), max(ys)) for z in (min(zs), max(zs))]
                for corner in corners:
                    add_anchor(corner)
                for i, j in ((0,1),(0,2),(0,4),(3,1),(3,2),(3,7),(5,1),(5,4),(5,7),(6,2),(6,4),(6,7)):
                    add_edge(corners[i], corners[j])
            except Exception:
                pass
        return tuple(anchors), tuple(edges)

    def _rebuild_planar_scene_snap_cache_for_payload(self, payload_type: type | tuple[type, ...]) -> None:
        state = self.state
        payload = getattr(state, "payload", None)
        if state is None or not isinstance(payload, payload_type) or not hasattr(payload, "plane"):
            return
        anchors, edges = self._scene_planar_snap_cache(payload.plane)
        state.scene_snap_anchor_cache = anchors
        state.scene_snap_edge_cache = edges
        state.scene_snap_compiled_cache = compile_planar_snap_cache(anchors, edges)
        self._invalidate_payload_snap_cache()
        state.drag_snap_anchor_cache = None
        state.drag_snap_edge_cache = None
        state.drag_snap_compiled_cache = None

    def rebuild_plan_trace_scene_snap_cache(self) -> None:
        self._rebuild_planar_scene_snap_cache_for_payload(PlanarPolygonDraft)

    def rebuild_vent_scene_snap_cache(self) -> None:
        self._rebuild_planar_scene_snap_cache_for_payload(VentPathDraft)


    def _compiled_payload_snap_cache(self, *, include_pending_anchor: bool = False):
        state = self.state
        if state is None:
            return None, (), ()
        pending = getattr(state, "pending_plane_point", None)
        pending_points = ((float(pending[0]), float(pending[1])),) if bool(include_pending_anchor) and pending is not None else ()
        if bool(getattr(state, "pointer_drag_active", False)) and getattr(state, "drag_snap_compiled_cache", None) is not None:
            return getattr(state, "drag_snap_compiled_cache", None), pending_points, ()
        payload = getattr(state, "payload", None)
        if isinstance(payload, PlanarPolygonDraft):
            # Scene + local sketch geometry are compiled together and reused for
            # every mouse move.  This keeps distant U/V alignment guides intact
            # without resampling rectangles/circles/arcs on each event.
            return self._ensure_payload_snap_cache(payload), pending_points, ()
        if isinstance(payload, VentPathDraft):
            return self._ensure_payload_snap_cache(payload), pending_points, ()
        return None, pending_points, ()

    def display_ray_from_qt_pos(self, qx: float, qy: float):

        try:
            plotter = getattr(self.owner, "plotter", None)
            renderer = getattr(plotter, "renderer", None)
            if renderer is None:
                return None
            h = float(plotter.height()) if callable(getattr(plotter, "height", None)) else 0.0
            vx = float(qx)
            vy = h - float(qy)
            near = self.owner._display_to_world_at_depth(vx, vy, 0.0)
            far = self.owner._display_to_world_at_depth(vx, vy, 1.0)
            return make_ray(tuple(float(v) for v in near), tuple(float(v) for v in far))
        except Exception:
            log_exception("planar_display_ray_from_qt_pos")
            return None

    def resolve_qt_pos_on_active_plane(
        self,
        qx: float,
        qy: float,
        *,
        snap: bool = True,
        include_pending_anchor: bool = False,
        record_snap_preview: bool = True,
    ) -> PlanarPointerResult | None:

        plane = getattr(self.state, "locked_plane", None)
        if plane is None:
            return None
        ray = self.display_ray_from_qt_pos(qx, qy)
        if ray is None:
            return None
        config = self.snap_config_from_owner() if snap else PlanarToolConfig(grid_snap_enabled=False, smart_snap_enabled=False)
        raw_world = intersect_ray_with_locked_plane(ray, plane)
        if raw_world is None:
            return None
        raw_plane = world_to_plane(plane, raw_world)
        payload = getattr(self.state, "payload", None)
        if isinstance(payload, VentPathDraft) and snap:
            try:
                from laserprog_studio.tooling.vent_generator.snap import snap_vent_route_point

                selected = getattr(payload, "selected_index", None)
                exclude_indices: tuple[int, ...] = ()
                if bool(getattr(self.state, "pointer_drag_active", False)) and getattr(self.state, "pointer_drag_mode", None) == "mod" and selected is not None:
                    try:
                        exclude_indices = (int(selected),)
                    except Exception:
                        exclude_indices = ()
                scene_points = tuple(getattr(self.state, "scene_snap_anchor_cache", ()) or ())
                scene_segments = tuple(getattr(self.state, "scene_snap_edge_cache", ()) or ())
                if bool(config.smart_snap_enabled) and not (scene_points or scene_segments):
                    self.rebuild_vent_scene_snap_cache()
                    scene_points = tuple(getattr(self.state, "scene_snap_anchor_cache", ()) or ())
                    scene_segments = tuple(getattr(self.state, "scene_snap_edge_cache", ()) or ())
                snap_result = snap_vent_route_point(
                    payload,
                    raw_plane,
                    enabled=bool(config.smart_snap_enabled),
                    exclude_indices=exclude_indices,
                    tolerance=float(config.smart_snap_tolerance),
                    scene_points=scene_points,
                    scene_segments=scene_segments,
                )
                snapped_world = plane_to_world(plane, snap_result.point[0], snap_result.point[1])
                result = PlanarPointerResult(
                    screen=(float(qx), float(qy)),
                    raw_world=raw_world,
                    raw_plane=raw_plane,
                    snapped_world=snapped_world,
                    snapped_plane=snap_result.point,
                    snap_label=str(snap_result.label or "") if bool(snap_result.snapped) else None,
                )
                if record_snap_preview:
                    self._record_planar_snap_preview(result)
                return result
            except Exception:
                pass
        compiled_cache, extra_anchor_points, extra_edge_segments = self._compiled_payload_snap_cache(include_pending_anchor=bool(include_pending_anchor))
        result = resolve_pointer_on_plane(
            (float(qx), float(qy)),
            ray,
            plane,
            config,
            anchor_points=extra_anchor_points,
            edge_segments=extra_edge_segments,
            compiled_cache=compiled_cache,
        )
        if record_snap_preview:
            self._record_planar_snap_preview(result)
        return result



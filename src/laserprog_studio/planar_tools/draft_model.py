# -*- coding: utf-8 -*-
from __future__ import annotations
import math
from dataclasses import dataclass, field
from .contracts import LockedPlaneSpec, PlanarEditMode, Vec2, Vec3
from .plan_trace_elements import PlanTraceAddKind, PlanTraceElement, install_plan_trace_extensions
from .orientation import plane_to_world, world_to_plane
from .polygon_constraints import clamp_polygon_point_candidate, polygon_close_is_valid, validate_open_polygon_trace
from .validation import distance2d, validate_polygon_for_extrusion
from .vent_path_geometry import sample_vent_centerline, segment_control_point
def _sign(value: float) -> float:
    if float(value) > 1e-9:
        return 1.0
    if float(value) < -1e-9:
        return -1.0
    return 0.0
def _dedupe_open(points: list[Vec2], *, tolerance: float = 1e-7) -> list[Vec2]:
    out: list[Vec2] = []
    for p in points:
        q = (float(p[0]), float(p[1]))
        if not out or distance2d(out[-1], q) > float(tolerance):
            out.append(q)
    return out
@dataclass(slots=True)
class PlanarPolygonDraft:
    """UI-independent model for the Plan tracer tool.
    The draft remains point-based in ADD, but MOD can bend each segment with a
    simple radius/force pair.  Curved boundaries are sampled only for preview,
    validation and final extrusion; user waypoints stay stable and easy to edit.
    """
    plane: LockedPlaneSpec
    extrusion_depth: float = 10.0
    mode: PlanarEditMode = PlanarEditMode.MOD; add_kind: PlanTraceAddKind = PlanTraceAddKind.POLYGON
    points: list[Vec2] = field(default_factory=list); elements: list[PlanTraceElement] = field(default_factory=list); active_element_points: list[Vec2] = field(default_factory=list)
    closed: bool = False
    selected_index: int | None = None; selected_element_index: int | None = None; selected_element_point_index: int | None = None
    curve_radius: float = 0.0
    curve_strength: float = 0.0; join_tolerance: float = 0.35
    segment_curve_offsets: list[float] = field(default_factory=list)
    segment_curve_radii: list[float] = field(default_factory=list)
    segment_curve_strengths: list[float] = field(default_factory=list)
    def set_mode(self, mode: PlanarEditMode | str) -> None:
        new_mode = mode if isinstance(mode, PlanarEditMode) else PlanarEditMode(str(mode))
        if new_mode is PlanarEditMode.RST:
            self.reset()
            self.mode = PlanarEditMode.ADD
            return
        if new_mode is not self.mode:
            self.clear_selection()
        self.mode = new_mode
    def clear_selection(self) -> None:
        self.selected_index = None
    def reset(self) -> None:
        self.points.clear()
        self.closed = False
        self.segment_curve_offsets.clear()
        self.segment_curve_radii.clear()
        self.segment_curve_strengths.clear()
        self.curve_radius = 0.0
        self.curve_strength = 0.0
        self.clear_selection()
    def _segment_count(self, *, closed: bool | None = None) -> int:
        is_closed = bool(self.closed if closed is None else closed)
        if is_closed:
            return len(self.points) if len(self.points) >= 3 else 0
        return max(len(self.points) - 1, 0)
    def _sync_curve_offsets(self) -> None:
        count = self._segment_count()
        for attr in ("segment_curve_offsets", "segment_curve_radii", "segment_curve_strengths"):
            values = getattr(self, attr, None)
            if values is None:
                setattr(self, attr, [])
                values = getattr(self, attr)
            if len(values) < count:
                values.extend([0.0] * (count - len(values)))
            elif len(values) > count:
                del values[count:]
        for i in range(count):
            offset = float(self.segment_curve_offsets[i])
            radius = float(self.segment_curve_radii[i])
            strength = float(self.segment_curve_strengths[i])
            if abs(offset) > 1e-9 and radius <= 1e-9 and abs(strength) <= 1e-9:
                self.segment_curve_radii[i] = abs(offset)
                self.segment_curve_strengths[i] = _sign(offset)
            else:
                r = max(float(radius), 0.0)
                s = max(-1.0, min(1.0, float(strength)))
                self.segment_curve_radii[i] = r
                self.segment_curve_strengths[i] = s
                self.segment_curve_offsets[i] = r * s
    def curve_offsets_for_sampling(self, *, closed: bool | None = None) -> list[float]:
        self._sync_curve_offsets()
        count = self._segment_count(closed=closed)
        values = [float(v) for v in self.segment_curve_offsets]
        if len(values) < count:
            values.extend([0.0] * (count - len(values)))
        return values[:count]
    def selected_segment_index(self) -> int | None:
        selected = self.selected_index
        count = self._segment_count()
        if selected is None or count <= 0:
            return None
        i = int(selected)
        if bool(self.closed):
            # A selected waypoint edits the incoming edge, except point 0 which
            # edits the first edge.  This mirrors EVT and keeps the UI simple.
            return 0 if i <= 0 else max(0, min(i - 1, count - 1))
        if i <= 0:
            return 0
        return max(0, min(i - 1, count - 1))
    def set_selected_segment_curve(self, *, radius: float, strength: float) -> int | None:
        self._sync_curve_offsets()
        idx = self.selected_segment_index()
        if idx is None:
            return None
        r = max(float(radius), 0.0)
        s = max(-1.0, min(1.0, float(strength)))
        self.curve_radius = r
        self.curve_strength = s
        self.segment_curve_radii[int(idx)] = r
        self.segment_curve_strengths[int(idx)] = s
        self.segment_curve_offsets[int(idx)] = r * s
        return int(idx)
    def segment_handle_points(self) -> list[Vec2]:
        if len(self.points) < 2:
            return []
        self._sync_curve_offsets()
        segs: list[tuple[Vec2, Vec2]] = list(zip(self.points, self.points[1:]))
        if self.closed and len(self.points) >= 3:
            segs.append((self.points[-1], self.points[0]))
        offsets = self.curve_offsets_for_sampling()
        return [segment_control_point(a, b, offsets[i] if i < len(offsets) else 0.0) for i, (a, b) in enumerate(segs)]
    def add_point_world(self, point: Vec3) -> int:
        return self.add_point_plane(world_to_plane(self.plane, point))
    def add_point_plane(self, point: Vec2, *, min_spacing: float = 1e-7) -> int:
        if self.closed:
            raise ValueError("Cannot add a point to a closed polygon; reset or reopen first.")
        new_point = (float(point[0]), float(point[1]))
        if self.points and distance2d(self.points[-1], new_point) <= max(float(min_spacing), 0.0):
            self.selected_index = len(self.points) - 1
            return self.selected_index
        self.points.append(new_point)
        self._sync_curve_offsets()
        self.selected_index = len(self.points) - 1
        return self.selected_index
    def update_selected_plane(self, point: Vec2) -> None:
        if self.selected_index is None:
            raise ValueError("No polygon point is selected.")
        self.points[int(self.selected_index)] = (float(point[0]), float(point[1]))
        self._sync_curve_offsets()
    def update_selected_world(self, point: Vec3) -> None:
        self.update_selected_plane(world_to_plane(self.plane, point))
    def nearest_point_index(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        if not self.points:
            return None
        q = (float(point[0]), float(point[1]))
        best_idx = min(range(len(self.points)), key=lambda i: _distance(self.points[i], q))
        if max_distance is not None and _distance(self.points[best_idx], q) > float(max_distance):
            return None
        return int(best_idx)
    def select_nearest_plane(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        self.selected_index = self.nearest_point_index(point, max_distance=max_distance)
        return self.selected_index
    def delete_nearest_plane(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        idx = self.nearest_point_index(point, max_distance=max_distance)
        if idx is None:
            return None
        del self.points[int(idx)]
        self.closed = self.closed and len(self.points) >= 3
        remove_idx = max(0, min(int(idx), max(len(self.segment_curve_offsets), len(self.segment_curve_radii), len(self.segment_curve_strengths)) - 1))
        for values in (self.segment_curve_offsets, self.segment_curve_radii, self.segment_curve_strengths):
            if values and 0 <= remove_idx < len(values):
                del values[remove_idx]
        self._sync_curve_offsets()
        self.clear_selection()
        return int(idx)
    def close_polygon(self) -> bool:
        if not self.can_close_polygon():
            return False
        self.closed = True
        self._sync_curve_offsets()
        self.clear_selection()
        return True
    def can_close_polygon(self) -> bool:
        return polygon_close_is_valid(
            self.points,
            extrusion_depth=max(abs(float(self.extrusion_depth)), 1.0),
        ).ok
    def close_validation_result(self):
        return polygon_close_is_valid(
            self.points,
            extrusion_depth=max(abs(float(self.extrusion_depth)), 1.0),
        )
    def open_trace_validation_result(self):
        return validate_open_polygon_trace(self.points)
    def clamp_point_candidate(
        self,
        point: Vec2,
        *,
        index: int | None = None,
        anchor: Vec2 | None = None,
    ):
        return clamp_polygon_point_candidate(
            self.points,
            point,
            index=index,
            closed=bool(self.closed),
            extrusion_depth=max(abs(float(self.extrusion_depth)), 1.0),
            anchor=anchor,
        )
    def world_points(self) -> list[Vec3]:
        return [plane_to_world(self.plane, u, v) for u, v in self.points]
    def sampled_boundary_points(self, *, samples_per_segment: int = 18, include_closure: bool = False) -> list[Vec2]:
        pts = _dedupe_open([(float(u), float(v)) for u, v in self.points])
        if len(pts) < 2:
            return pts
        closed = bool(self.closed and len(pts) >= 3)
        path = list(pts)
        if closed:
            path.append(pts[0])
        offsets = self.curve_offsets_for_sampling(closed=closed)
        sampled = sample_vent_centerline(path, samples_per_corner=max(2, int(samples_per_segment)), segment_curve_offsets=offsets, default_curve_offset=0.0)
        if closed and sampled and distance2d(sampled[0], sampled[-1]) <= 1e-6 and not include_closure:
            sampled = sampled[:-1]
        return _dedupe_open(sampled)
    def validation_result(self):
        polygon_points = self.sampled_boundary_points(samples_per_segment=18) if bool(self.closed) else list(self.points)
        return validate_polygon_for_extrusion(
            polygon_points,
            closed=self.closed,
            extrusion_depth=float(self.extrusion_depth),
        )
    def is_ready_for_extrusion(self) -> bool:
        return self.validation_result().ok
    def polygon_area(self) -> float:
        pts = self.sampled_boundary_points(samples_per_segment=18) if bool(self.closed) else list(self.points)
        if len(pts) < 3:
            return 0.0
        area2 = 0.0
        for i, (x0, y0) in enumerate(pts):
            x1, y1 = pts[(i + 1) % len(pts)]
            area2 += float(x0) * float(y1) - float(x1) * float(y0)
        return abs(area2) * 0.5
    def snap_anchor_points(self, *, samples_per_segment: int = 10) -> list[Vec2]:
        anchors: list[Vec2] = [(float(u), float(v)) for u, v in self.points]
        anchors.extend(self.segment_handle_points())
        anchors.extend(self.sampled_boundary_points(samples_per_segment=samples_per_segment))
        out: list[Vec2] = []
        seen: set[tuple[int, int]] = set()
        for u, v in anchors:
            key = (round(float(u) * 100000), round(float(v) * 100000))
            if key in seen:
                continue
            seen.add(key)
            out.append((float(u), float(v)))
        return out
def _distance(a: Vec2, b: Vec2) -> float:
    return math.hypot(float(a[0]) - float(b[0]), float(a[1]) - float(b[1]))

install_plan_trace_extensions(PlanarPolygonDraft)

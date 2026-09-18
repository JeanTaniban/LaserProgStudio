# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .contracts import Vec2
from .validation import distance2d


class PlanTraceAddKind(str, Enum):
    """2D junction/object kinds that the Plan tracer can place.

    The old PLN polygon workflow remains the first kind; the extra kinds are
    deliberately stored as independent sketch elements so future export/offset
    logic can grow without making ``PlanarToolController`` unreadable.
    """

    POLYGON = "polygon"
    LINE = "line"
    SEMICIRCLE = "semicircle"
    CIRCLE = "circle"


REQUIRED_POINTS_BY_KIND: dict[PlanTraceAddKind, int] = {
    PlanTraceAddKind.POLYGON: 0,  # Open-ended; double-click closes it.
    PlanTraceAddKind.LINE: 2,
    PlanTraceAddKind.SEMICIRCLE: 3,
    PlanTraceAddKind.CIRCLE: 2,
}


@dataclass(slots=True)
class PlanTraceElement:
    """A placed 2D plan element independent from the extrusion polygon."""

    kind: PlanTraceAddKind
    points: list[Vec2] = field(default_factory=list)
    selected_point_index: int | None = None

    def normalized_points(self) -> list[Vec2]:
        return [(float(u), float(v)) for u, v in self.points]

    def required_point_count(self) -> int:
        return int(REQUIRED_POINTS_BY_KIND.get(self.kind, 2))

    def is_complete(self) -> bool:
        required = self.required_point_count()
        return required > 0 and len(self.points) >= required

    def nearest_point_index(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        if not self.points:
            return None
        q = (float(point[0]), float(point[1]))
        best = min(range(len(self.points)), key=lambda i: distance2d(self.points[i], q))
        if max_distance is not None and distance2d(self.points[best], q) > float(max_distance):
            return None
        return int(best)

    def sampled_points(self, *, samples: int = 48) -> list[Vec2]:
        return sample_plan_trace_element(self.kind, self.points, samples=samples)


def normalize_add_kind(value: PlanTraceAddKind | str | None) -> PlanTraceAddKind:
    if isinstance(value, PlanTraceAddKind):
        return value
    raw = str(value or PlanTraceAddKind.POLYGON.value).strip().lower()
    aliases = {
        "add": PlanTraceAddKind.POLYGON,
        "poly": PlanTraceAddKind.POLYGON,
        "polygon": PlanTraceAddKind.POLYGON,
        "polygone": PlanTraceAddKind.POLYGON,
        "line": PlanTraceAddKind.LINE,
        "trait": PlanTraceAddKind.LINE,
        "segment": PlanTraceAddKind.LINE,
        "semi": PlanTraceAddKind.SEMICIRCLE,
        "semicircle": PlanTraceAddKind.SEMICIRCLE,
        "demicircle": PlanTraceAddKind.SEMICIRCLE,
        "half_circle": PlanTraceAddKind.SEMICIRCLE,
        "arc": PlanTraceAddKind.SEMICIRCLE,
        "circle": PlanTraceAddKind.CIRCLE,
        "cercle": PlanTraceAddKind.CIRCLE,
    }
    if raw in aliases:
        return aliases[raw]
    return PlanTraceAddKind(raw)


def required_points_for_kind(kind: PlanTraceAddKind | str) -> int:
    return int(REQUIRED_POINTS_BY_KIND.get(normalize_add_kind(kind), 2))


def sample_plan_trace_element(kind: PlanTraceAddKind | str, points: list[Vec2] | tuple[Vec2, ...], *, samples: int = 48) -> list[Vec2]:
    """Return drawable points for a 2D plan element.

    Incomplete elements intentionally return the currently placed points so the
    preview can show the staged construction without special-casing the UI.
    """

    item_kind = normalize_add_kind(kind)
    pts = [(float(u), float(v)) for u, v in points]
    if not pts:
        return []
    if item_kind is PlanTraceAddKind.LINE:
        return pts[:2]
    if item_kind is PlanTraceAddKind.CIRCLE:
        if len(pts) < 2:
            return pts
        return _sample_circle(pts[0], pts[1], samples=max(16, int(samples)))
    if item_kind is PlanTraceAddKind.SEMICIRCLE:
        if len(pts) < 3:
            return pts[:]
        return _sample_three_point_arc(pts[0], pts[1], pts[2], samples=max(8, int(samples)))
    return pts[:]


def _sample_circle(center: Vec2, radius_point: Vec2, *, samples: int = 64) -> list[Vec2]:
    cx, cy = float(center[0]), float(center[1])
    r = max(distance2d(center, radius_point), 1e-9)
    count = max(16, int(samples))
    return [(cx + math.cos((2.0 * math.pi * i) / count) * r, cy + math.sin((2.0 * math.pi * i) / count) * r) for i in range(count)]


def _circle_from_three_points(a: Vec2, b: Vec2, c: Vec2) -> tuple[Vec2, float] | None:
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])
    cx, cy = float(c[0]), float(c[1])
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) <= 1e-9:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    center = (float(ux), float(uy))
    return center, max(distance2d(center, a), 1e-9)


def _angle(center: Vec2, point: Vec2) -> float:
    return math.atan2(float(point[1]) - float(center[1]), float(point[0]) - float(center[0]))


def _ccw_delta(start: float, end: float) -> float:
    delta = end - start
    while delta < 0.0:
        delta += 2.0 * math.pi
    while delta >= 2.0 * math.pi:
        delta -= 2.0 * math.pi
    return delta


def _angle_on_ccw_arc(start: float, end: float, test: float) -> bool:
    total = _ccw_delta(start, end)
    probe = _ccw_delta(start, test)
    return probe <= total + 1e-9


def _sample_three_point_arc(start: Vec2, end: Vec2, curve_point: Vec2, *, samples: int = 32) -> list[Vec2]:
    circle = _circle_from_three_points(start, end, curve_point)
    if circle is None:
        # Degenerate 3-point arc: keep it editable and visible instead of hiding
        # it; the user can still move one point in Modify mode.
        return [(float(start[0]), float(start[1])), (float(curve_point[0]), float(curve_point[1])), (float(end[0]), float(end[1]))]
    center, radius = circle
    a0 = _angle(center, start)
    a1 = _angle(center, end)
    ac = _angle(center, curve_point)
    ccw = _angle_on_ccw_arc(a0, a1, ac)
    delta = _ccw_delta(a0, a1) if ccw else -_ccw_delta(a1, a0)
    count = max(8, int(samples))
    out = [
        (
            float(center[0]) + math.cos(a0 + delta * (i / count)) * radius,
            float(center[1]) + math.sin(a0 + delta * (i / count)) * radius,
        )
        for i in range(count + 1)
    ]
    out[0] = (float(start[0]), float(start[1]))
    out[-1] = (float(end[0]), float(end[1]))
    return out


def install_plan_trace_extensions(cls) -> None:
    """Attach focused Plan-tracer sketch behavior to the polygon draft.

    Keeping these extensions here protects ``draft_model.py`` from becoming a
    giant mixed UI/sketch/extrusion module while preserving the public
    ``PlanarPolygonDraft`` class used by older tests and tools.
    """

    original_clear_selection = cls.clear_selection
    original_reset = cls.reset
    original_update_selected_plane = cls.update_selected_plane
    original_snap_anchor_points = cls.snap_anchor_points
    original_is_ready_for_extrusion = cls.is_ready_for_extrusion
    original_validation_result = cls.validation_result
    original_polygon_area = cls.polygon_area

    def clear_selection(self) -> None:
        original_clear_selection(self)
        self.selected_element_index = None
        self.selected_element_point_index = None
        for element in self.elements:
            element.selected_point_index = None

    def has_selection(self) -> bool:
        return self.selected_index is not None or self.selected_element_index is not None

    def clear_active_element(self) -> None:
        self.active_element_points.clear()

    def set_add_kind(self, kind: PlanTraceAddKind | str) -> None:
        from .contracts import PlanarEditMode
        self.add_kind = normalize_add_kind(kind)
        self.mode = PlanarEditMode.ADD
        self.clear_selection()
        self.clear_active_element()

    def set_mode(self, mode) -> None:
        from .contracts import PlanarEditMode
        new_mode = mode if isinstance(mode, PlanarEditMode) else PlanarEditMode(str(mode))
        if new_mode is PlanarEditMode.RST:
            self.reset()
            self.mode = PlanarEditMode.ADD
            self.add_kind = PlanTraceAddKind.POLYGON
            return
        self.clear_selection()
        if new_mode is not PlanarEditMode.ADD:
            self.clear_active_element()
        self.mode = new_mode

    def reset(self) -> None:
        original_reset(self)
        from .contracts import PlanarEditMode
        self.elements.clear()
        self.active_element_points.clear()
        self.mode = PlanarEditMode.MOD
        self.add_kind = PlanTraceAddKind.POLYGON
        self.clear_selection()

    def update_selected_plane(self, point: Vec2) -> None:
        if self.selected_index is not None:
            original_update_selected_plane(self, point)
            return
        if self.selected_element_index is not None and self.selected_element_point_index is not None:
            eidx = int(self.selected_element_index)
            pidx = int(self.selected_element_point_index)
            if 0 <= eidx < len(self.elements) and 0 <= pidx < len(self.elements[eidx].points):
                self.elements[eidx].points[pidx] = (float(point[0]), float(point[1]))
                self.elements[eidx].selected_point_index = pidx
                return
        raise ValueError("No plan point is selected.")

    def nearest_edit_target(self, point: Vec2, *, max_distance: float | None = None) -> tuple[str, int, int] | None:
        q = (float(point[0]), float(point[1]))
        best: tuple[float, str, int, int] | None = None
        for idx, pt in enumerate(self.points):
            d = distance2d(pt, q)
            if max_distance is not None and d > float(max_distance):
                continue
            if best is None or d < best[0]:
                best = (d, "polygon", int(idx), int(idx))
        for eidx, element in enumerate(self.elements):
            pidx = element.nearest_point_index(q, max_distance=max_distance)
            if pidx is None:
                continue
            d = distance2d(element.points[int(pidx)], q)
            if best is None or d < best[0]:
                best = (d, "element", int(eidx), int(pidx))
        return None if best is None else (best[1], best[2], best[3])

    def select_nearest_plane(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        self.clear_selection()
        target = self.nearest_edit_target(point, max_distance=max_distance)
        if target is None:
            return None
        kind, major, minor = target
        if kind == "polygon":
            self.selected_index = int(minor)
            return self.selected_index
        self.selected_element_index = int(major)
        self.selected_element_point_index = int(minor)
        self.elements[int(major)].selected_point_index = int(minor)
        return int(minor)

    def delete_selected(self) -> bool:
        if self.selected_element_index is not None:
            eidx = int(self.selected_element_index)
            if 0 <= eidx < len(self.elements):
                del self.elements[eidx]
                self.clear_selection()
                return True
        if self.selected_index is not None:
            idx = int(self.selected_index)
            if 0 <= idx < len(self.points):
                self.delete_nearest_plane(self.points[idx], max_distance=0.0)
                return True
        return False

    def add_trace_point_plane(self, point: Vec2) -> bool:
        kind = normalize_add_kind(self.add_kind)
        if kind is PlanTraceAddKind.POLYGON:
            self.add_point_plane(point)
            return False
        self.active_element_points.append((float(point[0]), float(point[1])))
        required = required_points_for_kind(kind)
        if len(self.active_element_points) >= required:
            self.elements.append(PlanTraceElement(kind=kind, points=self.active_element_points[:required]))
            self.active_element_points.clear()
            self.clear_selection()
            return True
        return False

    def staged_trace_points(self, *, pending: Vec2 | None = None) -> list[Vec2]:
        pts = [(float(u), float(v)) for u, v in self.active_element_points]
        if pending is not None:
            pts.append((float(pending[0]), float(pending[1])))
        return pts


    def closed_trace_regions(self):
        from .plan_trace_regions import plan_trace_closed_regions
        return plan_trace_closed_regions(self, samples=48)

    def validation_result(self):
        if bool(getattr(self, "closed", False)):
            return original_validation_result(self)
        regions = self.closed_trace_regions()
        if regions:
            from .validation import validate_polygon_for_extrusion
            return validate_polygon_for_extrusion(regions[0].points, closed=True, extrusion_depth=float(self.extrusion_depth))
        return original_validation_result(self)

    def is_ready_for_extrusion(self) -> bool:
        if bool(original_is_ready_for_extrusion(self)):
            return True
        return bool(self.closed_trace_regions())

    def polygon_area(self) -> float:
        regions = self.closed_trace_regions()
        if regions:
            return float(sum(region.area for region in regions))
        return float(original_polygon_area(self))

    def snap_anchor_points(self, *, samples_per_segment: int = 10) -> list[Vec2]:
        from .plan_trace_snap import collect_plan_trace_snap_points

        base_points = list(original_snap_anchor_points(self, samples_per_segment=samples_per_segment))
        return collect_plan_trace_snap_points(
            self,
            base_points=base_points,
            samples_per_segment=max(6, int(samples_per_segment)),
            include_samples=True,
            include_active=True,
        )

    cls.clear_selection = clear_selection
    cls.has_selection = has_selection
    cls.clear_active_element = clear_active_element
    cls.set_add_kind = set_add_kind
    cls.set_mode = set_mode
    cls.reset = reset
    cls.update_selected_plane = update_selected_plane
    cls.nearest_edit_target = nearest_edit_target
    cls.select_nearest_plane = select_nearest_plane
    cls.delete_selected = delete_selected
    cls.add_trace_point_plane = add_trace_point_plane
    cls.staged_trace_points = staged_trace_points
    cls.closed_trace_regions = closed_trace_regions
    cls.validation_result = validation_result
    cls.is_ready_for_extrusion = is_ready_for_extrusion
    cls.polygon_area = polygon_area
    cls.snap_anchor_points = snap_anchor_points

# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .contracts import LockedPlaneSpec, PlanarEditMode, Vec2, Vec3, VentFlareSide, VentSectionKind
from .orientation import plane_to_world, world_to_plane
from .path_sampling import polyline_length
from .validation import PlanarValidationResult, distance2d, validate_vent_path
from .vent_constraints import VentClampResult, clamp_vent_waypoint_candidate, make_vent_clearance_policy, validate_vent_waypoints_and_curve
from .vent_curve_controls import (
    curve_handle_candidate_is_valid as _curve_handle_candidate_is_valid,
    curve_offsets_for_sampling as _curve_offsets_for_sampling,
    default_curve_offset as _default_curve_offset,
    nearest_curve_handle_index as _nearest_curve_handle_index,
    selected_segment_index as _selected_segment_index,
    selected_segment_offset as _selected_segment_offset,
    segment_count as _segment_count,
    segment_handle_points as _segment_handle_points,
    set_selected_segment_curve as _set_selected_segment_curve,
    sync_curve_offsets as _sync_curve_offsets,
    update_curve_handle_plane as _update_curve_handle_plane,
)
from .vent_flare import effective_vent_flare_side
from .vent_flare_sampling import sampled_centerline_with_flare_scales as _sampled_centerline_with_flare_scales
from .vent_path_geometry import sample_vent_centerline, validate_vent_bend_radius
from .vent_preview_snap import snap_anchor_points as _snap_anchor_points


@dataclass(slots=True)
class VentSectionSpec:
    kind: VentSectionKind = VentSectionKind.ROUND
    area: float = 100.0
    width: float | None = None
    height: float | None = None

    def dimensions(self) -> tuple[float, float]:
        area = max(float(self.area), 1e-9)
        if self.kind is VentSectionKind.ROUND or self.kind == VentSectionKind.ROUND.value:
            d = math.sqrt(4.0 * area / math.pi)
            return (d, d)
        if self.width is not None and self.height is not None and self.width > 0 and self.height > 0:
            return (float(self.width), float(self.height))
        side = math.sqrt(area)
        return (side, side)


@dataclass(frozen=True, slots=True)
class VentGeometryMetrics:
    inner_width: float
    inner_height: float
    wall_thickness: float
    outer_width: float
    outer_height: float
    centerline_length: float
    min_centerline_spacing: float
    target_length: float | None = None
    flare_side: VentFlareSide = VentFlareSide.NONE
    flare_factor: float = 1.0
    curve_radius: float = 0.0
    curve_strength: float = 0.0
    snap_grid_step: float = 1.0
    fill_area: bool = False

    @property
    def target_delta(self) -> float | None:
        if self.target_length is None or self.target_length <= 0.0:
            return None
        return float(self.centerline_length) - float(self.target_length)


@dataclass(slots=True)
class VentPathDraft:
    plane: LockedPlaneSpec
    section: VentSectionSpec = field(default_factory=VentSectionSpec)
    wall_thickness: float = 3.0
    compact_wall_fusion: bool = True
    only_walls: bool = False
    fill_area: bool = False
    target_length: float | None = None
    flare_side: VentFlareSide = VentFlareSide.NONE
    flare_factor: float = 1.0
    end_flare_finalized: bool = False
    curve_radius: float = 0.0
    curve_strength: float = 0.0
    segment_curve_offsets: list[float] = field(default_factory=list)
    segment_curve_radii: list[float] = field(default_factory=list)
    segment_curve_strengths: list[float] = field(default_factory=list)
    mode: PlanarEditMode = PlanarEditMode.ADD
    waypoints: list[Vec2] = field(default_factory=list)
    selected_index: int | None = None
    selected_curve_index: int | None = None

    def set_mode(self, mode: PlanarEditMode | str) -> None:
        new_mode = mode if isinstance(mode, PlanarEditMode) else PlanarEditMode(str(mode))
        if new_mode is PlanarEditMode.RST:
            self.reset(); self.mode = PlanarEditMode.ADD; return
        if new_mode is not self.mode:
            self.clear_selection()
        self.mode = new_mode

    def clear_selection(self) -> None:
        self.selected_index = None; self.selected_curve_index = None

    def reset(self) -> None:
        self.waypoints.clear(); self.segment_curve_offsets.clear(); self.segment_curve_radii.clear(); self.segment_curve_strengths.clear(); self.clear_selection(); self.end_flare_finalized = False

    def _segment_count(self) -> int:
        return _segment_count(self)

    def default_curve_offset(self) -> float:
        return _default_curve_offset(self)

    def _sync_curve_offsets(self) -> None:
        _sync_curve_offsets(self)

    def curve_offsets_for_sampling(self) -> list[float]:
        return _curve_offsets_for_sampling(self)

    def add_waypoint_plane(self, point: Vec2, *, min_spacing: float = 1e-7) -> int:
        new_point = (float(point[0]), float(point[1]))
        if self.waypoints and distance2d(self.waypoints[-1], new_point) <= max(float(min_spacing), 0.0):
            self.selected_index = len(self.waypoints) - 1; self.selected_curve_index = None; return self.selected_index
        self.end_flare_finalized = False; self.waypoints.append(new_point); self._sync_curve_offsets()
        self.selected_index = len(self.waypoints) - 1; self.selected_curve_index = None
        return self.selected_index

    def add_waypoint_world(self, point: Vec3) -> int:
        return self.add_waypoint_plane(world_to_plane(self.plane, point))

    def nearest_waypoint_index(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        if not self.waypoints:
            return None
        q = (float(point[0]), float(point[1]))
        best = min(range(len(self.waypoints)), key=lambda i: distance2d(self.waypoints[i], q))
        return None if max_distance is not None and distance2d(self.waypoints[best], q) > float(max_distance) else int(best)

    def nearest_curve_handle_index(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        return _nearest_curve_handle_index(self, point, max_distance=max_distance)

    def select_nearest_plane(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        self.selected_index = self.nearest_waypoint_index(point, max_distance=max_distance); self.selected_curve_index = None; return self.selected_index

    def select_nearest_curve_handle_plane(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        self.selected_curve_index = self.nearest_curve_handle_index(point, max_distance=max_distance)
        if self.selected_curve_index is not None:
            self.selected_index = None
        return self.selected_curve_index

    def update_selected_plane(self, point: Vec2) -> None:
        if self.selected_index is None:
            raise ValueError("No vent waypoint is selected.")
        self.waypoints[int(self.selected_index)] = (float(point[0]), float(point[1])); self._sync_curve_offsets()

    def update_curve_handle_plane(self, index: int, point: Vec2) -> float:
        return _update_curve_handle_plane(self, index, point)

    def curve_handle_candidate_is_valid(self, index: int, point: Vec2) -> PlanarValidationResult:
        return _curve_handle_candidate_is_valid(self, index, point)

    def delete_nearest_plane(self, point: Vec2, *, max_distance: float | None = None) -> int | None:
        idx = self.nearest_waypoint_index(point, max_distance=max_distance)
        if idx is None:
            return None
        del self.waypoints[int(idx)]
        remove_idx = max(0, min(int(idx), max(len(self.segment_curve_offsets), len(self.segment_curve_radii), len(self.segment_curve_strengths)) - 1))
        for values in (self.segment_curve_offsets, self.segment_curve_radii, self.segment_curve_strengths):
            if values and 0 <= remove_idx < len(values):
                del values[remove_idx]
        self._sync_curve_offsets(); self.end_flare_finalized = False; self.clear_selection()
        return int(idx)

    def world_waypoints(self) -> list[Vec3]:
        return [plane_to_world(self.plane, u, v) for u, v in self.waypoints]

    def section_dimensions(self) -> tuple[float, float]:
        return self.section.dimensions()

    def outer_dimensions(self) -> tuple[float, float]:
        width, height = self.section_dimensions(); wall = max(float(self.wall_thickness), 0.0)
        return (float(width) + 2.0 * wall, float(height) + 2.0 * wall)

    def snap_grid_step(self) -> float:
        outer_w, _outer_h = self.outer_dimensions()
        return max(float(outer_w) / 4.0, 0.01)

    def is_rectangle(self) -> bool:
        return self.section.kind is VentSectionKind.RECTANGLE or str(self.section.kind) == VentSectionKind.RECTANGLE.value

    def uses_only_walls(self) -> bool:
        return bool(self.only_walls) and not bool(self.fill_area) and self.is_rectangle()

    def normalized_flare_side(self) -> VentFlareSide:
        try:
            return self.flare_side if isinstance(self.flare_side, VentFlareSide) else VentFlareSide(str(self.flare_side))
        except Exception:
            return VentFlareSide.NONE

    def normalized_flare_factor(self) -> float:
        try:
            value = float(self.flare_factor)
        except Exception:
            value = 1.0
        return max(value, 1.0) if math.isfinite(value) else 1.0

    def has_flare(self) -> bool:
        return self.normalized_flare_side() is not VentFlareSide.NONE and self.normalized_flare_factor() > 1.000001

    def effective_flare_side(self) -> VentFlareSide:
        if not self.has_flare() or not self.waypoints:
            return VentFlareSide.NONE
        return effective_vent_flare_side(requested=self.normalized_flare_side(), end_finalized=bool(self.end_flare_finalized and len(self.waypoints) >= 2))

    def has_active_flare(self) -> bool:
        return self.effective_flare_side() is not VentFlareSide.NONE and self.normalized_flare_factor() > 1.000001

    def end_flare_requested(self) -> bool:
        return self.normalized_flare_side() in {VentFlareSide.END, VentFlareSide.BOTH} and self.normalized_flare_factor() > 1.000001

    def end_flare_needs_finalization(self) -> bool:
        # Rectangular EVT has no separate finalization step anymore: the current
        # last waypoint is always the outlet used by preview and Apply.
        return False

    def mark_end_flare_finalized(self, enabled: bool = True) -> None:
        self.end_flare_finalized = bool(enabled and len(self.waypoints) >= 2)

    def flare_applies_to_start(self) -> bool:
        return self.effective_flare_side() in {VentFlareSide.START, VentFlareSide.BOTH} and self.normalized_flare_factor() > 1.000001

    def flare_applies_to_end(self) -> bool:
        return self.effective_flare_side() in {VentFlareSide.END, VentFlareSide.BOTH} and self.normalized_flare_factor() > 1.000001

    def minimum_bend_radius(self) -> float:
        return max(float(self.curve_radius), 0.0)

    def smoothed_centerline(self, *, samples_per_segment: int = 18) -> list[Vec2]:
        return sample_vent_centerline(
            self.waypoints, bend_radius=self.minimum_bend_radius(), samples_per_corner=samples_per_segment,
            segment_curve_offsets=self.curve_offsets_for_sampling(), default_curve_offset=self.default_curve_offset(),
        )

    def sampled_centerline_with_flare_scales(self, *, samples_per_segment: int = 18) -> tuple[list[Vec2], list[float]]:
        return _sampled_centerline_with_flare_scales(self, samples_per_segment=samples_per_segment)
    def segment_handle_points(self) -> list[Vec2]:
        return _segment_handle_points(self)

    def selected_segment_index(self) -> int | None:
        return _selected_segment_index(self)

    def selected_segment_offset(self) -> float:
        return _selected_segment_offset(self)

    def set_selected_segment_curve(self, *, radius: float, strength: float) -> int | None:
        return _set_selected_segment_curve(self, radius=radius, strength=strength)

    def estimated_centerline_length(self, *, samples_per_segment: int = 18) -> float:
        return polyline_length(self.smoothed_centerline(samples_per_segment=samples_per_segment))

    def target_length_delta(self) -> float | None:
        if self.target_length is None or float(self.target_length) <= 0.0:
            return None
        return self.estimated_centerline_length() - float(self.target_length)

    def metrics(self) -> VentGeometryMetrics:
        width, height = self.section_dimensions(); outer_w, outer_h = self.outer_dimensions(); wall = max(float(self.wall_thickness), 0.0)
        target = None if self.target_length is None or float(self.target_length) <= 0.0 else float(self.target_length)
        return VentGeometryMetrics(float(width), float(height), wall, float(outer_w), float(outer_h), self.estimated_centerline_length(), float(self.clearance_policy().min_centerline_spacing), target, self.normalized_flare_side(), self.normalized_flare_factor(), float(self.curve_radius), float(self.curve_strength), float(self.snap_grid_step()), bool(self.fill_area))

    def clearance_policy(self):
        width, _height = self.section_dimensions()
        return make_vent_clearance_policy(section_kind=self.section.kind, section_width=float(width), wall_thickness=float(self.wall_thickness), compact_wall_fusion=bool(self.is_rectangle()))

    def _flare_segment_lengths(self) -> tuple[float, float]:
        if len(self.waypoints) < 2:
            return (0.0, 0.0)
        return (max(distance2d(self.waypoints[0], self.waypoints[1]), 0.0), max(distance2d(self.waypoints[-2], self.waypoints[-1]), 0.0))

    def flare_scale_at_distance(self, distance: float, total: float) -> float:
        factor, side = self.normalized_flare_factor(), self.effective_flare_side()
        if factor <= 1.000001 or side is VentFlareSide.NONE:
            return 1.0
        d = min(max(float(distance), 0.0), max(float(total), 0.0)); start_len, end_len = self._flare_segment_lengths(); scale = 1.0
        def smooth(x: float) -> float:
            x = min(max(float(x), 0.0), 1.0); return x * x * (3.0 - 2.0 * x)
        if side in {VentFlareSide.START, VentFlareSide.BOTH} and start_len > 1e-9 and d <= start_len:
            scale = max(scale, 1.0 + (factor - 1.0) * smooth(1.0 - d / start_len))
        if side in {VentFlareSide.END, VentFlareSide.BOTH} and end_len > 1e-9 and (float(total) - d) <= end_len:
            scale = max(scale, 1.0 + (factor - 1.0) * smooth(1.0 - (float(total) - d) / end_len))
        return float(scale)

    def clearance_width_profile(self):
        width, _height = self.section_dimensions()
        return lambda distance, total: float(width) * self.flare_scale_at_distance(float(distance), float(total))

    def clamp_waypoint_candidate(self, candidate: Vec2, *, index: int | None = None, anchor: Vec2 | None = None) -> VentClampResult:
        return clamp_vent_waypoint_candidate(
            self.waypoints, candidate, self.clearance_policy(), index=index, anchor=anchor,
            width_profile_factory=lambda _points: self.clearance_width_profile(), bend_radius=self.minimum_bend_radius(),
            segment_curve_offsets=self.curve_offsets_for_sampling(), default_curve_offset=self.default_curve_offset(),
        )

    def validation_result(self) -> PlanarValidationResult:
        width, height = self.section_dimensions(); area = max(float(width) * float(height), float(self.section.area))
        basic = validate_vent_path(self.waypoints, section_area=float(area), wall_thickness=float(self.wall_thickness))
        bend = validate_vent_bend_radius(self.waypoints, bend_radius=self.minimum_bend_radius())
        clearance = validate_vent_waypoints_and_curve(
            self.waypoints, self.clearance_policy(), width_profile=self.clearance_width_profile(), bend_radius=self.minimum_bend_radius(),
            segment_curve_offsets=self.curve_offsets_for_sampling(), default_curve_offset=self.default_curve_offset(),
        )
        errors = tuple(basic.errors) + tuple(bend.errors) + tuple(clearance.errors)
        warnings = tuple(basic.warnings) + tuple(bend.warnings) + tuple(clearance.warnings)
        return PlanarValidationResult(ok=bool(basic.ok and bend.ok and clearance.ok), errors=errors, warnings=warnings)

    def is_ready_for_mesh(self) -> bool:
        return self.validation_result().ok

    def snap_anchor_points(self, *, samples_per_segment: int = 12) -> list[Vec2]:
        return _snap_anchor_points(self, samples_per_segment=samples_per_segment)

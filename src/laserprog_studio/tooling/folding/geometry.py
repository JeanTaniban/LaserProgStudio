# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.planar_tools import LockedPlaneSpec
from laserprog_studio.tool_api.tracing import plane_from_origin_normal

from .models import (
    FoldingCurve,
    FoldingDeformationMode,
    FoldingFixedSide,
    FoldingMode,
    Point3,
    clamp_folding_angle_deg,
)


_EPS = 1.0e-9


def _v3(value: Iterable[float]) -> np.ndarray:
    arr = np.asarray(tuple(value), dtype=np.float64)
    if arr.shape != (3,) or not np.all(np.isfinite(arr)):
        raise ValueError("Expected a finite 3D point.")
    return arr


def _unit(value: Iterable[float], *, label: str) -> np.ndarray:
    arr = _v3(value)
    length = float(np.linalg.norm(arr))
    if length <= _EPS:
        raise ValueError(f"{label} is degenerate.")
    return arr / length


def arbitrary_face_plane(origin: Point3, normal: Point3) -> LockedPlaneSpec:
    """Compatibility wrapper over the shared tracing plane helper."""

    return plane_from_origin_normal(origin, normal)


@dataclass(frozen=True, slots=True)
class FoldingFrame:
    start: Point3
    end: Point3
    normal: Point3
    axis: Point3
    bend_axis: Point3
    length_mm: float


@dataclass(frozen=True, slots=True)
class LivingHingePose:
    angle_rad: float
    radius_mm: float
    end_center: Point3
    end_tangent: Point3
    end_normal: Point3


def build_folding_frame(plane: LockedPlaneSpec, curve: FoldingCurve) -> FoldingFrame:
    if not curve.complete:
        raise ValueError("The folding curve needs a start and an end point.")
    start = _v3(curve.start)
    end = _v3(curve.end)
    normal = _unit(plane.normal, label="fold plane normal")
    delta = end - start
    delta = delta - normal * float(np.dot(delta, normal))
    length = float(np.linalg.norm(delta))
    if length <= 1.0e-4:
        raise ValueError("Start and end points are too close.")
    axis = delta / length
    bend = _unit(np.cross(normal, axis), label="fold axis")
    return FoldingFrame(
        tuple(float(v) for v in start),
        tuple(float(v) for v in end),
        tuple(float(v) for v in normal),
        tuple(float(v) for v in axis),
        tuple(float(v) for v in bend),
        length,
    )


# ---------------------------------------------------------------------------
# Legacy free-curve deformation (v107-v113 project compatibility)
# ---------------------------------------------------------------------------
# Quintic displacement d(u) with d(0)=d'(0)=d(1)=d'(1)=0 and
# d(1/3)=h1, d(2/3)=h2.
_DISPLACEMENT_MATRIX = np.array(
    [
        [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
        [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        [1.0, 1.0 / 3.0, 1.0 / 9.0, 1.0 / 27.0, 1.0 / 81.0, 1.0 / 243.0],
        [1.0, 2.0 / 3.0, 4.0 / 9.0, 8.0 / 27.0, 16.0 / 81.0, 32.0 / 243.0],
    ],
    dtype=np.float64,
)
_DISPLACEMENT_MATRIX_INV = np.linalg.inv(_DISPLACEMENT_MATRIX)


def displacement_coefficients(h1: float, h2: float) -> np.ndarray:
    rhs = np.array((0.0, 0.0, 0.0, 0.0, float(h1), float(h2)), dtype=np.float64)
    return _DISPLACEMENT_MATRIX_INV @ rhs


def _poly_and_derivative(coeffs: np.ndarray, u: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    d = np.zeros_like(u, dtype=np.float64) + coeffs[5]
    for index in range(4, -1, -1):
        d = d * u + coeffs[index]
    derivative_coeffs = np.array((coeffs[1], 2.0 * coeffs[2], 3.0 * coeffs[3], 4.0 * coeffs[4], 5.0 * coeffs[5]))
    dd = np.zeros_like(u, dtype=np.float64) + derivative_coeffs[4]
    for index in range(3, -1, -1):
        dd = dd * u + derivative_coeffs[index]
    return d, dd


def _sample_free_curve(plane: LockedPlaneSpec, curve: FoldingCurve, *, count: int) -> tuple[Point3, ...]:
    frame = build_folding_frame(plane, curve)
    start = _v3(frame.start)
    axis = _v3(frame.axis)
    bend = _v3(frame.bend_axis)
    samples = np.linspace(0.0, 1.0, max(8, int(count)), dtype=np.float64)
    coeffs = displacement_coefficients(curve.control_1_offset_mm, curve.control_2_offset_mm)
    displacement, _derivative = _poly_and_derivative(coeffs, samples)
    points = start[None, :] + samples[:, None] * frame.length_mm * axis[None, :] + displacement[:, None] * bend[None, :]
    return tuple(tuple(float(v) for v in row) for row in points)


def control_points(plane: LockedPlaneSpec, curve: FoldingCurve) -> tuple[Point3, Point3]:
    frame = build_folding_frame(plane, curve)
    start = _v3(frame.start)
    axis = _v3(frame.axis)
    bend = _v3(frame.bend_axis)
    first = start + axis * (frame.length_mm / 3.0) + bend * float(curve.control_1_offset_mm)
    second = start + axis * (2.0 * frame.length_mm / 3.0) + bend * float(curve.control_2_offset_mm)
    return tuple(float(v) for v in first), tuple(float(v) for v in second)


def offset_from_control_point(plane: LockedPlaneSpec, curve: FoldingCurve, point: Point3, *, index: int) -> float:
    frame = build_folding_frame(plane, curve)
    start = _v3(frame.start)
    axis = _v3(frame.axis)
    bend = _v3(frame.bend_axis)
    fraction = 1.0 / 3.0 if int(index) == 1 else 2.0 / 3.0
    base = start + axis * (frame.length_mm * fraction)
    return float(np.dot(_v3(point) - base, bend))


def _deform_free_curve(vertices: Iterable[Iterable[float]], plane: LockedPlaneSpec, curve: FoldingCurve) -> list[Point3]:
    frame = build_folding_frame(plane, curve)
    points = np.asarray(tuple(vertices), dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError("The selected mesh has invalid vertices.")
    points = points[:, :3].copy()
    start = _v3(frame.start)
    normal = _v3(frame.normal)
    axis = _v3(frame.axis)
    bend = _v3(frame.bend_axis)
    rel = points - start[None, :]
    x = rel @ axis
    y = rel @ bend
    z = rel @ normal
    active = (x > 1.0e-8) & (x < frame.length_mm - 1.0e-8)
    if not np.any(active):
        return [tuple(float(v) for v in row) for row in points]
    u = np.clip(x[active] / frame.length_mm, 0.0, 1.0)
    coeffs = displacement_coefficients(curve.control_1_offset_mm, curve.control_2_offset_mm)
    displacement, derivative = _poly_and_derivative(coeffs, u)
    tangent = frame.length_mm * axis[None, :] + derivative[:, None] * bend[None, :]
    tangent_length = np.linalg.norm(tangent, axis=1)
    tangent_length[tangent_length <= _EPS] = 1.0
    tangent /= tangent_length[:, None]
    transported_bend = np.cross(normal[None, :], tangent)
    transported_length = np.linalg.norm(transported_bend, axis=1)
    transported_length[transported_length <= _EPS] = 1.0
    transported_bend /= transported_length[:, None]
    centerline = start[None, :] + (u * frame.length_mm)[:, None] * axis[None, :] + displacement[:, None] * bend[None, :]
    points[active] = centerline + y[active, None] * transported_bend + z[active, None] * normal[None, :]
    return [tuple(float(v) for v in row) for row in points]


# ---------------------------------------------------------------------------
# Living-hinge fold with an editable, arc-length-preserving profile
# ---------------------------------------------------------------------------
def normalized_fold_angle_deg(value: float) -> float:
    """Clamp a fold angle without wrapping away complete turns."""

    return clamp_folding_angle_deg(value)


def unwrap_fold_angle_deg(wrapped_angle_deg: float, reference_angle_deg: float) -> float:
    """Return the 360-degree equivalent nearest the current multi-turn angle.

    ``atan2`` necessarily reports a terminal-handle direction in ``[-180, 180]``.
    Folding angles are allowed to span several turns, so the handle interaction
    must preserve the current revolution instead of jumping from +180 to -180.
    """

    wrapped = float(wrapped_angle_deg)
    reference = float(reference_angle_deg)
    delta = (wrapped - reference + 180.0) % 360.0 - 180.0
    # At the exact half-turn boundary, preserve the direction of the raw delta.
    if abs(delta + 180.0) <= 1.0e-10 and wrapped - reference > 0.0:
        delta = 180.0
    return normalized_fold_angle_deg(reference + delta)


def shape_control_fractions(curve: FoldingCurve) -> tuple[float, ...]:
    count = max(1, min(7, int(curve.shape_control_count)))
    return tuple(float(index) / float(count + 1) for index in range(1, count + 1))


def resample_shape_angles(values: Iterable[float], count: int) -> tuple[float, ...]:
    """Resample a profile when the user changes its number of handles.

    Endpoint offsets are always zero because the start and terminal tangents are
    controlled by the fixed region and the global fold angle respectively.
    """

    target_count = max(1, min(7, int(count)))
    old = tuple(float(max(-270.0, min(270.0, value))) for value in tuple(values))
    if not old:
        return tuple(0.0 for _ in range(target_count))
    old_x = np.linspace(0.0, 1.0, len(old) + 2, dtype=np.float64)
    old_y = np.asarray((0.0, *old, 0.0), dtype=np.float64)
    new_x = np.linspace(0.0, 1.0, target_count + 2, dtype=np.float64)[1:-1]
    result = np.interp(new_x, old_x, old_y)
    return tuple(float(max(-270.0, min(270.0, value))) for value in result)


def _profile_knots_and_angles(curve: FoldingCurve, *, angle_deg: float | None = None) -> tuple[np.ndarray, np.ndarray]:
    offsets = curve.normalized_shape_angles()
    knots = np.linspace(0.0, 1.0, len(offsets) + 2, dtype=np.float64)
    theta = math.radians(normalized_fold_angle_deg(curve.fold_angle_deg if angle_deg is None else angle_deg))
    values = theta * knots
    if offsets:
        values[1:-1] += np.radians(np.asarray(offsets, dtype=np.float64))
    return knots, values


def _evaluate_tangent_angles(curve: FoldingCurve, u: np.ndarray | Iterable[float] | float, *, angle_deg: float | None = None) -> np.ndarray:
    """Evaluate a smooth tangent-angle profile along normalized arc length.

    Cubic Hermite interpolation keeps the original circular profile exactly when
    every shape offset is zero, while arbitrary positive/negative offsets can
    redistribute curvature or create an S-shaped neutral line.
    """

    query = np.asarray(u, dtype=np.float64)
    original_shape = query.shape
    flat = np.clip(query.reshape(-1), 0.0, 1.0)
    knots, values = _profile_knots_and_angles(curve, angle_deg=angle_deg)
    slopes = np.empty_like(values)
    slopes[0] = (values[1] - values[0]) / (knots[1] - knots[0])
    slopes[-1] = (values[-1] - values[-2]) / (knots[-1] - knots[-2])
    if len(values) > 2:
        slopes[1:-1] = (values[2:] - values[:-2]) / (knots[2:] - knots[:-2])

    segment = np.searchsorted(knots, flat, side="right") - 1
    segment = np.clip(segment, 0, len(knots) - 2)
    x0 = knots[segment]
    x1 = knots[segment + 1]
    h = x1 - x0
    t = np.divide(flat - x0, h, out=np.zeros_like(flat), where=h > _EPS)
    t2 = t * t
    t3 = t2 * t
    h00 = 2.0 * t3 - 3.0 * t2 + 1.0
    h10 = t3 - 2.0 * t2 + t
    h01 = -2.0 * t3 + 3.0 * t2
    h11 = t3 - t2
    result = h00 * values[segment] + h10 * h * slopes[segment] + h01 * values[segment + 1] + h11 * h * slopes[segment + 1]
    return result.reshape(original_shape)


def _living_hinge_table(
    plane: LockedPlaneSpec,
    curve: FoldingCurve,
    *,
    count: int,
    angle_deg: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return arc-length stations, centerline points and tangent angles.

    Each polyline increment has length ``L/(count-1)``.  The neutral line is
    therefore length-preserving by construction, independently of the profile.
    """

    frame = build_folding_frame(plane, curve)
    sample_count = max(8, int(count))
    u = np.linspace(0.0, 1.0, sample_count, dtype=np.float64)
    mid_u = 0.5 * (u[:-1] + u[1:])
    mid_angles = _evaluate_tangent_angles(curve, mid_u, angle_deg=angle_deg)
    axis = _v3(frame.axis)
    normal = _v3(frame.normal)
    ds = frame.length_mm / float(sample_count - 1)
    increments = ds * (np.cos(mid_angles)[:, None] * axis[None, :] + np.sin(mid_angles)[:, None] * normal[None, :])
    points = np.empty((sample_count, 3), dtype=np.float64)
    points[0] = _v3(frame.start)
    points[1:] = points[0][None, :] + np.cumsum(increments, axis=0)
    angles = _evaluate_tangent_angles(curve, u, angle_deg=angle_deg)
    return u, points, angles


def _interpolate_table(points: np.ndarray, u: np.ndarray) -> np.ndarray:
    positions = np.clip(np.asarray(u, dtype=np.float64), 0.0, 1.0) * float(len(points) - 1)
    lower = np.floor(positions).astype(np.int64)
    lower = np.clip(lower, 0, len(points) - 2)
    fraction = positions - lower
    return points[lower] * (1.0 - fraction[:, None]) + points[lower + 1] * fraction[:, None]


def living_hinge_pose(plane: LockedPlaneSpec, curve: FoldingCurve) -> LivingHingePose:
    frame = build_folding_frame(plane, curve)
    _u, points, _angles = _living_hinge_table(plane, curve, count=1025)
    theta = math.radians(normalized_fold_angle_deg(curve.fold_angle_deg))
    axis = _v3(frame.axis)
    normal = _v3(frame.normal)
    end_tangent = axis * math.cos(theta) + normal * math.sin(theta)
    end_normal = -axis * math.sin(theta) + normal * math.cos(theta)
    radius = math.inf if abs(theta) <= 1.0e-10 else abs(frame.length_mm / theta)
    return LivingHingePose(
        theta,
        float(radius),
        tuple(float(v) for v in points[-1]),
        tuple(float(v) for v in end_tangent),
        tuple(float(v) for v in end_normal),
    )


def _living_hinge_samples(plane: LockedPlaneSpec, curve: FoldingCurve, *, count: int) -> tuple[Point3, ...]:
    _u, points, _angles = _living_hinge_table(plane, curve, count=count)
    return tuple(tuple(float(v) for v in row) for row in points)


def shape_handle_points(plane: LockedPlaneSpec, curve: FoldingCurve) -> tuple[Point3, ...]:
    fractions = shape_control_fractions(curve)
    count = (len(fractions) + 1) * 64 + 1
    _u, points, _angles = _living_hinge_table(plane, curve, count=count)
    sampled = _interpolate_table(points, np.asarray(fractions, dtype=np.float64))
    return tuple(tuple(float(v) for v in row) for row in sampled)


def shape_handle_normals(plane: LockedPlaneSpec, curve: FoldingCurve) -> tuple[Point3, ...]:
    frame = build_folding_frame(plane, curve)
    fractions = np.asarray(shape_control_fractions(curve), dtype=np.float64)
    angles = _evaluate_tangent_angles(curve, fractions)
    axis = _v3(frame.axis)
    normal = _v3(frame.normal)
    vectors = -np.sin(angles)[:, None] * axis[None, :] + np.cos(angles)[:, None] * normal[None, :]
    return tuple(tuple(float(v) for v in row) for row in vectors)


def hinge_handle_point(plane: LockedPlaneSpec, curve: FoldingCurve) -> Point3:
    """Place the global-angle handle along the terminal rigid direction."""

    frame = build_folding_frame(plane, curve)
    pose = living_hinge_pose(plane, curve)
    center = _v3(pose.end_center)
    tangent = _v3(pose.end_tangent)
    distance = max(2.0, 0.18 * frame.length_mm)
    point = center + tangent * distance
    return tuple(float(v) for v in point)


def fold_angle_from_handle(plane: LockedPlaneSpec, curve: FoldingCurve, point: Point3) -> float:
    """Infer the terminal rigid-body angle from the direction handle.

    The handle is anchored at the current curve endpoint and points in the
    terminal tangent direction.  This remains intuitive for circular, S-shaped
    and strongly redistributed folds alike.
    """

    frame = build_folding_frame(plane, curve)
    pose = living_hinge_pose(plane, curve)
    vector = _v3(point) - _v3(pose.end_center)
    x = float(np.dot(vector, _v3(frame.axis)))
    z = float(np.dot(vector, _v3(frame.normal)))
    if math.hypot(x, z) <= 1.0e-8:
        return normalized_fold_angle_deg(curve.fold_angle_deg)
    wrapped = math.degrees(math.atan2(z, x))
    return unwrap_fold_angle_deg(wrapped, curve.fold_angle_deg)


def living_hinge_region_counts(vertices: Iterable[Iterable[float]], plane: LockedPlaneSpec, curve: FoldingCurve) -> tuple[int, int, int]:
    frame = build_folding_frame(plane, curve)
    points = np.asarray(tuple(vertices), dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 3:
        return 0, 0, 0
    x = (points[:, :3] - _v3(frame.start)[None, :]) @ _v3(frame.axis)
    return int(np.count_nonzero(x <= 1.0e-8)), int(np.count_nonzero((x > 1.0e-8) & (x < frame.length_mm - 1.0e-8))), int(np.count_nonzero(x >= frame.length_mm - 1.0e-8))


def hinge_boundary_segments(vertices: Iterable[Iterable[float]], plane: LockedPlaneSpec, curve: FoldingCurve) -> tuple[tuple[Point3, Point3], tuple[Point3, Point3]]:
    frame = build_folding_frame(plane, curve)
    points = np.asarray(tuple(vertices), dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError("The selected mesh has invalid vertices.")
    start = _v3(frame.start)
    bend = _v3(frame.bend_axis)
    rel = points[:, :3] - start[None, :]
    lateral = rel @ bend
    lo, hi = float(np.min(lateral)), float(np.max(lateral))
    padding = max(0.5, 0.03 * max(1.0, hi - lo))
    lo -= padding
    hi += padding
    start_a = start + bend * lo
    start_b = start + bend * hi
    end = _v3(frame.end)
    end_a = end + bend * lo
    end_b = end + bend * hi
    return (
        (tuple(float(v) for v in start_a), tuple(float(v) for v in start_b)),
        (tuple(float(v) for v in end_a), tuple(float(v) for v in end_b)),
    )


def _deform_living_hinge(vertices: Iterable[Iterable[float]], plane: LockedPlaneSpec, curve: FoldingCurve) -> list[Point3]:
    frame = build_folding_frame(plane, curve)
    points = np.asarray(tuple(vertices), dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 3:
        raise ValueError("The selected mesh has invalid vertices.")
    points = points[:, :3].copy()

    start = _v3(frame.start)
    end = _v3(frame.end)
    axis = _v3(frame.axis)
    bend = _v3(frame.bend_axis)
    normal = _v3(frame.normal)
    rel = points - start[None, :]
    x = rel @ axis
    y = rel @ bend
    z = rel @ normal

    active = (x > 1.0e-8) & (x < frame.length_mm - 1.0e-8)
    moving = x >= frame.length_mm - 1.0e-8
    result = points.copy()
    _table_u, centerline, _table_angles = _living_hinge_table(plane, curve, count=1025)

    if np.any(active):
        active_u = np.clip(x[active] / frame.length_mm, 0.0, 1.0)
        centers = _interpolate_table(centerline, active_u)
        angles = _evaluate_tangent_angles(curve, active_u)
        transported_normal = -np.sin(angles)[:, None] * axis[None, :] + np.cos(angles)[:, None] * normal[None, :]
        result[active] = centers + y[active, None] * bend[None, :] + z[active, None] * transported_normal

    theta = math.radians(normalized_fold_angle_deg(curve.fold_angle_deg))
    end_center = centerline[-1]
    end_tangent = axis * math.cos(theta) + normal * math.sin(theta)
    end_normal = -axis * math.sin(theta) + normal * math.cos(theta)
    if np.any(moving):
        result[moving] = (
            end_center[None, :]
            + (x[moving] - frame.length_mm)[:, None] * end_tangent[None, :]
            + y[moving, None] * bend[None, :]
            + z[moving, None] * end_normal[None, :]
        )

    if curve.normalized_fixed_side() == FoldingFixedSide.END.value:
        rel_terminal = result - end_center[None, :]
        local_x = rel_terminal @ end_tangent
        local_y = rel_terminal @ bend
        local_z = rel_terminal @ end_normal
        result = (
            end[None, :]
            + local_x[:, None] * axis[None, :]
            + local_y[:, None] * bend[None, :]
            + local_z[:, None] * normal[None, :]
        )

    return [tuple(float(v) for v in row) for row in result]


def sample_curve(plane: LockedPlaneSpec, curve: FoldingCurve, *, count: int = 80) -> tuple[Point3, ...]:
    if str(curve.mode) == FoldingMode.LIVING_HINGE.value:
        return _living_hinge_samples(plane, curve, count=count)
    return _sample_free_curve(plane, curve, count=count)


def deform_vertices(vertices: Iterable[Iterable[float]], plane: LockedPlaneSpec, curve: FoldingCurve) -> list[Point3]:
    if str(curve.mode) == FoldingMode.LIVING_HINGE.value:
        return _deform_living_hinge(vertices, plane, curve)
    return _deform_free_curve(vertices, plane, curve)


def _living_hinge_is_straight(curve: FoldingCurve) -> bool:
    samples = np.linspace(0.0, 1.0, 65, dtype=np.float64)
    angles = _evaluate_tangent_angles(curve, samples)
    return bool(np.max(np.abs(angles)) <= 1.0e-12)


def _adaptive_station_count(curve: FoldingCurve) -> int:
    """Choose enough longitudinal stations for a visually smooth, stable fold.

    The old kernel relied entirely on source tessellation.  Sparse triangles
    could therefore bridge the complete hinge and remain flat.  The station
    count is driven by total tangent variation, including S-curves, and is kept
    inside a conservative topology budget.
    """

    samples = np.linspace(0.0, 1.0, 257, dtype=np.float64)
    angles = np.unwrap(_evaluate_tangent_angles(curve, samples))
    total_turn = float(np.sum(np.abs(np.diff(angles))))
    max_step_angle = math.radians(7.5)
    by_angle = int(math.ceil(total_turn / max(max_step_angle, 1.0e-6)))
    by_handles = 4 * (curve.shape_control_count + 1)
    return max(8, min(96, max(by_angle, by_handles)))


def _balanced_station_indices(segment_count: int) -> tuple[int, ...]:
    """Return boundaries first, then increasingly fine dyadic stations.

    If a very large mesh reaches the topology budget early, the already added
    stations are still distributed over the full hinge instead of accumulating
    only near the first boundary.
    """

    count = max(1, int(segment_count))
    order = [0, count]
    queue: list[tuple[int, int]] = [(0, count)]
    while queue:
        left, right = queue.pop(0)
        if right - left <= 1:
            continue
        middle = (left + right) // 2
        order.append(middle)
        queue.append((left, middle))
        queue.append((middle, right))
    return tuple(dict.fromkeys(order))


def _clean_polygon(indices: list[int]) -> list[int]:
    result: list[int] = []
    for value in indices:
        if not result or result[-1] != value:
            result.append(int(value))
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    return result


def _triangulate_polygon(indices: list[int]) -> list[tuple[int, int, int]]:
    polygon = _clean_polygon(indices)
    if len(polygon) < 3:
        return []
    root = polygon[0]
    return [(root, polygon[index], polygon[index + 1]) for index in range(1, len(polygon) - 1)]


def _refine_mesh_longitudinally(source: Any, plane: LockedPlaneSpec, curve: FoldingCurve) -> WorkMesh:
    """Insert exact strip stations into every crossing triangle.

    Splitting by planes, rather than arbitrary triangle midpoints, makes both
    hinge boundaries exact and prevents cracks because intersections are shared
    through an edge/station cache.  Geometry outside the flexible band is left
    untouched.
    """

    result = copy.deepcopy(source)
    vertices = [
        tuple(float(v) for v in point[:3])
        for point in tuple(getattr(source, "vertices", ()) or ())
    ]
    triangles = [
        tuple(int(v) for v in tri[:3])
        for tri in tuple(getattr(source, "triangles", ()) or ())
    ]
    if not vertices or not triangles or not curve.is_living_hinge:
        result.vertices = vertices
        result.triangles = triangles
        return result

    frame = build_folding_frame(plane, curve)
    start = _v3(frame.start)
    axis = _v3(frame.axis)
    coordinates = [float(np.dot(np.asarray(point, dtype=np.float64) - start, axis)) for point in vertices]
    segment_count = _adaptive_station_count(curve)
    stations = np.linspace(0.0, frame.length_mm, segment_count + 1, dtype=np.float64)
    station_indices = _balanced_station_indices(segment_count)

    raw_uvs = getattr(source, "uvs", None)
    uvs: list[tuple[float, float]] | None = None
    if raw_uvs is not None and len(raw_uvs) == len(vertices):
        uvs = [tuple(float(value) for value in uv[:2]) for uv in raw_uvs]

    scale = max(1.0, frame.length_mm)
    epsilon = max(1.0e-9, scale * 1.0e-10)
    initial_vertex_count = len(vertices)
    initial_triangle_count = len(triangles)
    vertex_budget = max(
        initial_vertex_count,
        min(500_000, max(50_000, initial_vertex_count * 6, initial_vertex_count + 20_000)),
    )
    triangle_budget = max(
        initial_triangle_count,
        min(750_000, max(50_000, initial_triangle_count * 6, initial_triangle_count + 20_000)),
    )

    for station_index in station_indices:
        station = float(stations[station_index])
        previous_triangles = triangles
        previous_vertex_count = len(vertices)
        previous_coordinate_count = len(coordinates)
        previous_uv_count = len(uvs) if uvs is not None else 0
        edge_cache: dict[tuple[int, int, int], int] = {}

        def intersection(a: int, b: int) -> int:
            xa = coordinates[a]
            xb = coordinates[b]
            if abs(xa - station) <= epsilon:
                return a
            if abs(xb - station) <= epsilon:
                return b
            key = (min(a, b), max(a, b), station_index)
            cached = edge_cache.get(key)
            if cached is not None:
                return cached
            denominator = xb - xa
            if abs(denominator) <= epsilon:
                return a
            fraction = float(np.clip((station - xa) / denominator, 0.0, 1.0))
            pa = np.asarray(vertices[a], dtype=np.float64)
            pb = np.asarray(vertices[b], dtype=np.float64)
            point = pa + fraction * (pb - pa)
            index = len(vertices)
            vertices.append(tuple(float(value) for value in point))
            coordinates.append(float(station))
            if uvs is not None:
                ua = np.asarray(uvs[a], dtype=np.float64)
                ub = np.asarray(uvs[b], dtype=np.float64)
                uv = ua + fraction * (ub - ua)
                uvs.append((float(uv[0]), float(uv[1])))
            edge_cache[key] = index
            return index

        def clip(triangle: tuple[int, int, int], *, keep_low: bool) -> list[int]:
            polygon: list[int] = []
            sequence = list(triangle)
            for current, following in zip(sequence, sequence[1:] + sequence[:1]):
                xc = coordinates[current]
                xn = coordinates[following]
                current_inside = (
                    xc <= station + epsilon if keep_low else xc >= station - epsilon
                )
                next_inside = (
                    xn <= station + epsilon if keep_low else xn >= station - epsilon
                )
                if current_inside:
                    polygon.append(current)
                if current_inside != next_inside:
                    polygon.append(intersection(current, following))
            return _clean_polygon(polygon)

        refined: list[tuple[int, int, int]] = []
        for triangle in triangles:
            xs = (
                coordinates[triangle[0]],
                coordinates[triangle[1]],
                coordinates[triangle[2]],
            )
            if min(xs) >= station - epsilon or max(xs) <= station + epsilon:
                refined.append(triangle)
                continue
            refined.extend(_triangulate_polygon(clip(triangle, keep_low=True)))
            refined.extend(_triangulate_polygon(clip(triangle, keep_low=False)))
        if len(refined) > triangle_budget or len(vertices) > vertex_budget:
            del vertices[previous_vertex_count:]
            del coordinates[previous_coordinate_count:]
            if uvs is not None:
                del uvs[previous_uv_count:]
            triangles = previous_triangles
            break
        triangles = refined

    result.vertices = vertices
    result.triangles = triangles
    if uvs is not None:
        result.uvs = uvs
    return result


def _unique_mesh_edges(triangles: Iterable[Iterable[int]], vertex_count: int) -> np.ndarray:
    edges: set[tuple[int, int]] = set()
    for triangle in triangles:
        values = tuple(int(value) for value in tuple(triangle)[:3])
        if len(values) != 3:
            continue
        for a, b in ((values[0], values[1]), (values[1], values[2]), (values[2], values[0])):
            if 0 <= a < vertex_count and 0 <= b < vertex_count and a != b:
                edges.add((a, b) if a < b else (b, a))
    if not edges:
        return np.empty((0, 2), dtype=np.int64)
    return np.asarray(sorted(edges), dtype=np.int64)


def _connected_components(edges: np.ndarray, vertex_count: int) -> tuple[np.ndarray, ...]:
    adjacency: list[list[int]] = [[] for _ in range(vertex_count)]
    for a, b in edges:
        adjacency[int(a)].append(int(b))
        adjacency[int(b)].append(int(a))
    visited = np.zeros(vertex_count, dtype=bool)
    components: list[np.ndarray] = []
    for root in range(vertex_count):
        if visited[root]:
            continue
        stack = [root]
        visited[root] = True
        values: list[int] = []
        while stack:
            current = stack.pop()
            values.append(current)
            for neighbour in adjacency[current]:
                if not visited[neighbour]:
                    visited[neighbour] = True
                    stack.append(neighbour)
        components.append(np.asarray(values, dtype=np.int64))
    return tuple(components)


def _rigid_fit(source_points: np.ndarray, target_points: np.ndarray) -> np.ndarray:
    """Best-fit proper rigid transform of one isolated mesh feature."""

    if len(source_points) <= 1:
        return target_points.copy()
    source_center = np.mean(source_points, axis=0)
    target_center = np.mean(target_points, axis=0)
    covariance = (source_points - source_center).T @ (target_points - target_center)
    u, _singular, vt = np.linalg.svd(covariance, full_matrices=False)
    rotation = vt.T @ u.T
    if float(np.linalg.det(rotation)) < 0.0:
        vt[-1, :] *= -1.0
        rotation = vt.T @ u.T
    return (source_points - source_center) @ rotation.T + target_center


def _preserve_local_structure(
    original: np.ndarray,
    target: np.ndarray,
    triangles: Iterable[Iterable[int]],
    plane: LockedPlaneSpec,
    curve: FoldingCurve,
) -> np.ndarray:
    """Project the smooth fold toward an as-rigid-as-possible local metric.

    This lightweight position-based solve preserves original edge lengths while
    retaining the requested centerline as a soft guide.  Both outer regions and
    small disconnected details are hard rigid constraints.  It avoids a SciPy
    dependency and remains deterministic for preview/apply.
    """

    count = len(original)
    edges = _unique_mesh_edges(triangles, count)
    if not len(edges):
        return target

    frame = build_folding_frame(plane, curve)
    x = (original - _v3(frame.start)[None, :]) @ _v3(frame.axis)
    boundary_tolerance = max(1.0e-8, frame.length_mm * 1.0e-9)
    active = (x > boundary_tolerance) & (x < frame.length_mm - boundary_tolerance)
    mobility = active.astype(np.float64)
    result = target.copy()

    # Disconnected details that occupy only a short part of the hinge are moved
    # as exact rigid bodies.  This protects internal bosses/ribs/inserts instead
    # of smearing them through the curvature field.
    rigid_mask = np.zeros(count, dtype=bool)
    for component in _connected_components(edges, count):
        if len(component) <= 1:
            continue
        component_x = x[component]
        span = float(np.ptp(component_x))
        if np.all(active[component]) and span <= 0.22 * frame.length_mm:
            result[component] = _rigid_fit(original[component], target[component])
            rigid_mask[component] = True
    mobility[rigid_mask] = 0.0
    hard_target = result.copy()

    a = edges[:, 0]
    b = edges[:, 1]
    rest = np.linalg.norm(original[b] - original[a], axis=1)
    valid = rest > 1.0e-12
    a = a[valid]
    b = b[valid]
    rest = rest[valid]
    if not len(rest):
        return result

    pinned = mobility <= 0.0
    if len(rest) < 75_000:
        iterations = 48
    elif len(rest) < 250_000:
        iterations = 28
    else:
        iterations = 14
    for _iteration in range(iterations):
        delta = result[b] - result[a]
        lengths = np.linalg.norm(delta, axis=1)
        safe = lengths > 1.0e-12
        correction = np.zeros_like(delta)
        correction[safe] = delta[safe] * ((lengths[safe] - rest[safe]) / lengths[safe])[:, None]

        wa = mobility[a]
        wb = mobility[b]
        total = wa + wb
        movable = total > 0.0
        share_a = np.divide(wa, total, out=np.zeros_like(wa), where=movable)
        share_b = np.divide(wb, total, out=np.zeros_like(wb), where=movable)

        accumulated = np.zeros_like(result)
        weights = np.zeros(count, dtype=np.float64)
        np.add.at(accumulated, a, correction * share_a[:, None])
        np.add.at(accumulated, b, -correction * share_b[:, None])
        np.add.at(weights, a, share_a)
        np.add.at(weights, b, share_b)
        movable_vertices = (weights > 0.0) & (~pinned)
        result[movable_vertices] += 0.65 * accumulated[movable_vertices] / weights[movable_vertices, None]

        # The analytic sweep remains a soft positional guide, preventing a very
        # flexible constraint graph from unwinding or drifting sideways.
        guided = active & ~rigid_mask
        result[guided] += 0.025 * (target[guided] - result[guided])
        result[pinned] = hard_target[pinned]

    return result


def deform_mesh(source: Any, plane: LockedPlaneSpec, curve: FoldingCurve) -> WorkMesh:
    # Legacy free curves retain their exact historical topology and behaviour.
    if not curve.is_living_hinge:
        result = copy.deepcopy(source)
        result.vertices = deform_vertices(getattr(source, "vertices", ()) or (), plane, curve)
        if not getattr(result, "name", ""):
            result.name = "Folded mesh"
        return result

    if _living_hinge_is_straight(curve):
        result = copy.deepcopy(source)
        if not getattr(result, "name", ""):
            result.name = "Folded mesh"
        return result

    refined = _refine_mesh_longitudinally(source, plane, curve)
    original = np.asarray(tuple(getattr(refined, "vertices", ()) or ()), dtype=np.float64)
    if original.ndim != 2 or original.shape[1] < 3:
        raise ValueError("The selected mesh has invalid vertices.")
    original = original[:, :3].copy()
    target = np.asarray(_deform_living_hinge(original, plane, curve), dtype=np.float64)
    if curve.normalized_deformation_mode() == FoldingDeformationMode.PRESERVE_STRUCTURE.value:
        target = _preserve_local_structure(original, target, getattr(refined, "triangles", ()) or (), plane, curve)
    refined.vertices = [tuple(float(value) for value in row) for row in target]
    if not getattr(refined, "name", ""):
        refined.name = "Folded mesh"
    return refined


def serialize_mesh(mesh: Any) -> dict[str, Any]:
    metadata = copy.deepcopy(dict(getattr(mesh, "metadata", {}) or {}))
    metadata.pop("folding_source", None)
    return {
        "name": str(getattr(mesh, "name", "") or "Fold source"),
        "vertices": [tuple(float(v) for v in p[:3]) for p in tuple(getattr(mesh, "vertices", ()) or ())],
        "triangles": [tuple(int(v) for v in t[:3]) for t in tuple(getattr(mesh, "triangles", ()) or ())],
        "color": str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
        "material": copy.deepcopy(getattr(mesh, "material", None)),
        "engraving": copy.deepcopy(getattr(mesh, "engraving", None)),
        "uvs": copy.deepcopy(getattr(mesh, "uvs", None)),
        "texture_projections": copy.deepcopy(getattr(mesh, "texture_projections", []) or []),
        "metadata": metadata,
        "mesh_id": str(getattr(mesh, "mesh_id", "") or ""),
    }


def mesh_from_serialized(data: Any) -> WorkMesh:
    if not isinstance(data, dict):
        raise ValueError("Stored Folding source mesh is missing.")
    mesh = WorkMesh(
        name=str(data.get("name") or "Fold source"),
        vertices=[tuple(float(v) for v in p[:3]) for p in tuple(data.get("vertices") or ())],
        triangles=[tuple(int(v) for v in t[:3]) for t in tuple(data.get("triangles") or ())],
        color=str(data.get("color") or "#B8B8B8"),
    )
    mesh.material = copy.deepcopy(data.get("material"))
    mesh.engraving = copy.deepcopy(data.get("engraving"))
    mesh.uvs = copy.deepcopy(data.get("uvs"))
    mesh.texture_projections = copy.deepcopy(data.get("texture_projections") or [])
    mesh.metadata = copy.deepcopy(dict(data.get("metadata") or {}))
    if str(data.get("mesh_id") or ""):
        mesh.mesh_id = str(data.get("mesh_id"))
    return mesh


__all__ = [
    "FoldingFrame",
    "LivingHingePose",
    "arbitrary_face_plane",
    "build_folding_frame",
    "control_points",
    "deform_mesh",
    "deform_vertices",
    "displacement_coefficients",
    "fold_angle_from_handle",
    "hinge_boundary_segments",
    "hinge_handle_point",
    "living_hinge_pose",
    "living_hinge_region_counts",
    "mesh_from_serialized",
    "normalized_fold_angle_deg",
    "unwrap_fold_angle_deg",
    "offset_from_control_point",
    "resample_shape_angles",
    "sample_curve",
    "serialize_mesh",
    "shape_control_fractions",
    "shape_handle_normals",
    "shape_handle_points",
]

# -*- coding: utf-8 -*-
"""Small, dependency-free camera motion classifier used by diagnostics.

The viewport renderer only reports that the camera changed.  Performance work
needs a more useful distinction because pan, zoom and orbit stress different
parts of projected overlays.  This module compares two rendered camera states
without importing Qt or VTK types directly.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

Vec3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class CameraState:
    position: Vec3
    focal_point: Vec3
    view_up: Vec3
    parallel_scale: float
    view_angle: float
    parallel_projection: bool


def capture_camera_state(renderer: Any | None) -> CameraState | None:
    if renderer is None:
        return None
    try:
        camera = renderer.GetActiveCamera()
        return CameraState(
            position=_vec3(camera.GetPosition()),
            focal_point=_vec3(camera.GetFocalPoint()),
            view_up=_normalized(_vec3(camera.GetViewUp())),
            parallel_scale=float(camera.GetParallelScale()),
            view_angle=float(camera.GetViewAngle()),
            parallel_projection=bool(camera.GetParallelProjection()),
        )
    except Exception:
        return None


def classify_camera_motion(previous: CameraState | None, current: CameraState | None) -> str:
    """Return ``pan``, ``zoom``, ``orbit``, ``mixed``, ``static`` or ``initial``."""

    if current is None:
        return "unknown"
    if previous is None:
        return "initial"

    scene_scale = max(
        _distance(previous.position, previous.focal_point),
        _distance(current.position, current.focal_point),
        abs(previous.parallel_scale),
        abs(current.parallel_scale),
        1.0,
    )
    position_delta = _sub(current.position, previous.position)
    focal_delta = _sub(current.focal_point, previous.focal_point)
    position_moved = _length(position_delta) > scene_scale * 1.0e-9
    focal_moved = _length(focal_delta) > scene_scale * 1.0e-9

    previous_direction = _normalized(_sub(previous.focal_point, previous.position))
    current_direction = _normalized(_sub(current.focal_point, current.position))
    direction_changed = _distance(previous_direction, current_direction) > 1.0e-8
    up_changed = _distance(previous.view_up, current.view_up) > 1.0e-8
    projection_changed = previous.parallel_projection != current.parallel_projection

    scale_changed = not math.isclose(
        previous.parallel_scale,
        current.parallel_scale,
        rel_tol=1.0e-9,
        abs_tol=max(1.0e-12, scene_scale * 1.0e-12),
    )
    angle_changed = not math.isclose(previous.view_angle, current.view_angle, rel_tol=1.0e-9, abs_tol=1.0e-10)
    distance_changed = not math.isclose(
        _distance(previous.position, previous.focal_point),
        _distance(current.position, current.focal_point),
        rel_tol=1.0e-9,
        abs_tol=max(1.0e-12, scene_scale * 1.0e-12),
    )
    zoom_changed = scale_changed or angle_changed or (distance_changed and not direction_changed)

    if not any((position_moved, focal_moved, direction_changed, up_changed, projection_changed, zoom_changed)):
        return "static"

    same_translation = _distance(position_delta, focal_delta) <= scene_scale * 1.0e-8
    if same_translation and (position_moved or focal_moved) and not any(
        (direction_changed, up_changed, projection_changed, scale_changed, angle_changed, distance_changed)
    ):
        return "pan"

    if zoom_changed and not any((direction_changed, up_changed, projection_changed)):
        return "zoom"

    if (direction_changed or up_changed) and not any((scale_changed, angle_changed, projection_changed)):
        return "orbit"

    return "mixed"


def _vec3(value: Any) -> Vec3:
    values = tuple(float(component) for component in value)
    return (values[0], values[1], values[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _length(value: Vec3) -> float:
    return math.sqrt(value[0] * value[0] + value[1] * value[1] + value[2] * value[2])


def _distance(a: Vec3, b: Vec3) -> float:
    return _length(_sub(a, b))


def _normalized(value: Vec3) -> Vec3:
    length = _length(value)
    if length <= 1.0e-30:
        return (0.0, 0.0, 0.0)
    return (value[0] / length, value[1] / length, value[2] / length)


__all__ = ["CameraState", "capture_camera_state", "classify_camera_motion"]

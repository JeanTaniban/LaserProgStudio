# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from dataclasses import dataclass

from .contracts import FixedPlanarView, LockedPlaneSpec, Vec3


@dataclass(frozen=True, slots=True)
class FixedViewCameraSpec:
    """Camera and drawing-plane mapping for one fixed view."""

    view: FixedPlanarView
    camera_from: Vec3
    camera_up: Vec3
    u_axis: Vec3
    v_axis: Vec3
    normal: Vec3

    @property
    def camera_forward(self) -> Vec3:
        return (-self.camera_from[0], -self.camera_from[1], -self.camera_from[2])


_FIXED_VIEW_SPECS: dict[FixedPlanarView, FixedViewCameraSpec] = {
    FixedPlanarView.TOP: FixedViewCameraSpec(FixedPlanarView.TOP, (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    FixedPlanarView.BOTTOM: FixedViewCameraSpec(FixedPlanarView.BOTTOM, (0.0, 0.0, -1.0), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0)),
    FixedPlanarView.FRONT: FixedViewCameraSpec(FixedPlanarView.FRONT, (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
    FixedPlanarView.BACK: FixedViewCameraSpec(FixedPlanarView.BACK, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    FixedPlanarView.LEFT: FixedViewCameraSpec(FixedPlanarView.LEFT, (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (-1.0, 0.0, 0.0)),
    FixedPlanarView.RIGHT: FixedViewCameraSpec(FixedPlanarView.RIGHT, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
}


def fixed_view_specs() -> tuple[FixedViewCameraSpec, ...]:
    return tuple(_FIXED_VIEW_SPECS[view] for view in FixedPlanarView)


def fixed_view_spec(view: FixedPlanarView | str) -> FixedViewCameraSpec:
    return _FIXED_VIEW_SPECS[view if isinstance(view, FixedPlanarView) else FixedPlanarView(str(view))]


def _dot(a: Vec3, b: Vec3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _norm(v: Vec3) -> float:
    return math.sqrt(max(_dot(v, v), 0.0))


def _unit(v: Vec3, fallback: Vec3 = (0.0, 0.0, -1.0)) -> Vec3:
    n = _norm(v)
    if not math.isfinite(n) or n <= 1e-12:
        return fallback
    return (float(v[0]) / n, float(v[1]) / n, float(v[2]) / n)


def nearest_locked_view_from_forward(forward: Vec3) -> FixedPlanarView:
    """Return the orthographic view closest to the current camera direction."""

    fwd = _unit(forward)
    best = max(fixed_view_specs(), key=lambda spec: _dot(fwd, spec.camera_forward))
    return best.view


def nearest_locked_view_from_camera(position: Vec3, focal_point: Vec3) -> FixedPlanarView:
    return nearest_locked_view_from_forward(_sub(focal_point, position))


def make_locked_plane(view: FixedPlanarView | str, *, depth: float = 0.0) -> LockedPlaneSpec:
    spec = fixed_view_spec(view)
    return LockedPlaneSpec(spec.view, spec.normal, spec.u_axis, spec.v_axis, float(depth))


def plane_depth_for_world_point(plane: LockedPlaneSpec, point: Vec3) -> float:
    return _dot(plane.normal, point)


def plane_from_first_hit(view: FixedPlanarView | str, hit_point: Vec3 | None = None) -> LockedPlaneSpec:
    plane = make_locked_plane(view, depth=0.0)
    if hit_point is None:
        return plane
    return plane.with_depth(plane_depth_for_world_point(plane, hit_point))


def world_to_plane(plane: LockedPlaneSpec, point: Vec3) -> tuple[float, float]:
    p = tuple(float(v) for v in point)
    base = (plane.normal[0] * plane.depth, plane.normal[1] * plane.depth, plane.normal[2] * plane.depth)
    rel = _sub(p, base)
    return (_dot(rel, plane.u_axis), _dot(rel, plane.v_axis))


def plane_to_world(plane: LockedPlaneSpec, u: float, v: float) -> Vec3:
    n, ax_u, ax_v = plane.normal, plane.u_axis, plane.v_axis
    return (
        n[0] * plane.depth + ax_u[0] * float(u) + ax_v[0] * float(v),
        n[1] * plane.depth + ax_u[1] * float(u) + ax_v[1] * float(v),
        n[2] * plane.depth + ax_u[2] * float(u) + ax_v[2] * float(v),
    )


def clamp_world_point_to_plane(plane: LockedPlaneSpec, point: Vec3) -> Vec3:
    u, v = world_to_plane(plane, point)
    return plane_to_world(plane, u, v)

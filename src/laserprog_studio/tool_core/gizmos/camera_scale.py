"""Camera-aware gizmo sizing helpers.

Use these helpers for line/ring/mesh gizmos that are expressed in world units
but must keep a stable perceived size on screen. Point sprites can stay in
pixels; true 3D handles should convert their target pixel radius with this
module every redraw.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt, tan, radians
from typing import Any

Point3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class CameraScaleResult:
    world_units_per_pixel: float
    pixel_radius: float
    world_radius: float
    mode: str


def _call(obj: Any, name: str, default: Any) -> Any:
    try:
        value = getattr(obj, name)
        return value() if callable(value) else value
    except Exception:
        return default


def _vec3(value: Any, default: Point3) -> Point3:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return default


def _distance(a: Point3, b: Point3) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def viewport_height_px(viewport: Any, fallback: int = 800) -> int:
    """Return the active viewport height, supporting Qt widgets and VTK renderers."""
    if viewport is None:
        return int(fallback)
    for attr in ("height", "GetSize"):
        try:
            value = getattr(viewport, attr)
            value = value() if callable(value) else value
            if isinstance(value, tuple | list) and len(value) >= 2:
                return max(1, int(value[1]))
            return max(1, int(value))
        except Exception:
            pass
    try:
        size = viewport.GetRenderWindow().GetSize()
        return max(1, int(size[1]))
    except Exception:
        return int(fallback)


def world_units_per_pixel(camera: Any, viewport_height: int, world_position: Point3, *, fallback: float = 0.05) -> tuple[float, str]:
    """Compute world units represented by one screen pixel near a point."""
    height = max(1, int(viewport_height))
    if camera is None:
        return (float(fallback), "fallback")
    try:
        parallel = bool(camera.GetParallelProjection())
    except Exception:
        parallel = bool(_call(camera, "parallel_projection", False))
    if parallel:
        scale = float(_call(camera, "GetParallelScale", _call(camera, "parallel_scale", 20.0)))
        return (max(1.0e-9, (2.0 * scale) / float(height)), "parallel")
    position = _vec3(_call(camera, "GetPosition", _call(camera, "position", (0.0, 0.0, 1.0))), (0.0, 0.0, 1.0))
    distance = max(1.0e-6, _distance(position, world_position))
    view_angle = float(_call(camera, "GetViewAngle", _call(camera, "view_angle", 30.0)))
    visible_height = 2.0 * distance * tan(radians(view_angle) * 0.5)
    return (max(1.0e-9, visible_height / float(height)), "perspective")


def pixel_radius_to_world(camera: Any, viewport: Any, world_position: Point3, pixel_radius: float, *, fallback_world_per_px: float = 0.05) -> CameraScaleResult:
    height = viewport_height_px(viewport)
    units_per_px, mode = world_units_per_pixel(camera, height, world_position, fallback=fallback_world_per_px)
    px = max(1.0, float(pixel_radius))
    return CameraScaleResult(units_per_px, px, units_per_px * px, mode)


def plotter_pixel_radius_to_world(plotter: Any, world_position: Point3, pixel_radius: float, *, fallback_world_per_px: float = 0.05) -> CameraScaleResult:
    camera = None
    try:
        camera = plotter.camera
    except Exception:
        try:
            camera = plotter.renderer.GetActiveCamera()
        except Exception:
            camera = None
    viewport = plotter
    try:
        viewport = plotter.renderer
    except Exception:
        pass
    return pixel_radius_to_world(camera, viewport, world_position, pixel_radius, fallback_world_per_px=fallback_world_per_px)


@dataclass(frozen=True, slots=True)
class AxisBillboardBasis:
    """Stable axis-locked basis for viewport GUI guides.

    This is not a free billboard.  The normal snaps to the world axis that is
    closest to the camera direction, like transform scale handles: from a top
    view guides live in XY, from a front/back view in XZ, and from a side view
    in YZ.  That avoids the unpleasant spinning of direct camera-facing UI.
    """

    axis: str
    normal: Point3
    u: Point3
    v: Point3

    def point(self, center: Point3, u_offset: float, v_offset: float, normal_offset: float = 0.0) -> Point3:
        return (
            float(center[0]) + self.u[0] * float(u_offset) + self.v[0] * float(v_offset) + self.normal[0] * float(normal_offset),
            float(center[1]) + self.u[1] * float(u_offset) + self.v[1] * float(v_offset) + self.normal[1] * float(normal_offset),
            float(center[2]) + self.u[2] * float(u_offset) + self.v[2] * float(v_offset) + self.normal[2] * float(normal_offset),
        )


def _normalize(vec: Point3, fallback: Point3 = (0.0, 0.0, 1.0)) -> Point3:
    length = sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)
    if length <= 1.0e-9:
        return fallback
    return (vec[0] / length, vec[1] / length, vec[2] / length)


def axis_locked_billboard_basis(camera: Any | None) -> AxisBillboardBasis:
    """Return a camera-dependent GUI basis snapped to the nearest world axis.

    The chosen plane is stable and discrete.  It updates only when the nearest
    camera axis changes, so gizmos do not continuously twist while the user
    orbits the scene.
    """
    if camera is None:
        return AxisBillboardBasis("+Z", (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
    position = _vec3(_call(camera, "GetPosition", _call(camera, "position", (0.0, 0.0, 1.0))), (0.0, 0.0, 1.0))
    focal = _vec3(_call(camera, "GetFocalPoint", _call(camera, "focal_point", (0.0, 0.0, 0.0))), (0.0, 0.0, 0.0))
    # Direction from scene/focal point toward the camera.  The sign is useful
    # for z-offsets, while the absolute dominant axis chooses the GUI plane.
    toward_camera = _normalize((position[0] - focal[0], position[1] - focal[1], position[2] - focal[2]))
    ax, ay, az = abs(toward_camera[0]), abs(toward_camera[1]), abs(toward_camera[2])
    if ax >= ay and ax >= az:
        sign = 1.0 if toward_camera[0] >= 0.0 else -1.0
        normal = (sign, 0.0, 0.0)
        return AxisBillboardBasis(("+" if sign > 0 else "-") + "X", normal, (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    if ay >= ax and ay >= az:
        sign = 1.0 if toward_camera[1] >= 0.0 else -1.0
        normal = (0.0, sign, 0.0)
        return AxisBillboardBasis(("+" if sign > 0 else "-") + "Y", normal, (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    sign = 1.0 if toward_camera[2] >= 0.0 else -1.0
    normal = (0.0, 0.0, sign)
    return AxisBillboardBasis(("+" if sign > 0 else "-") + "Z", normal, (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


def plotter_axis_locked_billboard_basis(plotter: Any) -> AxisBillboardBasis:
    camera = None
    try:
        camera = plotter.camera
    except Exception:
        try:
            camera = plotter.renderer.GetActiveCamera()
        except Exception:
            camera = None
    return axis_locked_billboard_basis(camera)

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Any, Iterable

from laserprog_studio.planar_tools import FixedPlanarView, LockedPlaneSpec, clamp_world_point_to_plane, make_locked_plane, plane_to_world, world_to_plane

from .models import Point3, point3


def _dot(a: Point3, b: Point3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _unit(value: Iterable[float], fallback: Point3) -> Point3:
    x, y, z = point3(value)
    length = sqrt(x * x + y * y + z * z)
    if length <= 1.0e-12:
        return fallback
    return (x / length, y / length, z / length)


@dataclass(slots=True)
class MechanicalWorkPlane:
    """Serializable arbitrary-orientation work plane for one mechanism.

    The construction plane is the support face. Gear centres are offset from it
    along ``normal`` so their bottom face lies on the selected support.
    """

    view: str = FixedPlanarView.TOP.value
    normal: Point3 = (0.0, 0.0, 1.0)
    u_axis: Point3 = (1.0, 0.0, 0.0)
    v_axis: Point3 = (0.0, 1.0, 0.0)
    depth: float = 0.0
    anchor_world: Point3 = (0.0, 0.0, 0.0)
    support_object_id: str | None = None
    support_object_index: int | None = None

    def normalized(self) -> "MechanicalWorkPlane":
        normal = _unit(self.normal, (0.0, 0.0, 1.0))
        u_raw = point3(self.u_axis)
        u_projected = (
            u_raw[0] - normal[0] * _dot(u_raw, normal),
            u_raw[1] - normal[1] * _dot(u_raw, normal),
            u_raw[2] - normal[2] * _dot(u_raw, normal),
        )
        u_axis = _unit(u_projected, (1.0, 0.0, 0.0))
        v_axis = _unit(_cross(normal, u_axis), (0.0, 1.0, 0.0))
        u_axis = _unit(_cross(v_axis, normal), u_axis)
        self.normal = normal
        self.u_axis = u_axis
        self.v_axis = v_axis
        self.depth = float(self.depth)
        self.anchor_world = self.clamp(self.anchor_world)
        self.view = str(getattr(self.view, "value", self.view) or FixedPlanarView.TOP.value)
        return self

    @classmethod
    def from_locked(
        cls,
        plane: LockedPlaneSpec,
        *,
        anchor_world: Point3,
        support_object_id: str | None = None,
        support_object_index: int | None = None,
    ) -> "MechanicalWorkPlane":
        return cls(
            view=plane.view.value,
            normal=point3(plane.normal),
            u_axis=point3(plane.u_axis),
            v_axis=point3(plane.v_axis),
            depth=float(plane.depth),
            anchor_world=point3(anchor_world),
            support_object_id=support_object_id,
            support_object_index=support_object_index,
        ).normalized()

    @classmethod
    def horizontal_at(cls, point: Point3) -> "MechanicalWorkPlane":
        p = point3(point)
        plane = make_locked_plane(FixedPlanarView.TOP, depth=p[2])
        return cls.from_locked(plane, anchor_world=p)

    def locked(self) -> LockedPlaneSpec:
        try:
            view = FixedPlanarView(str(self.view))
        except Exception:
            view = FixedPlanarView.TOP
        return LockedPlaneSpec(view, self.normal, self.u_axis, self.v_axis, float(self.depth))

    def clamp(self, point: Point3) -> Point3:
        return point3(clamp_world_point_to_plane(self.locked(), point3(point)))

    def coordinates(self, point: Point3) -> tuple[float, float]:
        u, v = world_to_plane(self.locked(), point3(point))
        return float(u), float(v)

    def point(self, u: float, v: float, *, normal_offset: float = 0.0) -> Point3:
        base = point3(plane_to_world(self.locked(), float(u), float(v)))
        return self.offset(base, normal_offset)

    def offset(self, point: Point3, distance: float) -> Point3:
        p = point3(point)
        d = float(distance)
        return (
            p[0] + self.normal[0] * d,
            p[1] + self.normal[1] * d,
            p[2] + self.normal[2] * d,
        )

    def support_point_for_gear_center(self, center: Point3) -> Point3:
        return self.clamp(center)

    def gear_center(
        self,
        support_point: Point3,
        thickness_mm: float,
        *,
        layer: int = 0,
        layer_gap_mm: float = 0.0,
    ) -> Point3:
        """Return the centre of a gear carried by one axial layer.

        ``layer_gap_mm`` is the free axial spacing between neighbouring gear
        bodies.  Keeping this spacing explicit is important for compound trains:
        two different mesh stages must not touch merely because their layers are
        adjacent.  Standalone gears keep the historical zero-gap behaviour.
        """

        thickness = max(0.1, float(thickness_mm))
        layer_index = max(0, int(layer))
        gap = max(0.0, float(layer_gap_mm))
        offset = 0.5 * thickness + layer_index * (thickness + gap)
        return self.offset(self.clamp(support_point), offset)

    def radial_point(self, center: Point3, radius: float, angle_deg: float) -> Point3:
        angle = radians(float(angle_deg))
        c, s = cos(angle), sin(angle)
        base = self.clamp(center)
        r = max(0.0, float(radius))
        return (
            base[0] + r * (self.u_axis[0] * c + self.v_axis[0] * s),
            base[1] + r * (self.u_axis[1] * c + self.v_axis[1] * s),
            base[2] + r * (self.u_axis[2] * c + self.v_axis[2] * s),
        )

    def angle_deg(self, center: Point3, point: Point3) -> float:
        c = self.clamp(center)
        p = self.clamp(point)
        rel = (p[0] - c[0], p[1] - c[1], p[2] - c[2])
        return float(atan2(_dot(rel, self.v_axis), _dot(rel, self.u_axis)) * 180.0 / 3.141592653589793)


def pick_work_plane(ctx: Any, screen_pos: tuple[float, float], *, diagnostics: bool = False) -> MechanicalWorkPlane | None:
    """Raycast a real face and convert it to the persistent mechanical plane."""

    from laserprog_studio.tool_api import plan2d

    picked = plan2d.pick_plan_surface_anchor_by_raycast(
        ctx,
        screen_pos,
        log_diagnostics=bool(diagnostics),
        diagnostics_label="mechanical-work-plane",
    )
    if not picked.hit:
        return None
    return MechanicalWorkPlane.from_locked(
        picked.plane,
        anchor_world=picked.anchor_world,
        support_object_id=picked.object_id,
        support_object_index=picked.object_index,
    )


def placement_point(ctx: Any, screen_pos: tuple[float, float] | None, event_world_pos: Point3 | None, plane: MechanicalWorkPlane) -> Point3 | None:
    """Resolve a click by scene raycast, then lock it back onto the work plane.

    Raycast gives the intuitive location on the clicked part. Clamping is the
    invariant that prevents subsequent points and Bézier handles drifting in 3D.
    """

    if screen_pos is not None:
        try:
            from laserprog_studio.tool_api import plan2d

            picked = plan2d.pick_plan_surface_anchor_by_raycast(ctx, screen_pos)
            if picked.hit:
                return plane.clamp(picked.anchor_world)
            projected = plan2d.project_screen_to_locked_plane(ctx, screen_pos, plane.locked(), event_world_pos=event_world_pos)
            return plane.clamp(projected)
        except Exception:
            pass
    if event_world_pos is not None:
        return plane.clamp(event_world_pos)
    return None


__all__ = ["MechanicalWorkPlane", "pick_work_plane", "placement_point"]

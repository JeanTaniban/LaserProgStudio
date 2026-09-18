# -*- coding: utf-8 -*-
from __future__ import annotations

from math import cos, pi, radians, sin, sqrt
from typing import Iterable

from laserprog_studio.domain.work_model import WorkMesh

from .models import GearSpec, Point3, RackSpec, point3
from .plane import MechanicalWorkPlane


def _add(a: Point3, b: Point3) -> Point3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Point3, b: Point3) -> Point3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(v: Point3, value: float) -> Point3:
    return (v[0] * value, v[1] * value, v[2] * value)


def _dot(a: Point3, b: Point3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Point3, b: Point3) -> Point3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _unit(v: Point3, fallback: Point3 = (1.0, 0.0, 0.0)) -> Point3:
    length = sqrt(_dot(v, v))
    if length <= 1.0e-12:
        return fallback
    return _scale(v, 1.0 / length)


def rack_axis(rack: RackSpec) -> Point3:
    return _unit(_sub(rack.end, rack.start))


def rack_toward_pinion(rack: RackSpec, plane: MechanicalWorkPlane) -> Point3:
    base = _unit(_cross(plane.normal, rack_axis(rack)), plane.v_axis)
    return _scale(base, 1.0 if int(rack.contact_sign) >= 0 else -1.0)


def rack_motion_sign(rack: RackSpec, plane: MechanicalWorkPlane) -> float:
    """Signed rack travel per positive pinion arc length."""

    axis = rack_axis(rack)
    # Contact vector points from pinion centre to rack pitch line.
    contact = _scale(rack_toward_pinion(rack, plane), -1.0)
    tangent = _cross(plane.normal, contact)
    return 1.0 if _dot(tangent, axis) >= 0.0 else -1.0


def snap_rack_to_pinion(
    rack: RackSpec,
    pinion: GearSpec,
    plane: MechanicalWorkPlane,
) -> RackSpec:
    """Snap a user-drawn rack span to the pinion pitch-circle tangent."""

    rack.normalized()
    raw_start = plane.clamp(rack.start)
    raw_end = plane.clamp(rack.end)
    axis = _unit(_sub(raw_end, raw_start), plane.u_axis)
    length = max(2.0 * rack.tooth_pitch_mm, sqrt(_dot(_sub(raw_end, raw_start), _sub(raw_end, raw_start))))
    midpoint = _scale(_add(raw_start, raw_end), 0.5)
    pinion_center = plane.clamp(pinion.center)
    base_normal = _unit(_cross(plane.normal, axis), plane.v_axis)
    toward = base_normal if _dot(_sub(pinion_center, midpoint), base_normal) >= 0.0 else _scale(base_normal, -1.0)
    # Keep the user's tangential placement. Only the normal component is
    # constrained to the pitch-circle tangent; the rack is not forcibly
    # re-centred on the pinion after every endpoint drag.
    along_axis = _dot(_sub(midpoint, pinion_center), axis)
    pitch_midpoint = _add(
        _add(pinion_center, _scale(axis, along_axis)),
        _scale(toward, -pinion.pitch_radius_mm),
    )
    rack.contact_sign = 1 if _dot(toward, base_normal) >= 0.0 else -1
    rack.start = _sub(pitch_midpoint, _scale(axis, 0.5 * length))
    rack.end = _add(pitch_midpoint, _scale(axis, 0.5 * length))
    rack.pinion_gear_id = pinion.id
    rack.module_mm = pinion.module_mm
    rack.pressure_angle_deg = pinion.pressure_angle_deg
    return rack.normalized()


def _top_profile(rack: RackSpec) -> list[tuple[float, float]]:
    length = rack.length_mm
    pitch = rack.tooth_pitch_mm
    addendum = rack.module_mm
    dedendum = 1.25 * rack.module_mm
    root_y = -dedendum
    pressure = radians(rack.pressure_angle_deg)
    flank_run = max(0.08 * pitch, (addendum + dedendum) * max(0.05, sin(pressure)))
    half_tip = max(0.06 * pitch, 0.25 * pitch - 0.5 * rack.backlash_mm - 0.5 * flank_run)
    half_root = min(0.48 * pitch, half_tip + flank_run)
    phase = float(rack.phase_mm) % pitch

    points: list[tuple[float, float]] = [(0.0, root_y)]
    first = int((-phase / pitch) - 2)
    last = int(((length - phase) / pitch) + 2)
    for index in range(first, last + 1):
        center = phase + (index + 0.5) * pitch
        candidates = (
            (center - half_root, root_y),
            (center - half_tip, addendum),
            (center + half_tip, addendum),
            (center + half_root, root_y),
        )
        for x, y in candidates:
            if 0.0 < x < length:
                points.append((x, y))
    points.append((length, root_y))
    points.sort(key=lambda item: item[0])
    deduped: list[tuple[float, float]] = []
    for point in points:
        if deduped and abs(point[0] - deduped[-1][0]) <= 1.0e-9:
            if point[1] > deduped[-1][1]:
                deduped[-1] = point
        else:
            deduped.append(point)
    return deduped


def _polygon_area(points: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        points[i][0] * points[(i + 1) % len(points)][1]
        - points[(i + 1) % len(points)][0] * points[i][1]
        for i in range(len(points))
    )


def _point_in_triangle(p, a, b, c) -> bool:
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1, d2, d3 = sign(p, a, b), sign(p, b, c), sign(p, c, a)
    has_neg = d1 < -1.0e-10 or d2 < -1.0e-10 or d3 < -1.0e-10
    has_pos = d1 > 1.0e-10 or d2 > 1.0e-10 or d3 > 1.0e-10
    return not (has_neg and has_pos)


def _triangulate_polygon(points: list[tuple[float, float]]) -> list[tuple[int, int, int]]:
    if len(points) < 3:
        return []
    indices = list(range(len(points)))
    if _polygon_area(points) < 0.0:
        indices.reverse()
    triangles: list[tuple[int, int, int]] = []
    guard = 0
    while len(indices) > 3 and guard < len(points) * len(points):
        guard += 1
        ear_found = False
        for offset, current in enumerate(indices):
            previous = indices[offset - 1]
            following = indices[(offset + 1) % len(indices)]
            a, b, c = points[previous], points[current], points[following]
            cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            if cross <= 1.0e-10:
                continue
            if any(
                candidate not in {previous, current, following}
                and _point_in_triangle(points[candidate], a, b, c)
                for candidate in indices
            ):
                continue
            triangles.append((previous, current, following))
            del indices[offset]
            ear_found = True
            break
        if not ear_found:
            break
    if len(indices) == 3:
        triangles.append(tuple(indices))
    if not triangles:
        # Defensive fallback for pathological clipping at a very short length.
        triangles = [(0, index, index + 1) for index in range(1, len(points) - 1)]
    return triangles


def build_rack_mesh(
    rack: RackSpec,
    *,
    plane: MechanicalWorkPlane,
    name: str | None = None,
) -> WorkMesh:
    rack.normalized()
    axis = rack_axis(rack)
    toward = rack_toward_pinion(rack, plane)
    body_bottom = -max(rack.body_height_mm, 1.5 * rack.module_mm)
    top = _top_profile(rack)
    polygon = [(0.0, body_bottom), (rack.length_mm, body_bottom), *reversed(top)]
    faces = _triangulate_polygon(polygon)
    thickness = rack.thickness_mm

    def world(x: float, y: float, z: float) -> Point3:
        base = rack.start
        return (
            base[0] + axis[0] * x + toward[0] * y + plane.normal[0] * z,
            base[1] + axis[1] * x + toward[1] * y + plane.normal[1] * z,
            base[2] + axis[2] * x + toward[2] * y + plane.normal[2] * z,
        )

    vertices = [world(x, y, 0.0) for x, y in polygon]
    vertices.extend(world(x, y, thickness) for x, y in polygon)
    count = len(polygon)
    triangles: list[tuple[int, int, int]] = []
    triangles.extend((a, c, b) for a, b, c in faces)
    triangles.extend((a + count, b + count, c + count) for a, b, c in faces)
    for index in range(count):
        following = (index + 1) % count
        triangles.extend(
            (
                (index, following, following + count),
                (index, following + count, index + count),
            )
        )

    mesh = WorkMesh(name=name or rack.name, vertices=vertices, triangles=triangles, color=rack.color)
    mesh.metadata.update(
        {
            "mechanical_generated": True,
            "mechanical_element_kind": "rack",
            "mechanical_rack_id": rack.id,
            "mechanical_pinion_gear_id": rack.pinion_gear_id,
            "module_mm": rack.module_mm,
            "rack_length_mm": rack.length_mm,
            "rack_tooth_count": rack.tooth_count,
        }
    )
    return mesh


def rack_bounds(racks: Iterable[RackSpec], plane: MechanicalWorkPlane) -> tuple[float, float, float, float, float, float] | None:
    points: list[Point3] = []
    for rack in racks:
        toward = rack_toward_pinion(rack, plane)
        for endpoint in (rack.start, rack.end):
            points.append(endpoint)
            points.append(_add(endpoint, _scale(toward, rack.module_mm)))
            points.append(_sub(endpoint, _scale(toward, rack.body_height_mm)))
            points.append(plane.offset(endpoint, rack.thickness_mm))
    if not points:
        return None
    return (
        min(point[0] for point in points),
        min(point[1] for point in points),
        min(point[2] for point in points),
        max(point[0] for point in points),
        max(point[1] for point in points),
        max(point[2] for point in points),
    )


__all__ = [
    "build_rack_mesh",
    "rack_axis",
    "rack_bounds",
    "rack_motion_sign",
    "rack_toward_pinion",
    "snap_rack_to_pinion",
]

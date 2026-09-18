# -*- coding: utf-8 -*-
from __future__ import annotations

from math import cos, pi, radians, sin
from typing import Iterable

from laserprog_studio.domain.work_model import WorkMesh

from .models import GearSpec, Point3, ToothProfile
from .plane import MechanicalWorkPlane


def _outer_profile_points(gear: GearSpec) -> tuple[tuple[float, float], ...]:
    gear.normalized()
    teeth = max(6, int(gear.teeth))
    root = gear.root_radius_mm
    outer = gear.outer_radius_mm
    pitch_angle = 2.0 * pi / teeth
    backlash_angle = min(0.22 * pitch_angle, gear.backlash_mm / max(gear.pitch_radius_mm, 1e-6))
    # Backlash removes material symmetrically from both tooth flanks.  The old
    # implementation shifted both flanks in the same angular direction, so the
    # visible tooth centre no longer matched ``phase_deg`` and mating pairs could
    # look out of phase even when the solver's centre-line relation was correct.
    backlash_half_fraction = 0.5 * backlash_angle / pitch_angle
    profile = gear.profile
    points: list[tuple[float, float]] = []
    for tooth in range(teeth):
        center_angle = tooth * pitch_angle + radians(gear.phase_deg)
        if profile is ToothProfile.TRAPEZOID:
            samples = (
                (-0.50, root),
                (-0.31, root),
                (-0.13 + backlash_half_fraction, outer),
                (0.13 - backlash_half_fraction, outer),
                (0.31, root),
            )
        elif profile is ToothProfile.ROUNDED:
            samples = (
                (-0.50, root),
                (-0.34, root),
                (-0.22 + 0.5 * backlash_half_fraction, 0.55 * root + 0.45 * outer),
                (-0.11 + backlash_half_fraction, outer),
                (0.00, outer * 1.005),
                (0.11 - backlash_half_fraction, outer),
                (0.22 - 0.5 * backlash_half_fraction, 0.55 * root + 0.45 * outer),
                (0.34, root),
            )
        else:
            samples = (
                (-0.50, root),
                (-0.36, root),
                (-0.28, root + 0.18 * (outer - root)),
                (-0.20, root + 0.52 * (outer - root)),
                (-0.12 + backlash_half_fraction, outer),
                (0.12 - backlash_half_fraction, outer),
                (0.20, root + 0.52 * (outer - root)),
                (0.28, root + 0.18 * (outer - root)),
                (0.36, root),
            )
        for fraction, radius in samples:
            angle = center_angle + fraction * pitch_angle
            points.append((radius * cos(angle), radius * sin(angle)))
    return tuple(points)


def gear_drag_outline_points(gear: GearSpec, plane: MechanicalWorkPlane) -> tuple[Point3, ...]:
    """Return a lightweight recognizable tooth silhouette for live dragging.

    The production mesh may use many involute samples per tooth. Drag feedback
    deliberately uses four points per tooth, which preserves the real tooth
    count, pitch, outer radius and phase while keeping projected updates cheap.
    """

    teeth = max(6, int(gear.teeth))
    pitch_angle = 2.0 * pi / teeth
    center = gear.center
    points: list[Point3] = []
    for tooth in range(teeth):
        center_angle = tooth * pitch_angle + radians(float(gear.phase_deg))
        for fraction, radius in (
            (-0.50, gear.root_radius_mm),
            (-0.16, gear.outer_radius_mm),
            (0.16, gear.outer_radius_mm),
            (0.50, gear.root_radius_mm),
        ):
            angle = center_angle + fraction * pitch_angle
            x, y = radius * cos(angle), radius * sin(angle)
            points.append(
                (
                    center[0] + plane.u_axis[0] * x + plane.v_axis[0] * y,
                    center[1] + plane.u_axis[1] * x + plane.v_axis[1] * y,
                    center[2] + plane.u_axis[2] * x + plane.v_axis[2] * y,
                )
            )
    if points:
        points.append(points[0])
    return tuple(points)


def build_gear_mesh(gear: GearSpec, *, name: str | None = None, plane: MechanicalWorkPlane | None = None) -> WorkMesh:
    """Build a closed star-shaped gear prism, optionally with a real bore.

    A zero bore produces a solid centre instead of a hidden epsilon-sized hole.
    With a bore, top and bottom faces are tessellated between corresponding
    outline and bore samples so every edge remains manifold.
    """

    gear.normalized()
    outer = _outer_profile_points(gear)
    count = len(outer)
    half = 0.5 * gear.thickness_mm
    cx, cy, cz = gear.center
    frame = plane or MechanicalWorkPlane.horizontal_at((cx, cy, cz))

    def world(x: float, y: float, z: float) -> Point3:
        return (
            cx + frame.u_axis[0] * x + frame.v_axis[0] * y + frame.normal[0] * z,
            cy + frame.u_axis[1] * x + frame.v_axis[1] * y + frame.normal[1] * z,
            cz + frame.u_axis[2] * x + frame.v_axis[2] * y + frame.normal[2] * z,
        )

    vertices: list[Point3] = []
    triangles: list[tuple[int, int, int]] = []
    has_bore = float(gear.bore_diameter_mm) > 1.0e-9

    if not has_bore:
        vertices.extend(world(x, y, -half) for x, y in outer)
        vertices.extend(world(x, y, half) for x, y in outer)
        bottom_center = len(vertices)
        vertices.append(world(0.0, 0.0, -half))
        top_center = len(vertices)
        vertices.append(world(0.0, 0.0, half))
        for i in range(count):
            j = (i + 1) % count
            triangles.append((bottom_center, j, i))
            triangles.append((top_center, count + i, count + j))
            triangles.extend(((i, j, count + j), (i, count + j, count + i)))
    else:
        bore_radius = min(0.5 * float(gear.bore_diameter_mm), max(0.06, gear.root_radius_mm * 0.90))
        from math import atan2

        angles = [atan2(y, x) for x, y in outer]
        for z in (-half, half):
            vertices.extend(world(x, y, z) for x, y in outer)
            vertices.extend(world(bore_radius * cos(angle), bore_radius * sin(angle), z) for angle in angles)

        bottom_outer = 0
        bottom_inner = count
        top_outer = 2 * count
        top_inner = 3 * count
        for i in range(count):
            j = (i + 1) % count
            triangles.extend(((bottom_outer + i, bottom_inner + j, bottom_outer + j), (bottom_outer + i, bottom_inner + i, bottom_inner + j)))
            triangles.extend(((top_outer + i, top_outer + j, top_inner + j), (top_outer + i, top_inner + j, top_inner + i)))
            triangles.extend(((bottom_outer + i, bottom_outer + j, top_outer + j), (bottom_outer + i, top_outer + j, top_outer + i)))
            triangles.extend(((bottom_inner + i, top_inner + j, bottom_inner + j), (bottom_inner + i, top_inner + i, top_inner + j)))

    mesh = WorkMesh(name=name or gear.name, vertices=vertices, triangles=triangles, color=gear.color)
    mesh.metadata.update(
        {
            "mechanical_generated": True,
            "mechanical_element_kind": "gear",
            "mechanical_gear_id": gear.id,
            "mechanical_shaft_id": gear.shaft_id,
            "mechanical_stage_index": gear.stage_index,
            "mechanical_role": gear.role,
            "pitch_radius_mm": gear.pitch_radius_mm,
            "teeth": gear.teeth,
            "module_mm": gear.module_mm,
        }
    )
    return mesh


def merge_meshes(meshes: Iterable[WorkMesh], *, name: str = "Mechanical assembly", color: str = "#D9A441") -> WorkMesh:
    vertices: list[Point3] = []
    triangles: list[tuple[int, int, int]] = []
    for mesh in meshes:
        offset = len(vertices)
        vertices.extend(tuple(float(v) for v in point) for point in mesh.vertices)
        triangles.extend((a + offset, b + offset, c + offset) for a, b, c in mesh.triangles)
    return WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)


def build_draft_placeholder(bounds: tuple[float, float, float, float, float, float], *, name: str = "Mechanical assembly draft") -> WorkMesh:
    min_x, min_y, min_z, max_x, max_y, max_z = (float(value) for value in bounds)
    if max_x - min_x < 2.0:
        max_x = min_x + 2.0
    if max_y - min_y < 2.0:
        max_y = min_y + 2.0
    if max_z - min_z < 2.0:
        max_z = min_z + 2.0
    vertices = [
        (min_x, min_y, min_z), (max_x, min_y, min_z), (max_x, max_y, min_z), (min_x, max_y, min_z),
        (min_x, min_y, max_z), (max_x, min_y, max_z), (max_x, max_y, max_z), (min_x, max_y, max_z),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    mesh = WorkMesh(name=name, vertices=vertices, triangles=triangles, color="#F44336")
    mesh.metadata.update({"mechanical_generated": True, "mechanical_draft_placeholder": True})
    return mesh


def gear_bounds(gears: Iterable[GearSpec]) -> tuple[float, float, float, float, float, float] | None:
    values = tuple(gears)
    if not values:
        return None
    min_x = min(gear.center[0] - gear.outer_radius_mm for gear in values)
    max_x = max(gear.center[0] + gear.outer_radius_mm for gear in values)
    min_y = min(gear.center[1] - gear.outer_radius_mm for gear in values)
    max_y = max(gear.center[1] + gear.outer_radius_mm for gear in values)
    min_z = min(gear.center[2] - 0.5 * gear.thickness_mm for gear in values)
    max_z = max(gear.center[2] + 0.5 * gear.thickness_mm for gear in values)
    return (min_x, min_y, min_z, max_x, max_y, max_z)


__all__ = ["build_draft_placeholder", "build_gear_mesh", "gear_bounds", "gear_drag_outline_points", "merge_meshes"]

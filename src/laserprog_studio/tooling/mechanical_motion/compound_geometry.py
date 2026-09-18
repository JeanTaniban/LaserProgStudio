# -*- coding: utf-8 -*-
from __future__ import annotations

from math import cos, pi, sin
from typing import Iterable

from laserprog_studio.domain.work_model import WorkMesh

from .geometry import build_gear_mesh, merge_meshes
from .models import GearSpec, Point3
from .plane import MechanicalWorkPlane

_COMPOUND_HUB_OVERLAP_MM = 0.08
_COMPOUND_HUB_SEGMENTS = 48


def _axis_coordinate(gear: GearSpec, plane: MechanicalWorkPlane) -> float:
    return sum(float(gear.center[i]) * float(plane.normal[i]) for i in range(3))


def _world_ring_point(
    center: Point3,
    plane: MechanicalWorkPlane,
    radius: float,
    angle: float,
    axial_offset: float,
) -> Point3:
    radial_u = float(radius) * cos(angle)
    radial_v = float(radius) * sin(angle)
    return (
        float(center[0])
        + plane.u_axis[0] * radial_u
        + plane.v_axis[0] * radial_v
        + plane.normal[0] * axial_offset,
        float(center[1])
        + plane.u_axis[1] * radial_u
        + plane.v_axis[1] * radial_v
        + plane.normal[1] * axial_offset,
        float(center[2])
        + plane.u_axis[2] * radial_u
        + plane.v_axis[2] * radial_v
        + plane.normal[2] * axial_offset,
    )


def _compound_hub_radii(gears: tuple[GearSpec, ...]) -> tuple[float, float]:
    """Choose a compact hub that intersects every gear without reaching teeth."""

    minimum_root = max(0.05, min(float(gear.root_radius_mm) for gear in gears))
    requested_inner = max(0.5 * float(gear.bore_diameter_mm) for gear in gears)
    safe_outer = 0.92 * minimum_root
    # Generated chains normally share one bore.  For unusual manually stacked
    # gears, retain a through-bore whenever all roots permit it; otherwise use a
    # small solid connector rather than leaving the compound shaft disconnected.
    if requested_inner < 0.82 * minimum_root:
        inner = requested_inner
        radial_wall = max(0.04, min(0.8, 0.24 * minimum_root))
        outer = min(safe_outer, max(0.38 * minimum_root, inner + radial_wall))
        if outer <= inner + 1.0e-4:
            inner = 0.0
            outer = max(0.03, 0.38 * minimum_root)
    else:
        inner = 0.0
        outer = max(0.03, 0.38 * minimum_root)
    return inner, min(outer, safe_outer)


def _build_axial_hub_mesh(
    gears: tuple[GearSpec, ...],
    *,
    plane: MechanicalWorkPlane,
    name: str,
) -> WorkMesh:
    """Build a closed annular hub joining axially separated coaxial gears."""

    first = gears[0]
    coordinates = [_axis_coordinate(gear, plane) for gear in gears]
    lower = min(value - 0.5 * float(gear.thickness_mm) for value, gear in zip(coordinates, gears))
    upper = max(value + 0.5 * float(gear.thickness_mm) for value, gear in zip(coordinates, gears))
    lower -= _COMPOUND_HUB_OVERLAP_MM
    upper += _COMPOUND_HUB_OVERLAP_MM
    midpoint = 0.5 * (lower + upper)
    center = plane.offset(first.center, midpoint - _axis_coordinate(first, plane))
    half_length = 0.5 * (upper - lower)
    inner_radius, outer_radius = _compound_hub_radii(gears)
    segments = _COMPOUND_HUB_SEGMENTS

    vertices: list[Point3] = []
    triangles: list[tuple[int, int, int]] = []
    angles = [2.0 * pi * index / segments for index in range(segments)]

    if inner_radius <= 1.0e-9:
        bottom = len(vertices)
        vertices.extend(_world_ring_point(center, plane, outer_radius, angle, -half_length) for angle in angles)
        top = len(vertices)
        vertices.extend(_world_ring_point(center, plane, outer_radius, angle, half_length) for angle in angles)
        bottom_center = len(vertices)
        vertices.append(_world_ring_point(center, plane, 0.0, 0.0, -half_length))
        top_center = len(vertices)
        vertices.append(_world_ring_point(center, plane, 0.0, 0.0, half_length))
        for index in range(segments):
            nxt = (index + 1) % segments
            triangles.append((bottom_center, bottom + nxt, bottom + index))
            triangles.append((top_center, top + index, top + nxt))
            triangles.extend(((bottom + index, bottom + nxt, top + nxt), (bottom + index, top + nxt, top + index)))
    else:
        bottom_outer = len(vertices)
        vertices.extend(_world_ring_point(center, plane, outer_radius, angle, -half_length) for angle in angles)
        bottom_inner = len(vertices)
        vertices.extend(_world_ring_point(center, plane, inner_radius, angle, -half_length) for angle in angles)
        top_outer = len(vertices)
        vertices.extend(_world_ring_point(center, plane, outer_radius, angle, half_length) for angle in angles)
        top_inner = len(vertices)
        vertices.extend(_world_ring_point(center, plane, inner_radius, angle, half_length) for angle in angles)
        for index in range(segments):
            nxt = (index + 1) % segments
            triangles.extend(
                (
                    (bottom_outer + index, bottom_inner + nxt, bottom_outer + nxt),
                    (bottom_outer + index, bottom_inner + index, bottom_inner + nxt),
                    (top_outer + index, top_outer + nxt, top_inner + nxt),
                    (top_outer + index, top_inner + nxt, top_inner + index),
                    (bottom_outer + index, bottom_outer + nxt, top_outer + nxt),
                    (bottom_outer + index, top_outer + nxt, top_outer + index),
                    (bottom_inner + index, top_inner + nxt, bottom_inner + nxt),
                    (bottom_inner + index, top_inner + index, top_inner + nxt),
                )
            )

    mesh = WorkMesh(name=name, vertices=vertices, triangles=triangles, color=first.color)
    mesh.metadata.update(
        {
            "mechanical_generated": True,
            "mechanical_element_kind": "compound_hub",
            "mechanical_compound_hub": True,
            "mechanical_shaft_id": first.shaft_id,
            "mechanical_hub_inner_radius_mm": inner_radius,
            "mechanical_hub_outer_radius_mm": outer_radius,
            "mechanical_hub_length_mm": upper - lower,
        }
    )
    return mesh


def build_compound_shaft_mesh(
    gears: Iterable[GearSpec],
    *,
    plane: MechanicalWorkPlane,
    name: str | None = None,
) -> WorkMesh:
    """Build one rigid scene mesh for all coaxial gears carried by a shaft.

    Gear stages are separated axially so neighbouring stages cannot create a
    second parasitic mesh.  A compact central hub bridges those clearances and
    makes the coaxial gears one rigid printable part.  The optional boolean
    backend produces a manifold union; the deterministic merged fallback still
    renders and animates as one actor when that backend is unavailable.
    """

    values = sorted(tuple(gears), key=lambda item: _axis_coordinate(item, plane))
    if not values:
        raise ValueError("A compound shaft requires at least one gear.")
    if len(values) == 1:
        return build_gear_mesh(values[0], name=name, plane=plane)

    parts = [build_gear_mesh(gear, plane=plane) for gear in values]
    parts.append(
        _build_axial_hub_mesh(
            values,
            plane=plane,
            name=f"{name or values[0].name} hub",
        )
    )
    result: WorkMesh
    try:
        from laserprog_studio.boolean_ops import boolean_union

        result = parts[0]
        for part in parts[1:]:
            result = boolean_union(result, part)
    except Exception:
        result = merge_meshes(parts, name=name or f"{values[0].name} compound", color=values[0].color)
        result.metadata["mechanical_compound_union_fallback"] = True

    result.name = name or f"{values[0].name} compound"
    result.color = values[0].color
    result.metadata.update(
        {
            "mechanical_generated": True,
            "mechanical_element_kind": "compound_gear",
            "mechanical_compound": True,
            "mechanical_compound_hub": True,
            "mechanical_gear_ids": [gear.id for gear in values],
            "mechanical_shaft_id": values[0].shaft_id,
            "mechanical_stage_indices": [gear.stage_index for gear in values],
        }
    )
    return result


__all__ = ["build_compound_shaft_mesh"]

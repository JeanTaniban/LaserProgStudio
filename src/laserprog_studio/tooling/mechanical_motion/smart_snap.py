# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Iterable

from .models import GearSpec, GearStage, MechanicalAssembly, Point3, make_id
from .plane import MechanicalWorkPlane

SMART_MESH_CONNECTION_KIND = "smart_mesh"
DEFAULT_CAPTURE_MIN_MM = 4.0
DEFAULT_CAPTURE_MAX_MM = 14.0
DEFAULT_MODULE_REL_TOLERANCE = 0.005
DEFAULT_PRESSURE_ANGLE_TOLERANCE_DEG = 1.0
DEFAULT_AXIAL_CLEARANCE_MM = 0.20


@dataclass(frozen=True, slots=True)
class GearSnapCandidate:
    dragged_gear_id: str
    target_gear_id: str
    center: Point3
    phase_deg: float
    contact_point: Point3
    mesh_angle_deg: float
    center_distance_mm: float
    radial_error_mm: float
    capture_distance_mm: float

    @property
    def snapped(self) -> bool:
        return True


def chain_owned_stage_ids(assembly: MechanicalAssembly) -> set[str]:
    return {
        str(stage_id)
        for chain in assembly.chains.values()
        for stage_id in chain.stage_ids
        if str(stage_id)
    }


def is_smart_mesh_stage(stage: GearStage, assembly: MechanicalAssembly | None = None) -> bool:
    kind = str(getattr(stage, "connection_kind", "") or "")
    if kind == SMART_MESH_CONNECTION_KIND:
        return True
    if assembly is None:
        return False
    # Backward-compatible inference for early smart-snap development builds.
    return stage.id not in chain_owned_stage_ids(assembly) and int(stage.index) < 0


def smart_mesh_stages_for_gear(assembly: MechanicalAssembly, gear_id: str) -> tuple[GearStage, ...]:
    target = str(gear_id)
    return tuple(
        stage
        for stage in assembly.stages.values()
        if is_smart_mesh_stage(stage, assembly)
        and target in {str(stage.driver_gear_id), str(stage.driven_gear_id)}
    )


def detach_smart_mesh_stages(assembly: MechanicalAssembly, gear_id: str) -> tuple[str, ...]:
    removed: list[str] = []
    for stage in smart_mesh_stages_for_gear(assembly, gear_id):
        removed.append(stage.id)
        assembly.stages.pop(stage.id, None)
    return tuple(removed)


def standalone_gear_ids(assembly: MechanicalAssembly) -> set[str]:
    generated = {
        str(gear_id)
        for chain in assembly.chains.values()
        for gear_id in chain.gear_ids
    }
    return {
        gear.id
        for gear in assembly.gears.values()
        if gear.id not in generated and str(gear.role or "standalone") == "standalone"
    }


def is_unique_standalone_gear(assembly: MechanicalAssembly, gear_id: str) -> bool:
    value = str(gear_id)
    gear = assembly.gears.get(value)
    if gear is None or value not in standalone_gear_ids(assembly):
        return False
    shaft_id = str(gear.shaft_id or gear.id)
    return sum(1 for item in assembly.gears.values() if str(item.shaft_id or item.id) == shaft_id) == 1


def _normal_coordinate(point: Point3, plane: MechanicalWorkPlane) -> float:
    return sum(float(point[index]) * float(plane.normal[index]) for index in range(3))


def _axially_compatible(a: GearSpec, b: GearSpec, plane: MechanicalWorkPlane) -> bool:
    delta = abs(_normal_coordinate(a.center, plane) - _normal_coordinate(b.center, plane))
    maximum = 0.5 * (float(a.thickness_mm) + float(b.thickness_mm)) - DEFAULT_AXIAL_CLEARANCE_MM
    return delta <= max(0.0, maximum)


def gears_are_mesh_compatible(a: GearSpec, b: GearSpec, plane: MechanicalWorkPlane) -> bool:
    module_scale = max(float(a.module_mm), float(b.module_mm), 1.0e-9)
    module_error = abs(float(a.module_mm) - float(b.module_mm)) / module_scale
    return (
        module_error <= DEFAULT_MODULE_REL_TOLERANCE
        and abs(float(a.pressure_angle_deg) - float(b.pressure_angle_deg))
        <= DEFAULT_PRESSURE_ANGLE_TOLERANCE_DEG
        and _axially_compatible(a, b, plane)
        and str(a.shaft_id or a.id) != str(b.shaft_id or b.id)
    )


def _support_offset(gear: GearSpec, plane: MechanicalWorkPlane) -> float:
    support = plane.clamp(gear.center)
    return sum(
        (float(gear.center[index]) - float(support[index])) * float(plane.normal[index])
        for index in range(3)
    )


def _point_with_offset(support: Point3, offset: float, plane: MechanicalWorkPlane) -> Point3:
    return plane.offset(plane.clamp(support), float(offset))


def _phase_for_fixed_target(
    target: GearSpec,
    dragged: GearSpec,
    *,
    mesh_angle_deg: float,
) -> float:
    """Return the dragged phase while preserving the target's existing phase.

    At the contact line, the target and dragged tooth fractions must sum to one
    half pitch. This is the general external-gear relation and remains correct
    when the target belongs to a solved chain with a non-zero phase.
    """

    target_pitch = 360.0 / max(1, int(target.teeth))
    dragged_pitch = 360.0 / max(1, int(dragged.teeth))
    target_fraction = ((float(mesh_angle_deg) - float(target.phase_deg)) / target_pitch) % 1.0
    dragged_fraction = (0.5 - target_fraction) % 1.0
    opposite_angle = float(mesh_angle_deg) + 180.0
    return (opposite_angle - dragged_fraction * dragged_pitch) % 360.0


def _candidate_for_target(
    assembly: MechanicalAssembly,
    dragged: GearSpec,
    target: GearSpec,
    raw_support: Point3,
    plane: MechanicalWorkPlane,
    *,
    capture_scale: float,
) -> GearSnapCandidate | None:
    if not gears_are_mesh_compatible(dragged, target, plane):
        return None
    target_support = plane.clamp(target.center)
    raw_u, raw_v = plane.coordinates(raw_support)
    target_u, target_v = plane.coordinates(target_support)
    du, dv = raw_u - target_u, raw_v - target_v
    distance = hypot(du, dv)
    required = float(dragged.pitch_radius_mm) + float(target.pitch_radius_mm)
    capture = max(
        DEFAULT_CAPTURE_MIN_MM,
        min(DEFAULT_CAPTURE_MAX_MM, max(float(dragged.module_mm), float(target.module_mm)) * 2.8),
    ) * max(0.25, float(capture_scale))
    error = abs(distance - required)
    if error > capture:
        return None
    if distance <= 1.0e-9:
        direction_u, direction_v = 1.0, 0.0
    else:
        direction_u, direction_v = du / distance, dv / distance
    snapped_support = plane.point(target_u + direction_u * required, target_v + direction_v * required)
    center = _point_with_offset(snapped_support, _support_offset(dragged, plane), plane)
    mesh_angle = plane.angle_deg(target_support, snapped_support)
    phase = _phase_for_fixed_target(target, dragged, mesh_angle_deg=mesh_angle)
    contact = plane.radial_point(target_support, target.pitch_radius_mm, mesh_angle)
    return GearSnapCandidate(
        dragged_gear_id=dragged.id,
        target_gear_id=target.id,
        center=center,
        phase_deg=phase,
        contact_point=contact,
        mesh_angle_deg=mesh_angle,
        center_distance_mm=required,
        radial_error_mm=error,
        capture_distance_mm=capture,
    )


def find_gear_snap_candidate(
    assembly: MechanicalAssembly,
    dragged_gear_id: str,
    raw_support: Point3,
    plane: MechanicalWorkPlane,
    *,
    capture_scale: float = 1.0,
    target_ids: Iterable[str] | None = None,
) -> GearSnapCandidate | None:
    dragged = assembly.gears.get(str(dragged_gear_id))
    if dragged is None or not is_unique_standalone_gear(assembly, dragged.id):
        return None
    allowed = {str(value) for value in target_ids} if target_ids is not None else None
    candidates = []
    for target in assembly.gears.values():
        if target.id == dragged.id or (allowed is not None and target.id not in allowed):
            continue
        candidate = _candidate_for_target(
            assembly,
            dragged,
            target,
            raw_support,
            plane,
            capture_scale=capture_scale,
        )
        if candidate is not None:
            candidates.append(candidate)
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda item: (
            float(item.radial_error_mm),
            float(item.center_distance_mm),
            str(item.target_gear_id),
        ),
    )


def connect_smart_mesh(
    assembly: MechanicalAssembly,
    *,
    target_gear_id: str,
    dragged_gear_id: str,
) -> GearStage:
    target = assembly.gears[str(target_gear_id)]
    dragged = assembly.gears[str(dragged_gear_id)]
    detach_smart_mesh_stages(assembly, dragged.id)
    stage = GearStage(
        id=make_id("smart_stage"),
        index=-1,
        driver_gear_id=target.id,
        driven_gear_id=dragged.id,
        driver_shaft_id=str(target.shaft_id or target.id),
        driven_shaft_id=str(dragged.shaft_id or dragged.id),
        target_reduction=float(dragged.teeth) / max(1.0, float(target.teeth)),
        actual_reduction=float(dragged.teeth) / max(1.0, float(target.teeth)),
        center_distance_mm=float(target.pitch_radius_mm + dragged.pitch_radius_mm),
        axial_layer=0,
        connection_kind=SMART_MESH_CONNECTION_KIND,
        owner_id=dragged.id,
    )
    assembly.stages[stage.id] = stage
    return stage


__all__ = [
    "GearSnapCandidate",
    "SMART_MESH_CONNECTION_KIND",
    "chain_owned_stage_ids",
    "connect_smart_mesh",
    "detach_smart_mesh_stages",
    "find_gear_snap_candidate",
    "gears_are_mesh_compatible",
    "is_smart_mesh_stage",
    "is_unique_standalone_gear",
    "smart_mesh_stages_for_gear",
    "standalone_gear_ids",
]

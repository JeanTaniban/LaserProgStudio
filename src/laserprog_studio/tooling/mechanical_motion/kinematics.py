# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, radians, sin, sqrt
from typing import Any, Iterable, Mapping

from laserprog_studio.domain.work_model import WorkMesh

from .models import MechanicalAssembly, Point3
from .plane import MechanicalWorkPlane
from .rack_geometry import rack_axis, rack_motion_sign
from .shafts import normalize_coaxial_shafts


@dataclass(frozen=True, slots=True)
class KinematicState:
    shaft_angles_deg: dict[str, float]
    shaft_speeds_rpm: dict[str, float]
    gear_angles_deg: dict[str, float]
    rack_displacements_mm: dict[str, float]
    rack_speeds_mm_s: dict[str, float]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class MeshMotionTransform:
    center: Point3 = (0.0, 0.0, 0.0)
    angle_deg: float = 0.0
    translation: Point3 = (0.0, 0.0, 0.0)


def solve_kinematics(assembly: MechanicalAssembly, input_angle_deg: float | Mapping[str, float]) -> KinematicState:
    # Repair legacy/manual stacked gears before building the graph. A rigid
    # compound shaft must be represented by one node, not merely look fused.
    normalization = normalize_coaxial_shafts(assembly)
    shaft_angles: dict[str, float] = {}
    shaft_speeds: dict[str, float] = {}
    warnings: list[str] = []
    if normalization.changed:
        warnings.append(f"{len(normalization.merged_groups)} coaxial shaft group(s) were synchronized")

    drivers = tuple(assembly.drivers.values())
    angle_by_driver = input_angle_deg if isinstance(input_angle_deg, Mapping) else None
    fallback_angle = 0.0 if angle_by_driver is not None else float(input_angle_deg)
    if not drivers:
        first_gear = next(iter(assembly.gears.values()), None)
        if first_gear is not None:
            shaft = first_gear.shaft_id or first_gear.id
            shaft_angles[shaft] = fallback_angle
            shaft_speeds[shaft] = 10.0
    for driver in drivers:
        shaft = driver.shaft_id
        if not shaft and driver.target_gear_id in assembly.gears:
            shaft = assembly.gears[str(driver.target_gear_id)].shaft_id or driver.target_gear_id
        if not shaft:
            shaft = driver.id
        raw_angle = float(angle_by_driver.get(driver.id, 0.0)) if angle_by_driver is not None else fallback_angle
        angle = raw_angle if angle_by_driver is not None else raw_angle * int(driver.direction)
        speed = float(driver.speed_rpm) * int(driver.direction)
        if shaft in shaft_angles and abs(shaft_angles[shaft] - angle) > 1.0e-6:
            warnings.append(f"multiple drivers disagree on shaft {shaft}; newest value used")
        shaft_angles[str(shaft)] = angle
        shaft_speeds[str(shaft)] = speed

    unresolved = list(assembly.stages.values())
    for _ in range(max(1, len(unresolved) + 1)):
        next_round = []
        changed = False
        for stage in unresolved:
            driver_shaft = str(stage.driver_shaft_id)
            driven_shaft = str(stage.driven_shaft_id)
            ratio = max(1e-9, float(stage.actual_reduction))
            if driver_shaft == driven_shaft:
                # A migrated bad topology can contain a stage whose two gears
                # became one rigid shaft. It is not a gear mesh anymore.
                warnings.append(f"stage {stage.index + 1} collapsed onto one coaxial shaft and was ignored")
                continue
            if driver_shaft in shaft_angles and driven_shaft not in shaft_angles:
                shaft_angles[driven_shaft] = -shaft_angles[driver_shaft] / ratio
                shaft_speeds[driven_shaft] = -shaft_speeds.get(driver_shaft, 0.0) / ratio
                changed = True
            elif driven_shaft in shaft_angles and driver_shaft not in shaft_angles:
                shaft_angles[driver_shaft] = -shaft_angles[driven_shaft] * ratio
                shaft_speeds[driver_shaft] = -shaft_speeds.get(driven_shaft, 0.0) * ratio
                changed = True
            elif driver_shaft in shaft_angles and driven_shaft in shaft_angles:
                expected = -shaft_angles[driver_shaft] / ratio
                if abs(expected - shaft_angles[driven_shaft]) > 1.0e-4:
                    warnings.append(f"stage {stage.index + 1} has a conflicting closed-loop ratio")
            else:
                next_round.append(stage)
        unresolved = next_round
        if not changed:
            break
    if unresolved:
        warnings.append(f"{len(unresolved)} stage(s) are not connected to a rotary driver")

    gear_angles: dict[str, float] = {}
    for gear_id, gear in assembly.gears.items():
        shaft = str(gear.shaft_id or gear_id)
        gear_angles[gear_id] = shaft_angles.get(shaft, 0.0) + float(gear.phase_deg)

    rack_displacements: dict[str, float] = {}
    rack_speeds: dict[str, float] = {}
    plane = assembly.work_plane if isinstance(assembly.work_plane, MechanicalWorkPlane) else None
    for rack_id, rack in assembly.racks.items():
        pinion = assembly.gears.get(str(rack.pinion_gear_id or ""))
        if pinion is None or plane is None:
            rack_displacements[rack_id] = 0.0
            rack_speeds[rack_id] = 0.0
            warnings.append(f"rack {rack.name or rack_id} is not connected to a valid pinion")
            continue
        shaft = str(pinion.shaft_id or pinion.id)
        sign = rack_motion_sign(rack, plane)
        rack_displacements[rack_id] = radians(shaft_angles.get(shaft, 0.0)) * pinion.pitch_radius_mm * sign
        rack_speeds[rack_id] = shaft_speeds.get(shaft, 0.0) * (2.0 * pi * pinion.pitch_radius_mm / 60.0) * sign

    return KinematicState(
        shaft_angles,
        shaft_speeds,
        gear_angles,
        rack_displacements,
        rack_speeds,
        tuple(dict.fromkeys(warnings)),
    )


def _unit_axis(axis: Point3) -> Point3:
    x, y, z = (float(axis[0]), float(axis[1]), float(axis[2]))
    length = sqrt(x * x + y * y + z * z)
    if length <= 1.0e-12:
        return (0.0, 0.0, 1.0)
    return (x / length, y / length, z / length)


def rotate_point_about_axis(point: Point3, center: Point3, angle_deg: float, axis: Point3 = (0.0, 0.0, 1.0)) -> Point3:
    angle = radians(float(angle_deg))
    c, s = cos(angle), sin(angle)
    ax = _unit_axis(axis)
    rel = (float(point[0]) - float(center[0]), float(point[1]) - float(center[1]), float(point[2]) - float(center[2]))
    cross = (
        ax[1] * rel[2] - ax[2] * rel[1],
        ax[2] * rel[0] - ax[0] * rel[2],
        ax[0] * rel[1] - ax[1] * rel[0],
    )
    dot = ax[0] * rel[0] + ax[1] * rel[1] + ax[2] * rel[2]
    rotated = (
        rel[0] * c + cross[0] * s + ax[0] * dot * (1.0 - c),
        rel[1] * c + cross[1] * s + ax[1] * dot * (1.0 - c),
        rel[2] * c + cross[2] * s + ax[2] * dot * (1.0 - c),
    )
    return (float(center[0]) + rotated[0], float(center[1]) + rotated[1], float(center[2]) + rotated[2])


def rotate_point_about_z(point: Point3, center: Point3, angle_deg: float) -> Point3:
    return rotate_point_about_axis(point, center, angle_deg, (0.0, 0.0, 1.0))


def rotated_mesh(mesh: Any, center: Point3, angle_deg: float, *, axis: Point3 = (0.0, 0.0, 1.0), name: str | None = None) -> WorkMesh:
    return WorkMesh(
        name=name or str(getattr(mesh, "name", "Part")),
        vertices=[rotate_point_about_axis(tuple(float(v) for v in point), center, angle_deg, axis) for point in getattr(mesh, "vertices", ())],
        triangles=[tuple(int(v) for v in tri) for tri in getattr(mesh, "triangles", ())],
        color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
        material=getattr(mesh, "material", None),
        engraving=getattr(mesh, "engraving", None),
        uvs=getattr(mesh, "uvs", None),
        texture_projections=list(getattr(mesh, "texture_projections", ()) or ()),
        metadata=dict(getattr(mesh, "metadata", {}) or {}),
        mesh_id=str(getattr(mesh, "mesh_id", "") or ""),
    )


def translated_mesh(mesh: Any, translation: Point3, *, name: str | None = None) -> WorkMesh:
    dx, dy, dz = (float(value) for value in translation)
    return WorkMesh(
        name=name or str(getattr(mesh, "name", "Part")),
        vertices=[(float(point[0]) + dx, float(point[1]) + dy, float(point[2]) + dz) for point in getattr(mesh, "vertices", ())],
        triangles=[tuple(int(v) for v in tri) for tri in getattr(mesh, "triangles", ())],
        color=str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
        material=getattr(mesh, "material", None),
        engraving=getattr(mesh, "engraving", None),
        uvs=getattr(mesh, "uvs", None),
        texture_projections=list(getattr(mesh, "texture_projections", ()) or ()),
        metadata=dict(getattr(mesh, "metadata", {}) or {}),
        mesh_id=str(getattr(mesh, "mesh_id", "") or ""),
    )


def element_motion_transform(
    assembly: MechanicalAssembly,
    state: KinematicState,
    element_id: str | None,
) -> MeshMotionTransform | None:
    """Resolve one mechanical element to a reusable scene motion transform.

    Attachments now depend on this generic output rather than knowing every
    concrete mechanism type. Future cams, belts or crank-slider elements only
    need to expose their transform here to become valid Attach sources.
    """

    source_id = str(element_id or "")
    if not source_id:
        return None
    plane = assembly.work_plane if isinstance(assembly.work_plane, MechanicalWorkPlane) else None
    rack = assembly.racks.get(source_id)
    if rack is not None:
        displacement = float(state.rack_displacements_mm.get(rack.id, 0.0))
        axis = rack_axis(rack)
        return MeshMotionTransform(
            translation=(axis[0] * displacement, axis[1] * displacement, axis[2] * displacement)
        )
    gear = assembly.gears.get(source_id)
    if gear is not None:
        shaft = str(gear.shaft_id or gear.id)
        center = plane.clamp(gear.center) if plane is not None else gear.center
        return MeshMotionTransform(center=center, angle_deg=float(state.shaft_angles_deg.get(shaft, 0.0)))
    driver = assembly.drivers.get(source_id)
    if driver is not None:
        shaft = str(driver.shaft_id or driver.id)
        return MeshMotionTransform(center=driver.center, angle_deg=float(state.shaft_angles_deg.get(shaft, 0.0)))
    chain = assembly.chains.get(source_id)
    if chain is not None and chain.gear_ids:
        return element_motion_transform(assembly, state, chain.gear_ids[-1])
    return None


def mesh_motion_transforms(assembly: MechanicalAssembly, state: KinematicState) -> dict[str, MeshMotionTransform]:
    transforms: dict[str, MeshMotionTransform] = {}
    for driver in assembly.drivers.values():
        if not driver.target_mesh_id:
            continue
        shaft = str(driver.shaft_id or driver.id)
        transforms[str(driver.target_mesh_id)] = MeshMotionTransform(
            center=driver.center,
            angle_deg=float(state.shaft_angles_deg.get(shaft, 0.0)),
        )
    for attachment in assembly.attachments.values():
        source_id = (
            attachment.source_element_id
            or attachment.source_rack_id
            or attachment.source_gear_id
            or attachment.source_driver_id
        )
        transform = element_motion_transform(assembly, state, source_id)
        if transform is None:
            shaft = attachment.shaft_id
            if not shaft and attachment.source_gear_id in assembly.gears:
                source = assembly.gears[str(attachment.source_gear_id)]
                shaft = source.shaft_id or source.id
            angle = float(state.shaft_angles_deg.get(str(shaft), 0.0)) + float(attachment.angle_offset_deg)
            transform = MeshMotionTransform(center=attachment.center, angle_deg=angle)
        elif abs(float(attachment.angle_offset_deg)) > 1.0e-12:
            transform = MeshMotionTransform(
                center=transform.center,
                angle_deg=transform.angle_deg + float(attachment.angle_offset_deg),
                translation=transform.translation,
            )
        for mesh_id in attachment.target_mesh_ids:
            transforms[str(mesh_id)] = transform
    return transforms


def apply_attachment_motion(meshes: Iterable[Any], assembly: MechanicalAssembly, state: KinematicState) -> list[Any]:
    attachments_by_mesh = mesh_motion_transforms(assembly, state)
    plane = getattr(assembly, "work_plane", None)
    axis = tuple(getattr(plane, "normal", (0.0, 0.0, 1.0)))
    result: list[Any] = []
    for mesh in meshes:
        mesh_id = str(getattr(mesh, "mesh_id", "") or "")
        motion = attachments_by_mesh.get(mesh_id)
        if motion is None:
            result.append(mesh)
            continue
        moved = mesh
        if abs(motion.angle_deg) > 1.0e-12:
            moved = rotated_mesh(moved, motion.center, motion.angle_deg, axis=axis)
        if any(abs(value) > 1.0e-12 for value in motion.translation):
            moved = translated_mesh(moved, motion.translation)
        result.append(moved)
    return result


__all__ = [
    "KinematicState",
    "MeshMotionTransform",
    "apply_attachment_motion",
    "element_motion_transform",
    "mesh_motion_transforms",
    "rotate_point_about_axis",
    "rotate_point_about_z",
    "rotated_mesh",
    "solve_kinematics",
    "translated_mesh",
]

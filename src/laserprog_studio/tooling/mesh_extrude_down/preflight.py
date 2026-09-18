# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .settings import ExtrudeDownSettings


@dataclass(frozen=True, slots=True)
class ExtrudeDownCheck:
    ok: bool
    message: str
    target_indices: tuple[int, ...] = ()
    before_triangles: int = 0
    z_min: float = 0.0
    z_max: float = 0.0
    plane_z: float = 0.0
    ground_z: float = 0.0


def triangle_count(mesh: Any) -> int:
    try:
        return int(len(getattr(mesh, "triangles", []) or []))
    except Exception:
        return 0


def selected_indices_text(indices: Iterable[int]) -> str:
    values = tuple(int(i) for i in indices)
    if not values:
        return "No selection"
    return ", ".join(f"{i:02d}" for i in values)


def z_limits(meshes: list[Any], indices: Iterable[int]) -> tuple[float, float]:
    values: list[float] = []
    for raw_index in indices:
        index = int(raw_index)
        if not (0 <= index < len(meshes)):
            continue
        for vertex in getattr(meshes[index], "vertices", ()) or ():
            try:
                values.append(float(vertex[2]))
            except Exception:
                continue
    if not values:
        return (0.0, 0.0)
    return (float(min(values)), float(max(values)))


def plane_z_from_ratio(meshes: list[Any], indices: Iterable[int], ratio: float) -> float:
    z_min, z_max = z_limits(meshes, indices)
    if z_max <= z_min:
        return float(z_max)
    t = max(1.0, min(99.0, float(ratio))) / 100.0
    return float(z_min + (z_max - z_min) * t)


def validate_extrude_down_targets(ctx: Any, settings: ExtrudeDownSettings) -> ExtrudeDownCheck:
    try:
        ctx.document.ensure()
        meshes = list(ctx.document.meshes(include_preview=False))
    except Exception:
        return ExtrudeDownCheck(False, "Open or create a scene before extruding meshes down.")

    raw_indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    if not raw_indices:
        return ExtrudeDownCheck(False, "Select one or more parts to extrude down.")
    valid = tuple(i for i in sorted(set(raw_indices)) if 0 <= i < len(meshes))
    if not valid:
        return ExtrudeDownCheck(False, "The extrude-down selection contains no valid scene object.")

    before = sum(triangle_count(meshes[i]) for i in valid)
    if before <= 0:
        return ExtrudeDownCheck(False, "Selected parts contain no triangles to extrude.", target_indices=valid, before_triangles=before)

    z_min, z_max = z_limits(meshes, valid)
    flat_selection = abs(float(z_max) - float(z_min)) <= max(float(settings.tolerance), 1e-7)
    if settings.tolerance <= 0.0:
        return ExtrudeDownCheck(False, "Tolerance must be greater than zero.", target_indices=valid, before_triangles=before, z_min=z_min, z_max=z_max)
    if settings.plane_z <= settings.ground_z + max(settings.tolerance, 1e-7):
        return ExtrudeDownCheck(False, "Plane Z must be above the ground Z.", target_indices=valid, before_triangles=before, z_min=z_min, z_max=z_max, plane_z=settings.plane_z, ground_z=settings.ground_z)
    if flat_selection:
        if abs(float(settings.plane_z) - float(z_max)) > max(float(settings.tolerance), 1e-7) * 2.0:
            return ExtrudeDownCheck(False, f"Flat face selections must extrude from their own Z level ({z_max:g} mm).", target_indices=valid, before_triangles=before, z_min=z_min, z_max=z_max, plane_z=settings.plane_z, ground_z=settings.ground_z)
    else:
        if settings.plane_z <= z_min + settings.tolerance:
            return ExtrudeDownCheck(False, f"Plane Z is below the usable section. Raise it above {z_min + settings.tolerance:g} mm.", target_indices=valid, before_triangles=before, z_min=z_min, z_max=z_max, plane_z=settings.plane_z, ground_z=settings.ground_z)
        if settings.plane_z >= z_max - settings.tolerance:
            return ExtrudeDownCheck(False, f"Plane Z is above the usable section. Lower it below {z_max - settings.tolerance:g} mm.", target_indices=valid, before_triangles=before, z_min=z_min, z_max=z_max, plane_z=settings.plane_z, ground_z=settings.ground_z)

    return ExtrudeDownCheck(
        True,
        f"Ready to extrude {len(valid)} part{'s' if len(valid) != 1 else ''} down · {before} triangles · Z {settings.plane_z:g} → {settings.ground_z:g} mm.",
        target_indices=valid,
        before_triangles=before,
        z_min=z_min,
        z_max=z_max,
        plane_z=settings.plane_z,
        ground_z=settings.ground_z,
    )


__all__ = [
    "ExtrudeDownCheck",
    "plane_z_from_ratio",
    "selected_indices_text",
    "triangle_count",
    "validate_extrude_down_targets",
    "z_limits",
]

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import math

from .settings import SplitPlaneSettings


@dataclass(frozen=True, slots=True)
class SplitPlaneCheck:
    ok: bool
    message: str
    target_indices: tuple[int, ...] = ()
    selected_vertices: int = 0
    before_triangles: int = 0
    center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)
    normal: tuple[float, float, float] = (0.0, 0.0, 1.0)
    plane_size_mm: float = 120.0


def triangle_count(mesh: Any) -> int:
    try:
        return int(len(getattr(mesh, "triangles", []) or []))
    except Exception:
        return 0


def scene_vertices(meshes: list[Any], indices: tuple[int, ...] | None = None) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    target = indices if indices is not None else tuple(range(len(meshes)))
    for index in target:
        if not (0 <= int(index) < len(meshes)):
            continue
        for vertex in getattr(meshes[int(index)], "vertices", ()) or ():
            try:
                x, y, z = vertex[:3]
                points.append((float(x), float(y), float(z)))
            except Exception:
                continue
    return points


def center_of(points: list[tuple[float, float, float]]) -> tuple[float, float, float]:
    if not points:
        return (0.0, 0.0, 0.0)
    count = float(len(points))
    return (sum(p[0] for p in points) / count, sum(p[1] for p in points) / count, sum(p[2] for p in points) / count)


def bounds_size(points: list[tuple[float, float, float]]) -> float:
    if not points:
        return 120.0
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)
    return max(math.sqrt(dx * dx + dy * dy + dz * dz), 20.0)


def validate_split_targets(ctx: Any, settings: SplitPlaneSettings) -> SplitPlaneCheck:
    try:
        ctx.document.ensure()
        meshes = list(ctx.document.meshes(include_preview=False))
    except Exception:
        return SplitPlaneCheck(False, "Open or create a scene before splitting meshes.")

    raw_indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    if not raw_indices:
        return SplitPlaneCheck(False, "Select one or more parts to split.")
    valid = tuple(i for i in sorted(set(raw_indices)) if 0 <= i < len(meshes))
    if not valid:
        return SplitPlaneCheck(False, "The split selection contains no valid scene object.")

    selected_points = scene_vertices(meshes, valid)
    before = sum(triangle_count(meshes[i]) for i in valid)
    if before <= 0:
        return SplitPlaneCheck(False, "Selected parts contain no triangles to split.", target_indices=valid, before_triangles=before)
    if len(selected_points) < 3:
        return SplitPlaneCheck(False, "Selected parts do not contain enough vertices to place a split plane.", target_indices=valid, before_triangles=before)
    if settings.plane_size_mm <= 0.0:
        return SplitPlaneCheck(False, "Plane size must be greater than zero.", target_indices=valid, before_triangles=before)
    if settings.tolerance <= 0.0:
        return SplitPlaneCheck(False, "Tolerance must be greater than zero.", target_indices=valid, before_triangles=before)

    center = center_of(selected_points)
    normal = settings.normal
    origin = (
        center[0] + normal[0] * settings.offset_mm,
        center[1] + normal[1] * settings.offset_mm,
        center[2] + normal[2] * settings.offset_mm,
    )
    return SplitPlaneCheck(
        True,
        f"Ready to split {len(valid)} part{'s' if len(valid) != 1 else ''} · {before} triangles · {settings.summary}.",
        target_indices=valid,
        selected_vertices=len(selected_points),
        before_triangles=before,
        center=center,
        origin=origin,
        normal=normal,
        plane_size_mm=settings.plane_size_mm,
    )


__all__ = [
    "SplitPlaneCheck",
    "bounds_size",
    "center_of",
    "scene_vertices",
    "triangle_count",
    "validate_split_targets",
]

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .settings import HollowMeshSettings


@dataclass(frozen=True, slots=True)
class HollowMeshCheck:
    ok: bool
    message: str
    target_indices: tuple[int, ...] = ()
    before_triangles: int = 0
    suggested_max_thickness: float | None = None


def triangle_count(mesh: Any) -> int:
    try:
        return int(len(getattr(mesh, "triangles", []) or []))
    except Exception:
        return 0


def _vertices(mesh: Any) -> tuple[tuple[float, float, float], ...]:
    points: list[tuple[float, float, float]] = []
    for value in getattr(mesh, "vertices", ()) or ():
        try:
            x, y, z = value[:3]
            points.append((float(x), float(y), float(z)))
        except Exception:
            return ()
    return tuple(points)


def _suggested_wall(meshes: list[Any], indices: tuple[int, ...]) -> float | None:
    limits: list[float] = []
    for index in indices:
        points = _vertices(meshes[index])
        if len(points) < 4:
            continue
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        zs = [p[2] for p in points]
        dims = [max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)]
        positive = [float(dim) for dim in dims if dim > 1e-8]
        if len(positive) == 3:
            limits.append(min(positive) * 0.45)
    if not limits:
        return None
    return max(0.001, min(limits))


def validate_hollow_targets(ctx: Any, settings: HollowMeshSettings) -> HollowMeshCheck:
    try:
        ctx.document.ensure()
        base_meshes = list(ctx.document.meshes(include_preview=False))
    except Exception:
        return HollowMeshCheck(False, "Open or create a scene before hollowing meshes.")

    raw_indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    if not raw_indices:
        return HollowMeshCheck(False, "Select one or more closed parts to hollow.")
    valid = tuple(i for i in sorted(set(raw_indices)) if 0 <= i < len(base_meshes))
    if not valid:
        return HollowMeshCheck(False, "The hollow selection contains no valid scene object.")
    before = sum(triangle_count(base_meshes[i]) for i in valid)
    if before <= 0:
        return HollowMeshCheck(False, "Selected parts contain no triangles to hollow.", target_indices=valid, before_triangles=before)
    if settings.thickness_mm <= 0.0:
        return HollowMeshCheck(False, "Wall thickness must be greater than zero.", target_indices=valid, before_triangles=before)
    suggested = _suggested_wall(base_meshes, valid)
    if suggested is not None and settings.thickness_mm >= suggested:
        return HollowMeshCheck(
            True,
            f"Ready, but wall thickness may be too large for the smallest selected part. Suggested maximum: {suggested:.3f} mm.",
            target_indices=valid,
            before_triangles=before,
            suggested_max_thickness=suggested,
        )
    return HollowMeshCheck(
        True,
        f"Ready to hollow {len(valid)} part{'s' if len(valid) != 1 else ''} · {before} triangles · {settings.summary}.",
        target_indices=valid,
        before_triangles=before,
        suggested_max_thickness=suggested,
    )


__all__ = ["HollowMeshCheck", "triangle_count", "validate_hollow_targets"]

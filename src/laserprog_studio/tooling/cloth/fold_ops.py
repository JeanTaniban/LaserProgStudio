"""Editable straight-fold operations for the Cloth panel graph."""
from __future__ import annotations

import math
from collections import deque

from .drawing import infer_fold_angle
from .models import ClothDocument, ClothFoldKind
from .topology import curve_endpoint_ids, patch_point_ids


class ClothFoldEditError(RuntimeError):
    pass


def set_fold_angle(document: ClothDocument, fold_id: str, angle_degrees: float) -> tuple[str, ...]:
    """Rotate the patch component on side B around the selected hinge.

    V1 intentionally supports tree-like fold graphs.  If removing the selected
    hinge does not separate the graph, the fold belongs to a cycle and changing
    one angle would require a constraint solver; the operation is rejected with
    a clear domain error instead of distorting the textile.
    """

    fold = document.folds.get(str(fold_id))
    if fold is None:
        raise ClothFoldEditError("Unknown Cloth fold.")
    target = float(angle_degrees)
    if not math.isfinite(target) or not -180.0 <= target <= 180.0:
        raise ClothFoldEditError("Fold angle must stay between -180° and 180°.")

    moving_patches = _component_after_cut(document, fold.patch_b_id, blocked_fold_id=fold.id)
    if fold.patch_a_id in moving_patches:
        raise ClothFoldEditError("This fold belongs to a closed panel cycle. V1 can only rotate tree-like folds.")

    curve = document.curves[fold.curve_id]
    start_id, end_id = curve_endpoint_ids(curve)
    if not start_id or not end_id:
        raise ClothFoldEditError("The fold edge is invalid.")
    start = document.points[start_id].position
    end = document.points[end_id].position
    axis = tuple(end[index] - start[index] for index in range(3))
    length = math.sqrt(sum(value * value for value in axis))
    if length <= 1.0e-9:
        raise ClothFoldEditError("The fold edge is degenerate.")
    axis = tuple(value / length for value in axis)

    current = infer_fold_angle(document, fold.curve_id, fold.patch_a_id, fold.patch_b_id)
    delta = math.radians(target - current)
    target_kind = ClothFoldKind.VALLEY if target > 1.0e-6 else ClothFoldKind.MOUNTAIN if target < -1.0e-6 else ClothFoldKind.NEUTRAL
    if abs(delta) <= 1.0e-12:
        if fold.angle_degrees != target or fold.kind is not target_kind:
            fold.angle_degrees = target
            fold.kind = target_kind
            document.revision += 1
        return ()

    stationary_patches = set(document.patches) - set(moving_patches)
    moving_points = set()
    for patch_id in moving_patches:
        moving_points.update(patch_point_ids(document, patch_id))
    stationary_points = set()
    for patch_id in stationary_patches:
        stationary_points.update(patch_point_ids(document, patch_id))
    shared_non_hinge = (moving_points & stationary_points) - {start_id, end_id}
    if shared_non_hinge:
        raise ClothFoldEditError("The moving panel component shares non-hinge points with the stationary side.")

    changed: list[str] = []
    for point_id in sorted(moving_points - {start_id, end_id}):
        point = document.points[point_id]
        point.position = _rotate_about_axis(point.position, start, axis, delta)
        changed.append(point_id)
    fold.angle_degrees = target
    fold.kind = target_kind
    # One revision represents the complete atomic fold edit, including the
    # angle metadata and all transformed vertices.
    document.revision += 1
    return tuple(changed)


def _component_after_cut(document: ClothDocument, start_patch_id: str, *, blocked_fold_id: str) -> set[str]:
    adjacency: dict[str, set[str]] = {patch_id: set() for patch_id in document.patches}
    for fold in document.folds.values():
        if fold.id == blocked_fold_id:
            continue
        adjacency.setdefault(fold.patch_a_id, set()).add(fold.patch_b_id)
        adjacency.setdefault(fold.patch_b_id, set()).add(fold.patch_a_id)
    visited: set[str] = set()
    queue = deque((str(start_patch_id),))
    while queue:
        patch_id = queue.popleft()
        if patch_id in visited:
            continue
        visited.add(patch_id)
        queue.extend(adjacency.get(patch_id, ()))
    return visited


def _rotate_about_axis(point, origin, axis, angle):
    px, py, pz = (float(point[index]) - float(origin[index]) for index in range(3))
    ax, ay, az = axis
    c = math.cos(angle)
    s = math.sin(angle)
    dot = ax * px + ay * py + az * pz
    cross = (ay * pz - az * py, az * px - ax * pz, ax * py - ay * px)
    return (
        float(origin[0]) + px * c + cross[0] * s + ax * dot * (1.0 - c),
        float(origin[1]) + py * c + cross[1] * s + ay * dot * (1.0 - c),
        float(origin[2]) + pz * c + cross[2] * s + az * dot * (1.0 - c),
    )


__all__ = ["ClothFoldEditError", "set_fold_angle"]

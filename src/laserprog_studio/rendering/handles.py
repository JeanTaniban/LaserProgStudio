# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SPLIT_HANDLE_SHAFT_RADIUS_RATIO = 0.0105
SPLIT_HANDLE_TIP_RADIUS_RATIO = 0.0360
SPLIT_HANDLE_TIP_LENGTH_RATIO = 0.24
SPLIT_HANDLE_SHAFT_RESOLUTION = 18
SPLIT_HANDLE_TIP_RESOLUTION = 24


@dataclass(frozen=True)
class ArrowHandleDimensions:
    """World-space dimensions for a camera-scaled arrow manipulator."""

    length: float
    shaft_radius: float
    tip_radius: float


def split_handle_dimensions_from_gizmo_length(gizmo_length: float) -> ArrowHandleDimensions:
    """Return the Cut/Split plane handle dimensions from a transform-gizmo scale.

    The split handle should use the same camera-driven basis as the transform
    gizmo, but with thinner proportions. Keeping the ratios in this rendering
    module prevents controller code from accumulating PyVista/VTK sizing magic.
    """
    eps = 1.0e-6
    basis = max(float(gizmo_length), eps)
    shaft_radius = max(basis * SPLIT_HANDLE_SHAFT_RADIUS_RATIO, eps)
    tip_radius = max(basis * SPLIT_HANDLE_TIP_RADIUS_RATIO, shaft_radius * 2.8, eps)
    return ArrowHandleDimensions(length=basis, shaft_radius=shaft_radius, tip_radius=tip_radius)


def make_arrow_handle_mesh(
    origin: tuple[float, float, float],
    forward: tuple[float, float, float],
    dimensions: ArrowHandleDimensions,
) -> Any:
    """Build an explicit cylinder+cone arrow mesh with world-space radii.

    Do not use ``pyvista.Arrow(scale=..., shaft_radius=...)`` for this handle:
    PyVista applies scale after the arrow source radii, which can multiply the
    visual thickness and create an oversized mushroom-shaped handle.
    """
    import numpy as np
    import pyvista as pv

    start = np.asarray(origin, dtype=float)
    direction = np.asarray(forward, dtype=float)
    norm = float(np.linalg.norm(direction))
    if norm <= 1.0e-12:
        direction = np.asarray((0.0, 0.0, 1.0), dtype=float)
    else:
        direction = direction / norm

    total_len = max(float(dimensions.length), 1.0e-6)
    tip_len = max(total_len * SPLIT_HANDLE_TIP_LENGTH_RATIO, 1.0e-6)
    shaft_len = max(total_len - tip_len, 1.0e-6)
    shaft_center = tuple(start + direction * (shaft_len * 0.5))
    tip_center = tuple(start + direction * (shaft_len + tip_len * 0.5))
    vec = (float(direction[0]), float(direction[1]), float(direction[2]))

    try:
        shaft = pv.Cylinder(
            center=shaft_center,
            direction=vec,
            radius=float(dimensions.shaft_radius),
            height=float(shaft_len),
            resolution=SPLIT_HANDLE_SHAFT_RESOLUTION,
        )
    except TypeError:
        shaft = pv.Cylinder(center=shaft_center, direction=vec, radius=float(dimensions.shaft_radius), height=float(shaft_len))

    try:
        tip = pv.Cone(
            center=tip_center,
            direction=vec,
            height=float(tip_len),
            radius=float(dimensions.tip_radius),
            resolution=SPLIT_HANDLE_TIP_RESOLUTION,
        )
    except TypeError:
        tip = pv.Cone(center=tip_center, direction=vec, height=float(tip_len), radius=float(dimensions.tip_radius))

    try:
        return shaft.merge(tip, merge_points=False)
    except TypeError:
        return shaft.merge(tip)
    except Exception:
        try:
            return shaft + tip
        except Exception:
            return pv.Arrow(
                start=origin,
                direction=tuple(direction * total_len),
                scale=1.0,
                tip_length=tip_len,
                tip_radius=float(dimensions.tip_radius),
                shaft_radius=float(dimensions.shaft_radius),
            )

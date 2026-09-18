# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from typing import Any

Bounds3D = tuple[float, float, float, float, float, float]
Line3D = tuple[tuple[float, float, float], tuple[float, float, float]]
GridLayerLines = dict[str, list[Line3D]]

FLOOR_GRID_MINOR_STEP_MM = 10.0
FLOOR_GRID_MAJOR_EVERY = 5
FLOOR_GRID_MIN_HALF_SPAN_MM = 420.0
FLOOR_GRID_MAX_MINOR_VALUES = 480
FLOOR_GRID_ORIGIN_RADIUS_FACTOR = 0.55


def bounds_size(bounds: Bounds3D) -> float:
    return max(
        float(bounds[1]) - float(bounds[0]),
        float(bounds[3]) - float(bounds[2]),
        float(bounds[5]) - float(bounds[4]),
        1.0,
    )


def floor_grid_plan(bounds: Bounds3D, requested_step: float = FLOOR_GRID_MINOR_STEP_MM) -> dict[str, Any]:
    """Return a viewport grid plan that includes the scene and the world origin.

    The grid is intentionally wider than the mesh bounds.  It is still finite
    geometry for VTK performance, but the span and layered styling make it read
    as an infinite workplane in normal use.
    """

    base_step = max(float(requested_step), 0.1)
    size = max(bounds_size(bounds), 40.0)

    ux0 = min(float(bounds[0]), 0.0)
    ux1 = max(float(bounds[1]), 0.0)
    uy0 = min(float(bounds[2]), 0.0)
    uy1 = max(float(bounds[3]), 0.0)

    union_w = max(ux1 - ux0, base_step * 8.0)
    union_h = max(uy1 - uy0, base_step * 8.0)
    cx = (ux0 + ux1) * 0.5
    cy = (uy0 + uy1) * 0.5

    half_x = max(union_w * 1.15, size * 1.35, FLOOR_GRID_MIN_HALF_SPAN_MM, base_step * 42.0)
    half_y = max(union_h * 1.15, size * 1.35, FLOOR_GRID_MIN_HALF_SPAN_MM, base_step * 42.0)

    xmin = math.floor((cx - half_x) / base_step) * base_step
    xmax = math.ceil((cx + half_x) / base_step) * base_step
    ymin = math.floor((cy - half_y) / base_step) * base_step
    ymax = math.ceil((cy + half_y) / base_step) * base_step

    x_count = int(round((xmax - xmin) / base_step)) + 1
    y_count = int(round((ymax - ymin) / base_step)) + 1
    step = base_step
    if x_count + y_count > FLOOR_GRID_MAX_MINOR_VALUES:
        factor = math.ceil((x_count + y_count) / FLOOR_GRID_MAX_MINOR_VALUES)
        step = base_step * float(factor)
        xmin = math.floor(xmin / step) * step
        xmax = math.ceil(xmax / step) * step
        ymin = math.floor(ymin / step) * step
        ymax = math.ceil(ymax / step) * step

    major_step = step * float(FLOOR_GRID_MAJOR_EVERY)
    z = min(0.0, float(bounds[4]) - 0.002)
    return {
        "xmin": float(xmin),
        "xmax": float(xmax),
        "ymin": float(ymin),
        "ymax": float(ymax),
        "z": float(z),
        "step": float(step),
        "major_step": float(major_step),
        "origin_radius": max(step * FLOOR_GRID_ORIGIN_RADIUS_FACTOR, 4.0),
    }


def _axis_value(value: float, step: float) -> bool:
    return abs(float(value)) <= max(float(step) * 1e-7, 1e-8)


def _major_value(value: float, major_step: float) -> bool:
    if major_step <= 0:
        return False
    nearest = round(float(value) / float(major_step)) * float(major_step)
    return abs(float(value) - nearest) <= max(float(major_step) * 1e-7, 1e-8)


def _stepped_values(vmin: float, vmax: float, step: float) -> list[float]:
    start = int(math.floor(float(vmin) / float(step)))
    end = int(math.ceil(float(vmax) / float(step)))
    return [float(i) * float(step) for i in range(start, end + 1)]


def _add_line(lines: list[Line3D], a: tuple[float, float, float], b: tuple[float, float, float]) -> None:
    lines.append(((float(a[0]), float(a[1]), float(a[2])), (float(b[0]), float(b[1]), float(b[2]))))


def floor_grid_layers(bounds: Bounds3D, requested_step: float = FLOOR_GRID_MINOR_STEP_MM) -> tuple[dict[str, Any], GridLayerLines]:
    """Build semantic line layers for a readable origin-centered floor grid."""

    plan = floor_grid_plan(bounds, requested_step=requested_step)
    step = float(plan["step"])
    major_step = float(plan["major_step"])
    xmin = float(plan["xmin"])
    xmax = float(plan["xmax"])
    ymin = float(plan["ymin"])
    ymax = float(plan["ymax"])
    z = float(plan["z"])

    layers: GridLayerLines = {"minor": [], "major": [], "axis_x": [], "axis_y": [], "origin": []}

    for x in _stepped_values(xmin, xmax, step):
        if _axis_value(x, step):
            _add_line(layers["axis_y"], (0.0, ymin, z + 0.0012), (0.0, ymax, z + 0.0012))
        elif _major_value(x, major_step):
            _add_line(layers["major"], (x, ymin, z + 0.0006), (x, ymax, z + 0.0006))
        else:
            _add_line(layers["minor"], (x, ymin, z), (x, ymax, z))

    for y in _stepped_values(ymin, ymax, step):
        if _axis_value(y, step):
            _add_line(layers["axis_x"], (xmin, 0.0, z + 0.0014), (xmax, 0.0, z + 0.0014))
        elif _major_value(y, major_step):
            _add_line(layers["major"], (xmin, y, z + 0.0006), (xmax, y, z + 0.0006))
        else:
            _add_line(layers["minor"], (xmin, y, z), (xmax, y, z))

    r = float(plan["origin_radius"])
    segments = 36
    previous = (math.cos(0.0) * r, math.sin(0.0) * r, z + 0.0020)
    for i in range(1, segments + 1):
        a = 2.0 * math.pi * float(i) / float(segments)
        current = (math.cos(a) * r, math.sin(a) * r, z + 0.0020)
        _add_line(layers["origin"], previous, current)
        previous = current
    _add_line(layers["origin"], (-r * 1.35, 0.0, z + 0.0022), (r * 1.35, 0.0, z + 0.0022))
    _add_line(layers["origin"], (0.0, -r * 1.35, z + 0.0022), (0.0, r * 1.35, z + 0.0022))

    return plan, layers


__all__ = [
    "FLOOR_GRID_MAJOR_EVERY",
    "FLOOR_GRID_MINOR_STEP_MM",
    "floor_grid_layers",
    "floor_grid_plan",
]

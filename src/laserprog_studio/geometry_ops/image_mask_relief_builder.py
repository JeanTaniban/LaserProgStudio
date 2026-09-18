# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .image_mask_relief_heightfield import _build_grayscale_heightfield_mesh
from .image_mask_relief_types import MaskReliefResult
from .image_mask_relief_vector import _build_binary_vector_mesh


def build_mask_relief_mesh(
    path: str | Path,
    *,
    max_height_mm: float,
    pixel_size_mm: float = 1.0,
    invert: bool = False,
    binary: bool = False,
    binary_threshold: float = 0.5,
    max_grid_size: int = 240,
    name: str | None = None,
    color: str = "#8E8E8E",
    levels: float | None = None,
    smooth: float = 0.0,
) -> MaskReliefResult:
    """Convert a PNG/JPG mask to a closed 3D mesh.

    - Grayscale mode keeps the historical heightfield pipeline.
    - Binary mode vectorises the cleaned mask, triangulates the resulting
      polygons and extrudes them, which avoids heavy per-pixel column meshes.
    - ``levels`` enables the simplified smart importer: 50 uses an automatic
      threshold, lower values are stricter, higher values keep more detail.
    - ``smooth`` rounds and simplifies the vector contour after thresholding.
    """

    mesh_name = name or f"mask_relief_{Path(path).stem}"
    if bool(binary):
        return _build_binary_vector_mesh(
            path,
            max_height_mm=float(max_height_mm),
            pixel_size_mm=float(pixel_size_mm),
            invert=bool(invert),
            binary_threshold=float(binary_threshold),
            max_grid_size=int(max_grid_size),
            name=mesh_name,
            color=color,
            levels=levels,
            smooth=float(smooth),
        )
    return _build_grayscale_heightfield_mesh(
        path,
        max_height_mm=float(max_height_mm),
        pixel_size_mm=float(pixel_size_mm),
        invert=bool(invert),
        max_grid_size=int(max_grid_size),
        name=mesh_name,
        color=color,
    )

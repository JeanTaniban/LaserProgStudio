# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from pathlib import Path

from .image_mask_relief_types import MaskPhysicalSize, MaskReliefResult, MaskReliefStats


def _build_binary_vector_mesh(
    path: str | Path,
    *,
    max_height_mm: float,
    pixel_size_mm: float,
    invert: bool,
    binary_threshold: float,
    max_grid_size: int,
    name: str,
    color: str,
    levels: float | None = None,
    smooth: float = 0.0,
    physical_size: MaskPhysicalSize | None = None,
    legacy_size_cap_px: int | None = None,
) -> MaskReliefResult:
    """Create a certified solid from a sub-pixel binary-mask footprint.

    Raster/vector processing is completed before any 3D mesh is built. The
    footprint is then extruded through the same planar-solid boundary used by
    Plan Tracer, so Image Mask no longer maintains a private 3D triangulator.
    """

    from shapely.geometry import MultiPolygon, Polygon

    from laserprog_studio.planar_tools import make_locked_plane

    from .image_mask_relief_contour import build_binary_mask_footprint
    from .planar_boolean_solid import extrude_planar_regions_boolean_ready

    max_h = float(max_height_mm)
    if not math.isfinite(max_h) or max_h <= 1.0e-9:
        raise ValueError("Mask height must be greater than zero.")

    footprint = build_binary_mask_footprint(
        path,
        pixel_size_mm=float(pixel_size_mm),
        invert=bool(invert),
        binary_threshold=float(binary_threshold),
        levels=levels,
        smooth=float(smooth),
        max_grid_size=int(max_grid_size),
        physical_size=physical_size,
        legacy_size_cap_px=legacy_size_cap_px,
    )
    geometry = footprint.geometry

    if isinstance(geometry, Polygon):
        polygons = [geometry]
    elif isinstance(geometry, MultiPolygon):
        polygons = [poly for poly in geometry.geoms if not poly.is_empty]
    else:
        polygons = [
            poly
            for poly in getattr(geometry, "geoms", ())
            if isinstance(poly, Polygon) and not poly.is_empty
        ]
    if not polygons:
        raise ValueError("No valid polygon contour was found in the binary mask.")

    regions = []
    for poly in polygons:
        outer = tuple((float(x), float(y)) for x, y in list(poly.exterior.coords)[:-1])
        holes = tuple(
            tuple((float(x), float(y)) for x, y in list(ring.coords)[:-1])
            for ring in poly.interiors
        )
        if len(outer) >= 3:
            regions.append((outer, holes))
    if not regions:
        raise ValueError("The binary mask contains no manufacturable planar region.")

    mesh, solid_report = extrude_planar_regions_boolean_ready(
        regions,
        plane=make_locked_plane("top"),
        depth=max_h,
        name=name,
        color=color,
    )

    metadata = dict(getattr(mesh, "metadata", {}) or {})
    metadata.update(
        {
            "source_tool": "mask_relief",
            "mask_contour_contract": "subpixel_marching_squares_v1",
            "mask_source_width": int(footprint.source_size[0]),
            "mask_source_height": int(footprint.source_size[1]),
            "mask_grid_width": int(footprint.width),
            "mask_grid_height": int(footprint.height),
            "mask_step_x_mm": float(footprint.step_x_mm),
            "mask_step_y_mm": float(footprint.step_y_mm),
            "mask_physical_width_mm": float(footprint.physical_width_mm),
            "mask_physical_height_mm": float(footprint.physical_height_mm),
            "mask_smooth": float(smooth),
            "mask_threshold": float(footprint.threshold),
            "mask_extrusion_backend": str(solid_report.backend),
        }
    )
    metadata.pop("boolean_skip_merge", None)
    mesh.metadata = metadata

    stats = MaskReliefStats(
        source_width=int(footprint.source_size[0]),
        source_height=int(footprint.source_size[1]),
        width=int(footprint.width),
        height=int(footprint.height),
        active_pixels=int(footprint.active_pixels),
        vertices=len(mesh.vertices),
        triangles=len(mesh.triangles),
        max_height_mm=max_h,
        pixel_size_mm=float(pixel_size_mm),
        downsampled=bool(footprint.downsampled),
        binary=True,
        binary_threshold=float(footprint.threshold),
    )
    return MaskReliefResult(mesh=mesh, stats=stats)


__all__ = ["_build_binary_vector_mesh"]

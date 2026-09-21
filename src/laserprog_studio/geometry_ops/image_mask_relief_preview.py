# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .image_mask_relief_contour import build_binary_mask_footprint
from .image_mask_relief_loading import _resample_filter
from .image_mask_relief_types import MaskPhysicalSize


def render_mask_preview_image(
    path: str | Path,
    *,
    invert: bool = False,
    levels: float | None = 50.0,
    smooth: float = 35.0,
    max_grid_size: int = 512,
    max_preview_size: tuple[int, int] = (380, 240),
    physical_size: MaskPhysicalSize | None = None,
    legacy_size_cap_px: int | None = None,
):
    """Rasterize the exact vector footprint used by the binary 3D importer."""

    from PIL import Image, ImageDraw
    from shapely.geometry import MultiPolygon, Polygon

    footprint = build_binary_mask_footprint(
        path,
        pixel_size_mm=1.0,
        invert=bool(invert),
        binary_threshold=0.5,
        levels=levels,
        smooth=float(smooth),
        max_grid_size=int(max_grid_size),
        physical_size=physical_size,
        legacy_size_cap_px=legacy_size_cap_px,
    )
    rows = int(footprint.height)
    cols = int(footprint.width)
    max_w = max(1, int(max_preview_size[0]))
    max_h = max(1, int(max_preview_size[1]))
    raster_scale = 4
    raster_size = (max(1, cols * raster_scale), max(1, rows * raster_scale))

    preview = Image.new("RGB", raster_size, "white")
    draw = ImageDraw.Draw(preview)
    geom = footprint.geometry
    if isinstance(geom, Polygon):
        polygons = [geom]
    elif isinstance(geom, MultiPolygon):
        polygons = [poly for poly in geom.geoms if isinstance(poly, Polygon) and not poly.is_empty]
    else:
        polygons = [
            poly
            for poly in getattr(geom, "geoms", ())
            if isinstance(poly, Polygon) and not poly.is_empty
        ]

    material = (17, 24, 39)
    width_mm = max(float(footprint.physical_width_mm), 1.0e-12)
    height_mm = max(float(footprint.physical_height_mm), 1.0e-12)
    x_min = -width_mm / 2.0
    y_max = height_mm / 2.0
    sx = float(raster_size[0]) / width_mm
    sy = float(raster_size[1]) / height_mm

    def scale_point(point: tuple[float, float]) -> tuple[float, float]:
        x, y = float(point[0]), float(point[1])
        return ((x - x_min) * sx, (y_max - y) * sy)

    for poly in polygons:
        exterior = [scale_point((float(x), float(y))) for x, y in poly.exterior.coords]
        if len(exterior) >= 3:
            draw.polygon(exterior, fill=material)
        for ring in poly.interiors:
            hole = [scale_point((float(x), float(y))) for x, y in ring.coords]
            if len(hole) >= 3:
                draw.polygon(hole, fill="white")

    if preview.width > max_w or preview.height > max_h:
        if float(smooth) <= 0.0:
            try:
                resample = Image.Resampling.NEAREST
            except Exception:  # pragma: no cover - older Pillow fallback
                resample = Image.NEAREST
        else:
            resample = _resample_filter()
        preview.thumbnail((max_w, max_h), resample)
    return preview

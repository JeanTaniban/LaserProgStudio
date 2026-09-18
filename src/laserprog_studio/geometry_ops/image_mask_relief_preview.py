# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from .image_mask_relief_loading import _load_binary_mask, _resample_filter
from .image_mask_relief_vector import _binary_mask_to_smoothed_geometry


def _draw_binary_mask_fallback(mask: list[list[bool]]):
    from PIL import Image

    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    image = Image.new("RGB", (max(1, cols), max(1, rows)), "white")
    pixels = image.load()
    for r, row in enumerate(mask):
        for c, active in enumerate(row):
            if bool(active):
                pixels[c, r] = (17, 24, 39)
    return image


def render_mask_preview_image(
    path: str | Path,
    *,
    invert: bool = False,
    levels: float | None = 50.0,
    smooth: float = 35.0,
    max_grid_size: int = 512,
    max_preview_size: tuple[int, int] = (380, 240),
):
    """Return the simplified 2D mask preview used by the import dialog.

    The preview mirrors the binary importer: transparent areas are composited on
    white, Levels changes the binary threshold, Invert swaps material/background,
    and Smooth previews the vector-cleaned footprint instead of the raw pixels.
    Black pixels represent the final 10 mm material, white pixels represent void.
    """

    from PIL import Image, ImageDraw
    from shapely.geometry import MultiPolygon, Polygon

    mask, _source_size, _downsampled, _threshold = _load_binary_mask(
        path,
        invert=bool(invert),
        binary_threshold=0.5,
        levels=levels,
        smooth=float(smooth),
        max_grid_size=int(max_grid_size),
    )
    rows = len(mask)
    cols = len(mask[0]) if rows else 0
    if rows <= 0 or cols <= 0:
        return Image.new("RGB", (1, 1), "white")

    geom, active_pixels = _binary_mask_to_smoothed_geometry(mask, pixel_size_mm=1.0, smooth=float(smooth))
    max_w = max(1, int(max_preview_size[0]))
    max_h = max(1, int(max_preview_size[1]))
    raster_scale = 4
    raster_size = (max(1, cols * raster_scale), max(1, rows * raster_scale))

    if geom is None or active_pixels <= 0 or getattr(geom, "is_empty", False):
        preview = _draw_binary_mask_fallback(mask).resize(raster_size, Image.Resampling.NEAREST if hasattr(Image, "Resampling") else Image.NEAREST)
    else:
        preview = Image.new("RGB", raster_size, "white")
        draw = ImageDraw.Draw(preview)
        polygons: list[Polygon]
        if isinstance(geom, Polygon):
            polygons = [geom]
        elif isinstance(geom, MultiPolygon):
            polygons = [poly for poly in geom.geoms if isinstance(poly, Polygon) and not poly.is_empty]
        else:
            polygons = [poly for poly in getattr(geom, "geoms", []) if isinstance(poly, Polygon) and not poly.is_empty]
        material = (17, 24, 39)

        def scale_point(point: tuple[float, float]) -> tuple[float, float]:
            x, y = point
            return float(x) * float(raster_scale), float(y) * float(raster_scale)

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

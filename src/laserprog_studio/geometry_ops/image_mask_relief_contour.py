# -*- coding: utf-8 -*-
"""Sub-pixel vector footprint generation for binary image masks.

The public image-mask tool should treat raster processing and 3D solid
construction as separate responsibilities.  This module owns only the first
half: image -> scalar activity -> threshold iso-contour -> safe 2D smoothing.

It deliberately returns Shapely geometry, not a WorkMesh.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np

from .image_mask_relief_loading import _clamp_float, _otsu_threshold, _resample_filter


@dataclass(frozen=True, slots=True)
class BinaryMaskFootprint:
    geometry: Any
    source_size: tuple[int, int]
    width: int
    height: int
    active_pixels: int
    downsampled: bool
    threshold: float
    step_x_mm: float
    step_y_mm: float
    physical_width_mm: float
    physical_height_mm: float


def _iter_polygons(geometry: Any) -> tuple[Any, ...]:
    if geometry is None or bool(getattr(geometry, "is_empty", True)):
        return ()
    kind = str(getattr(geometry, "geom_type", "") or "")
    if kind == "Polygon":
        return (geometry,)
    if kind == "MultiPolygon":
        return tuple(poly for poly in geometry.geoms if not poly.is_empty)
    if hasattr(geometry, "geoms"):
        return tuple(poly for part in geometry.geoms for poly in _iter_polygons(part))
    return ()


def _load_activity(
    path: str | Path,
    *,
    invert: bool,
    binary_threshold: float | None,
    levels: float | None,
    max_grid_size: int,
) -> tuple[np.ndarray, tuple[int, int], bool, float]:
    """Return continuous material activity (0..255) and the selected threshold."""

    from PIL import Image

    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")

    with Image.open(p) as img:
        rgba = img.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        gray = Image.alpha_composite(white, rgba).convert("L")
        source_size = (int(gray.width), int(gray.height))
        downsampled = False
        max_grid = int(max_grid_size)
        if max_grid > 0 and max(gray.size) > max_grid:
            w, h = gray.size
            if w >= h:
                nw = max_grid
                nh = max(1, int(round(h * max_grid / max(w, 1))))
            else:
                nh = max_grid
                nw = max(1, int(round(w * max_grid / max(h, 1))))
            gray = gray.resize((nw, nh), _resample_filter())
            downsampled = True
        gray_array = np.asarray(gray, dtype=np.uint8)

    activity = gray_array if bool(invert) else (255 - gray_array)
    activity = np.asarray(activity, dtype=np.float64)

    hist = np.bincount(np.asarray(activity, dtype=np.uint8).ravel(), minlength=256).tolist()
    if levels is None:
        threshold_norm = _clamp_float(float(binary_threshold or 0.5), 0.0, 1.0)
        threshold_byte = int(math.ceil(threshold_norm * 255.0))
    else:
        level = _clamp_float(float(levels), 0.0, 100.0)
        automatic = _otsu_threshold(hist)
        threshold_byte = int(round(float(automatic) + (50.0 - level) * 1.9))
        threshold_byte = max(8, min(247, threshold_byte))
        threshold_norm = float(threshold_byte) / 255.0

    threshold_byte = max(0, min(255, int(threshold_byte)))
    return activity, source_size, bool(downsampled), float(threshold_norm)


def _point_key(point: tuple[float, float]) -> tuple[float, float]:
    # Shared cell edges must polygonize to exactly the same endpoint.
    return (round(float(point[0]), 12), round(float(point[1]), 12))


def _ambiguous_case_pairs(
    case: int,
    values: tuple[float, float, float, float],
    threshold: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Resolve marching-squares saddle cases with the asymptotic decider."""

    if int(case) not in (5, 10):
        raise ValueError("Asymptotic decider is only defined for cases 5 and 10.")
    a = float(values[0]) - float(threshold)
    b = float(values[1]) - float(threshold)
    c = float(values[2]) - float(threshold)
    d = float(values[3]) - float(threshold)
    q = a * c - b * d
    if int(case) == 5:
        return ((0, 3), (1, 2)) if q < 0.0 else ((0, 1), (3, 2))
    return ((0, 1), (3, 2)) if q > 0.0 else ((0, 3), (1, 2))


def _bilinear_sample(array: np.ndarray, row: float, col: float) -> float:
    """Sample a 2D scalar array continuously in array-index coordinates."""

    data = np.asarray(array, dtype=np.float64)
    if data.ndim != 2 or data.size <= 0:
        raise ValueError("Bilinear sampling requires a non-empty 2D array.")
    rows, cols = int(data.shape[0]), int(data.shape[1])
    rr = max(0.0, min(float(rows - 1), float(row)))
    cc = max(0.0, min(float(cols - 1), float(col)))
    r0 = min(max(int(math.floor(rr)), 0), rows - 1)
    c0 = min(max(int(math.floor(cc)), 0), cols - 1)
    r1 = min(r0 + 1, rows - 1)
    c1 = min(c0 + 1, cols - 1)
    ty = max(0.0, min(1.0, rr - float(r0)))
    tx = max(0.0, min(1.0, cc - float(c0)))
    top = float(data[r0, c0]) * (1.0 - tx) + float(data[r0, c1]) * tx
    bottom = float(data[r1, c0]) * (1.0 - tx) + float(data[r1, c1]) * tx
    return top * (1.0 - ty) + bottom * ty


def _subpixel_footprint(
    activity: np.ndarray,
    *,
    threshold_byte: float,
    physical_width_mm: float,
    physical_height_mm: float,
) -> Any:
    """Extract an interpolated threshold contour with marching squares."""

    from shapely import make_valid
    from shapely.geometry import LineString, box
    from shapely.ops import polygonize, unary_union

    values = np.asarray(activity, dtype=np.float64)
    if values.ndim != 2 or values.size <= 0:
        raise ValueError("Empty mask activity field.")
    rows, cols = int(values.shape[0]), int(values.shape[1])
    step_x = float(physical_width_mm) / max(cols, 1)
    step_y = float(physical_height_mm) / max(rows, 1)
    x_min = -float(physical_width_mm) / 2.0
    y_max = float(physical_height_mm) / 2.0

    padded = np.zeros((rows + 2, cols + 2), dtype=np.float64)
    padded[1:-1, 1:-1] = values
    threshold = float(threshold_byte)

    def sample_point(pr: int, pc: int) -> tuple[float, float]:
        # Padded sample (1,1) is the center of source pixel (0,0).
        return (
            x_min + (float(pc) - 0.5) * step_x,
            y_max - (float(pr) - 0.5) * step_y,
        )

    def interpolate(
        p0: tuple[float, float],
        p1: tuple[float, float],
        v0: float,
        v1: float,
    ) -> tuple[float, float]:
        dv = float(v1) - float(v0)
        t = 0.5 if abs(dv) <= 1.0e-12 else (threshold - float(v0)) / dv
        t = max(0.0, min(1.0, float(t)))
        return _point_key(
            (
                p0[0] + (p1[0] - p0[0]) * t,
                p0[1] + (p1[1] - p0[1]) * t,
            )
        )

    # Bits: TL=8, TR=4, BR=2, BL=1. Edges: top=0, right=1,
    # bottom=2, left=3.
    standard_cases: dict[int, tuple[tuple[int, int], ...]] = {
        0: (),
        1: ((3, 2),),
        2: ((2, 1),),
        3: ((3, 1),),
        4: ((0, 1),),
        6: ((0, 2),),
        7: ((0, 3),),
        8: ((3, 0),),
        9: ((0, 2),),
        11: ((0, 1),),
        12: ((3, 1),),
        13: ((2, 1),),
        14: ((3, 2),),
        15: (),
    }

    lines: list[Any] = []
    for r in range(rows + 1):
        for c in range(cols + 1):
            vals = (
                float(padded[r, c]),
                float(padded[r, c + 1]),
                float(padded[r + 1, c + 1]),
                float(padded[r + 1, c]),
            )
            bits = tuple(value >= threshold for value in vals)
            case = (
                (8 if bits[0] else 0)
                | (4 if bits[1] else 0)
                | (2 if bits[2] else 0)
                | (1 if bits[3] else 0)
            )
            if case in (0, 15):
                continue

            pts = (
                sample_point(r, c),
                sample_point(r, c + 1),
                sample_point(r + 1, c + 1),
                sample_point(r + 1, c),
            )
            edges = {
                0: interpolate(pts[0], pts[1], vals[0], vals[1]),
                1: interpolate(pts[1], pts[2], vals[1], vals[2]),
                2: interpolate(pts[3], pts[2], vals[3], vals[2]),
                3: interpolate(pts[0], pts[3], vals[0], vals[3]),
            }

            if case in (5, 10):
                pairs = _ambiguous_case_pairs(case, vals, threshold)
            else:
                pairs = standard_cases.get(case, ())

            for first, second in pairs:
                a, b = edges[first], edges[second]
                if math.hypot(b[0] - a[0], b[1] - a[1]) <= 1.0e-10:
                    continue
                lines.append(LineString((a, b)))

    if not lines:
        raise ValueError("The binary mask contains no closed material contour.")

    faces = tuple(polygonize(lines))
    if not faces:
        raise ValueError("The binary mask contour could not be polygonized.")

    def sample_activity_at_world(x: float, y: float) -> float:
        """Bilinearly evaluate the same scalar field used for contouring."""

        pc = (float(x) - x_min) / max(step_x, 1.0e-12) + 0.5
        pr = (y_max - float(y)) / max(step_y, 1.0e-12) + 0.5
        return _bilinear_sample(padded, pr, pc)

    def is_material_face(face: Any) -> bool:
        probe = face.representative_point()
        return sample_activity_at_world(float(probe.x), float(probe.y)) >= threshold

    selected = [face for face in faces if not face.is_empty and is_material_face(face)]
    if not selected:
        raise ValueError("The binary mask contains no material after contour extraction.")

    geometry = unary_union(selected)
    # The padded outside samples are only a contour-closing device. They must
    # never make the physical mask extend beyond the source image rectangle.
    image_bounds = box(
        x_min,
        y_max - float(physical_height_mm),
        x_min + float(physical_width_mm),
        y_max,
    )
    geometry = geometry.intersection(image_bounds)
    if not bool(getattr(geometry, "is_valid", False)):
        try:
            geometry = make_valid(geometry)
        except Exception:
            geometry = geometry.buffer(0)
    polygons = _iter_polygons(geometry)
    if not polygons:
        raise ValueError("The binary mask contour contains no valid polygon.")
    geometry = unary_union(polygons)
    if not bool(getattr(geometry, "is_valid", False)):
        geometry = geometry.buffer(0)
    if bool(getattr(geometry, "is_empty", True)):
        raise ValueError("The binary mask contour collapsed during normalization.")
    return geometry


def _topology_signature(geometry: Any) -> tuple[int, tuple[int, ...]]:
    polygons = _iter_polygons(geometry)
    return (len(polygons), tuple(sorted(len(poly.interiors) for poly in polygons)))


def _safe_smooth_footprint(geometry: Any, *, sample_step_mm: float, smooth: float) -> Any:
    """Simplify a sub-pixel footprint without changing its topology."""

    level = _clamp_float(float(smooth), 0.0, 100.0)
    if level <= 0.0:
        return geometry

    reference = geometry
    signature = _topology_signature(reference)
    ref_area = max(float(getattr(reference, "area", 0.0)), 1.0e-12)
    step = max(float(sample_step_mm), 1.0e-9)
    target_tolerance = step * (0.04 + 0.76 * level / 100.0)
    max_displacement = step * (0.15 + 0.85 * level / 100.0)

    def acceptable(candidate: Any) -> bool:
        if candidate is None or bool(getattr(candidate, "is_empty", True)):
            return False
        if not bool(getattr(candidate, "is_valid", False)):
            return False
        if _topology_signature(candidate) != signature:
            return False
        cand_area = float(getattr(candidate, "area", 0.0))
        if cand_area <= 0.0:
            return False
        if abs(cand_area - ref_area) > max(ref_area * 0.08, step * step * 4.0):
            return False
        try:
            changed = float(candidate.symmetric_difference(reference).area)
            if changed > max(ref_area * 0.10, step * step * 8.0):
                return False
        except Exception:
            return False
        try:
            if float(candidate.hausdorff_distance(reference)) > max_displacement:
                return False
        except Exception:
            return False
        return True

    # Try the requested level first, then back off deterministically.  A high
    # Smooth request is allowed to produce a milder result, never a broken one.
    for factor in (1.0, 0.75, 0.5, 0.25):
        tolerance = target_tolerance * factor
        try:
            candidate = reference.simplify(float(tolerance), preserve_topology=True)
        except Exception:
            continue
        if acceptable(candidate):
            return candidate
    return reference


def build_binary_mask_footprint(
    path: str | Path,
    *,
    pixel_size_mm: float = 1.0,
    invert: bool = False,
    binary_threshold: float = 0.5,
    levels: float | None = None,
    smooth: float = 0.0,
    max_grid_size: int = 512,
) -> BinaryMaskFootprint:
    """Build the shared, scale-preserving vector footprint for a 2D mask."""

    activity, source_size, downsampled, threshold_norm = _load_activity(
        path,
        invert=bool(invert),
        binary_threshold=float(binary_threshold),
        levels=levels,
        max_grid_size=int(max_grid_size),
    )
    rows, cols = int(activity.shape[0]), int(activity.shape[1])
    if rows <= 0 or cols <= 0:
        raise ValueError("Empty or unreadable image.")

    source_pixel = max(1.0e-9, float(pixel_size_mm))
    physical_width = float(source_size[0]) * source_pixel
    physical_height = float(source_size[1]) * source_pixel
    step_x = physical_width / float(cols)
    step_y = physical_height / float(rows)
    threshold_byte = float(threshold_norm) * 255.0
    active_pixels = int(np.count_nonzero(activity >= threshold_byte))
    if active_pixels <= 0:
        raise ValueError(
            "The binary mask contains no material. Adjust Levels, enable Invert, "
            "or use a higher-contrast image."
        )

    geometry = _subpixel_footprint(
        activity,
        threshold_byte=threshold_byte,
        physical_width_mm=physical_width,
        physical_height_mm=physical_height,
    )
    geometry = _safe_smooth_footprint(
        geometry,
        sample_step_mm=max(step_x, step_y),
        smooth=float(smooth),
    )

    return BinaryMaskFootprint(
        geometry=geometry,
        source_size=(int(source_size[0]), int(source_size[1])),
        width=cols,
        height=rows,
        active_pixels=active_pixels,
        downsampled=bool(downsampled),
        threshold=float(threshold_norm),
        step_x_mm=float(step_x),
        step_y_mm=float(step_y),
        physical_width_mm=float(physical_width),
        physical_height_mm=float(physical_height),
    )


__all__ = [
    "BinaryMaskFootprint",
    "build_binary_mask_footprint",
    "_ambiguous_case_pairs",
    "_bilinear_sample",
]

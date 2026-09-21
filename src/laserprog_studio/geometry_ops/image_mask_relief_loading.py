# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from pathlib import Path


def _resample_filter() -> int:
    from PIL import Image

    # Pillow 9/10 API selection.
    try:
        return Image.Resampling.LANCZOS
    except Exception:  # pragma: no cover - older Pillow fallback
        return Image.LANCZOS


def _load_height_map(
    path: str | Path,
    *,
    max_height_mm: float,
    invert: bool = False,
    binary: bool = False,
    binary_threshold: float = 0.5,
    max_grid_size: int = 240,
) -> tuple[list[list[float]], tuple[int, int], bool]:
    """Load an image as a black=high, white=empty height map.

    The returned map is indexed [row][column]. Values are in millimetres.
    When binary is enabled, relief values are thresholded using
    ``binary_threshold`` after the optional inversion step. By default very
    large images are resampled to protect the UI from creating millions of tiny
    cells. Passing ``max_grid_size <= 0`` disables this guard.
    """

    from PIL import Image

    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Image introuvable : {p}")
    max_h = max(0.0, float(max_height_mm))
    threshold = max(0.0, min(1.0, float(binary_threshold)))
    with Image.open(p) as img:
        gray = img.convert("L")
        source_size = gray.size
        max_grid = int(max_grid_size)
        downsampled = False
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
        width, height = gray.size
        pixels = gray.tobytes()

    heights: list[list[float]] = []
    for row in range(height):
        line: list[float] = []
        base = row * width
        for col in range(width):
            value = int(pixels[base + col])
            # Normal mode: black=100%, white=0%. Invert swaps that relation.
            relief = (value / 255.0) if invert else (1.0 - value / 255.0)
            relief = max(0.0, min(1.0, relief))
            if binary:
                relief = 1.0 if relief >= threshold else 0.0
            h_mm = max_h * relief
            # Snap almost-white to real void, avoiding microscopic sliver faces.
            if h_mm <= max(max_h * 1e-6, 1e-9):
                h_mm = 0.0
            line.append(float(h_mm))
        heights.append(line)
    return heights, source_size, downsampled


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(float(minimum), min(float(maximum), float(value)))


def _otsu_threshold(hist: list[int]) -> int:
    """Return a stable automatic material threshold for a 0..255 histogram.

    Otsu can have a whole plateau of equally optimal thresholds when the image
    contains separated intensity bands (the extreme case is a pure black/white
    mask). Picking the *first* optimum biases the threshold toward the darker
    peak and can make diagonal pixels connect through the interpolated field.
    Choose the midpoint of the optimal plateau instead.
    """

    total = int(sum(int(v) for v in hist))
    if total <= 0:
        return 127
    sum_total = sum(i * int(v) for i, v in enumerate(hist))
    weight_bg = 0
    sum_bg = 0.0
    scores: list[tuple[int, float]] = []
    for t, count in enumerate(hist):
        weight_bg += int(count)
        if weight_bg <= 0:
            continue
        weight_fg = total - weight_bg
        if weight_fg <= 0:
            break
        sum_bg += float(t * int(count))
        mean_bg = sum_bg / float(weight_bg)
        mean_fg = (float(sum_total) - sum_bg) / float(weight_fg)
        score = float(weight_bg) * float(weight_fg) * (mean_bg - mean_fg) ** 2
        scores.append((int(t), float(score)))
    if not scores:
        return 127
    best_score = max(score for _t, score in scores)
    if best_score <= 0.0:
        return 127
    tolerance = max(1.0e-12, abs(best_score) * 1.0e-12)
    optimal = [t for t, score in scores if abs(score - best_score) <= tolerance]
    if not optimal:
        return 127
    return int(round((float(optimal[0]) + float(optimal[-1])) * 0.5))


def _resolve_activity_threshold(
    hist: list[int],
    *,
    binary_threshold: float | None,
    levels: float | None,
) -> tuple[float, float]:
    """Return (threshold_level_0_255, threshold_norm_0_1)."""

    if levels is None:
        threshold_norm = _clamp_float(float(binary_threshold or 0.5), 0.0, 1.0)
        return float(threshold_norm) * 255.0, float(threshold_norm)

    level = _clamp_float(float(levels), 0.0, 100.0)
    automatic = _otsu_threshold(hist)
    threshold_index = int(round(float(automatic) + (50.0 - level) * 1.9))
    threshold_index = max(8, min(247, threshold_index))
    threshold_level = float(threshold_index) + 0.5
    return threshold_level, float(threshold_level) / 255.0


def _load_binary_mask(
    path: str | Path,
    *,
    invert: bool = False,
    binary_threshold: float | None = 0.5,
    levels: float | None = None,
    smooth: float = 0.0,
    max_grid_size: int = 512,
) -> tuple[list[list[bool]], tuple[int, int], bool, float]:
    """Load a 2D image as a clean binary material mask.

    Transparent pixels are composited on white so logos and PNG masks behave as
    users expect: on a white/transparent background the dark shape becomes
    material.  ``levels`` is the simple UI control; at 50 it uses an automatic
    threshold, lower values are stricter, higher values keep more faint detail.
    """

    from PIL import Image

    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Image not found: {p}")

    max_grid = int(max_grid_size)
    smooth_level = _clamp_float(float(smooth), 0.0, 100.0)
    with Image.open(p) as img:
        rgba = img.convert("RGBA")
        white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        gray = Image.alpha_composite(white, rgba).convert("L")
        source_size = gray.size
        downsampled = False
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
        # Keep thresholding edge-faithful.  The Smooth slider must not blur the
        # source before binarization: a Gaussian pass can erase fine strokes,
        # holes and sharp border information before the vector stage ever sees
        # them.  Smoothing is applied only after the binary mask has been built.
        _ = smooth_level  # kept for API symmetry; used by the vector stage.
        width, height = gray.size
        pixels = gray.tobytes()

    activity: list[int] = []
    hist = [0] * 256
    for value in pixels:
        # Normal mode: dark pixels are material.  Invert swaps the relation so
        # light pixels become material.  Values are 0=no material, 255=material.
        v = int(value)
        a = v if bool(invert) else 255 - v
        a = max(0, min(255, int(a)))
        activity.append(a)
        hist[a] += 1

    threshold_level, threshold_norm = _resolve_activity_threshold(
        hist,
        binary_threshold=binary_threshold,
        levels=levels,
    )

    rows: list[list[bool]] = []
    for row in range(height):
        base = row * width
        rows.append([float(activity[base + col]) >= threshold_level for col in range(width)])
    return rows, source_size, bool(downsampled), float(threshold_norm)

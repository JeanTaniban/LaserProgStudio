# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from .texture_projection_types import Vec3

def _bounds(vertices: list[tuple[float, float, float]]) -> tuple[float, float, float, float, float, float]:
    if not vertices:
        return (0, 1, 0, 1, 0, 1)
    xs = [float(v[0]) for v in vertices]
    ys = [float(v[1]) for v in vertices]
    zs = [float(v[2]) for v in vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _norm(value: float, lo: float, hi: float) -> float:
    span = float(hi) - float(lo)
    if abs(span) < 1e-9:
        return 0.5
    return (float(value) - float(lo)) / span


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (float(a[0]) - float(b[0]), float(a[1]) - float(b[1]), float(a[2]) - float(b[2]))


def _dot(a: Vec3, b: Vec3) -> float:
    return float(a[0]) * float(b[0]) + float(a[1]) * float(b[1]) + float(a[2]) * float(b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _length(v: Vec3) -> float:
    return math.sqrt(_dot(v, v))


def _unit(v: Vec3, fallback: Vec3 = (1.0, 0.0, 0.0)) -> Vec3:
    length = _length(v)
    if length < 1e-12:
        return fallback
    return (float(v[0]) / length, float(v[1]) / length, float(v[2]) / length)


def _image_aspect(image_width: int | None, image_height: int | None) -> float | None:
    try:
        w = float(image_width or 0)
        h = float(image_height or 0)
        if w > 0 and h > 0:
            return w / h
    except Exception:
        pass
    return None




def _normalize_rotation_deg(value: float) -> float:
    """Return a stable display/edit rotation in [-180, 180)."""
    try:
        out = math.fmod(float(value), 360.0)
    except Exception:
        return 0.0
    if not math.isfinite(out):
        return 0.0
    if out >= 180.0:
        out -= 360.0
    if out < -180.0:
        out += 360.0
    # Avoid displaying -0.0 in the inspector/overlay.
    return 0.0 if abs(out) < 1.0e-9 else out


def _fit_aspect_tile(span_u: float, span_v: float, aspect: float | None, *, preserve_aspect: bool = True) -> tuple[float, float]:
    """Return a tile size clamped inside the target bounds.

    The old TEX implementation used a cover strategy. That was useful for
    filling an object, but terrible for initial placement: large bitmap ratios
    could create a projection far larger than the clicked face. The new Creator
    contract starts with a *fit inside* tile; users can then scale or stretch it.
    """
    span_u = max(float(span_u), 1.0e-9)
    span_v = max(float(span_v), 1.0e-9)
    try:
        a = float(aspect or 0.0)
    except Exception:
        a = 0.0
    if not bool(preserve_aspect) or not math.isfinite(a) or a <= 0.0:
        return (span_u, span_v)
    target_ratio = span_u / span_v
    if target_ratio >= a:
        tile_h = span_v
        tile_w = max(tile_h * a, 1.0e-9)
    else:
        tile_w = span_u
        tile_h = max(tile_w / a, 1.0e-9)
    return (max(tile_w, 1.0e-9), max(tile_h, 1.0e-9))

def _apply_uv_transform(
    u: float,
    v: float,
    *,
    scale: float,
    rotation_deg: float,
    offset_u: float,
    offset_v: float,
    stretch_u: float = 1.0,
    stretch_v: float = 1.0,
) -> tuple[float, float]:
    s = max(float(scale), 1e-6)
    su = max(float(stretch_u), 1e-6)
    sv = max(float(stretch_v), 1e-6)
    uu = (float(u) - 0.5) / (s * su)
    vv = (float(v) - 0.5) / (s * sv)
    a = math.radians(float(rotation_deg))
    ca, sa = math.cos(a), math.sin(a)
    ru = uu * ca - vv * sa
    rv = uu * sa + vv * ca
    return (ru + 0.5 + float(offset_u), rv + 0.5 + float(offset_v))


def _uv_from_plane_coords(
    coord_u: float,
    coord_v: float,
    *,
    tile_w: float,
    tile_h: float,
    scale: float,
    rotation_deg: float,
    offset_u: float,
    offset_v: float,
    stretch_u: float = 1.0,
    stretch_v: float = 1.0,
) -> tuple[float, float]:
    """Map physical in-plane coordinates to texture UVs without shear.

    Older TEX code first normalized U and V independently, then rotated those
    normalized values.  When the image was not square, that mixed two different
    physical scales and produced a visible deformation during rotation.

    This helper rotates in model-space coordinates first, then applies the image
    tile dimensions.  The texture can rotate, but the bitmap aspect ratio and
    angles remain stable.
    """

    s = max(float(scale), 1e-6)
    su = max(float(stretch_u), 1e-6)
    sv = max(float(stretch_v), 1e-6)
    tw = max(float(tile_w), 1e-9) * s * su
    th = max(float(tile_h), 1e-9) * s * sv
    a = math.radians(float(rotation_deg))
    ca, sa = math.cos(a), math.sin(a)
    x = float(coord_u)
    y = float(coord_v)
    # Inverse-rotate the sample point into the texture's local axes.  Positive
    # angles visually rotate the image counter-clockwise on the selected face.
    xr = x * ca + y * sa
    yr = -x * sa + y * ca
    return (xr / tw + 0.5 + float(offset_u), yr / th + 0.5 + float(offset_v))

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

Vec3 = tuple[float, float, float]

@dataclass(frozen=True, slots=True)
class TextureProjectionParams:
    texture_id: str
    texture_path: str | Path
    projection_mode: str = "planar"
    usage: str = "visual"
    coverage_angle_deg: float = 20.0
    scale: float = 1.0
    # Non-uniform viewport edge stretch. ``scale`` keeps ratio; these fields let
    # users grab the frame edges to stretch width/height intentionally.
    stretch_u: float = 1.0
    stretch_v: float = 1.0
    rotation_deg: float = 0.0
    offset_u: float = 0.0
    offset_v: float = 0.0
    repeat: bool = False
    attach_to_mesh: bool = False
    # V18.1: keep the imported bitmap aspect ratio by default.  Without this,
    # a rectangular image is stretched to the picked face/object bounds.
    preserve_aspect: bool = True
    image_width: int | None = None
    image_height: int | None = None
    # Optional face anchor filled by the TEX picker.  It lets planar projection
    # follow the clicked face instead of always using global XY.
    seed_face_index: int | None = None
    projection_origin: Vec3 | None = None
    projection_normal: Vec3 | None = None

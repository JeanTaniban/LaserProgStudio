# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.domain.work_model import WorkMesh


@dataclass(frozen=True, slots=True)
class MaskReliefStats:
    source_width: int
    source_height: int
    width: int
    height: int
    active_pixels: int
    vertices: int
    triangles: int
    max_height_mm: float
    pixel_size_mm: float
    downsampled: bool = False
    binary: bool = False
    binary_threshold: float = 0.5


@dataclass(frozen=True, slots=True)
class MaskReliefResult:
    mesh: WorkMesh
    stats: MaskReliefStats

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.domain.work_model import WorkMesh


@dataclass(frozen=True, slots=True)
class MaskPhysicalSize:
    """Mechanical size of the raster footprint, independent of sample count."""

    width_mm: float
    height_mm: float


@dataclass(frozen=True, slots=True)
class MaskSmoothingReport:
    """Measured result of topology-safe 2D contour smoothing."""

    requested_level: float
    accepted_level: float
    source_components: int
    result_components: int
    source_holes: int
    result_holes: int
    source_area: float
    result_area: float
    symmetric_difference_area: float
    hausdorff_distance: float
    source_vertices: int
    result_vertices: int
    fallback_used: bool


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

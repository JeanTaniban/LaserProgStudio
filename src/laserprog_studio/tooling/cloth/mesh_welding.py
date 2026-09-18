"""Topology-aware vertex sharing for Cloth panel mesh generation."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from .models import ClothDocument
from .topology import curve_patch_incidence, sample_curve

Point3 = tuple[float, float, float]
_EPS = 1.0e-9


@dataclass(frozen=True, slots=True)
class SharedBoundarySample:
    curve_id: str
    samples: tuple[Point3, ...]
    endpoints: tuple[tuple[str, Point3], ...]


def build_shared_boundary_samples(
    document: ClothDocument,
    *,
    flattened: bool,
    arc_segments: int,
    excluded_curve_ids: Iterable[str] = (),
) -> dict[str, tuple[SharedBoundarySample, ...]]:
    """Sample only document-authored interfaces eligible for vertex sharing."""

    incidence = curve_patch_incidence(document)
    fold_ids = {fold.curve_id for fold in document.folds.values()}
    excluded = {str(value) for value in excluded_curve_ids}
    shared_curve_ids = {
        curve_id
        for curve_id, patch_ids in incidence.items()
        if (
            len(patch_ids) == 2
            and curve_id not in excluded
            and (not flattened or curve_id in fold_ids)
        )
    }
    samples_by_patch: dict[str, tuple[SharedBoundarySample, ...]] = {}
    for patch in document.patches.values():
        values: list[SharedBoundarySample] = []
        for curve_id in patch.outer_curve_ids:
            if curve_id not in shared_curve_ids:
                continue
            curve = document.curves.get(curve_id)
            if curve is None:
                continue
            samples = sample_curve(document, curve, arc_segments=arc_segments)
            endpoints = tuple(
                (point_id, document.points[point_id].position)
                for point_id in curve.endpoint_ids
                if point_id in document.points
            )
            values.append(SharedBoundarySample(curve_id, samples, endpoints))
        samples_by_patch[patch.id] = tuple(values)
    return samples_by_patch


def _point_segment_distance_and_parameter(
    point: Point3,
    start: Point3,
    end: Point3,
) -> tuple[float, float]:
    vector = (
        end[0] - start[0],
        end[1] - start[1],
        end[2] - start[2],
    )
    length_squared = sum(component * component for component in vector)
    if length_squared <= _EPS * _EPS:
        return math.dist(point, start), 0.0
    delta = (
        point[0] - start[0],
        point[1] - start[1],
        point[2] - start[2],
    )
    parameter = max(
        0.0,
        min(
            1.0,
            sum(delta[axis] * vector[axis] for axis in range(3)) / length_squared,
        ),
    )
    projected = tuple(
        start[axis] + vector[axis] * parameter
        for axis in range(3)
    )
    return math.dist(point, projected), parameter


def shared_boundary_weld_key(
    source_world: Point3,
    *,
    shared_samples: Iterable[SharedBoundarySample],
    tolerance_mm: float,
) -> tuple[object, ...] | None:
    """Return a stable topological key for one authored panel interface.

    Folded output may share every interface because the 3D boolean envelope must
    be watertight.  Flat output shares only true folds; explicit pattern cuts stay
    independent.  Global coordinate coincidence is never used as authority.
    """

    tolerance = max(1.0e-7, float(tolerance_mm))
    endpoint_match: tuple[float, str] | None = None
    interior_match: tuple[float, str, float] | None = None
    for boundary in shared_samples:
        for point_id, endpoint in boundary.endpoints:
            distance = math.dist(source_world, endpoint)
            if distance <= tolerance and (
                endpoint_match is None or distance < endpoint_match[0]
            ):
                endpoint_match = distance, point_id

        lengths = tuple(
            math.dist(boundary.samples[index - 1], boundary.samples[index])
            for index in range(1, len(boundary.samples))
        )
        total = sum(lengths)
        if total <= _EPS:
            continue
        accumulated = 0.0
        for index, segment_length in enumerate(lengths, start=1):
            first = boundary.samples[index - 1]
            second = boundary.samples[index]
            distance, parameter = _point_segment_distance_and_parameter(
                source_world,
                first,
                second,
            )
            if distance <= tolerance:
                arclength = (accumulated + segment_length * parameter) / total
                if interior_match is None or distance < interior_match[0]:
                    interior_match = distance, boundary.curve_id, arclength
            accumulated += segment_length

    if endpoint_match is not None:
        return "shared-point", endpoint_match[1]
    if interior_match is not None:
        # One part per million of curve arclength absorbs GEOS projection noise
        # without collapsing distinct points on normal-sized patterns.
        return (
            "shared-curve",
            interior_match[1],
            int(round(interior_match[2] * 1.0e6)),
        )
    return None


__all__ = [
    "SharedBoundarySample",
    "build_shared_boundary_samples",
    "shared_boundary_weld_key",
]

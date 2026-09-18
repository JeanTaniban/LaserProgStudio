"""Apply persisted 3D boolean modifiers to Cloth panel regions.

A generic boolean result cannot be unfolded by itself.  Cloth therefore keeps
its editable panel graph plus validated cutter meshes.  This module applies the
2D cross-section of those cutters to one panel; persistence and slicing live in
separate modules so this orchestration remains small and testable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .boolean_modifiers import (
    CLOTH_BOOLEAN_MODIFIERS_KEY,
    ClothBooleanModifier,
    append_cloth_boolean_modifier,
    cloth_boolean_modifiers,
    load_cloth_boolean_modifiers,
)
from .boolean_slicing import slice_cloth_boolean_modifier
from .models import ClothDocument, ClothPatch
from .topology import PatchFrame, sample_curve_loop_boundary, sample_patch_boundary

_EPS = 1.0e-9


@dataclass(frozen=True, slots=True)
class ClothBooleanRegionResult:
    geometry: Any
    applied_modifiers: int = 0
    ignored_modifiers: int = 0
    issues: tuple[str, ...] = ()


def base_patch_polygon(
    document: ClothDocument,
    patch: ClothPatch,
    frame: PatchFrame,
    *,
    arc_segments: int = 24,
):
    """Build the unmodified panel polygon, including authored holes."""

    from shapely.geometry import Polygon

    outer = [
        frame.project(point)
        for point in sample_patch_boundary(document, patch, arc_segments=arc_segments)
    ]
    holes = [
        [
            frame.project(point)
            for point in sample_curve_loop_boundary(document, loop, arc_segments=arc_segments)
        ]
        for loop in patch.hole_curve_loops
    ]
    polygon = Polygon(outer, holes=holes)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return polygon


def modified_patch_geometry(
    document: ClothDocument,
    patch: ClothPatch,
    frame: PatchFrame,
    *,
    arc_segments: int = 24,
    tolerance_mm: float = 0.01,
    modifiers: Sequence[ClothBooleanModifier] | None = None,
) -> ClothBooleanRegionResult:
    """Return one panel region after all flatten-aware boolean modifiers.

    ``modifiers`` should be loaded once by a caller processing several panels.
    The optional fallback keeps the public function convenient for isolated use.
    """

    geometry = base_patch_polygon(document, patch, frame, arc_segments=arc_segments)
    if geometry.is_empty or float(getattr(geometry, "area", 0.0)) <= _EPS:
        return ClothBooleanRegionResult(
            geometry,
            issues=(f"Panel {patch.name}: empty source region.",),
        )

    load_issues: tuple[str, ...] = ()
    if modifiers is None:
        loaded = load_cloth_boolean_modifiers(document)
        modifiers = loaded.modifiers
        load_issues = loaded.issues

    applied = 0
    ignored = 0
    issues = list(load_issues)
    tolerance = max(1.0e-7, float(tolerance_mm))
    for index, modifier in enumerate(modifiers, start=1):
        try:
            sliced = slice_cloth_boolean_modifier(
                modifier,
                frame,
                tolerance_mm=tolerance,
            )
        except Exception as exc:
            ignored += 1
            issues.append(
                f"Panel {patch.name}: modifier {index} could not be sliced "
                f"({type(exc).__name__}: {exc})."
            )
            continue
        if sliced is None or sliced.is_empty:
            ignored += 1
            continue

        try:
            if modifier.operation == "difference":
                updated = geometry.difference(sliced)
            else:
                # A union can be unfolded only when the added material touches
                # this panel on its mid-plane.  Disconnected 3D additions do not
                # define a unique sheet-pattern relation and are left untouched.
                if geometry.distance(sliced) > tolerance:
                    ignored += 1
                    continue
                updated = geometry.union(sliced)
            geometry = updated if updated.is_valid else updated.buffer(0)
            applied += 1
        except Exception as exc:
            ignored += 1
            issues.append(
                f"Panel {patch.name}: modifier {index} failed "
                f"({type(exc).__name__}: {exc})."
            )

    return ClothBooleanRegionResult(geometry, applied, ignored, tuple(issues))


__all__ = [
    "CLOTH_BOOLEAN_MODIFIERS_KEY",
    "ClothBooleanRegionResult",
    "append_cloth_boolean_modifier",
    "base_patch_polygon",
    "cloth_boolean_modifiers",
    "load_cloth_boolean_modifiers",
    "modified_patch_geometry",
]

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_left, bisect_right
from typing import Any, Iterable, Sequence


_AXIS_TO_INDEX = {"x": 0, "y": 1, "z": 2}
_BOUND_INDEX = {
    "x": (0, 1),
    "y": (2, 3),
    "z": (4, 5),
}


@dataclass(frozen=True)
class SnapSettings:
    grid_enabled: bool = False
    smart_enabled: bool = False
    grid_step: float = 5.0
    smart_tolerance: float = 2.0


@dataclass(frozen=True)
class SnapCandidate:
    axis: str
    correction: float
    distance: float
    kind: str
    moving_anchor: str
    target_anchor: str
    target_index: int


@dataclass(frozen=True)
class SnapResult:
    axis: str
    correction: float = 0.0
    mode: str = "none"  # none, grid, smart
    label: str = ""
    candidate: SnapCandidate | None = None

    @property
    def active(self) -> bool:
        return self.mode != "none" and abs(float(self.correction)) > 1e-9



@dataclass(frozen=True)
class TranslationSnapTarget:
    index: int
    bounds_values_by_axis: dict[str, dict[str, float]]
    feature_values_by_axis: dict[str, list[tuple[str, float]]]


@dataclass(frozen=True)
class TranslationSnapAxisIndex:
    """Sorted lookup tables for one translation axis.

    The first cached implementation still compared every moving feature against
    every target feature on every mouse move.  That was fine with a few parts,
    but with many boards it became expensive exactly when the dragged object
    entered a snap/contact zone.  This index keeps feature values sorted so the
    live drag only inspects candidates inside the snap tolerance.
    """
    bounds_by_anchor: dict[str, tuple[tuple[float, int], ...]]
    features: tuple[tuple[float, str, int], ...]
    feature_values: tuple[float, ...]


@dataclass(frozen=True)
class TranslationSnapCache:
    """Precomputed static snap targets for a live translation drag.

    Smart snapping used to rescan every vertex of every other mesh on every
    mouse move.  With many objects this becomes O(scene) per event and makes
    Light UI translation feel sticky.  This cache is built once at drag start;
    the drag loop then only recomputes the moving selection anchors.
    """
    targets: tuple[TranslationSnapTarget, ...]
    axis_index: dict[str, TranslationSnapAxisIndex] | None = None


@dataclass(frozen=True)
class TranslationMovingProfile:
    """Immutable moving-selection anchors used by the translation fast path.

    A translation does not deform the selection: every bound and feature value
    on the active world axis is shifted by the same scalar offset.  Capturing
    those values once at drag start avoids rebuilding/copying every mesh vertex
    on every mouse move.
    """

    bounds_values_by_axis: dict[str, dict[str, float]]
    feature_values_by_axis: dict[str, tuple[tuple[str, float], ...]]


def build_translation_moving_profile(
    vertices: Sequence[Sequence[float]],
    *,
    max_features: int = 96,
) -> TranslationMovingProfile:
    bounds = _bounds_from_vertices(vertices)
    return TranslationMovingProfile(
        bounds_values_by_axis={axis: _axis_values(bounds, axis) for axis in ("x", "y", "z")},
        feature_values_by_axis={
            axis: tuple(_unique_axis_features(vertices, axis, prefix="edge", max_features=max_features))
            for axis in ("x", "y", "z")
        },
    )


def build_translation_snap_cache(
    *,
    meshes: Sequence[Any],
    moving_index: int = -1,
    moving_indices: set[int] | None = None,
    max_features: int = 96,
) -> TranslationSnapCache:
    ignored = set(moving_indices or ({int(moving_index)} if int(moving_index) >= 0 else set()))
    targets: list[TranslationSnapTarget] = []
    for target_index, mesh in enumerate(meshes):
        if target_index in ignored:
            continue
        target_vertices = getattr(mesh, "vertices", []) or []
        if not target_vertices:
            continue
        bounds = _mesh_bounds(mesh)
        targets.append(
            TranslationSnapTarget(
                index=int(target_index),
                bounds_values_by_axis={axis: _axis_values(bounds, axis) for axis in ("x", "y", "z")},
                feature_values_by_axis={
                    axis: _unique_axis_features(target_vertices, axis, prefix="edge", max_features=max_features)
                    for axis in ("x", "y", "z")
                },
            )
        )

    axis_index: dict[str, TranslationSnapAxisIndex] = {}
    for axis in ("x", "y", "z"):
        bounds_by_anchor: dict[str, list[tuple[float, int]]] = {"min": [], "center": [], "max": []}
        features: list[tuple[float, str, int]] = []
        for target in targets:
            for anchor, value in (target.bounds_values_by_axis.get(axis) or {}).items():
                bounds_by_anchor.setdefault(str(anchor), []).append((float(value), int(target.index)))
            for anchor, value in target.feature_values_by_axis.get(axis) or []:
                features.append((float(value), str(anchor), int(target.index)))
        sorted_bounds = {anchor: tuple(sorted(values, key=lambda item: item[0])) for anchor, values in bounds_by_anchor.items()}
        features_sorted = tuple(sorted(features, key=lambda item: item[0]))
        axis_index[axis] = TranslationSnapAxisIndex(
            bounds_by_anchor=sorted_bounds,
            features=features_sorted,
            feature_values=tuple(value for value, _anchor, _index in features_sorted),
        )
    return TranslationSnapCache(targets=tuple(targets), axis_index=axis_index)


def _iter_sorted_values_near(
    values: Sequence[tuple[float, int]],
    target_value: float,
    tolerance: float,
) -> Iterable[tuple[float, int]]:
    numeric = [float(v) for v, _idx in values]
    start = bisect_left(numeric, float(target_value) - float(tolerance))
    end = bisect_right(numeric, float(target_value) + float(tolerance))
    for pos in range(start, end):
        yield values[pos]


def find_smart_translation_snap_cached(
    *,
    cache: TranslationSnapCache | None,
    proposed_vertices: Sequence[Sequence[float]],
    axis: str,
    tolerance: float,
    max_moving_features: int = 96,
) -> SnapResult:
    axis = (axis or "").lower().strip()
    if cache is None or axis not in _AXIS_TO_INDEX or tolerance <= 0 or not proposed_vertices:
        return SnapResult(axis=axis)

    moving_bounds = _bounds_from_vertices(proposed_vertices)
    moving_values = _axis_values(moving_bounds, axis)
    moving_feature_values = _unique_axis_features(proposed_vertices, axis, prefix="edge", max_features=max_moving_features)
    best: SnapCandidate | None = None
    best_score = float("inf")

    def consider(candidate: SnapCandidate, *, priority_bias: float = 0.0) -> None:
        nonlocal best, best_score
        if candidate.distance > tolerance:
            return
        score = float(candidate.distance) + float(priority_bias)
        if score < best_score:
            best = candidate
            best_score = score

    contact_pairs = (("min", "max"), ("max", "min"))
    align_pairs = (("min", "min"), ("center", "center"), ("max", "max"))

    indexed = (cache.axis_index or {}).get(axis)
    if indexed is None:
        # Fallback for a cache built by an older object during hot reload.
        for target in cache.targets:
            target_values = target.bounds_values_by_axis.get(axis)
            if not target_values:
                continue
            for moving_anchor, target_anchor in contact_pairs:
                correction = float(target_values[target_anchor] - moving_values[moving_anchor])
                consider(SnapCandidate(axis, correction, abs(correction), "contact", moving_anchor, target_anchor, target.index))
            for moving_anchor, target_anchor in align_pairs:
                correction = float(target_values[target_anchor] - moving_values[moving_anchor])
                consider(SnapCandidate(axis, correction, abs(correction), "align", moving_anchor, target_anchor, target.index), priority_bias=1e-6)
            target_feature_values = target.feature_values_by_axis.get(axis) or []
            for moving_anchor, moving_value in moving_feature_values:
                for target_anchor, target_value in target_feature_values:
                    correction = float(target_value - moving_value)
                    consider(SnapCandidate(axis, correction, abs(correction), "feature", moving_anchor, target_anchor, target.index), priority_bias=2e-6)
    else:
        for moving_anchor, target_anchor in contact_pairs:
            moving_value = float(moving_values[moving_anchor])
            for target_value, target_index in _iter_sorted_values_near(indexed.bounds_by_anchor.get(target_anchor, ()), moving_value, tolerance):
                correction = float(target_value - moving_value)
                consider(SnapCandidate(axis, correction, abs(correction), "contact", moving_anchor, target_anchor, int(target_index)))
        for moving_anchor, target_anchor in align_pairs:
            moving_value = float(moving_values[moving_anchor])
            for target_value, target_index in _iter_sorted_values_near(indexed.bounds_by_anchor.get(target_anchor, ()), moving_value, tolerance):
                correction = float(target_value - moving_value)
                consider(SnapCandidate(axis, correction, abs(correction), "align", moving_anchor, target_anchor, int(target_index)), priority_bias=1e-6)
        feature_values = indexed.feature_values
        features = indexed.features
        for moving_anchor, moving_value in moving_feature_values:
            lo = bisect_left(feature_values, float(moving_value) - float(tolerance))
            hi = bisect_right(feature_values, float(moving_value) + float(tolerance))
            for pos in range(lo, hi):
                target_value, target_anchor, target_index = features[pos]
                correction = float(target_value - moving_value)
                consider(SnapCandidate(axis, correction, abs(correction), "feature", moving_anchor, target_anchor, int(target_index)), priority_bias=2e-6)

    if best is None:
        return SnapResult(axis=axis)
    return SnapResult(axis=axis, correction=best.correction, mode="smart", label=_make_label(best), candidate=best)


def compute_translation_snap_cached(
    *,
    cache: TranslationSnapCache | None,
    start_vertices: Sequence[Sequence[float]],
    proposed_vertices: Sequence[Sequence[float]],
    axis: str,
    settings: SnapSettings,
) -> SnapResult:
    axis = (axis or "").lower().strip()
    if axis not in _AXIS_TO_INDEX:
        return SnapResult(axis=axis)
    if settings.smart_enabled:
        smart = find_smart_translation_snap_cached(
            cache=cache,
            proposed_vertices=proposed_vertices,
            axis=axis,
            tolerance=max(float(settings.smart_tolerance), 0.0),
        )
        if smart.mode == "smart":
            return smart
    if settings.grid_enabled:
        return apply_grid_translation_snap(
            start_vertices=start_vertices,
            proposed_vertices=proposed_vertices,
            axis=axis,
            grid_step=max(float(settings.grid_step), 0.0),
        )
    return SnapResult(axis=axis)


def find_smart_translation_snap_offset_cached(
    *,
    cache: TranslationSnapCache | None,
    moving_profile: TranslationMovingProfile | None,
    axis: str,
    offset: float,
    tolerance: float,
) -> SnapResult:
    """Smart-snap a rigid translation from cached scalar anchors only."""

    axis = (axis or "").lower().strip()
    if cache is None or moving_profile is None or axis not in _AXIS_TO_INDEX or tolerance <= 0:
        return SnapResult(axis=axis)
    base_values = moving_profile.bounds_values_by_axis.get(axis) or {}
    if not base_values:
        return SnapResult(axis=axis)
    moving_values = {name: float(value) + float(offset) for name, value in base_values.items()}
    moving_features = tuple(
        (str(anchor), float(value) + float(offset))
        for anchor, value in (moving_profile.feature_values_by_axis.get(axis) or ())
    )
    best: SnapCandidate | None = None
    best_score = float("inf")

    def consider(candidate: SnapCandidate, *, priority_bias: float = 0.0) -> None:
        nonlocal best, best_score
        if candidate.distance > tolerance:
            return
        score = float(candidate.distance) + float(priority_bias)
        if score < best_score:
            best = candidate
            best_score = score

    contact_pairs = (("min", "max"), ("max", "min"))
    align_pairs = (("min", "min"), ("center", "center"), ("max", "max"))
    indexed = (cache.axis_index or {}).get(axis)
    if indexed is None:
        for target in cache.targets:
            target_values = target.bounds_values_by_axis.get(axis) or {}
            for moving_anchor, target_anchor in contact_pairs:
                correction = float(target_values[target_anchor] - moving_values[moving_anchor])
                consider(SnapCandidate(axis, correction, abs(correction), "contact", moving_anchor, target_anchor, target.index))
            for moving_anchor, target_anchor in align_pairs:
                correction = float(target_values[target_anchor] - moving_values[moving_anchor])
                consider(SnapCandidate(axis, correction, abs(correction), "align", moving_anchor, target_anchor, target.index), priority_bias=1e-6)
            for moving_anchor, moving_value in moving_features:
                for target_anchor, target_value in target.feature_values_by_axis.get(axis) or ():
                    correction = float(target_value - moving_value)
                    consider(SnapCandidate(axis, correction, abs(correction), "feature", moving_anchor, target_anchor, target.index), priority_bias=2e-6)
    else:
        for moving_anchor, target_anchor in contact_pairs:
            moving_value = float(moving_values[moving_anchor])
            for target_value, target_index in _iter_sorted_values_near(indexed.bounds_by_anchor.get(target_anchor, ()), moving_value, tolerance):
                correction = float(target_value - moving_value)
                consider(SnapCandidate(axis, correction, abs(correction), "contact", moving_anchor, target_anchor, int(target_index)))
        for moving_anchor, target_anchor in align_pairs:
            moving_value = float(moving_values[moving_anchor])
            for target_value, target_index in _iter_sorted_values_near(indexed.bounds_by_anchor.get(target_anchor, ()), moving_value, tolerance):
                correction = float(target_value - moving_value)
                consider(SnapCandidate(axis, correction, abs(correction), "align", moving_anchor, target_anchor, int(target_index)), priority_bias=1e-6)
        for moving_anchor, moving_value in moving_features:
            lo = bisect_left(indexed.feature_values, float(moving_value) - float(tolerance))
            hi = bisect_right(indexed.feature_values, float(moving_value) + float(tolerance))
            for pos in range(lo, hi):
                target_value, target_anchor, target_index = indexed.features[pos]
                correction = float(target_value - moving_value)
                consider(SnapCandidate(axis, correction, abs(correction), "feature", moving_anchor, target_anchor, int(target_index)), priority_bias=2e-6)
    if best is None:
        return SnapResult(axis=axis)
    return SnapResult(axis=axis, correction=best.correction, mode="smart", label=_make_label(best), candidate=best)


def compute_translation_snap_offset_cached(
    *,
    cache: TranslationSnapCache | None,
    moving_profile: TranslationMovingProfile | None,
    axis: str,
    offset: float,
    settings: SnapSettings,
) -> SnapResult:
    """Compute translation snap without allocating translated vertex arrays."""

    axis = (axis or "").lower().strip()
    if axis not in _AXIS_TO_INDEX or moving_profile is None:
        return SnapResult(axis=axis)
    if settings.smart_enabled:
        smart = find_smart_translation_snap_offset_cached(
            cache=cache,
            moving_profile=moving_profile,
            axis=axis,
            offset=float(offset),
            tolerance=max(float(settings.smart_tolerance), 0.0),
        )
        if smart.mode == "smart":
            return smart
    if settings.grid_enabled and float(settings.grid_step) > 0.0:
        values = moving_profile.bounds_values_by_axis.get(axis) or {}
        center = float(values.get("center", 0.0)) + float(offset)
        step = float(settings.grid_step)
        snapped = round(center / step) * step
        correction = float(snapped - center)
        if abs(correction) > 1.0e-9:
            return SnapResult(axis=axis, correction=correction, mode="grid", label=f"grid {axis.upper()}: {snapped:.3f}")
    return SnapResult(axis=axis)

def _bounds_from_vertices(vertices: Sequence[Sequence[float]]) -> tuple[float, float, float, float, float, float]:
    if not vertices:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    xs = [float(v[0]) for v in vertices]
    ys = [float(v[1]) for v in vertices]
    zs = [float(v[2]) for v in vertices]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _mesh_bounds(mesh: Any) -> tuple[float, float, float, float, float, float]:
    return _bounds_from_vertices(getattr(mesh, "vertices", []) or [])


def _axis_values(bounds: tuple[float, float, float, float, float, float], axis: str) -> dict[str, float]:
    lo_i, hi_i = _BOUND_INDEX[axis]
    lo = float(bounds[lo_i])
    hi = float(bounds[hi_i])
    return {"min": lo, "center": (lo + hi) * 0.5, "max": hi}


def _unique_axis_features(
    vertices: Sequence[Sequence[float]],
    axis: str,
    *,
    prefix: str = "feature",
    max_features: int = 96,
) -> list[tuple[str, float]]:
    """Return deduped vertex/edge coordinate anchors on one world axis.

    Bounds min/center/max catch whole-part placement.  This helper adds real
    mesh coordinates so translation smart snap can also lock onto visible
    board edges, imported mesh arrêtes and internal feature lines.
    """
    idx = _AXIS_TO_INDEX.get((axis or "").lower().strip())
    if idx is None or not vertices:
        return []
    values: list[float] = []
    seen: set[int] = set()
    for v in vertices:
        try:
            value = float(v[idx])
        except Exception:
            continue
        key = round(value * 100000)
        if key in seen:
            continue
        seen.add(key)
        values.append(value)
        if len(values) >= max_features:
            break
    return [(f"{prefix}{i:02d}", value) for i, value in enumerate(values)]


def _make_label(candidate: SnapCandidate) -> str:
    if candidate.kind == "contact":
        prefix = "contact"
    elif candidate.kind == "feature":
        prefix = "edge"
    else:
        prefix = "align"
    return f"{prefix} {candidate.axis.upper()}: {candidate.moving_anchor} -> part {candidate.target_index:02d} {candidate.target_anchor}"


def find_smart_translation_snap(
    *,
    meshes: Sequence[Any],
    moving_index: int,
    proposed_vertices: Sequence[Sequence[float]],
    axis: str,
    tolerance: float,
    moving_indices: set[int] | None = None,
) -> SnapResult:
    """Find the best bounds-based translation snap for one axis.

    The function is intentionally axis-local. It never changes the other two
    coordinates, which keeps drag behavior predictable with X/Y/Z gizmos.
    """
    axis = (axis or "").lower().strip()
    if axis not in _AXIS_TO_INDEX or tolerance <= 0:
        return SnapResult(axis=axis)
    ignored = set(moving_indices or {int(moving_index)})
    if not ignored and not (0 <= int(moving_index) < len(meshes)):
        return SnapResult(axis=axis)

    moving_bounds = _bounds_from_vertices(proposed_vertices)
    moving_values = _axis_values(moving_bounds, axis)
    best: SnapCandidate | None = None

    def consider(candidate: SnapCandidate, *, priority_bias: float = 0.0) -> None:
        nonlocal best
        if candidate.distance > tolerance:
            return
        score = float(candidate.distance) + float(priority_bias)
        best_score = float(best.distance) if best is not None else float("inf")
        if best is None or score < best_score:
            best = candidate

    # Contact snaps: side-to-side placement.
    contact_pairs = (
        ("min", "max"),
        ("max", "min"),
    )
    # Alignment snaps: same anchor to same anchor. Center is useful for stacking.
    align_pairs = (
        ("min", "min"),
        ("center", "center"),
        ("max", "max"),
    )

    moving_feature_values = _unique_axis_features(proposed_vertices, axis, prefix="edge")

    for target_index, mesh in enumerate(meshes):
        if target_index in ignored:
            continue
        target_vertices = getattr(mesh, "vertices", []) or []
        if not target_vertices:
            continue
        target_values = _axis_values(_mesh_bounds(mesh), axis)

        for moving_anchor, target_anchor in contact_pairs:
            correction = float(target_values[target_anchor] - moving_values[moving_anchor])
            distance = abs(correction)
            consider(SnapCandidate(axis, correction, distance, "contact", moving_anchor, target_anchor, target_index))

        for moving_anchor, target_anchor in align_pairs:
            correction = float(target_values[target_anchor] - moving_values[moving_anchor])
            distance = abs(correction)
            consider(SnapCandidate(axis, correction, distance, "align", moving_anchor, target_anchor, target_index), priority_bias=1e-6)

        # Rich feature snaps: align any moving vertex/edge coordinate to any
        # target vertex/edge coordinate along the active translation axis.  This
        # catches board arrêtes and imported object edges that are not simply
        # the global min/max bounds.
        target_feature_values = _unique_axis_features(target_vertices, axis, prefix="edge")
        for moving_anchor, moving_value in moving_feature_values:
            for target_anchor, target_value in target_feature_values:
                correction = float(target_value - moving_value)
                distance = abs(correction)
                consider(SnapCandidate(axis, correction, distance, "feature", moving_anchor, target_anchor, target_index), priority_bias=2e-6)

    if best is None:
        return SnapResult(axis=axis)
    return SnapResult(axis=axis, correction=best.correction, mode="smart", label=_make_label(best), candidate=best)


def _projected_axis_values(
    vertices: Sequence[Sequence[float]],
    axis_vector: Sequence[float],
) -> dict[str, float]:
    """Return min/center/max after projecting vertices on an arbitrary axis."""
    import math

    ax = [float(axis_vector[0]), float(axis_vector[1]), float(axis_vector[2])]
    n = math.sqrt(ax[0] * ax[0] + ax[1] * ax[1] + ax[2] * ax[2])
    if n <= 1e-12 or not vertices:
        return {"min": 0.0, "center": 0.0, "max": 0.0}
    ax = [ax[0] / n, ax[1] / n, ax[2] / n]
    values = [float(v[0]) * ax[0] + float(v[1]) * ax[1] + float(v[2]) * ax[2] for v in vertices]
    lo = min(values)
    hi = max(values)
    return {"min": lo, "center": (lo + hi) * 0.5, "max": hi}


def find_smart_scale_edge_snap(
    *,
    meshes: Sequence[Any],
    moving_index: int,
    proposed_vertices: Sequence[Sequence[float]],
    axis: str,
    axis_vector: Sequence[float],
    dragged_anchor: str,
    tolerance: float,
    moving_indices: set[int] | None = None,
) -> SnapResult:
    """Find a smart snap correction for a scale-frame edge drag.

    Unlike translation snapping, this helper is intentionally limited to the
    dragged bounds edge (``min`` or ``max``). The returned correction is measured
    along ``axis_vector`` in world units. The caller converts that correction
    back to a scale factor while keeping the opposite edge fixed.

    This is used only for the square/frame scale handles, not for the X/Y/Z axis
    cube handles. Axis handles remain free-form because snapping them would make
    single-axis scaling feel sticky and unpredictable.
    """
    axis = (axis or "").lower().strip()
    dragged_anchor = (dragged_anchor or "").lower().strip()
    if axis not in _AXIS_TO_INDEX or dragged_anchor not in {"min", "max"} or tolerance <= 0:
        return SnapResult(axis=axis)
    ignored = set(moving_indices or {int(moving_index)})
    if not proposed_vertices:
        return SnapResult(axis=axis)

    moving_values = _projected_axis_values(proposed_vertices, axis_vector)
    moving_value = float(moving_values[dragged_anchor])
    best: SnapCandidate | None = None

    for target_index, mesh in enumerate(meshes):
        if target_index in ignored:
            continue
        target_vertices = getattr(mesh, "vertices", []) or []
        if not target_vertices:
            continue
        target_values = _projected_axis_values(target_vertices, axis_vector)
        for target_anchor in ("min", "center", "max"):
            correction = float(target_values[target_anchor] - moving_value)
            distance = abs(correction)
            if distance > tolerance:
                continue
            is_contact = (
                (dragged_anchor == "min" and target_anchor == "max")
                or (dragged_anchor == "max" and target_anchor == "min")
            )
            kind = "contact" if is_contact else "align"
            cand = SnapCandidate(axis, correction, distance, kind, dragged_anchor, target_anchor, target_index)
            if best is None or cand.distance < best.distance:
                best = cand

    if best is None:
        return SnapResult(axis=axis)
    return SnapResult(axis=axis, correction=best.correction, mode="smart", label=_make_label(best), candidate=best)


def apply_grid_translation_snap(
    *,
    start_vertices: Sequence[Sequence[float]],
    proposed_vertices: Sequence[Sequence[float]],
    axis: str,
    grid_step: float,
) -> SnapResult:
    """Snap the moving bounds center to a grid on one axis."""
    axis = (axis or "").lower().strip()
    if axis not in _AXIS_TO_INDEX or grid_step <= 0:
        return SnapResult(axis=axis)
    b = _bounds_from_vertices(proposed_vertices)
    values = _axis_values(b, axis)
    center = float(values["center"])
    snapped = round(center / float(grid_step)) * float(grid_step)
    correction = float(snapped - center)
    if abs(correction) <= 1e-9:
        return SnapResult(axis=axis, mode="none")
    return SnapResult(axis=axis, correction=correction, mode="grid", label=f"grid {axis.upper()}: {snapped:.3f}")


def compute_translation_snap(
    *,
    meshes: Sequence[Any],
    moving_index: int,
    start_vertices: Sequence[Sequence[float]],
    proposed_vertices: Sequence[Sequence[float]],
    axis: str,
    settings: SnapSettings,
    moving_indices: set[int] | None = None,
) -> SnapResult:
    """Compute smart/grid correction for a translation drag.

    Smart snap has priority. Grid snap is used only when no smart snap captures
    the active axis, so grid rounding cannot destroy a valid part-to-part snap.
    """
    axis = (axis or "").lower().strip()
    if axis not in _AXIS_TO_INDEX:
        return SnapResult(axis=axis)

    if settings.smart_enabled:
        smart = find_smart_translation_snap(
            meshes=meshes,
            moving_index=moving_index,
            proposed_vertices=proposed_vertices,
            axis=axis,
            tolerance=max(float(settings.smart_tolerance), 0.0),
            moving_indices=moving_indices,
        )
        if smart.mode == "smart":
            return smart

    if settings.grid_enabled:
        return apply_grid_translation_snap(
            start_vertices=start_vertices,
            proposed_vertices=proposed_vertices,
            axis=axis,
            grid_step=max(float(settings.grid_step), 0.0),
        )

    return SnapResult(axis=axis)


def apply_axis_correction(
    vertices: Iterable[Sequence[float]],
    axis: str,
    correction: float,
) -> list[tuple[float, float, float]]:
    axis = (axis or "").lower().strip()
    idx = _AXIS_TO_INDEX.get(axis)
    if idx is None or abs(float(correction)) <= 1e-12:
        return [(float(v[0]), float(v[1]), float(v[2])) for v in vertices]
    out: list[tuple[float, float, float]] = []
    for v in vertices:
        p = [float(v[0]), float(v[1]), float(v[2])]
        p[idx] += float(correction)
        out.append((p[0], p[1], p[2]))
    return out


__all__ = [
    "SnapSettings",
    "SnapCandidate",
    "SnapResult",
    "apply_axis_correction",
    "apply_grid_translation_snap",
    "build_translation_moving_profile",
    "build_translation_snap_cache",
    "compute_translation_snap",
    "compute_translation_snap_cached",
    "compute_translation_snap_offset_cached",
    "find_smart_translation_snap",
    "find_smart_translation_snap_cached",
    "TranslationMovingProfile",
    "TranslationSnapCache",
    "TranslationSnapAxisIndex",
    "find_smart_translation_snap_offset_cached",
    "find_smart_scale_edge_snap",
]

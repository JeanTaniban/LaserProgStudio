"""Pattern-edge editing for Cloth folds and cuts.

A shared Cloth curve has two independent meanings:

* the folded 3D surface remains geometrically continuous along the curve;
* the flat pattern either keeps the adjacent panels linked (fold) or separates
  them into different unfold components (cut).

The functions below keep those meanings explicit and transactional.  UI code
never has to mutate half of a fold relation and hope that validation repairs it
later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .drawing import infer_fold_angle
from .fold_ops import ClothFoldEditError, set_fold_angle
from .models import ClothCurveKind, ClothCurveRole, ClothDocument, ClothFold, ClothFoldKind
from .topology import curve_patch_incidence

PatternEdgeOperation = Literal["fold", "cut"]
_PATTERN_KIND_KEY = "cloth_pattern_edge_kind"
_PATTERN_USER_CUT_KEY = "cloth_user_cut"
_PATTERN_SPACING_KEY = "cloth_pattern_component_margin_mm"


class ClothPatternEdgeError(RuntimeError):
    """Raised when a requested fold/cut edit cannot be represented safely."""


@dataclass(frozen=True, slots=True)
class PatternEdgeState:
    curve_id: str
    patch_ids: tuple[str, str]
    operation: PatternEdgeOperation
    fold_id: str | None
    angle_degrees: float
    radius_mm: float
    can_fold: bool


@dataclass(frozen=True, slots=True)
class PatternAnalysis:
    shared_edge_count: int
    fold_count: int
    cut_count: int
    component_count: int
    cycle_fold_ids: tuple[str, ...]

    @property
    def unfoldable(self) -> bool:
        return not self.cycle_fold_ids


@dataclass(frozen=True, slots=True)
class PatternEditResult:
    operation: PatternEdgeOperation
    curve_id: str
    fold_id: str | None
    changed: bool
    message: str


def pattern_spacing_mm(document: ClothDocument) -> float:
    try:
        value = float(document.metadata.get(_PATTERN_SPACING_KEY, 20.0))
    except (TypeError, ValueError):
        value = 20.0
    return max(0.0, min(1000.0, value))


def set_pattern_spacing(document: ClothDocument, spacing_mm: float) -> bool:
    value = max(0.0, min(1000.0, float(spacing_mm)))
    if pattern_spacing_mm(document) == value and _PATTERN_SPACING_KEY in document.metadata:
        return False
    document.metadata[_PATTERN_SPACING_KEY] = value
    document.revision += 1
    return True


def fold_for_curve(document: ClothDocument, curve_id: str) -> ClothFold | None:
    key = str(curve_id)
    return next((fold for fold in document.folds.values() if fold.curve_id == key), None)


def pattern_edge_state(document: ClothDocument, curve_id: str) -> PatternEdgeState:
    curve_id = str(curve_id)
    curve = document.curves.get(curve_id)
    if curve is None:
        raise ClothPatternEdgeError("Unknown Cloth edge.")
    incidence = tuple(curve_patch_incidence(document).get(curve_id, ()))
    if len(incidence) != 2:
        raise ClothPatternEdgeError("A pattern edge must be shared by exactly two panels.")
    fold = fold_for_curve(document, curve_id)
    explicit_cut = bool(curve.metadata.get(_PATTERN_USER_CUT_KEY) or curve.metadata.get("cloth_auto_cut"))
    operation: PatternEdgeOperation = "fold" if fold is not None else "cut" if explicit_cut else "fold"
    angle = float(fold.angle_degrees) if fold is not None else infer_fold_angle(document, curve_id, incidence[0], incidence[1])
    return PatternEdgeState(
        curve_id=curve_id,
        patch_ids=(incidence[0], incidence[1]),
        operation=operation,
        fold_id=None if fold is None else fold.id,
        angle_degrees=angle,
        radius_mm=0.0 if fold is None else float(fold.radius_mm),
        can_fold=curve.kind is ClothCurveKind.LINE,
    )


def analyze_pattern(document: ClothDocument) -> PatternAnalysis:
    incidence = curve_patch_incidence(document)
    fold_by_curve = {fold.curve_id: fold for fold in document.folds.values()}
    shared = tuple(curve_id for curve_id, patch_ids in incidence.items() if len(patch_ids) == 2)
    cuts = tuple(curve_id for curve_id in shared if curve_id not in fold_by_curve)
    cycles = _cycle_fold_ids(document)

    parent = {patch_id: patch_id for patch_id in document.patches}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    for fold in document.folds.values():
        if fold.patch_a_id not in parent or fold.patch_b_id not in parent:
            continue
        first, second = find(fold.patch_a_id), find(fold.patch_b_id)
        if first != second:
            parent[first] = second
    components = len({find(patch_id) for patch_id in parent}) if parent else 0
    return PatternAnalysis(len(shared), len(document.folds), len(cuts), components, cycles)


def would_create_fold_cycle(document: ClothDocument, curve_id: str) -> bool:
    state = pattern_edge_state(document, curve_id)
    if state.fold_id is not None:
        return False
    adjacency: dict[str, set[str]] = {patch_id: set() for patch_id in document.patches}
    for fold in document.folds.values():
        adjacency.setdefault(fold.patch_a_id, set()).add(fold.patch_b_id)
        adjacency.setdefault(fold.patch_b_id, set()).add(fold.patch_a_id)
    start, target = state.patch_ids
    stack = [start]
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(adjacency.get(current, ()))
    return False


def apply_pattern_edge(
    document: ClothDocument,
    curve_id: str,
    operation: PatternEdgeOperation,
    *,
    angle_degrees: float = 0.0,
    radius_mm: float = 0.0,
) -> PatternEditResult:
    operation = str(operation).lower()  # type: ignore[assignment]
    if operation not in {"fold", "cut"}:
        raise ClothPatternEdgeError(f"Unsupported pattern-edge operation: {operation!r}.")
    state = pattern_edge_state(document, curve_id)
    if operation == "fold" and not state.can_fold:
        raise ClothPatternEdgeError("Only a straight shared edge can become a fold. Use Cut for curved boundaries.")
    if operation == "fold" and would_create_fold_cycle(document, curve_id):
        raise ClothPatternEdgeError(
            "This fold would close a panel cycle and make the pattern ambiguous. Cut another edge in that loop first."
        )

    working = document.clone()
    try:
        if operation == "cut":
            changed, fold_id = _apply_cut(working, state.curve_id)
            message = "Pattern cut applied. The 3D panels stay joined, but unfold as separate pattern components."
        else:
            changed, fold_id = _apply_fold(
                working,
                state.curve_id,
                angle_degrees=float(angle_degrees),
                radius_mm=float(radius_mm),
            )
            message = f"Fold applied at {float(angle_degrees):.1f}° with radius {max(0.0, float(radius_mm)):.3g} mm."
    except (ClothFoldEditError, ValueError, KeyError) as exc:
        raise ClothPatternEdgeError(str(exc)) from exc

    if changed:
        restore_pattern_document(document, working)
    return PatternEditResult(operation, state.curve_id, fold_id, changed, message)


def apply_cycle_cuts(document: ClothDocument) -> tuple[str, ...]:
    """Cut only the fold relations that close cycles, preserving a spanning forest."""

    cycle_ids = _cycle_fold_ids(document)
    if not cycle_ids:
        return ()
    working = document.clone()
    curve_ids: list[str] = []
    for fold_id in cycle_ids:
        fold = working.folds.get(fold_id)
        if fold is None:
            continue
        curve_ids.append(fold.curve_id)
        _apply_cut(working, fold.curve_id)
    restore_pattern_document(document, working)
    return tuple(curve_ids)


def _apply_cut(document: ClothDocument, curve_id: str) -> tuple[bool, str | None]:
    fold = fold_for_curve(document, curve_id)
    changed = False
    fold_id = None if fold is None else fold.id
    if fold is not None:
        document.folds.pop(fold.id, None)
        changed = True
    curve = document.curves[curve_id]
    metadata_changed = (
        curve.metadata.get(_PATTERN_KIND_KEY) != "cut"
        or not curve.metadata.get(_PATTERN_USER_CUT_KEY)
        or "cloth_auto_cut" in curve.metadata
    )
    curve.metadata[_PATTERN_KIND_KEY] = "cut"
    curve.metadata[_PATTERN_USER_CUT_KEY] = True
    curve.metadata.pop("cloth_auto_cut", None)
    if not any(existing.curve_id == curve_id for existing in document.folds.values()):
        curve.role = ClothCurveRole.BOUNDARY
    if changed or metadata_changed:
        document.revision += 1
        changed = True
    return changed, fold_id


def _apply_fold(document: ClothDocument, curve_id: str, *, angle_degrees: float, radius_mm: float) -> tuple[bool, str]:
    target_angle = max(-180.0, min(180.0, float(angle_degrees)))
    target_radius = max(0.0, min(1000.0, float(radius_mm)))
    curve = document.curves[curve_id]
    incidence = tuple(curve_patch_incidence(document).get(curve_id, ()))
    fold = fold_for_curve(document, curve_id)
    initial_revision = document.revision
    created = False
    if fold is None:
        current = infer_fold_angle(document, curve_id, incidence[0], incidence[1])
        kind = ClothFoldKind.VALLEY if current > 1.0e-6 else ClothFoldKind.MOUNTAIN if current < -1.0e-6 else ClothFoldKind.NEUTRAL
        fold = document.add_fold(
            curve_id,
            incidence[0],
            incidence[1],
            angle_degrees=current,
            radius_mm=target_radius,
            kind=kind,
            metadata={"cloth_pattern_edge_kind": "fold"},
        )
        created = True

    target_kind = ClothFoldKind.VALLEY if target_angle > 1.0e-6 else ClothFoldKind.MOUNTAIN if target_angle < -1.0e-6 else ClothFoldKind.NEUTRAL
    angle_changed = abs(float(fold.angle_degrees) - target_angle) > 1.0e-12 or fold.kind is not target_kind
    radius_changed = abs(float(fold.radius_mm) - target_radius) > 1.0e-12
    metadata_changed = (
        curve.metadata.get(_PATTERN_KIND_KEY) != "fold"
        or _PATTERN_USER_CUT_KEY in curve.metadata
        or "cloth_auto_cut" in curve.metadata
        or fold.metadata.get(_PATTERN_KIND_KEY) != "fold"
    )
    if radius_changed:
        fold.radius_mm = target_radius
    set_fold_angle(document, fold.id, target_angle)
    curve.metadata[_PATTERN_KIND_KEY] = "fold"
    curve.metadata.pop(_PATTERN_USER_CUT_KEY, None)
    curve.metadata.pop("cloth_auto_cut", None)
    fold.metadata[_PATTERN_KIND_KEY] = "fold"
    changed = created or angle_changed or radius_changed or metadata_changed
    if changed and document.revision == initial_revision:
        document.revision += 1
    return changed, fold.id


def _cycle_fold_ids(document: ClothDocument) -> tuple[str, ...]:
    parent = {patch_id: patch_id for patch_id in document.patches}

    def find(value: str) -> str:
        root = value
        while parent[root] != root:
            root = parent[root]
        while parent[value] != value:
            following = parent[value]
            parent[value] = root
            value = following
        return root

    cycle_ids: list[str] = []
    for fold in document.folds.values():
        if fold.patch_a_id not in parent or fold.patch_b_id not in parent:
            continue
        first, second = find(fold.patch_a_id), find(fold.patch_b_id)
        if first == second:
            cycle_ids.append(fold.id)
        else:
            parent[first] = second
    return tuple(cycle_ids)


def restore_pattern_document(target: ClothDocument, source: ClothDocument) -> None:
    target.layers = source.layers
    target.points = source.points
    target.curves = source.curves
    target.patches = source.patches
    target.folds = source.folds
    target.seams = source.seams
    target.metadata = source.metadata
    target.revision = source.revision
    target._next_id = source._next_id


__all__ = [
    "ClothPatternEdgeError",
    "PatternAnalysis",
    "PatternEdgeOperation",
    "PatternEdgeState",
    "PatternEditResult",
    "analyze_pattern",
    "apply_cycle_cuts",
    "apply_pattern_edge",
    "fold_for_curve",
    "pattern_edge_state",
    "pattern_spacing_mm",
    "restore_pattern_document",
    "set_pattern_spacing",
    "would_create_fold_cycle",
]

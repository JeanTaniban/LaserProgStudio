"""Validated persistence model for flatten-aware Cloth boolean operations.

The generic boolean engine returns only a triangle mesh.  That result cannot be
unfolded by itself, so editable Cloth outputs keep a compact copy of each cutter
inside the source document.  This module owns the persistence contract and is
intentionally independent from Shapely, mesh generation and the UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from types import SimpleNamespace
from typing import Any, Literal, cast

from .models import ClothDocument

Point3 = tuple[float, float, float]
Triangle = tuple[int, int, int]
BooleanOperation = Literal["difference", "union"]

CLOTH_BOOLEAN_MODIFIERS_KEY = "cloth_boolean_modifiers"
CLOTH_BOOLEAN_MODIFIER_VERSION = 1
MAX_MODIFIER_TRIANGLES = 250_000
MAX_MODIFIER_VERTICES = 750_000


@dataclass(frozen=True, slots=True)
class ClothBooleanModifier:
    """One validated boolean operand stored with an editable Cloth document."""

    operation: BooleanOperation
    vertices: tuple[Point3, ...]
    triangles: tuple[Triangle, ...]
    margin_mm: float = 0.0
    version: int = CLOTH_BOOLEAN_MODIFIER_VERSION
    _bounds: tuple[Point3, Point3] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if not self.vertices:
            raise ValueError("A Cloth boolean modifier requires at least one vertex.")
        minimum = tuple(min(point[axis] for point in self.vertices) for axis in range(3))
        maximum = tuple(max(point[axis] for point in self.vertices) for axis in range(3))
        object.__setattr__(self, "_bounds", (minimum, maximum))

    @property
    def bounds(self) -> tuple[Point3, Point3]:
        return self._bounds

    def to_payload(self) -> dict[str, Any]:
        """Return a JSON-compatible, detached metadata payload."""

        return {
            "version": int(self.version),
            "operation": self.operation,
            # The cutter stored below already includes the effective boolean
            # clearance.  The margin remains audit information for the user and
            # for future migrations; it must not be applied a second time.
            "margin_mm": float(self.margin_mm),
            "mesh": {
                "vertices": [list(point) for point in self.vertices],
                "triangles": [list(face) for face in self.triangles],
            },
        }


@dataclass(frozen=True, slots=True)
class ClothBooleanModifierLoadResult:
    modifiers: tuple[ClothBooleanModifier, ...] = ()
    issues: tuple[str, ...] = ()


def _normalise_operation(value: Any) -> BooleanOperation:
    operation = str(value or "").strip().lower()
    if operation not in {"difference", "union"}:
        raise ValueError(f"Unsupported Cloth boolean modifier: {value!r}")
    return cast(BooleanOperation, operation)


def _point3(value: Any, *, label: str) -> Point3:
    try:
        coordinates = tuple(float(component) for component in value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} is not a numeric 3D point.") from exc
    if len(coordinates) != 3 or not all(math.isfinite(component) for component in coordinates):
        raise ValueError(f"{label} must contain exactly three finite coordinates.")
    return coordinates[0], coordinates[1], coordinates[2]


def _triangle(value: Any, *, label: str, vertex_count: int) -> Triangle:
    try:
        raw_indices = tuple(value)
    except TypeError as exc:
        raise ValueError(f"{label} is not a valid triangle index triplet.") from exc
    indices: list[int] = []
    for component in raw_indices:
        if isinstance(component, bool):
            raise ValueError(f"{label} contains a boolean instead of an index.")
        try:
            index = int(component)
            numeric = float(component)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} is not a valid triangle index triplet.") from exc
        if not math.isfinite(numeric) or numeric != float(index):
            raise ValueError(f"{label} contains a non-integer index.")
        indices.append(index)
    indices_tuple = tuple(indices)
    if len(indices_tuple) != 3 or len(set(indices_tuple)) != 3:
        raise ValueError(f"{label} must reference three distinct vertices.")
    if any(index < 0 or index >= vertex_count for index in indices_tuple):
        raise ValueError(f"{label} references a vertex outside the cutter mesh.")
    return indices_tuple[0], indices_tuple[1], indices_tuple[2]


def modifier_from_mesh(
    mesh: Any,
    *,
    operation: Any,
    margin_mm: float = 0.0,
) -> ClothBooleanModifier:
    """Validate a runtime mesh and convert it to the persisted Cloth contract."""

    raw_vertices = list(getattr(mesh, "vertices", ()) or ())
    raw_triangles = list(getattr(mesh, "triangles", ()) or ())
    if not raw_vertices or not raw_triangles:
        raise ValueError("The Cloth boolean modifier mesh is empty.")
    if len(raw_vertices) > MAX_MODIFIER_VERTICES:
        raise ValueError(
            "The Cloth boolean cutter has too many vertices to store safely "
            f"({len(raw_vertices)}; limit {MAX_MODIFIER_VERTICES})."
        )
    if len(raw_triangles) > MAX_MODIFIER_TRIANGLES:
        raise ValueError(
            "The Cloth boolean cutter is too dense to store safely "
            f"({len(raw_triangles)} triangles; limit {MAX_MODIFIER_TRIANGLES})."
        )

    vertices = tuple(
        _point3(point, label=f"Cutter vertex {index}")
        for index, point in enumerate(raw_vertices)
    )
    triangles = tuple(
        _triangle(face, label=f"Cutter triangle {index}", vertex_count=len(vertices))
        for index, face in enumerate(raw_triangles)
    )
    try:
        margin = float(margin_mm)
    except (TypeError, ValueError) as exc:
        raise ValueError("The Cloth boolean margin must be a finite number.") from exc
    if not math.isfinite(margin):
        raise ValueError("The Cloth boolean margin must be a finite number.")
    return ClothBooleanModifier(
        operation=_normalise_operation(operation),
        vertices=vertices,
        triangles=triangles,
        margin_mm=margin,
    )


def modifier_from_payload(payload: Any) -> ClothBooleanModifier:
    """Parse and validate one persisted modifier.

    Invalid older-format metadata is rejected explicitly by the caller instead of
    leaking malformed indices into panel slicing.
    """

    if not isinstance(payload, dict):
        raise ValueError("Modifier entry is not an object.")
    try:
        version = int(payload.get("version", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("Modifier version is invalid.") from exc
    if version != CLOTH_BOOLEAN_MODIFIER_VERSION:
        raise ValueError(f"Unsupported modifier version {version}.")
    mesh = payload.get("mesh")
    if not isinstance(mesh, dict):
        raise ValueError("Modifier mesh payload is missing.")

    payload_mesh = SimpleNamespace(
        vertices=mesh.get("vertices"),
        triangles=mesh.get("triangles"),
    )
    return modifier_from_mesh(
        payload_mesh,
        operation=payload.get("operation"),
        margin_mm=payload.get("margin_mm", 0.0),
    )


def load_cloth_boolean_modifiers(document: ClothDocument) -> ClothBooleanModifierLoadResult:
    """Load all valid modifiers once and report malformed persisted entries."""

    raw = document.metadata.get(CLOTH_BOOLEAN_MODIFIERS_KEY, ())
    if raw in (None, ()):
        return ClothBooleanModifierLoadResult()
    if not isinstance(raw, list):
        return ClothBooleanModifierLoadResult(issues=("Cloth boolean modifier metadata is not a list.",))

    modifiers: list[ClothBooleanModifier] = []
    issues: list[str] = []
    for index, payload in enumerate(raw, start=1):
        try:
            modifiers.append(modifier_from_payload(payload))
        except ValueError as exc:
            issues.append(f"Cloth boolean modifier {index} is invalid: {exc}")
    return ClothBooleanModifierLoadResult(tuple(modifiers), tuple(issues))


def append_cloth_boolean_modifier(
    document: ClothDocument,
    cutter: Any,
    *,
    operation: str,
    margin_mm: float = 0.0,
) -> dict[str, Any]:
    """Validate and append one modifier atomically to the document metadata."""

    modifier = modifier_from_mesh(cutter, operation=operation, margin_mm=margin_mm)
    payload = modifier.to_payload()
    existing = document.metadata.get(CLOTH_BOOLEAN_MODIFIERS_KEY)
    values = list(existing) if isinstance(existing, list) else []
    values.append(payload)
    document.metadata[CLOTH_BOOLEAN_MODIFIERS_KEY] = values
    document.revision += 1
    return payload


def cloth_boolean_modifiers(document: ClothDocument) -> tuple[dict[str, Any], ...]:
    """Detached public view of validated metadata payloads."""

    loaded = load_cloth_boolean_modifiers(document)
    return tuple(modifier.to_payload() for modifier in loaded.modifiers)


__all__ = [
    "CLOTH_BOOLEAN_MODIFIERS_KEY",
    "CLOTH_BOOLEAN_MODIFIER_VERSION",
    "MAX_MODIFIER_TRIANGLES",
    "MAX_MODIFIER_VERTICES",
    "ClothBooleanModifier",
    "ClothBooleanModifierLoadResult",
    "append_cloth_boolean_modifier",
    "cloth_boolean_modifiers",
    "load_cloth_boolean_modifiers",
    "modifier_from_mesh",
    "modifier_from_payload",
]

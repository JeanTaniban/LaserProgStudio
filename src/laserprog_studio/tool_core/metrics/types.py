"""Typed metric-edit primitives for Creator drawing tools.

The metric subsystem is intentionally small and UI-toolkit independent.  It does
not know about Plan Tracer, sketches or Qt widgets: it only describes temporary
numeric fields shown while a placement transaction is waiting for validation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class MetricKind(str, Enum):
    LENGTH = "length"
    ANGLE = "angle"
    RADIUS = "radius"
    DIAMETER = "diameter"
    WIDTH = "width"
    HEIGHT = "height"
    CHORD = "chord"


class MetricSessionState(str, Enum):
    PREVIEW = "preview"
    EDITING = "editing"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class MetricFieldSpec:
    """One editable numeric value in a placement metric overlay."""

    id: str
    label: str
    kind: MetricKind | str
    value: float
    unit: str = "mm"
    precision: int = 1
    enabled: bool = True
    linked_to: str | None = None
    tooltip: str | None = None

    @staticmethod
    def length(field_id: str = "length", *, value: float = 0.0, label: str = "Length", unit: str = "mm") -> "MetricFieldSpec":
        return MetricFieldSpec(str(field_id), str(label), MetricKind.LENGTH, float(value), unit=str(unit))

    @staticmethod
    def angle(field_id: str = "angle", *, value: float = 0.0, label: str = "Angle", unit: str = "°") -> "MetricFieldSpec":
        return MetricFieldSpec(str(field_id), str(label), MetricKind.ANGLE, float(value), unit=str(unit), precision=1)

    @staticmethod
    def radius(field_id: str = "radius", *, value: float = 0.0, label: str = "Radius", unit: str = "mm") -> "MetricFieldSpec":
        return MetricFieldSpec(str(field_id), str(label), MetricKind.RADIUS, float(value), unit=str(unit))

    @staticmethod
    def diameter(field_id: str = "diameter", *, value: float = 0.0, label: str = "Diameter", unit: str = "mm") -> "MetricFieldSpec":
        return MetricFieldSpec(str(field_id), str(label), MetricKind.DIAMETER, float(value), unit=str(unit), linked_to="radius")

    @staticmethod
    def width(field_id: str = "width", *, value: float = 0.0, label: str = "Width", unit: str = "mm") -> "MetricFieldSpec":
        return MetricFieldSpec(str(field_id), str(label), MetricKind.WIDTH, float(value), unit=str(unit))

    @staticmethod
    def height(field_id: str = "height", *, value: float = 0.0, label: str = "Height", unit: str = "mm") -> "MetricFieldSpec":
        return MetricFieldSpec(str(field_id), str(label), MetricKind.HEIGHT, float(value), unit=str(unit))

    @staticmethod
    def chord(field_id: str = "chord", *, value: float = 0.0, label: str = "Chord", unit: str = "mm") -> "MetricFieldSpec":
        return MetricFieldSpec(str(field_id), str(label), MetricKind.CHORD, float(value), unit=str(unit))


@dataclass(slots=True)
class MetricEditSession:
    """Temporary metric edit state owned by a drawing placement transaction."""

    id: str
    title: str
    mode_label: str
    fields: dict[str, MetricFieldSpec] = field(default_factory=dict)
    state: MetricSessionState = MetricSessionState.EDITING
    message: str = "Adjust values, then validate."

    @classmethod
    def from_fields(
        cls,
        session_id: str,
        *,
        title: str,
        mode_label: str,
        fields: tuple[MetricFieldSpec, ...] | list[MetricFieldSpec],
        message: str = "Adjust values, then validate.",
    ) -> "MetricEditSession":
        return cls(
            id=str(session_id),
            title=str(title),
            mode_label=str(mode_label),
            fields={field.id: field for field in fields},
            message=str(message),
        )

    def as_values(self) -> dict[str, float]:
        return {field_id: float(field.value) for field_id, field in self.fields.items()}

    def replace_field_value(self, field_id: str, value: float) -> None:
        from dataclasses import replace

        field_id = str(field_id)
        if field_id not in self.fields:
            raise KeyError(field_id)
        self.fields[field_id] = replace(self.fields[field_id], value=float(value))


@dataclass(frozen=True, slots=True)
class MetricOverlayIds:
    window_id: str
    validate_button_id: str
    cancel_button_id: str


def field_tuple(fields: Mapping[str, MetricFieldSpec] | tuple[MetricFieldSpec, ...] | list[MetricFieldSpec]) -> tuple[MetricFieldSpec, ...]:
    if isinstance(fields, Mapping):
        return tuple(fields.values())
    return tuple(fields)

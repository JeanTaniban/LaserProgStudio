# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ParameterKind = Literal["float", "int", "text", "choice", "bool", "file"]


@dataclass(frozen=True)
class ParameterSpec:
    """Declarative parameter used by future tools/modifiers.

    The UI factory can later turn these specs into Qt widgets. Geometry code can
    validate the resulting dictionary without importing Qt.
    """

    id: str
    label: str
    kind: ParameterKind
    default: Any
    min_value: float | int | None = None
    max_value: float | int | None = None
    step: float | int | None = None
    choices: tuple[tuple[str, str], ...] = ()
    file_filter: str | None = None
    tooltip: str | None = None

    def validate(self, value: Any) -> Any:
        if self.kind == "bool":
            return bool(value)
        if self.kind == "int":
            value = int(value)
            if self.min_value is not None:
                value = max(value, int(self.min_value))
            if self.max_value is not None:
                value = min(value, int(self.max_value))
            return value
        if self.kind == "float":
            value = float(value)
            if self.min_value is not None:
                value = max(value, float(self.min_value))
            if self.max_value is not None:
                value = min(value, float(self.max_value))
            return value
        if self.kind == "choice":
            allowed = {choice_id for choice_id, _ in self.choices}
            if value not in allowed:
                return self.default
            return value
        if self.kind in {"text", "file"}:
            return "" if value is None else str(value)
        return value


def defaults_for(parameters: tuple[ParameterSpec, ...]) -> dict[str, Any]:
    return {param.id: param.default for param in parameters}


def validate_values(parameters: tuple[ParameterSpec, ...], values: dict[str, Any]) -> dict[str, Any]:
    return {param.id: param.validate(values.get(param.id, param.default)) for param in parameters}

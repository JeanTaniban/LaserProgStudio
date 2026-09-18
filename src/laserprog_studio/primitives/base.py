# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..parameters import ParameterSpec, defaults_for, validate_values


@dataclass(frozen=True, slots=True)
class PrimitiveBuildRequest:
    primitive_id: str
    values: dict[str, Any]
    name_index: int = 1


@dataclass(frozen=True, slots=True)
class PrimitiveSpec:
    id: str
    label: str
    name_prefix: str
    parameters: tuple[ParameterSpec, ...]
    builder: Callable[[PrimitiveBuildRequest], Any]
    display_order: int = 0

    def defaults(self) -> dict[str, Any]:
        return defaults_for(self.parameters)

    def validate(self, values: dict[str, Any]) -> dict[str, Any]:
        return validate_values(self.parameters, values)

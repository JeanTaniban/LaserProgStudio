# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class OperationResult:
    """Standard result object for future geometry operations.

    Geometry code should return this instead of showing QMessageBox directly.
    Controllers can decide how to log warnings, show errors and build previews.
    """

    meshes: list[Any] = field(default_factory=list)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    @classmethod
    def success(cls, meshes: Iterable[Any], warnings: Iterable[str] = ()) -> "OperationResult":
        return cls(meshes=list(meshes), warnings=tuple(str(w) for w in warnings), errors=())

    @classmethod
    def failure(cls, message: str, warnings: Iterable[str] = ()) -> "OperationResult":
        return cls(meshes=[], warnings=tuple(str(w) for w in warnings), errors=(str(message),))

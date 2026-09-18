# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from ..geometry_ops import OperationResult
from .base import ModifierSpec


@runtime_checkable
class MeshModifier(Protocol):
    """Runtime contract for mesh modifiers.

    Modifiers expose a consistent selection, preview and apply workflow. Most
    shipped modifiers are now driven by their Creator tool runtime; this module
    keeps a small non-Qt contract for tests, registries and future services.
    """

    spec: ModifierSpec

    def can_start(self, context: Any, selected_count: int) -> bool:
        ...

    def preview(self, context: Any, params: dict[str, Any]) -> OperationResult:
        ...

    def apply(self, context: Any, params: dict[str, Any]) -> OperationResult:
        ...


@dataclass(frozen=True, slots=True)
class ToolHostedModifier:
    """Modifier entry represented by a concrete Studio tool runtime."""

    spec: ModifierSpec

    def can_start(self, context: Any, selected_count: int) -> bool:
        if not self.spec.requires_selection:
            return True
        return selected_count >= 1

    def preview(self, context: Any, params: dict[str, Any]) -> OperationResult:
        return OperationResult.failure(f"{self.spec.label} preview is handled by its Studio tool runtime.")

    def apply(self, context: Any, params: dict[str, Any]) -> OperationResult:
        return OperationResult.failure(f"{self.spec.label} apply is handled by its Studio tool runtime.")

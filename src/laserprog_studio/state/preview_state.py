# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PreviewState:
    """UI-level preview metadata kept outside ModelStore.

    ModelStore owns the actual preview meshes. This state records the user-facing
    reason/warnings so future tools and modifiers can expose a consistent
    preview/apply/cancel workflow without storing that metadata in the geometry
    model.
    """

    reason: str | None = None
    warnings: list[str] = field(default_factory=list)

    def clear(self) -> None:
        self.reason = None
        self.warnings.clear()

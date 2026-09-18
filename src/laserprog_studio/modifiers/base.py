# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModifierSpec:
    """Static description for mesh modifiers.

    Modifiers are tools that transform selected meshes, often with preview/apply
    lifecycle. Split Plane is currently the only implemented modifier, but this
    registry is ready for simplify, relief, extrude-down and hollow operations.
    """

    id: str
    label: str
    tool_id: str
    requires_selection: bool = True
    interactive: bool = False
    panel_index: int | None = None
    operation_module: str | None = None

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TransformState:
    mode: str = "translate"
    scale_ratio_locked: bool = False
    drag_axis: str | None = None
    drag_mesh_indices: list[int] = field(default_factory=list)
    highlighted_axis: str | None = None
    hovered_axis: str | None = None
    start_vertices_by_index: dict[int, list[tuple[float, float, float]]] = field(default_factory=dict)
    undo_snapshot: Any = None

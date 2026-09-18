# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SelectionState:
    selected_indices: list[int] = field(default_factory=list)
    active_index: int | None = None

    def set_single(self, index: int | None) -> None:
        self.selected_indices = [] if index is None else [int(index)]
        self.active_index = index

    def clear(self) -> None:
        self.selected_indices.clear()
        self.active_index = None

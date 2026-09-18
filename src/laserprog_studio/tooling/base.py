# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from ..parameters import ParameterSpec, defaults_for, validate_values

ToolCategory = Literal["tool", "modifier"]
SelectionPolicy = Literal["none", "single", "multi"]


@dataclass(frozen=True)
class ToolSpec:
    """Static description of a Studio tool/modifier.

    The current UI is still mostly hand-built, but this spec is the extension
    point new tools should target: label, panel index, button attr, selection
    constraints and optional lifecycle hooks live in one place instead of being
    duplicated across scene/menu/button code.
    """

    id: str
    label: str
    category: ToolCategory
    panel_index: int
    button_attr: str | None = None
    selection_policy: SelectionPolicy = "none"
    clear_selection_on_open: bool = False
    active_index_from_selection: bool = False
    open_hook: str | None = None
    close_hook: str | None = None
    display_order: int = 0
    parameters: tuple[ParameterSpec, ...] = ()
    allow_multi_selection: bool | None = None
    open_without_initial_selection: bool = False

    @property
    def requires_selection(self) -> bool:
        return self.selection_policy in {"single", "multi"}

    @property
    def allows_multi_selection(self) -> bool:
        if self.allow_multi_selection is not None:
            return bool(self.allow_multi_selection)
        return self.selection_policy == "multi"

    def default_parameters(self) -> dict[str, Any]:
        return defaults_for(self.parameters)

    def validate_parameters(self, values: dict[str, Any]) -> dict[str, Any]:
        return validate_values(self.parameters, values)

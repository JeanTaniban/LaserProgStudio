# -*- coding: utf-8 -*-
"""Minimal inspector for Cloth.

All workflow commands live in the single viewport overlay. The inspector owns
only the smart logical-surface continuity requested by the user.
"""
from __future__ import annotations

from typing import Any, Callable

from laserprog_studio.tool_api.inspector import FloatField, HelpText, Panel, Section


def build_cloth_panel(*, on_value_changed: Callable[[str, Any], None], on_action: Callable[[Any], None]) -> Any:  # noqa: ARG001
    return Panel(
        "Cloth",
        id="cloth.tool",
        owner_tool="cloth",
        description="Select logical surfaces, create textile geometry, close it and assign roles from one contextual overlay.",
        sections=(
            Section(
                "Selection",
                fields=(
                    FloatField(
                        "cloth_surface_continuity",
                        "Logical surface",
                        default=0.35,
                        min_value=0.0,
                        max_value=1.0,
                        step=0.01,
                        tooltip="Propagation used by the smart-selection API for logical mesh and textile groups.",
                        on_change=on_value_changed,
                    ),
                    HelpText(
                        "cloth_surface_help",
                        "0 selects strict local faces. 1 accepts broader continuous surfaces. Shift adds another selected group.",
                    ),
                ),
            ),
        ),
    )


__all__ = ["build_cloth_panel"]

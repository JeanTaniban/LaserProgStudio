# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from laserprog_studio.tool_api.inspector import ChoiceField, FloatField, Panel, ReadonlyField, Section, SliderField

from .models import FOLDING_MAX_ANGLE_DEG, FOLDING_MIN_ANGLE_DEG


_FIXED_SIDE_CHOICES = (
    ("start", "First side"),
    ("end", "Second side"),
)

_DEFORMATION_MODE_CHOICES = (
    ("preserve_structure", "Preserve internal structure"),
    ("uniform", "Uniform deformation"),
)


_PROFILE_DETAIL_CHOICES = (
    ("1", "Simple · 1 handle"),
    ("3", "Standard · 3 handles"),
    ("5", "Detailed · 5 handles"),
    ("7", "Advanced · 7 handles"),
)


def build_folding_panel(*, on_value_changed: Callable[[str, Any], None], on_action: Callable[[Any], None]) -> Any:  # noqa: ARG001
    """Minimal inspector. Workflow guidance lives in the viewport card."""

    return Panel(
        "Folding",
        id="folding.tool",
        owner_tool="folding",
        description="Living-hinge fold",
        sections=(
            Section(
                "Fold",
                fields=(
                    SliderField(
                        "folding_angle",
                        "Angle",
                        default=90.0,
                        min_value=FOLDING_MIN_ANGLE_DEG,
                        max_value=FOLDING_MAX_ANGLE_DEG,
                        step=1.0,
                        unit="°",
                        tooltip="Range: -720° to +720°. The guide updates immediately; the 3D mesh is rebuilt after 1.5 s. Over-folds may self-intersect.",
                        on_change=on_value_changed,
                        visible=False,
                    ),
                    ChoiceField(
                        "folding_fixed_side",
                        "Fixed side",
                        default="start",
                        choices=_FIXED_SIDE_CHOICES,
                        tooltip="The opposite solid region moves rigidly.",
                        on_change=on_value_changed,
                        visible=False,
                    ),
                    ChoiceField(
                        "folding_deformation_mode",
                        "Internal geometry",
                        default="preserve_structure",
                        choices=_DEFORMATION_MODE_CHOICES,
                        tooltip="Preserve structure keeps local edge lengths and small internal details rigid. Uniform deformation bends, stretches and compresses every detail continuously with the material.",
                        on_change=on_value_changed,
                        visible=False,
                    ),
                    ChoiceField(
                        "folding_profile_detail",
                        "Shape handles",
                        default="3",
                        choices=_PROFILE_DETAIL_CHOICES,
                        tooltip="More handles allow S-curves and locally concentrated bends without changing the neutral-line length.",
                        on_change=on_value_changed,
                        visible=False,
                    ),
                    ReadonlyField("folding_length", "Flexible width", default="Not defined", visible=False),
                    ReadonlyField("folding_preview_state", "Mesh", default="Waiting", visible=False),
                ),
            ),
            Section(
                "Legacy curve",
                fields=(
                    FloatField("folding_control_1", "Control 1", default=0.0, min_value=-100000.0, max_value=100000.0, step=1.0, unit="mm", on_change=on_value_changed, visible=False),
                    FloatField("folding_control_2", "Control 2", default=0.0, min_value=-100000.0, max_value=100000.0, step=1.0, unit="mm", on_change=on_value_changed, visible=False),
                ),
                collapsed=True,
            ),
        ),
    )


__all__ = ["build_folding_panel"]

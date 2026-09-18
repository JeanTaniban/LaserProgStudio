# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from laserprog_studio.tool_api.inspector import (
    BoolField,
    ButtonRow,
    ChoiceField,
    FloatField,
    HelpText,
    IntField,
    Panel,
    ReadonlyField,
    Section,
    Separator,
)

from .models import MechanicalMode, ToothProfile


MODE_CHOICES = (
    (MechanicalMode.PICK_PLANE.value, "Start / open assembly"),
    (MechanicalMode.SELECT.value, "Select / edit"),
    (MechanicalMode.PLACE_GEAR.value, "Place gear"),
    (MechanicalMode.PLACE_CHAIN_START.value, "Place gear chain"),
    (MechanicalMode.PLACE_RACK_START.value, "Place rack and pinion"),
    (MechanicalMode.EDIT_CURVE.value, "Edit selected curve"),
    (MechanicalMode.PICK_DRIVER_TARGET.value, "Create rotary driver"),
    (MechanicalMode.PICK_ATTACHMENT_SOURCE.value, "Attach driven parts"),
    (MechanicalMode.TEST.value, "Test motion"),
)

PROFILE_CHOICES = (
    (ToothProfile.INVOLUTE_APPROX.value, "Approx. involute"),
    (ToothProfile.TRAPEZOID.value, "Trapezoid"),
    (ToothProfile.ROUNDED.value, "Rounded"),
)


def build_mechanical_panel(
    *,
    on_mode_changed: Callable[[str, Any], None],
    on_value_changed: Callable[[str, Any], None],
    on_action: Callable[[Any], None],
) -> Any:
    return Panel(
        "Mechanical motion",
        id="mechanical.motion",
        owner_tool="mechanical_motion",
        description="Design editable rotary and linear mechanisms, attach scene parts, then test the kinematics.",
        sections=(
            Section(
                "Workflow",
                fields=(
                    ChoiceField(
                        "mechanical_mode",
                        "Mode",
                        default=MechanicalMode.PICK_PLANE.value,
                        choices=MODE_CHOICES,
                        on_change=on_mode_changed,
                        tooltip="Choose what the next viewport interaction does.",
                    ),
                    ReadonlyField("mechanical_status", "Status", default="Select a planar face."),
                    ReadonlyField("mechanical_work_plane", "Construction plane", default="Not selected."),
                    ReadonlyField("mechanical_summary", "Assembly", default="0 gear · 0 chain · 0 rack · 0 driver · 0 attachment"),
                    ReadonlyField("mechanical_selection", "Selection", default="No mechanical element selected."),
                    HelpText("mechanical_workflow_help", "Start by clicking a planar model face, or select an existing MEC assembly to edit it or create a separate assembly on the same plane. The camera always remains free to orbit."),
                ),
            ),
            Section(
                "Gear",
                fields=(
                    IntField("gear_teeth", "Teeth", default=24, min_value=6, max_value=500, step=1, on_change=on_value_changed),
                    FloatField("gear_module", "Module", default=2.0, min_value=0.05, max_value=100.0, step=0.1, unit="mm", on_change=on_value_changed),
                    FloatField("gear_thickness", "Thickness", default=6.0, min_value=0.1, max_value=1000.0, step=0.5, unit="mm", on_change=on_value_changed),
                    FloatField("gear_bore", "Bore diameter", default=5.0, min_value=0.0, max_value=1000.0, step=0.5, unit="mm", on_change=on_value_changed),
                    ChoiceField("gear_profile", "Tooth profile", default=ToothProfile.INVOLUTE_APPROX.value, choices=PROFILE_CHOICES, on_change=on_value_changed),
                    FloatField("gear_pressure_angle", "Pressure angle", default=20.0, min_value=10.0, max_value=35.0, step=1.0, unit="°", on_change=on_value_changed),
                    FloatField("gear_backlash", "Backlash", default=0.10, min_value=0.0, max_value=10.0, step=0.02, unit="mm", on_change=on_value_changed),
                ),
            ),
            Section(
                "Gear chain",
                fields=(
                    IntField("chain_intermediate_shafts", "Intermediate shafts", default=2, min_value=0, max_value=24, step=1, on_change=on_value_changed),
                    FloatField("chain_reduction", "Reduction ratio", default=4.0, min_value=0.01, max_value=10000.0, step=0.1, unit=":1", on_change=on_value_changed),
                    FloatField("chain_distribution", "Ratio distribution", default=0.0, min_value=-1.0, max_value=1.0, step=0.05, tooltip="-1 concentrates reduction near the input; +1 near the output.", on_change=on_value_changed),
                    FloatField("chain_target_module", "Target module", default=2.0, min_value=0.05, max_value=100.0, step=0.1, unit="mm", on_change=on_value_changed),
                    IntField("chain_min_teeth", "Minimum teeth", default=12, min_value=6, max_value=200, step=1, on_change=on_value_changed),
                    IntField("chain_max_teeth", "Maximum teeth", default=120, min_value=6, max_value=1000, step=1, on_change=on_value_changed),
                    ReadonlyField("chain_actual_ratio", "Obtained ratio", default="No chain selected."),
                    ReadonlyField("chain_warning", "Solver", default="No warning."),
                    HelpText("chain_help", "Intermediate axes carry two coaxial gears fused into one connected part. Their contiguous layers distribute the requested ratio without axial gaps."),
                ),
            ),
            Section(
                "Rack and pinion",
                fields=(
                    FloatField("rack_body_height", "Rack body height", default=10.0, min_value=0.1, max_value=1000.0, step=0.5, unit="mm", on_change=on_value_changed),
                    FloatField("rack_thickness", "Rack thickness", default=6.0, min_value=0.1, max_value=1000.0, step=0.5, unit="mm", on_change=on_value_changed),
                    FloatField("rack_backlash", "Rack backlash", default=0.10, min_value=0.0, max_value=10.0, step=0.02, unit="mm", on_change=on_value_changed),
                    ReadonlyField("rack_pinion", "Pinion", default="No rack selected."),
                    ReadonlyField("rack_travel", "Linear travel", default="No rack selected."),
                    HelpText("rack_help", "Select a pinion gear, then draw the rack direction and length. MEC snaps the pitch line tangent to the gear and converts pinion rotation to exact no-slip linear travel during Test."),
                ),
            ),
            Section(
                "Drive & test",
                fields=(
                    FloatField("driver_speed_rpm", "Driver speed", default=10.0, min_value=0.0, max_value=100000.0, step=1.0, unit="rpm", on_change=on_value_changed),
                    BoolField("driver_reverse", "Reverse direction", default=False, on_change=on_value_changed),
                    FloatField("test_angle_deg", "Test angle", default=0.0, min_value=-100000.0, max_value=100000.0, step=5.0, unit="°", on_change=on_value_changed),
                    BoolField("test_playing", "Play test", default=False, on_change=on_value_changed),
                    HelpText("test_help", "Test mode opens one compact driver RPM control and a planar rotation handle. Motion uses cached actor matrices, so the scene is not rebuilt on every animation frame and the stored geometry remains neutral."),
                ),
            ),
            Section(
                "Actions",
                fields=(
                    Separator("mechanical_actions_separator"),
                    ButtonRow(
                        "mechanical_actions",
                        "Assembly",
                        buttons=(
                            ("attach_selection", "Confirm attachment"),
                            ("make_driver", "Driver from selection"),
                            ("delete_selected", "Delete selected element"),
                            ("refresh_preview", "Refresh preview"),
                            ("save_draft", "Save recoverable draft"),
                            ("reset_assembly", "Reset assembly"),
                        ),
                        columns=2,
                        callbacks={
                            "attach_selection": on_action,
                            "make_driver": on_action,
                            "delete_selected": on_action,
                            "refresh_preview": on_action,
                            "save_draft": on_action,
                            "reset_assembly": on_action,
                        },
                    ),
                ),
            ),
        ),
    )


__all__ = ["MODE_CHOICES", "PROFILE_CHOICES", "build_mechanical_panel"]

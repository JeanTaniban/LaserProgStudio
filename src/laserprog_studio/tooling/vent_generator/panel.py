# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from laserprog_studio.planar_tools import VentFlareSide, VentSectionKind
from laserprog_studio.tool_api.inspector import AutoPreview, BoolField, ButtonRow, ChoiceField, FloatField, HelpText, Panel, ReadonlyField, Section, Separator, Title
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR

from .presets import CUSTOM_PRESET_ID, PRESET_CHOICES
from .settings import FLARE_CHOICES, MODE_CHOICES, SECTION_CHOICES


def build_vent_generator_panel(*, on_mode_changed: Callable[[str, Any], None], on_values_changed: Callable[[str, Any], None], on_preset_changed: Callable[[str, Any], None], on_action: Callable[[Any], None]) -> Any:
    """Build the Creator API inspector panel for Vent Generator."""

    return Panel(
        "Vent generator",
        id="vent.generator",
        owner_tool=TOOL_VENT_GENERATOR,
        description="Draw a locked-plan vent route, tune it, apply a printable mesh.",
        auto_preview=AutoPreview(action_id="refresh", debounce_ms=180, exclude_fields=("mode", "quick_preset", "preset_help", "vent_report", "route_summary", "selected_point", "viewport_feedback", "apply_check", "build_mode_summary", "compact_route_guide", "vent_constraint_help", "timing", "enclosure_volume_l", "vent_length_measure", "vent_height_measure", "vent_area_measure", "vent_tuning_measure")),
        sections=(
            Section(
                "Route workflow",
                fields=(
                    ChoiceField("mode", "Mode", default="ADD", choices=MODE_CHOICES, tooltip="Add points, modify a selected point, delete a point, or reset the route.", on_change=on_mode_changed),
                    ReadonlyField("route_summary", "Route", default="0 waypoint — click Add to start the route."),
                    ReadonlyField("viewport_feedback", "Viewport", default="Overlay and route preview are ready."),
                    HelpText("vent_workflow_help", "Pick a plane. Add inlet/outlet points. Modify bends. Apply when ready."),
                ),
            ),
            Section(
                "Snap & constraints",
                fields=(
                    BoolField("smart_snap", "Smart snap", default=True, tooltip="Snap to scene geometry and waypoint alignment guides.", on_change=on_values_changed),
                    HelpText("vent_constraint_help", "Smart snap ignores the route itself. Hold Shift for strict 45° routing."),
                ),
            ),
            Section(
                "Presets",
                fields=(
                    ChoiceField("quick_preset", "Quick start", default=CUSTOM_PRESET_ID, choices=PRESET_CHOICES, tooltip="Load a common duct profile, then fine-tune any field.", on_change=on_preset_changed),
                    ReadonlyField("preset_help", "Preset note", default="Choose a preset to load common dimensions, or stay on Custom."),
                    HelpText("vent_preset_help", "Presets are only starters. Editing any dimension switches the tool back to Custom values."),
                ),
            ),
            Section(
                "Duct profile",
                fields=(
                    ChoiceField("section_kind", "Profile", default=VentSectionKind.RECTANGLE.value, choices=SECTION_CHOICES, tooltip="Rectangular ducts expose width/height; round pipes use area.", on_change=on_values_changed),
                    FloatField("section_area", "Flow area", default=100.0, min_value=0.001, max_value=1_000_000.0, step=1.0, unit="mm²", tooltip="Round-pipe section area.", on_change=on_values_changed, visible=False),
                    FloatField("rect_width", "Inner width", default=10.0, min_value=0.001, max_value=100_000.0, step=0.5, unit="mm", tooltip="Clear inner duct width before wall thickness.", on_change=on_values_changed),
                    FloatField("rect_height", "Inner height / extrusion", default=10.0, min_value=0.001, max_value=100_000.0, step=0.5, unit="mm", tooltip="Clear inner duct height before wall thickness.", on_change=on_values_changed),
                    FloatField("wall_thickness", "Wall thickness", default=3.0, min_value=0.001, max_value=100_000.0, step=0.25, unit="mm", tooltip="Printed wall thickness around the airflow path.", on_change=on_values_changed),
                    BoolField("fill_area", "Solid fill / carve block", default=False, tooltip="Off: duct walls only. On: stock block carved by the airway.", on_change=on_values_changed),
                    ReadonlyField("build_mode_summary", "Build mode", default="Wall-only rectangular duct · open airway with generated walls."),
                    ReadonlyField("compact_route_guide", "Compact guide", default="Compact pitch: inner width + wall thickness for a shared wall."),
                    HelpText("vent_profile_help", "Default rectangular mode is wall-only. Enable fill for a carved stock block."),
                ),
            ),
            Section(
                "Selected bend",
                fields=(
                    ReadonlyField("selected_point", "Selection", default="No selected waypoint."),
                    FloatField("target_length", "Target length", default=0.0, min_value=0.0, max_value=1_000_000.0, step=1.0, unit="mm", tooltip="Optional target to compare against the current centerline. 0 disables it.", on_change=on_values_changed),
                    FloatField("curve_radius", "Bend radius", default=0.0, min_value=0.0, max_value=100_000.0, step=0.5, unit="mm", tooltip="Radius for the selected Modify point. Hidden until a waypoint is selected.", on_change=on_values_changed, enabled=False, visible=False),
                    FloatField("curve_strength", "Bend force", default=0.0, min_value=-1.0, max_value=1.0, step=0.05, tooltip="Signed curve force for the selected Modify point.", on_change=on_values_changed, enabled=False, visible=False),
                ),
            ),
            Section(
                "Openings",
                fields=(
                    ChoiceField("flare_side", "Flare", default=VentFlareSide.NONE.value, choices=FLARE_CHOICES, tooltip="Gradually widen the inlet, outlet or both ends.", on_change=on_values_changed),
                    FloatField("flare_factor", "Flare scale", default=1.0, min_value=1.0, max_value=10.0, step=0.1, unit="×", tooltip="Opening scale. 1.5 means 50% wider.", on_change=on_values_changed, visible=False),
                ),
            ),
            Section(
                "Acoustic tuning",
                fields=(
                    FloatField("enclosure_volume_l", "Box volume", default=20.0, min_value=0.0, max_value=1_000_000.0, step=0.1, unit="L", tooltip="Net enclosure volume used for the Helmholtz tuning estimate.", on_change=on_values_changed),
                    ReadonlyField("vent_length_measure", "Vent length", default="0.0 mm"),
                    ReadonlyField("vent_height_measure", "Vent height", default="0.0 mm"),
                    ReadonlyField("vent_area_measure", "Section", default="0.0 cm²"),
                    ReadonlyField("vent_tuning_measure", "Tuning", default="Enter a box volume and draw at least two waypoints."),
                    HelpText("vent_acoustic_help", "First-pass Helmholtz estimate from section, length and end correction."),
                ),
            ),
            Section(
                "Preview & apply",
                fields=(
                    Title("vent_preview_title", "Generated duct"),
                    ReadonlyField("vent_report", "Status", default="Pick a plane, then draw at least two route points."),
                    ReadonlyField("apply_check", "Apply check", default="Add at least two waypoints to enable Apply."),
                    ReadonlyField("timing", "Timing", default="No timing samples yet."),
                    Separator("vent_actions_sep"),
                    ButtonRow(
                        "vent_actions",
                        "Actions",
                        buttons=(("refresh", "Refresh preview"), ("apply_mesh", "Apply mesh"), ("export_timings", "Export timings"), ("start_over", "Start over"), ("reset_path", "Reset route")),
                        columns=2,
                        tooltip="Refresh, apply, start over, or clear only the route.",
                        callbacks={"refresh": on_action, "apply_mesh": on_action, "export_timings": on_action, "start_over": on_action, "reset_path": on_action},
                    ),
                ),
            ),
        ),
    )


__all__ = ["build_vent_generator_panel"]

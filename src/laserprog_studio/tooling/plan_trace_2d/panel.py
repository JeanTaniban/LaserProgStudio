# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from laserprog_studio.tool_api.inspector import AutoPreview, BoolField, Button, ChoiceField, FloatField, HelpText, IntField, Panel, ReadonlyField, Section, Separator, SliderField, Title
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE

from .constants import (
    _MODE_ARC,
    _MODE_CIRCLE,
    _MODE_DIMENSION,
    _MODE_DUPLICATE,
    _MODE_MIRROR,
    _MODE_BEZIER,
    _MODE_HALF_CIRCLE,
    _MODE_LINE,
    _MODE_MESH_TRACE,
    _MODE_MODIFY,
    _MODE_POINT,
    _MODE_POLYLINE,
    _MODE_RECTANGLE,
)
from .patterns import PATTERN_KIND_CHOICES

PLAN_TRACE_MODE_CHOICES: tuple[tuple[str, str], ...] = (
    (_MODE_MODIFY, "Modify"),
    (_MODE_MESH_TRACE, "Mesh trace"),
    (_MODE_DUPLICATE, "Duplicate"),
    (_MODE_MIRROR, "Mirror"),
    (_MODE_POINT, "Point"),
    (_MODE_LINE, "Line"),
    (_MODE_POLYLINE, "Polyline"),
    (_MODE_RECTANGLE, "Rectangle"),
    (_MODE_CIRCLE, "Circle"),
    (_MODE_ARC, "Arc"),
    (_MODE_BEZIER, "Curve"),
    (_MODE_HALF_CIRCLE, "Half-circle"),
    (_MODE_DIMENSION, "Dimension"),
)


def build_plan_trace_2d_panel(
    *,
    on_mode_changed: Callable[[str, Any], None],
    on_settings_changed: Callable[[str, Any], None],
    on_action: Callable[[Any], None],
) -> Any:
    """Build the Creator API inspector panel for Plan Tracer."""

    return Panel(
        "Plan tracer",
        id="plan_trace_2d.panel",
        owner_tool=TOOL_PLAN_TRACE,
        description="Face-locked 2D sketch. Draw in the viewport; use this panel for snap, constraints, status and exact values.",
        auto_preview=AutoPreview(
            action_id="refresh",
            debounce_ms=140,
            exclude_fields=(
                "plan_trace_2d.phase",
                "plan_trace_2d.view",
                "plan_trace_2d.plane",
                "plan_trace_2d.anchor",
                "plan_trace_2d.editing",
                "plan_trace_2d.tool",
                "plan_trace_2d.counts",
                "plan_trace_2d.selection",
                "plan_trace_2d.selection_length",
                "plan_trace_2d.snap",
                "plan_trace_2d.perf",
                "plan_trace_2d.status",
            ),
        ),
        sections=(
            Section(
                "Workflow",
                fields=(
                    ChoiceField(
                        "plan_trace_2d.mode",
                        "Mode",
                        default=_MODE_POINT,
                        choices=PLAN_TRACE_MODE_CHOICES,
                        tooltip="Choose the active drawing or edit mode. The viewport toolbar stays in sync.",
                        on_change=on_mode_changed,
                    ),
                    ReadonlyField("plan_trace_2d.phase", "Phase", default="Pick height"),
                    ReadonlyField("plan_trace_2d.view", "View", default="top"),
                    ReadonlyField("plan_trace_2d.plane", "Plane", default="not locked"),
                    ReadonlyField("plan_trace_2d.anchor", "Anchor", default="not selected"),
                    ReadonlyField("plan_trace_2d.editing", "Editing", default="New volume"),
                    HelpText("plan_trace_2d.workflow_help", "Pick a face/height, an editable Plan Tracer volume, or a red draft placeholder. Esc cancels the current placement; Esc in Modify saves a recoverable draft."),
                ),
            ),
            Section(
                "Snap & constraints",
                fields=(
                    BoolField("plan_trace_2d.smart_snap", "Smart snap", default=True, tooltip="Snap to scene geometry and the current 2D sketch.", on_change=on_settings_changed),
                    BoolField("plan_trace_2d.active_part_snap", "Active part only", default=False, tooltip="When enabled, scene smart-snaps are limited to the object that owns the picked face. The current sketch still snaps normally.", on_change=on_settings_changed),
                    BoolField("plan_trace_2d.grid_snap", "Grid snap", default=False, tooltip="Use the construction grid when no stronger snap is found.", on_change=on_settings_changed),
                    FloatField("plan_trace_2d.grid_step", "Grid step", default=5.0, min_value=0.001, max_value=100_000.0, step=1.0, unit="mm", tooltip="Construction grid spacing used by grid snap.", on_change=on_settings_changed, visible=False),
                    ReadonlyField("plan_trace_2d.snap", "Last snap", default="none"),
                    HelpText("plan_trace_2d.constraint_help", "Shift constrains axes/squares while drawing."),
                ),
            ),
            Section(
                "Sketch status",
                fields=(
                    ReadonlyField("plan_trace_2d.tool", "Tool", default="Point"),
                    ReadonlyField("plan_trace_2d.counts", "Sketch", default="0 point · 0 edge · 0 face"),
                    ReadonlyField("plan_trace_2d.selection", "Selection", default="0 selected"),
                    ReadonlyField("plan_trace_2d.selection_length", "Selected length", default="—", tooltip="Exact total length of selected line, polyline, arc and circle entities. Connectivity is reported for end-to-end selections."),
                    ReadonlyField("plan_trace_2d.perf", "Timing", default="No timing samples yet."),
                    ReadonlyField("plan_trace_2d.status", "Status", default="Click a face or part to lock the 2D drawing height."),
                ),
            ),
            Section(
                "Metric editing",
                fields=(
                    Title("plan_trace_2d.metric_title", "Precise placement"),
                    ReadonlyField("plan_trace_2d.metric", "Metric", default="No active metric edit."),
                    HelpText("plan_trace_2d.metric_help", "Validate the metric overlay, or keep drawing to accept the shown value."),
                ),
            ),
            Section(
                "Build · patterns",
                fields=(
                    HelpText(
                        "plan_trace_2d.pattern_help",
                        "Workflow: switch to Modify, click the target face, then "
                        "the Plan Tracer toolbar exposes a Pattern button that "
                        "opens the editor. The preview updates live; Apply "
                        "commits, Back cancels. The parameters below mirror "
                        "the Pattern editor state and can also be "
                        "edited directly here.",
                    ),
                    ReadonlyField(
                        "plan_trace_2d.pattern_face",
                        "Target face",
                        default="No face selected",
                    ),
                    ChoiceField(
                        "plan_trace_2d.pattern_kind",
                        "Pattern",
                        default="honeycomb",
                        choices=PATTERN_KIND_CHOICES,
                        tooltip=(
                            "Pattern type. 'Living hinge' variants create "
                            "parallel slots to make thin plywood "
                            "flexible."
                        ),
                        on_change=on_settings_changed,
                    ),
                    FloatField(
                        "plan_trace_2d.pattern_cell_size",
                        "Pitch / size",
                        default=12.0,
                        min_value=0.5,
                        max_value=100_000.0,
                        step=1.0,
                        unit="mm",
                        tooltip=(
                            "Cell pitch for regular patterns, or slot spacing for "
                            "living hinges."
                        ),
                        on_change=on_settings_changed,
                    ),
                    FloatField(
                        "plan_trace_2d.pattern_wall",
                        "Wall / kerf",
                        default=2.0,
                        min_value=0.1,
                        max_value=100_000.0,
                        step=0.5,
                        unit="mm",
                        tooltip=(
                            "Material left between openings. For living "
                            "hinges, this is the width of each slot (laser kerf)."
                        ),
                        on_change=on_settings_changed,
                    ),
                    FloatField(
                        "plan_trace_2d.pattern_margin",
                        "Edge margin",
                        default=2.0,
                        min_value=0.0,
                        max_value=100_000.0,
                        step=0.5,
                        unit="mm",
                        tooltip="Distance kept between the face boundary and openings. At 0, motifs are clipped exactly on the face contour.",
                        on_change=on_settings_changed,
                    ),
                    BoolField(
                        "plan_trace_2d.pattern_keep_form",
                        "Keep forme",
                        default=True,
                        tooltip=(
                            "Checked: preserve the selected face outer contour. "
                            "Unchecked: remove the original contour and let the motif cuts define the resulting face outline."
                        ),
                        on_change=on_settings_changed,
                    ),
                    SliderField(
                        "plan_trace_2d.pattern_angle",
                        "Rotation",
                        default=0.0,
                        min_value=-180.0,
                        max_value=180.0,
                        step=1.0,
                        unit="°",
                        tooltip="Pattern rotation around the target face centre.",
                        on_change=on_settings_changed,
                    ),
                    FloatField(
                        "plan_trace_2d.pattern_aspect",
                        "Secondary ratio",
                        default=1.0,
                        min_value=0.1,
                        max_value=10.0,
                        step=0.1,
                        tooltip=(
                            "Pattern-specific secondary parameter: slot length "
                            "vs pitch for living hinges, diamond flattening, "
                            "star branch length, or organic cell jitter."
                        ),
                        on_change=on_settings_changed,
                    ),
                    IntField(
                        "plan_trace_2d.pattern_seed",
                        "Random seed",
                        default=7,
                        min_value=0,
                        max_value=999_999,
                        step=1,
                        tooltip=(
                            "Seed for stochastic patterns (organic cells). "
                            "Changes the layout while staying reproducible."
                        ),
                        on_change=on_settings_changed,
                    ),
                    ReadonlyField(
                        "plan_trace_2d.pattern_status",
                        "Status",
                        default="Select a face in Modify mode, then click Pattern in the toolbar.",
                    ),
                ),
            ),
            Section(
                "Actions",
                fields=(
                    Separator("plan_trace_2d.action_sep"),
                    Button("refresh", "Refresh visuals", tooltip="Refresh Plan Tracer viewport feedback.", on_click=on_action),
                    Button("export_timings", "Export timings", tooltip="Write a Plan Tracer timing report to diagnostics/plan_trace_2d_timings.md.", on_click=on_action),
                    Button("save_draft", "Cancel to draft", tooltip="Cancel the current sketch into a red recoverable draft placeholder.", on_click=on_action),
                    Button("restore_faces", "Rebuild faces", tooltip="Restore generated faces from closed boundaries.", on_click=on_action),
                    Button("copy_selection", "Copy selection", tooltip="Copy selected points, curves or faces (Ctrl+C).", on_click=on_action),
                    Button("paste_selection", "Paste selection", tooltip="Paste a detached sketch copy (Ctrl+V).", on_click=on_action),
                    Button("delete_selection", "Delete selection", tooltip="Delete selected Plan Tracer geometry.", on_click=on_action),
                    Button("reset", "Start over", tooltip="Clear the current Plan Tracer sketch and restart.", on_click=on_action),
                ),
            ),
        ),
    )


__all__ = ["PLAN_TRACE_MODE_CHOICES", "build_plan_trace_2d_panel"]

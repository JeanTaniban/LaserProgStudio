"""Public Plan 2D Metric Input API for Creator drawing tools.

Metric input is temporary: it helps the user validate numeric values after a
visual placement, without immediately turning every value into a persistent
constraint.  The implementation stays in ``tool_core.metrics`` so the public API
remains a small facade rather than another monolithic tool file.
"""
from __future__ import annotations

from laserprog_studio.tool_core.metrics import (
    MetricEditSession,
    MetricFieldSpec,
    MetricKind,
    MetricOverlayIds,
    MetricSessionState,
    arc_metric_session,
    circle_metric_session,
    half_circle_metric_session,
    field_tuple,
    format_metric_value,
    line_metric_session,
    rectangle_metric_session,
    parse_metric_value,
)
from laserprog_studio.tool_core.overlay import OverlayFieldSpec, OverlayWindowSpec, ToolButtonSpec

from laserprog_studio.tool_core.metrics.geometry import (
    ArcMetricGeometry,
    CircleMetricGeometry,
    LineMetricGeometry,
    RectangleMetricGeometry,
    arc_control_from_metrics,
    arc_metrics,
    circle_metrics,
    circle_radius_point_from_metrics,
    distance,
    half_circle_end_from_metrics,
    half_circle_metrics,
    line_end_from_metrics,
    line_metrics,
    rectangle_metrics,
    rectangle_opposite_from_metrics,
)


def metric_field_overlay_id(window_id: str, field_id: str) -> str:
    return f"{window_id}.metric.{field_id}"


def metric_edit_window_width_px(session: MetricEditSession, *, requested_width_px: int = 0) -> int:
    """Return the natural width for the Plan 2D placement validation bar.

    The metric overlay is a transient CAD confirmation HUD: numeric fields need
    enough width to be edited confidently, while the viewport must stay visible.
    The sizing is therefore derived from the number of editable fields instead of
    a hard-coded 360px strip that clips labels and makes actions feel cramped.
    """

    requested = int(requested_width_px or 0)
    if requested > 0:
        return max(420, min(760, requested))
    editable_count = sum(1 for field in field_tuple(session.fields) if bool(field.enabled))
    # left title block + fields + actions + gutters.  Three-field sessions such
    # as half-circle need the extra room; two-field sessions stay compact.
    return max(520, min(760, 238 + editable_count * 126 + 174))


def build_metric_edit_window(
    *,
    window_id: str,
    owner_tool: str,
    session: MetricEditSession,
    validate_button_id: str,
    cancel_button_id: str,
    anchor: str = "viewport_bottom_center",
    width_px: int = 360,
    overlay_kind: str = "toolbar",
) -> OverlayWindowSpec:
    """Build the standard viewport placement validation overlay.

    Tools pass a typed session; the overlay API emits plain declarative fields
    and buttons.  The native Qt renderer materializes this as a dedicated
    ``metric_bar`` when requested by a tool; the default remains the legacy
    compact toolbar contract for API compatibility.
    """

    fields: list[OverlayFieldSpec] = []
    for field in field_tuple(session.fields):
        fields.append(
            OverlayFieldSpec(
                metric_field_overlay_id(window_id, field.id),
                field.label,
                format_metric_value(field),
                kind="number" if field.enabled else "info",
                enabled=bool(field.enabled),
                tooltip=field.tooltip,
            )
        )
    buttons = [
        ToolButtonSpec(str(validate_button_id), "Validate", icon=None, enabled=True, style="primary", tooltip="Commit the edited dimensions and finish this placement."),
        ToolButtonSpec(str(cancel_button_id), "Cancel", icon=None, enabled=True, style="ghost", tooltip="Restore the sketch to the state before this placement."),
    ]
    use_metric_bar = str(overlay_kind) == "metric_bar"
    return OverlayWindowSpec(
        id=str(window_id),
        title=f"{session.mode_label} placement" if use_metric_bar else "",
        owner_tool=str(owner_tool),
        overlay_kind="metric_bar" if use_metric_bar else "toolbar",  # type: ignore[arg-type]
        anchor=anchor,  # type: ignore[arg-type]
        width_px=metric_edit_window_width_px(session, requested_width_px=width_px) if use_metric_bar else int(width_px),
        movable=False,
        persistent=False,
        close_on_click_outside=False,
        cursor_offset_px=(0, 0),
        fields=fields,
        buttons=buttons,
    )


__all__ = [
    "MetricEditSession",
    "MetricFieldSpec",
    "MetricKind",
    "MetricOverlayIds",
    "MetricSessionState",
    "ArcMetricGeometry",
    "CircleMetricGeometry",
    "LineMetricGeometry",
    "RectangleMetricGeometry",
    "arc_control_from_metrics",
    "arc_metrics",
    "arc_metric_session",
    "build_metric_edit_window",
    "metric_edit_window_width_px",
    "circle_metrics",
    "circle_radius_point_from_metrics",
    "distance",
    "half_circle_end_from_metrics",
    "half_circle_metrics",
    "line_end_from_metrics",
    "line_metrics",
    "rectangle_metrics",
    "rectangle_opposite_from_metrics",
    "circle_metric_session",
    "half_circle_metric_session",
    "format_metric_value",
    "line_metric_session",
    "rectangle_metric_session",
    "metric_field_overlay_id",
    "parse_metric_value",
]

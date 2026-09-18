"""Helpers for constructing metric edit sessions."""
from __future__ import annotations

from .types import MetricEditSession, MetricFieldSpec


def line_metric_session(session_id: str, *, length: float, angle_degrees: float) -> MetricEditSession:
    return MetricEditSession.from_fields(
        session_id,
        title="Line metrics",
        mode_label="Line",
        fields=(
            MetricFieldSpec.length("length", value=float(length)),
            MetricFieldSpec.angle("angle", value=float(angle_degrees)),
        ),
        message="Validate the line dimensions or cancel to restore the previous sketch.",
    )


def circle_metric_session(session_id: str, *, radius: float) -> MetricEditSession:
    radius = max(float(radius), 0.0)
    return MetricEditSession.from_fields(
        session_id,
        title="Circle metrics",
        mode_label="Circle",
        fields=(
            MetricFieldSpec.radius("radius", value=radius),
            MetricFieldSpec.diameter("diameter", value=radius * 2.0),
        ),
        message="Validate the circle dimensions or cancel to restore the previous sketch.",
    )


def rectangle_metric_session(session_id: str, *, width: float, height: float) -> MetricEditSession:
    return MetricEditSession.from_fields(
        session_id,
        title="Rectangle metrics",
        mode_label="Rectangle",
        fields=(
            MetricFieldSpec.width("width", value=float(width)),
            MetricFieldSpec.height("height", value=float(height)),
        ),
        message="Validate the rectangle dimensions or cancel to restore the previous sketch.",
    )


def half_circle_metric_session(session_id: str, *, radius: float, angle_degrees: float) -> MetricEditSession:
    radius = max(float(radius), 0.0)
    return MetricEditSession.from_fields(
        session_id,
        title="Half-circle metrics",
        mode_label="Half-circle",
        fields=(
            MetricFieldSpec.radius("radius", value=radius),
            MetricFieldSpec.diameter("diameter", value=radius * 2.0),
            MetricFieldSpec.angle("angle", value=float(angle_degrees)),
        ),
        message="Validate the half-circle diameter/radius or cancel to restore the previous sketch.",
    )


def arc_metric_session(session_id: str, *, radius: float, angle_degrees: float) -> MetricEditSession:
    return MetricEditSession.from_fields(
        session_id,
        title="Arc metrics",
        mode_label="Arc",
        fields=(
            MetricFieldSpec.radius("radius", value=max(float(radius), 0.0)),
            MetricFieldSpec.angle("angle", value=float(angle_degrees)),
        ),
        message="Validate the arc radius/angle or cancel to restore the previous sketch.",
    )

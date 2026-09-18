"""Stable aggregate module for the Plan 2D metric-edit API.

New sketch-like tools should import from ``laserprog_studio.tool_api.plan2d.metrics``
or from the lazy package facade ``laserprog_studio.tool_api.plan2d``.
"""
from __future__ import annotations

from laserprog_studio.tool_api.plan2d.metrics import *  # noqa: F401,F403
from laserprog_studio.tool_api.plan2d.metrics import __all__ as _PLAN2D_METRICS_ALL

# Source markers kept explicit for architecture checks and grep-based audits.
from laserprog_studio.tool_api.plan2d.metrics import (
    rectangle_opposite_from_metrics,
    rectangle_metrics,
    line_end_from_metrics,
    circle_radius_point_from_metrics,
    arc_control_from_metrics,
)

__all__ = list(_PLAN2D_METRICS_ALL)

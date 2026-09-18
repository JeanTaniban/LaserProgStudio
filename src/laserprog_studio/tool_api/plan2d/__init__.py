"""Focused Plan 2D API for sketch-like Creator tools.

The generic Creator API remains split into broad domains such as ``core``,
``scene`` and ``visual``.  This package is the long-term public subdomain for
locked-plane drawing tools: plane anchoring, coordinate mapping, plan actors,
snap, sketch topology, dimensions, metric editing and curve intent.

The package is intentionally lazy.  Importing ``tool_api.plan2d.curves`` from a
built-in tool must not pull the full visual/registry stack during tool registry
initialization.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

_MODULE_NAMES = {"actors", "curves", "dimensions", "metrics", "plane", "sketch", "snap", "surface"}
_SYMBOL_TO_MODULE: dict[str, str] = {
    # plane
    "FixedPlanarView": "plane",
    "LockedPlaneSpec": "plane",
    "PLAN_TRACE_DEFAULT_SURFACE_OFFSET": "plane",
    "PLAN_TRACE_ANCHOR_FALLBACK_DEPTH": "plane",
    "Plan2DPhase": "plane",
    "Plan2DPlanePick": "plane",
    "Plan2DAnchorPick": "plane",
    "Plan2DStateSummary": "plane",
    "Plan2DTool": "plane",
    "Plan2DCoordinateMapper": "plane",
    "create_coordinate_mapper": "plane",
    "display_point_for_plan_world": "plane",
    "lock_camera_to_plan_view": "plane",
    "align_camera_to_plan_surface": "surface",
    "make_locked_plane_from_surface": "surface",
    "release_plan_view_camera": "plane",
    "nearest_plan_view": "plane",
    "normalize_plan_tool": "plane",
    "offset_plan_height_pick_for_visibility": "plane",
    "pick_plan_anchor_by_raycast": "plane",
    "pick_plan_surface_anchor_by_raycast": "surface",
    "pick_plan_height": "plane",
    "plan_xy_to_world": "plane",
    "project_screen_to_locked_plane": "plane",
    "sample_plan_arc_xy": "plane",
    "semantic_point_for_display_world": "plane",
    "world_to_plan_xy": "plane",
    # actors
    "PLAN_TRACE_MOTIF_FAMILY": "actors",
    "PLAN_TRACE_CURSOR_ROLE": "actors",
    "PLAN_TRACE_POINT_ROLE": "actors",
    "PLAN_TRACE_EDGE_ROLE": "actors",
    "PLAN_TRACE_FACE_ROLE": "actors",
    "PLAN_TRACE_CIRCLE_ROLE": "actors",
    "PLAN_TRACE_ARC_ROLE": "actors",
    "PLAN_TRACE_DIMENSION_ROLE": "actors",
    "PLAN_TRACE_ANCHOR_ROLE": "actors",
    "Plan2DPoint": "actors",
    "hide_plan_cursor": "actors",
    "plan_point_actor_metadata": "actors",
    "register_plan_anchor_target": "actors",
    "register_plan_arc": "actors",
    "register_plan_bezier": "actors",
    "register_plan_circle": "actors",
    "register_plan_cursor": "actors",
    "register_plan_dimension": "actors",
    "register_plan_face": "actors",
    "register_plan_line": "actors",
    "register_plan_point": "actors",
    "mark_plan_actor_visuals_dirty": "actors",
    "sync_plan_actor_visuals": "actors",
    # snap
    "PLAN_2D_SNAP_CURSOR_STYLES": "snap",
    "Plan2DConstraintResult": "snap",
    "Plan2DSnapCursorStyle": "snap",
    "Plan2DSnapResult": "snap",
    "constrain_angle_step_on_plan": "snap",
    "constrain_square_from_corner_on_plan": "snap",
    "smart_snap_on_plan": "snap",
    "snap_cursor_style_for_kind": "snap",
    # sketch
    "PlanSketch": "sketch",
    "PlanSketchCompileOptions": "sketch",
    "PlanSketchCompileResult": "sketch",
    "create_sketch": "sketch",
    "wrap_core_sketch": "sketch",
    # curves
    "ArcIntent": "curves",
    "HalfCircleIntent": "curves",
    "arc_control_from_intent": "curves",
    "circular_arc_length": "curves",
    "curve_intent_metadata": "curves",
    "distance_xy": "curves",
    "half_circle_control_point": "curves",
    "normalize_side": "curves",
    "sample_circle": "curves",
    "sample_circular_arc_through_points": "curves",
    "sample_cubic_bezier": "curves",
    "signed_side": "curves",
    # common dimension/metric symbols used by docs/examples
    "DimensionSpec": "dimensions",
    "MetricEditSession": "metrics",
    "MetricFieldSpec": "metrics",
    "MetricKind": "metrics",
    "MetricSessionState": "metrics",
    "build_metric_edit_window": "metrics",
    "parse_metric_value": "metrics",
}


def __getattr__(name: str) -> Any:
    if name in _MODULE_NAMES:
        module = import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    module_name = _SYMBOL_TO_MODULE.get(name)
    if module_name is not None:
        module = import_module(f"{__name__}.{module_name}")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted([*globals(), *_MODULE_NAMES, *_SYMBOL_TO_MODULE])


__all__ = sorted([*_MODULE_NAMES, *_SYMBOL_TO_MODULE])

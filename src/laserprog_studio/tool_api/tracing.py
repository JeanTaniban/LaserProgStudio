"""Public tracing contracts shared by Plan Tracer-like Creator tools.

The API owns interaction vocabulary only.  It intentionally does not impose a
2D or 3D document model: Plan Tracer keeps its planar sketch kernel, while Cloth
uses a piecewise-planar surface graph.
"""
from __future__ import annotations

from laserprog_studio.tool_core.tracing import (
    PlanePoint3,
    plane_from_origin_normal,
    point_plane_distance,
    world_plane,
    Point2,
    Point3,
    TraceDraft,
    TraceDraftMachine,
    TraceDraftStatus,
    TraceDraftUpdate,
    TraceMode,
    distance3,
    max_plane_deviation,
    normalize_trace_mode,
    polyline_length,
    sample_circular_arc_3d,
)

__all__ = [
    "PlanePoint3",
    "plane_from_origin_normal",
    "point_plane_distance",
    "world_plane",
    "Point2",
    "Point3",
    "TraceDraft",
    "TraceDraftMachine",
    "TraceDraftStatus",
    "TraceDraftUpdate",
    "TraceMode",
    "distance3",
    "max_plane_deviation",
    "normalize_trace_mode",
    "polyline_length",
    "sample_circular_arc_3d",
]

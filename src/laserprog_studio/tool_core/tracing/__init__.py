"""Shared headless contracts for tools that draw points and curves."""
from .curves import Point2, Point3, distance3, max_plane_deviation, polyline_length, sample_circular_arc_3d
from .draft import TraceDraft, TraceDraftMachine, TraceDraftStatus, TraceDraftUpdate
from .planes import Point3 as PlanePoint3, plane_from_origin_normal, point_plane_distance, world_plane
from .modes import TraceMode, normalize_trace_mode

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

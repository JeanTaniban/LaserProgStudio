"""Shared smart-snap contracts and providers."""
from .manager import SMART_SOURCES, SnapManager
from .providers import ExtraSnapProvider, GridSnapProvider, PointSnapProvider, SegmentSnapProvider, closest_point_on_segment_3d, midpoint_on_segment_3d, snap_targets_to_results
from .types import Point2, Point3, SnapKind, SnapProvider, SnapResult, SnapSource, SnapTarget, snap_kind_for_source, snap_label_for_kind

__all__ = [
    "ExtraSnapProvider",
    "GridSnapProvider",
    "Point2",
    "Point3",
    "PointSnapProvider",
    "SMART_SOURCES",
    "SegmentSnapProvider",
    "SnapKind",
    "SnapManager",
    "SnapProvider",
    "SnapResult",
    "SnapSource",
    "SnapTarget",
    "closest_point_on_segment_3d",
    "midpoint_on_segment_3d",
    "snap_kind_for_source",
    "snap_label_for_kind",
    "snap_targets_to_results",
]

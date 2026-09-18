from __future__ import annotations

import pytest
from types import SimpleNamespace

from laserprog_studio.application._preview_face_triangulation import _triangulate_preview_face_points
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.overlay.qt_adapter import QtOverlayAdapter


def test_metric_field_focus_out_consumed_by_tool_does_not_resync_before_validate_click() -> None:
    manager = ToolContext().overlay
    adapter = QtOverlayAdapter(SimpleNamespace(), manager)
    calls: list[str] = []

    adapter._notify_active_tool_overlay_field = lambda *_args: True  # type: ignore[method-assign]
    adapter.sync = lambda: calls.append("sync") or 0  # type: ignore[method-assign]

    adapter._overlay_field_committed("plan_trace_2d.metric", "plan_trace_2d.metric.metric.length", "18 mm")

    assert calls == []


def test_metric_field_focus_out_not_consumed_keeps_generic_overlay_sync() -> None:
    manager = ToolContext().overlay
    adapter = QtOverlayAdapter(SimpleNamespace(), manager)
    calls: list[str] = []

    adapter._notify_active_tool_overlay_field = lambda *_args: False  # type: ignore[method-assign]
    adapter.sync = lambda: calls.append("sync") or 0  # type: ignore[method-assign]

    adapter._overlay_field_committed("generic", "generic.field", "42")

    assert calls == ["sync"]


def test_preview_face_triangulation_removes_hole_from_fill_mesh() -> None:
    pytest.importorskip("shapely")
    outer = ((0.0, 0.0, 0.0), (40.0, 0.0, 0.0), (40.0, 40.0, 0.0), (0.0, 40.0, 0.0))
    hole = ((15.0, 15.0, 0.0), (25.0, 15.0, 0.0), (25.0, 25.0, 0.0), (15.0, 25.0, 0.0))

    result = _triangulate_preview_face_points(outer, (hole,))

    assert result is not None
    vertices, faces = result
    assert len(vertices) >= 3
    assert len(faces) % 4 == 0
    # No rendered triangle should put its centroid inside the hole.  This catches
    # the old visual stacking bug where the outer rectangle was filled as a solid
    # sheet above the circular/square inner region.
    for offset in range(0, len(faces), 4):
        assert faces[offset] == 3
        tri = [vertices[faces[offset + 1]], vertices[faces[offset + 2]], vertices[faces[offset + 3]]]
        cx = sum(point[0] for point in tri) / 3.0
        cy = sum(point[1] for point in tri) / 3.0
        assert not (15.0 < cx < 25.0 and 15.0 < cy < 25.0)

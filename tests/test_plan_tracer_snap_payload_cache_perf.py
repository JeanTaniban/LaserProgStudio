# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.application.planar_tool_snap import PlanarToolSnapLayer
from laserprog_studio.planar_tools import (
    PlanTraceAddKind,
    PlanTraceElement,
    PlanarPolygonDraft,
    compile_planar_snap_cache,
    make_locked_plane,
    snap_plane_point,
    PlanarToolConfig,
)
from laserprog_studio.state.planar_tool_state import PlanarToolState


class _SnapHarness(PlanarToolSnapLayer):
    def __init__(self, payload: PlanarPolygonDraft):
        self.state = PlanarToolState()
        self.state.payload = payload
        self.state.scene_snap_anchor_cache = ((500.0, 1000.0),)
        self.state.scene_snap_edge_cache = (((0.0, 0.0), (1000.0, 0.0)),)
        self.state.scene_snap_compiled_cache = compile_planar_snap_cache(
            self.state.scene_snap_anchor_cache,
            self.state.scene_snap_edge_cache,
        )
        self.owner = SimpleNamespace()


def test_plan_tracer_local_snap_points_are_compiled_once_per_geometry_change(monkeypatch):
    draft = PlanarPolygonDraft(make_locked_plane("top"))
    draft.elements.extend(
        [
            PlanTraceElement(PlanTraceAddKind.LINE, [(0.0, 0.0), (25.0, 0.0)]),
            PlanTraceElement(PlanTraceAddKind.CIRCLE, [(50.0, 50.0), (55.0, 50.0)]),
        ]
    )
    harness = _SnapHarness(draft)

    calls = {"count": 0}
    original = PlanarPolygonDraft.snap_anchor_points

    def counted(self, *args, **kwargs):
        calls["count"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PlanarPolygonDraft, "snap_anchor_points", counted)

    for _ in range(40):
        cache, extra_points, extra_edges = harness._compiled_payload_snap_cache()
        assert cache is not None
        assert extra_points == ()
        assert extra_edges == ()

    assert calls["count"] == 1

    draft.elements[0].points[1] = (30.0, 0.0)
    cache, _, _ = harness._compiled_payload_snap_cache()
    assert cache is not None
    assert calls["count"] == 2


def test_compiled_plan_tracer_cache_keeps_far_alignment_without_resampling():
    draft = PlanarPolygonDraft(make_locked_plane("top"))
    draft.elements.append(PlanTraceElement(PlanTraceAddKind.LINE, [(10.0, 0.0), (10.0, 20.0)]))
    harness = _SnapHarness(draft)
    cache, _, _ = harness._compiled_payload_snap_cache()

    snapped, label = snap_plane_point(
        (500.4, 12.0),
        PlanarToolConfig(grid_snap_enabled=False, smart_snap_enabled=True, smart_snap_tolerance=1.0, smart_snap_priority=True),
        compiled_cache=cache,
    )

    assert snapped == (500.0, 12.0)
    assert label == "smart U"


def test_compiled_edge_grid_limits_dense_edge_distance_checks(monkeypatch):
    import laserprog_studio.planar_tools.pointer as pointer

    segments = [((0.0, float(i) * 10.0), (100.0, float(i) * 10.0)) for i in range(2500)]
    cache = compile_planar_snap_cache((), segments)
    calls = {"count": 0}
    original = pointer._nearest_point_on_compiled_segment

    def counted(point, edge):
        calls["count"] += 1
        return original(point, edge)

    monkeypatch.setattr(pointer, "_nearest_point_on_compiled_segment", counted)
    hit = cache.nearest_edge(50.0, 1230.4, 1.0)

    assert hit is not None
    assert calls["count"] < 120


def test_compiled_edge_grid_preserves_very_long_edge_snap():
    cache = compile_planar_snap_cache((), [((0.0, 0.0), (100000.0, 0.0))])
    hit = cache.nearest_edge(50000.0, 0.4, 1.0)
    assert hit is not None
    assert round(hit[1], 3) == 50000.0
    assert round(hit[2], 3) == 0.0

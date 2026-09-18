from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.snap.providers import snap_targets_to_results
from laserprog_studio.tool_core.snap.types import SnapKind, SnapSource, SnapTarget


def test_pass305_segment_snap_uses_screen_parameter_for_world_point() -> None:
    """Edge snap must not project the locked-plane cursor onto the 3D edge.

    In Plan Tracer 2D the candidate world position is on the locked drawing
    plane.  A visible scene edge can be screen-near while not being 3D-near to
    that candidate.  The accepted edge snap is therefore screen-space; the world
    snap point must use the same screen-space segment parameter.
    """

    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))

    target = SnapTarget.segment(
        "mesh.edge.diagonal",
        (0.0, 0.0, 100.0),
        (100.0, 0.0, 100.0),
        source=SnapSource.MESH_EDGE,
        radius_px=8.0,
        priority=10,
        metadata={
            "snap_start_screen": (0.0, 0.0),
            "snap_end_screen": (200.0, 0.0),
        },
    )

    # The 3D closest-point parameter is 0.0 because the locked-plan candidate is
    # at x=0, but the screen cursor lies at 75% of the displayed edge.
    results = snap_targets_to_results((target,), (0.0, 999.0, 0.0), (150.0, 0.0), ctx)
    edge = next(result for result in results if result.kind == SnapKind.EDGE)

    assert edge.position == (75.0, 0.0, 100.0)
    assert edge.metadata["snap_segment_screen_t"] == 0.75
    assert ctx.profiler.gauges["snap.segment.last_source_id"] == "mesh.edge.diagonal"
    assert ctx.profiler.gauges["snap.segment.last_screen_t"] == 0.75
    assert ctx.profiler.gauges["snap.segment.last_world_t"] == 0.0


def test_pass305_segment_snap_keeps_world_projection_without_screen_cache() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))

    target = SnapTarget.segment(
        "mesh.edge.no_cache",
        (0.0, 0.0, 0.0),
        (100.0, 0.0, 0.0),
        source=SnapSource.MESH_EDGE,
        radius_px=8.0,
        priority=10,
    )

    results = snap_targets_to_results((target,), (25.0, 10.0, 0.0), (25.0, 0.0), ctx)
    edge = next(result for result in results if result.kind == SnapKind.EDGE)

    assert edge.position == (25.0, 0.0, 0.0)
    assert "snap_segment_screen_t" not in edge.metadata

from __future__ import annotations

import math

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tooling.smart_surface_selection_test_tool import SmartSurfaceSelectionTestCreatorTool


def _cube() -> WorkMesh:
    vertices = [
        (-1.0, -1.0, -1.0), (1.0, -1.0, -1.0), (1.0, 1.0, -1.0), (-1.0, 1.0, -1.0),
        (-1.0, -1.0, 1.0), (1.0, -1.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, 1.0),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    return WorkMesh("Cube", vertices, triangles)


def _curved_strip(segments: int = 48) -> WorkMesh:
    vertices = []
    for index in range(segments + 1):
        angle = math.radians(-35.0 + 70.0 * index / segments)
        for z in (0.0, 1.0):
            vertices.append((8.0 * math.sin(angle), z, 8.0 * math.cos(angle)))
    triangles = []
    for index in range(segments):
        a = 2 * index
        b = a + 2
        triangles.extend(((a, b, b + 1), (a, b + 1, a + 1)))
    return WorkMesh("Curved strip", vertices, triangles)


def test_auto_uses_one_incremental_accessibility_field() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_curved_strip(), object_id="strip")
    events: list[tuple[str, dict]] = []
    result = surface_selection.auto_surface_region(snapshot, 0, diagnostics=lambda stage, payload: events.append((stage, payload)))
    assert result.automatic
    assert len(events) == 1
    stage, payload = events[0]
    assert stage == "auto.solve"
    assert payload["incremental"] is True
    assert payload["level_count"] == 40
    assert len(payload["levels"]) == 40
    assert payload["field_crossing_evaluations"] > 0
    assert payload["field_crossing_evaluations"] < 40 * len(snapshot.triangles) * 3


def test_progressive_cache_reuses_exact_and_logical_regions() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    cache = surface_selection.SurfaceSelectionCache(logical_reuse=True)
    first = surface_selection.auto_surface_region(snapshot, 0, cache=cache)
    assert set(first.face_indices) == {0, 1}

    events: list[tuple[str, dict]] = []
    repeated = surface_selection.auto_surface_region(snapshot, 0, cache=cache, diagnostics=lambda stage, payload: events.append((stage, payload)))
    assert repeated is first
    assert events[-1][1]["cache_kind"] == "exact"

    events.clear()
    adjacent = surface_selection.auto_surface_region(snapshot, 1, cache=cache, diagnostics=lambda stage, payload: events.append((stage, payload)))
    assert set(adjacent.face_indices) == {0, 1}
    assert adjacent.seed_face == 1
    # Both triangles touch the logical boundary, so v152 deliberately computes
    # the adjacent seed exactly rather than applying a speculative region hit.
    assert events[-1][1]["cache_kind"] == "miss"
    assert cache.result_hits == 1
    assert cache.logical_hits == 0


def test_manual_slider_reuses_the_seed_accessibility_field() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_curved_strip(), object_id="strip")
    cache = surface_selection.SurfaceSelectionCache(logical_reuse=False)
    first_events: list[tuple[str, dict]] = []
    second_events: list[tuple[str, dict]] = []
    narrow = surface_selection.select_surface_region(
        snapshot, 0, 0.10, cache=cache, diagnostics=lambda stage, payload: first_events.append((stage, payload))
    )
    broad = surface_selection.select_surface_region(
        snapshot, 0, 0.75, cache=cache, diagnostics=lambda stage, payload: second_events.append((stage, payload))
    )
    assert narrow.metrics.face_count < broad.metrics.face_count
    assert first_events[-1][1]["field_cache_hit"] is False
    assert second_events[-1][1]["field_cache_hit"] is True


def test_geometry_signature_changes_when_geometry_changes_without_count_changes() -> None:
    mesh = _cube()
    first = surface_selection.SurfaceMeshSnapshot.from_mesh(mesh, object_id="cube")
    mesh.vertices[0] = (-1.25, -1.0, -1.0)
    second = surface_selection.SurfaceMeshSnapshot.from_mesh(mesh, object_id="cube")
    assert first.geometry_signature != second.geometry_signature


def test_test_tool_exposes_progressive_cache_controls(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    tool = SmartSurfaceSelectionTestCreatorTool()
    ctx = ToolContext()
    tool.on_open(ctx)
    try:
        panel = ctx.inspector.panel
        assert panel is not None
        assert {"reuse_logical_cache", "cache_stats"}.issubset(panel.field_ids())
        assert tool._session.cache.logical_reuse is False
    finally:
        tool.on_close(ctx)

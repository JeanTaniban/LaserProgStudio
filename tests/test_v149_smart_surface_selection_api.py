from __future__ import annotations

import math

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_core.context import ToolContext
from laserprog_studio.tooling.ids import TOOL_SMART_SURFACE_SELECTION_TEST
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.toolbar_catalog import get_toolbar_item_spec


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


def _curved_strip(segments: int = 12) -> WorkMesh:
    vertices = []
    for index in range(segments + 1):
        angle = math.radians(-24.0 + 48.0 * index / segments)
        for z in (0.0, 1.0):
            vertices.append((6.0 * math.sin(angle), z, 6.0 * math.cos(angle)))
    triangles = []
    for index in range(segments):
        a = 2 * index
        b = a + 2
        triangles.extend(((a, b, b + 1), (a, b + 1, a + 1)))
    return WorkMesh("Curved strip", vertices, triangles)


def test_public_api_selects_one_logical_cube_side() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_cube(), object_id="cube")
    result = surface_selection.auto_surface_region(snapshot, 0)
    assert result.automatic
    assert set(result.face_indices) == {0, 1}
    assert len(result.boundary_edges) == 4
    assert result.confidence >= 0.5


def test_manual_continuity_grows_over_a_smooth_curved_strip() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_curved_strip(), object_id="strip")
    strict = surface_selection.select_surface_region(snapshot, 0, 0.05)
    broad = surface_selection.select_surface_region(snapshot, 0, 0.80)
    assert strict.metrics.face_count < broad.metrics.face_count
    assert broad.metrics.face_count == len(snapshot.triangles)
    assert broad.metrics.maximum_local_angle_degrees < 10.0


def test_session_constraints_can_include_then_exclude_faces() -> None:
    snapshot = surface_selection.SurfaceMeshSnapshot.from_mesh(_curved_strip(), object_id="strip")
    session = surface_selection.SurfaceSelectionSession(tolerance=0.05, automatic=False)
    session.bind(snapshot, 0)
    before = set(session.result.face_indices)
    session.require(len(snapshot.triangles) - 1)
    after_include = set(session.result.face_indices)
    assert len(after_include) > len(before)
    assert len(snapshot.triangles) - 1 in after_include
    session.exclude(4)
    assert 4 not in set(session.result.face_indices)


def test_test_tool_is_registered_and_builds_headless_panel(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    spec = get_tool_spec(TOOL_SMART_SURFACE_SELECTION_TEST)
    assert spec is not None
    assert spec.open_without_initial_selection
    assert get_toolbar_item_spec("tool:smart_surface_selection_test") is not None
    runtime = get_studio_tool(TOOL_SMART_SURFACE_SELECTION_TEST)
    ctx = ToolContext()
    runtime.creator.on_open(ctx)
    try:
        panel = ctx.inspector.panel
        assert panel is not None
        assert panel.id == "smart_surface_selection_test.panel"
        assert {"automatic", "tolerance", "profile", "face_count", "confidence"}.issubset(set(panel.field_ids()))
    finally:
        runtime.creator.on_close(ctx)

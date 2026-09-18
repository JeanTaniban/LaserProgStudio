from __future__ import annotations

import math

import pytest

from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.auto_faces import discover_auto_face_loops
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.geometry_overlay import (
    CLOTH_GEOMETRY_ACTION_PREFIX,
    CLOTH_GEOMETRY_WINDOW_ID,
    ClothGeometryTraceOverlay,
)
from laserprog_studio.tooling.cloth.mesh_builder import build_cloth_surface_mesh
from laserprog_studio.tooling.cloth.models import ClothDocument, ClothEditMode
from laserprog_studio.tooling.cloth.selection import delete_cloth_selection
from laserprog_studio.tooling.cloth.topology import patch_frame, sample_patch_boundary
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _annular_sector_document() -> tuple[ClothDocument, str, tuple[tuple[float, float, float], ...]]:
    document = ClothDocument()
    outer_radius = 10.0
    inner_radius = 6.0
    outer_start = document.add_point((outer_radius * math.cos(math.radians(150)), outer_radius * math.sin(math.radians(150)), 0.0))
    outer_end = document.add_point((outer_radius * math.cos(math.radians(30)), outer_radius * math.sin(math.radians(30)), 0.0))
    outer_control = document.add_point((0.0, outer_radius, 0.0))
    inner_end = document.add_point((inner_radius * math.cos(math.radians(30)), inner_radius * math.sin(math.radians(30)), 0.0))
    inner_start = document.add_point((inner_radius * math.cos(math.radians(150)), inner_radius * math.sin(math.radians(150)), 0.0))
    inner_control = document.add_point((0.0, inner_radius, 0.0))
    outer = document.add_arc(outer_start.id, outer_end.id, outer_control.id)
    right = document.add_line(outer_end.id, inner_end.id)
    inner = document.add_arc(inner_end.id, inner_start.id, inner_control.id)
    left = document.add_line(inner_start.id, outer_start.id)
    outcome = ClothDrawingController(document).create_patch_from_curves((outer.id, right.id, inner.id, left.id))
    assert outcome.committed and outcome.created_patch_id is not None
    return document, outcome.created_patch_id, (outer_control.position, inner_control.position)


def test_panel_between_two_arcs_uses_stable_adaptive_boundary_and_triangulation() -> None:
    document, patch_id, controls = _annular_sector_document()
    boundary = sample_patch_boundary(document, patch_id, arc_segments=8, chord_tolerance_mm=0.02)
    assert len(boundary) > 20
    assert all(any(math.dist(point, control) <= 1.0e-9 for point in boundary) for control in controls)

    built = build_cloth_surface_mesh(document, arc_segments=8)
    assert built.success, built.issues
    assert built.mesh is not None
    assert len(built.mesh.triangles) == len(built.mesh.vertices) - 2

    frame = patch_frame(document, patch_id)
    assert frame is not None
    from shapely.geometry import Point, Polygon

    polygon = Polygon([frame.project(point) for point in boundary])
    assert polygon.is_valid
    for triangle in built.mesh.triangles:
        centroid = tuple(sum(built.mesh.vertices[index][axis] for index in triangle) / 3.0 for axis in range(3))
        assert polygon.covers(Point(frame.project(centroid)))


def test_auto_face_stops_when_two_comparable_arc_regions_are_possible() -> None:
    document = ClothDocument()
    start = document.add_point((-10.0, 0.0, 0.0))
    end = document.add_point((10.0, 0.0, 0.0))
    upper_control = document.add_point((0.0, 5.0, 0.0))
    lower_control = document.add_point((0.0, -5.0, 0.0))
    document.add_arc(start.id, end.id, upper_control.id)
    document.add_arc(start.id, end.id, lower_control.id)
    trigger = document.add_line(start.id, end.id)

    plan = discover_auto_face_loops(document, (trigger.id,))

    assert not plan.found
    assert "Several valid Cloth faces" in plan.message


def test_delete_face_keeps_boundaries_and_unrelated_construction_point() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    outcome = drawing.create_surface_from_positions(((0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)))
    assert outcome.committed and outcome.created_patch_id
    construction = document.add_point((100.0, 100.0, 0.0), metadata={"construction": True})
    curve_ids = set(document.curves)

    result = delete_cloth_selection(document, patch_ids=(outcome.created_patch_id,))

    assert result.changed and result.patches == 1
    assert set(document.curves) == curve_ids
    assert construction.id in document.points


def _context() -> ToolContext:
    ctx = ToolContext()
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    return ctx


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float, *, shift: bool = False) -> None:
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"}) if shift else frozenset())
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT, modifiers=frozenset({"shift"}) if shift else frozenset())
    tool.on_event(press, ctx)
    assert tool.on_event(release, ctx)


def test_modify_selects_and_deletes_a_cloth_face() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    _click(tool, ctx, 0, 0)
    _click(tool, ctx, 100, 0)
    _click(tool, ctx, 100, 100)
    _click(tool, ctx, 0, 100)
    _click(tool, ctx, 0, 0)
    assert len(tool.session.document.patches) == 1

    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_modify", ctx)
    _click(tool, ctx, 50, 50)
    assert len(tool.session.selected_patch_ids) == 1

    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="delete"), ctx)
    assert not tool.session.document.patches
    assert tool.session.document.curves
    assert tool.session.edit_mode is ClothEditMode.MODIFY


def _parallel_arc_strip_snapshot(*, samples: int = 9, reverse_second_geometry: bool = False):
    from laserprog_studio.tooling.cloth.geometry_trace import SourceEdgeSelection, SourceMeshSnapshot

    first = [
        (20.0 * math.cos(math.radians(150.0 - 120.0 * index / (samples - 1))),
         20.0 * math.sin(math.radians(150.0 - 120.0 * index / (samples - 1))),
         0.0)
        for index in range(samples)
    ]
    second_geometry = [(x, y, 8.0) for x, y, _z in first]
    if reverse_second_geometry:
        second_geometry.reverse()
    vertices = tuple((*first, *second_geometry))
    triangles = []
    for index in range(samples - 1):
        a0, a1 = index, index + 1
        b0, b1 = samples + index, samples + index + 1
        triangles.extend(((a0, a1, b1), (a0, b1, b0)))
    snapshot = SourceMeshSnapshot("parallel-arcs", 0, "Parallel arcs", vertices, tuple(triangles))
    selections = tuple(
        SourceEdgeSelection(snapshot.object_id, edge)
        for edge in (
            *((index, index + 1) for index in range(samples - 1)),
            *((samples + index, samples + index + 1) for index in range(samples - 1)),
        )
    )
    return snapshot, selections, tuple(first), tuple((x, y, 8.0) for x, y, _z in first)


def test_two_parallel_selected_arc_chains_plan_one_untwisted_ruled_strip() -> None:
    from laserprog_studio.tooling.cloth.geometry_trace import plan_ruled_strip_from_selection

    snapshot, selections, expected_first, expected_second = _parallel_arc_strip_snapshot(reverse_second_geometry=True)
    plan = plan_ruled_strip_from_selection({snapshot.object_id: snapshot}, selections)

    assert plan is not None
    assert plan.segment_count == len(expected_first) - 1
    assert all(math.dist(value, expected) <= 1.0e-9 for value, expected in zip(plan.rail_a, expected_first))
    assert all(math.dist(value, expected) <= 1.0e-9 for value, expected in zip(plan.rail_b, expected_second))
    assert abs(plan.mean_width_mm - 8.0) <= 1.0e-9
    assert abs(plan.minimum_width_mm - 8.0) <= 1.0e-9
    assert abs(plan.maximum_width_mm - 8.0) <= 1.0e-9


def test_mesh_trace_builds_regular_cover_between_two_parallel_arc_rails() -> None:
    from laserprog_studio.tooling.cloth.geometry_trace import ClothGeometryTraceController

    snapshot, selections, _first, _second = _parallel_arc_strip_snapshot(samples=11)
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    controller.selected_edges = selections
    document = ClothDocument()

    outcome = controller.create(document, ClothDrawingController(document))

    assert outcome.committed, outcome.message
    assert len(document.patches) == 10
    assert all(len(patch.outer_curve_ids) == 4 for patch in document.patches.values())
    assert {patch.metadata.get("cloth_surface_kind") for patch in document.patches.values()} == {"ruled_strip"}
    assert len({patch.metadata.get("cloth_ruled_strip_id") for patch in document.patches.values()}) == 1
    assert len(document.folds) == 9
    built = build_cloth_surface_mesh(document)
    assert built.success, built.issues
    assert built.mesh is not None
    assert len(built.mesh.triangles) == 20
    from laserprog_studio.tooling.cloth.flattening import flatten_cloth_document

    flattened = flatten_cloth_document(document)
    assert flattened.success, flattened.issues
    flat_mesh = build_cloth_surface_mesh(document, flattened=flattened)
    assert flat_mesh.success, flat_mesh.issues
    assert flat_mesh.mesh is not None
    assert len(flat_mesh.mesh.triangles) == 20
    assert controller.selection_count == 0


def test_ruled_strip_prediction_requires_exactly_two_open_non_branching_chains() -> None:
    from laserprog_studio.tooling.cloth.geometry_trace import SourceEdgeSelection, SourceMeshSnapshot, plan_ruled_strip_from_selection

    snapshot, selections, _first, _second = _parallel_arc_strip_snapshot(samples=6)
    assert plan_ruled_strip_from_selection({snapshot.object_id: snapshot}, selections) is not None
    assert plan_ruled_strip_from_selection({snapshot.object_id: snapshot}, selections[:5]) is None

    branched = SourceMeshSnapshot(
        "branch",
        0,
        "Branch",
        ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 1.0, 0.0),
         (0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (2.0, 0.0, 5.0)),
        ((0, 1, 3), (1, 2, 3), (4, 5, 6)),
    )
    bad = tuple(
        SourceEdgeSelection("branch", edge)
        for edge in ((0, 1), (1, 2), (1, 3), (4, 5), (5, 6))
    )
    assert plan_ruled_strip_from_selection({"branch": branched}, bad) is None


def test_smart_mesh_overlay_enables_cover_only_for_two_compatible_rails() -> None:
    from laserprog_studio.tooling.cloth.geometry_trace import ClothGeometryTraceController

    snapshot, selections, _first, _second = _parallel_arc_strip_snapshot(samples=7)
    controller = ClothGeometryTraceController(pick_kind="edge")
    controller.snapshots[snapshot.object_id] = snapshot
    overlay = ClothGeometryTraceOverlay("cloth", controller)
    ctx = ToolContext()

    controller.selected_edges = selections[:6]
    overlay.sync(ctx)
    buttons = {button.id: button for button in ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID).buttons}
    assert not buttons[f"{CLOTH_GEOMETRY_ACTION_PREFIX}create_bridge"].enabled

    controller.selected_edges = selections
    controller.revision += 1
    overlay.sync(ctx)
    buttons = {button.id: button for button in ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID).buttons}
    assert buttons[f"{CLOTH_GEOMETRY_ACTION_PREFIX}create_bridge"].enabled
    window = ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID)
    status = next(field.value for field in window.fields if field.id == "cloth.geometry.status")
    assert "Two compatible rails" in status


def test_cover_action_creates_strip_clears_mesh_trace_and_returns_to_modify() -> None:
    snapshot, selections, _first, _second = _parallel_arc_strip_snapshot(samples=6)
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_mesh_trace", ctx)
    tool.geometry_trace.snapshots[snapshot.object_id] = snapshot
    tool.geometry_trace.selected_edges = selections
    tool.geometry_trace.revision += 1

    tool.on_overlay_button_clicked(f"{CLOTH_GEOMETRY_ACTION_PREFIX}create_bridge", ctx)

    assert tool.session.edit_mode is ClothEditMode.MODIFY
    assert len(tool.session.document.patches) == 5
    assert tool.geometry_trace.selection_count == 0
    geometry_window = ctx.overlay.window(CLOTH_GEOMETRY_WINDOW_ID)
    assert geometry_window is None or not geometry_window.visible


def test_cover_pairs_two_separate_plan_tracer_meshes_with_different_arc_tessellation() -> None:
    from laserprog_studio.tooling.cloth.geometry_trace import SourceEdgeSelection, SourceMeshSnapshot, plan_ruled_strip_from_selection

    def rail_snapshot(object_id: str, samples: int, z: float):
        rail = tuple(
            (
                25.0 * math.cos(math.radians(145.0 - 110.0 * index / (samples - 1))),
                25.0 * math.sin(math.radians(145.0 - 110.0 * index / (samples - 1))),
                z,
            )
            for index in range(samples)
        )
        support = (0.0, 0.0, z - 3.0)
        snapshot = SourceMeshSnapshot(
            object_id,
            None,
            object_id,
            (*rail, support),
            tuple((index, index + 1, samples) for index in range(samples - 1)),
        )
        selected = tuple(SourceEdgeSelection(object_id, (index, index + 1)) for index in range(samples - 1))
        return snapshot, selected

    first, first_selection = rail_snapshot("plan-tracer-arc-a", 7, 0.0)
    second, second_selection = rail_snapshot("plan-tracer-arc-b", 15, 8.0)
    plan = plan_ruled_strip_from_selection(
        {first.object_id: first, second.object_id: second},
        (*first_selection, *second_selection),
    )

    assert plan is not None
    assert plan.segment_count >= 14
    assert math.dist(plan.rail_a[0], plan.rail_b[0]) == pytest.approx(8.0, abs=1.0e-6)
    assert math.dist(plan.rail_a[-1], plan.rail_b[-1]) == pytest.approx(8.0, abs=1.0e-6)
    assert plan.mean_width_mm == pytest.approx(8.0, abs=0.2)

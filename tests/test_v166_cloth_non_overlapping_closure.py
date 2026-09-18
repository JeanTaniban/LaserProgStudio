from __future__ import annotations

import math

from shapely.geometry import Polygon
from shapely.ops import unary_union

from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.join_faces import (
    _build_closure_cell_validator,
    analyze_textile_close_groups,
    commit_join_proposal,
)
from laserprog_studio.tooling.cloth.mesh_builder import build_cloth_surface_mesh
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan


def _u_panel(dx: float = 0.0, z: float = 0.0):
    return (
        (dx + 0.0, 100.0, z), (dx + 0.0, 20.0, z), (dx + 2.0, 10.0, z),
        (dx + 8.0, 2.0, z), (dx + 20.0, 0.0, z), (dx + 32.0, 2.0, z),
        (dx + 38.0, 10.0, z), (dx + 40.0, 20.0, z), (dx + 40.0, 100.0, z),
        (dx + 34.0, 100.0, z), (dx + 34.0, 22.0, z), (dx + 32.0, 14.0, z),
        (dx + 27.0, 8.0, z), (dx + 20.0, 6.0, z), (dx + 13.0, 8.0, z),
        (dx + 8.0, 14.0, z), (dx + 6.0, 22.0, z), (dx + 6.0, 100.0, z),
    )


def _subdivided_rectangle(x0: float, x1: float, y0: float, y1: float, *, steps: int = 12):
    points = []
    for index in range(steps):
        factor = index / steps
        points.append((x0 + (x1 - x0) * factor, y0, 0.0))
    for index in range(steps):
        factor = index / steps
        points.append((x1, y0 + (y1 - y0) * factor, 0.0))
    for index in range(steps):
        factor = index / steps
        points.append((x1 - (x1 - x0) * factor, y1, 0.0))
    for index in range(steps):
        factor = index / steps
        points.append((x0, y1 - (y1 - y0) * factor, 0.0))
    return tuple(points)


def _triangle_polygon(triangle):
    return Polygon([(point[0], point[1]) for point in triangle])


def _preview_overlap_area(proposal, source_polygons) -> float:
    source = unary_union(source_polygons)
    return sum(_triangle_polygon(triangle).intersection(source).area for triangle in proposal.triangle_preview)


def test_lateral_u_closure_never_covers_the_selected_source_panels() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first_points = _u_panel(0.0)
    second_points = _u_panel(60.0)
    first = drawing.create_surface_from_positions(first_points)
    second = drawing.create_surface_from_positions(second_points)
    assert first.committed and second.committed

    proposals = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )

    assert proposals
    primary = proposals[0]
    assert primary.id == "close_facing_edge"
    assert _preview_overlap_area(
        primary,
        (Polygon([(x, y) for x, y, _z in first_points]), Polygon([(x, y) for x, y, _z in second_points])),
    ) <= 1.0e-8
    pair = primary.pairs[0]
    assert pair.first_rail == ((40.0, 20.0, 0.0), (40.0, 100.0, 0.0))
    assert pair.second_rail == ((60.0, 20.0, 0.0), (60.0, 100.0, 0.0))


def test_facing_chain_reaches_both_real_top_endpoints_without_a_missing_piece() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_subdivided_rectangle(0.0, 10.0, 0.0, 100.0))
    second = drawing.create_surface_from_positions(_subdivided_rectangle(30.0, 40.0, 0.0, 100.0))
    assert first.committed and second.committed

    proposal = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )[0]

    pair = proposal.pairs[0]
    assert max(point[1] for point in pair.first_rail) == 100.0
    assert max(point[1] for point in pair.second_rail) == 100.0
    assert min(point[1] for point in pair.first_rail) == 0.0
    assert min(point[1] for point in pair.second_rail) == 0.0
    source = (
        Polygon([(point[0], point[1]) for point in _subdivided_rectangle(0.0, 10.0, 0.0, 100.0)]),
        Polygon([(point[0], point[1]) for point in _subdivided_rectangle(30.0, 40.0, 0.0, 100.0)]),
    )
    assert _preview_overlap_area(proposal, source) <= 1.0e-8


def test_committed_lateral_closure_keeps_created_triangles_outside_source_interiors() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first_points = _u_panel(0.0)
    second_points = _u_panel(60.0)
    first = drawing.create_surface_from_positions(first_points)
    second = drawing.create_surface_from_positions(second_points)
    assert first.committed and second.committed
    proposal = analyze_textile_close_groups(document, ((first.created_patch_id,), (second.created_patch_id,)))[0]
    before = set(document.patches)

    outcome = commit_join_proposal(document, proposal)

    assert outcome.committed, outcome.message
    created = set(document.patches) - before
    assert created
    built = build_cloth_surface_mesh(document, name="closure validation")
    assert built.mesh is not None, built.issues
    source = unary_union(
        (
            Polygon([(x, y) for x, y, _z in first_points]),
            Polygon([(x, y) for x, y, _z in second_points]),
        )
    )
    overlap = 0.0
    for patch_id in created:
        start, end = built.patch_triangle_ranges[patch_id]
        for triangle_index in range(start, end):
            indices = built.mesh.triangles[triangle_index]
            triangle = tuple(built.mesh.vertices[index] for index in indices)
            overlap += _triangle_polygon(triangle).intersection(source).area
    assert overlap <= 1.0e-8


def test_parallel_offset_u_panels_still_receive_a_complete_closed_sidewall() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_u_panel(0.0, 0.0))
    second = drawing.create_surface_from_positions(_u_panel(0.0, 25.0))
    assert first.committed and second.committed

    proposal = analyze_textile_close_groups(document, ((first.created_patch_id,), (second.created_patch_id,)))[0]

    assert proposal.id == "close_complete_boundary"
    assert sum(pair.coverage for pair in proposal.pairs) >= 0.95
    assert all(math.dist(pair.first_rail[0], pair.first_rail[-1]) <= 1.0e-7 for pair in proposal.pairs)
    assert all(math.dist(pair.second_rail[0], pair.second_rail[-1]) <= 1.0e-7 for pair in proposal.pairs)


def test_projected_touching_corner_never_creates_zero_width_closure_cells() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(((0, 0, 0), (30, 0, 0), (30, 30, 0), (0, 30, 0)))
    second = drawing.create_surface_from_positions(((0, 0, 0), (30, 0, 12), (30, 30, 12), (0, 30, 12)))
    assert first.committed and second.committed

    proposals = analyze_textile_close_groups(document, ((first.created_patch_id,), (second.created_patch_id,)))

    # A shared corner makes a complete sidewall ambiguous.  Close must now
    # refuse the proposal instead of silently dropping one cell and leaving a
    # visible gap at the top.
    assert proposals == ()


def test_existing_third_textile_blocks_a_partial_close_instead_of_being_covered() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_subdivided_rectangle(0.0, 10.0, 0.0, 100.0))
    second = drawing.create_surface_from_positions(_subdivided_rectangle(30.0, 40.0, 0.0, 100.0))
    blocker = drawing.create_surface_from_positions(((10.0, 35.0, 0.0), (30.0, 35.0, 0.0), (30.0, 65.0, 0.0), (10.0, 65.0, 0.0)))
    assert first.committed and second.committed and blocker.committed

    proposals = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )

    # Close must not silently return two partial strips around an existing
    # textile obstacle; that would leave an incomplete logical face.
    assert proposals == ()


def test_committed_collision_free_closure_remains_flattenable_and_apply_ready() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_u_panel(0.0))
    second = drawing.create_surface_from_positions(_u_panel(60.0))
    assert first.committed and second.committed

    proposal = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )[0]
    outcome = commit_join_proposal(document, proposal)
    assert outcome.committed, outcome.message

    plan = build_cloth_apply_plan(document, name="Collision-free U closure")

    assert plan.ready, plan.issues
    assert plan.flattening is not None and plan.flattening.success
    assert plan.folded_mesh is not None
    assert plan.flat_mesh is not None
    assert plan.issues == ()


def test_corridor_validator_checks_the_whole_cell_not_only_its_middle_connector() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    second = drawing.create_surface_from_positions(((30, 0, 0), (40, 0, 0), (40, 10, 0), (30, 10, 0)))
    assert first.committed and second.committed
    validator, _metadata = _build_closure_cell_validator(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )
    assert validator is not None

    # The middle cross-section (x=10..12.5 at y=5) is free, but the upper
    # portion folds back through the first source panel.  A midpoint-only test
    # used to accept this twisted cell.
    assert not validator(
        "group:0",
        "group:1",
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (5.0, 10.0, 0.0),
        (20.0, 0.0, 0.0),
    )


def test_tilted_reversed_u_groups_keep_a_complete_collision_free_sidewall() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first_points = _u_panel(0.0, 0.0)
    angle = math.radians(12.0)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    second_points = tuple(
        reversed(
            tuple(
                (
                    cosine * x + 2.0,
                    y + 3.0,
                    -sine * x + 25.0,
                )
                for x, y, _z in first_points
            )
        )
    )
    first = drawing.create_surface_from_positions(first_points)
    second = drawing.create_surface_from_positions(second_points)
    assert first.committed and second.committed

    proposals = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )

    assert proposals
    primary = proposals[0]
    assert primary.id == "close_complete_boundary"
    assert min(pair.coverage for pair in primary.pairs) >= 0.98
    assert all(
        math.dist(pair.first_rail[0], pair.first_rail[-1]) <= 1.0e-7
        and math.dist(pair.second_rail[0], pair.second_rail[-1]) <= 1.0e-7
        for pair in primary.pairs
    )
    validator, _metadata = _build_closure_cell_validator(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )
    assert validator is not None
    assert all(
        validator(
            pair.first_patch_id,
            pair.second_patch_id,
            pair.first_rail[index],
            pair.first_rail[index + 1],
            pair.second_rail[index + 1],
            pair.second_rail[index],
        )
        for pair in primary.pairs
        for index in range(pair.segment_count)
    )

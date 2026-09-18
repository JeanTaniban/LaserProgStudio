from __future__ import annotations

import math

from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.join_faces import analyze_textile_close_groups, commit_join_proposal
from laserprog_studio.tooling.cloth.models import ClothDocument


def _coverage(proposal) -> float:
    return min(1.0, sum(pair.coverage for pair in proposal.pairs))


def _triangle_area(triangle) -> float:
    a, b, c = triangle
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    cross = (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )
    return 0.5 * math.sqrt(sum(value * value for value in cross))


def _u_centerline(z: float = 0.0) -> tuple[tuple[float, float, float], ...]:
    values: list[tuple[float, float, float]] = []
    for index in range(7):
        values.append((0.0, 100.0 - index * 10.0, z))
    for index in range(1, 13):
        angle = math.pi - math.pi * index / 12.0
        values.append((20.0 + 20.0 * math.cos(angle), 40.0 - 20.0 * math.sin(angle), z))
    for index in range(1, 7):
        values.append((40.0, 40.0 + index * 10.0, z))
    return tuple(values)


def _offset_rails(centerline, half_width: float = 2.0):
    first = []
    second = []
    for index, point in enumerate(centerline):
        previous = centerline[max(0, index - 1)]
        following = centerline[min(len(centerline) - 1, index + 1)]
        tangent_x = following[0] - previous[0]
        tangent_y = following[1] - previous[1]
        length = max(1.0e-9, math.hypot(tangent_x, tangent_y))
        normal_x = -tangent_y / length
        normal_y = tangent_x / length
        first.append((point[0] + normal_x * half_width, point[1] + normal_y * half_width, point[2]))
        second.append((point[0] - normal_x * half_width, point[1] - normal_y * half_width, point[2]))
    return tuple(first), tuple(second)


def _technical_u_group(document: ClothDocument, z: float) -> tuple[str, ...]:
    drawing = ClothDrawingController(document)
    before = set(document.patches)
    first, second = _offset_rails(_u_centerline(z))
    outcome = drawing.create_ruled_strip_from_positions(first, second)
    assert outcome.committed, outcome.message
    return tuple(patch_id for patch_id in document.patches if patch_id not in before)


def _subdivided_rectangle(x0: float, x1: float, y0: float, y1: float, *, z: float = 0.0, steps: int = 12):
    points = []
    for index in range(steps):
        factor = index / steps
        points.append((x0 + (x1 - x0) * factor, y0, z))
    for index in range(steps):
        factor = index / steps
        points.append((x1, y0 + (y1 - y0) * factor, z))
    for index in range(steps):
        factor = index / steps
        points.append((x1 - (x1 - x0) * factor, y1, z))
    for index in range(steps):
        factor = index / steps
        points.append((x0, y1 - (y1 - y0) * factor, z))
    return tuple(points)


def _add_polygon_patch(document: ClothDocument, points, patch_id: str) -> str:
    point_ids = []
    for index, position in enumerate(points):
        point = document.add_point(position, point_id=f"{patch_id}_p{index}")
        point_ids.append(point.id)
    curve_ids = []
    for index, point_id in enumerate(point_ids):
        curve = document.add_line(point_id, point_ids[(index + 1) % len(point_ids)], curve_id=f"{patch_id}_c{index}")
        curve_ids.append(curve.id)
    return document.add_patch(curve_ids, patch_id=patch_id).id


def test_close_parallel_technical_u_groups_covers_the_complete_selected_curvature() -> None:
    document = ClothDocument()
    first_group = _technical_u_group(document, 0.0)
    second_group = _technical_u_group(document, 30.0)

    proposals = analyze_textile_close_groups(document, (first_group, second_group))

    assert proposals
    primary = proposals[0]
    assert primary.id == "close_complete_boundary"
    assert _coverage(primary) >= 0.95
    assert sum(pair.segment_count for pair in primary.pairs) >= 40
    assert len(primary.triangle_preview) >= 80
    assert all(_triangle_area(triangle) > 1.0e-8 for triangle in primary.triangle_preview)
    assert "boundary coverage 100%" in primary.message


def test_close_parallel_technical_u_groups_commits_the_whole_cover() -> None:
    document = ClothDocument()
    first_group = _technical_u_group(document, 0.0)
    second_group = _technical_u_group(document, 30.0)
    proposal = analyze_textile_close_groups(document, (first_group, second_group))[0]
    before = len(document.patches)

    outcome = commit_join_proposal(document, proposal)

    assert outcome.committed, outcome.message
    assert len(document.patches) > before
    assert "connecting textile" in outcome.message


def test_close_segmented_lateral_faces_extends_a_seed_over_the_whole_facing_side() -> None:
    document = ClothDocument()
    first = _add_polygon_patch(document, _subdivided_rectangle(0.0, 10.0, 0.0, 100.0), "left")
    second = _add_polygon_patch(document, _subdivided_rectangle(30.0, 40.0, 0.0, 100.0), "right")

    proposals = analyze_textile_close_groups(document, ((first,), (second,)))

    assert proposals
    primary = proposals[0]
    assert primary.id.startswith("close_facing_chain")
    assert primary.id != "close_local_bridge"
    assert sum(pair.segment_count for pair in primary.pairs) >= 10
    assert _coverage(primary) >= 0.35
    assert max(pair.mean_width_mm for pair in primary.pairs) < 25.0


def test_close_prefers_the_collision_free_facing_edge_for_lateral_u_panels() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    u_shape = (
        (0, 100, 0), (0, 20, 0), (2, 10, 0), (8, 2, 0), (20, 0, 0),
        (32, 2, 0), (38, 10, 0), (40, 20, 0), (40, 100, 0),
        (34, 100, 0), (34, 22, 0), (32, 14, 0), (27, 8, 0), (20, 6, 0),
        (13, 8, 0), (8, 14, 0), (6, 22, 0), (6, 100, 0),
    )
    first = drawing.create_surface_from_positions(u_shape)
    second = drawing.create_surface_from_positions(tuple((x + 60.0, y, z) for x, y, z in u_shape))
    assert first.committed and second.committed

    proposals = analyze_textile_close_groups(document, ((first.created_patch_id,), (second.created_patch_id,)))

    assert proposals[0].id == "close_facing_edge"
    assert proposals[0].pairs[0].first_rail == ((40.0, 20.0, 0.0), (40.0, 100.0, 0.0))
    assert proposals[0].pairs[0].second_rail == ((60.0, 20.0, 0.0), (60.0, 100.0, 0.0))


def test_close_reversed_boundary_winding_keeps_global_correspondence() -> None:
    document = ClothDocument()
    first = _add_polygon_patch(document, _subdivided_rectangle(0, 20, 0, 40, z=0, steps=8), "first")
    second_points = tuple(reversed(_subdivided_rectangle(0, 20, 0, 40, z=25, steps=11)))
    second = _add_polygon_patch(document, second_points, "second")

    proposals = analyze_textile_close_groups(document, ((first,), (second,)))

    assert proposals
    assert proposals[0].id == "close_complete_boundary"
    assert _coverage(proposals[0]) >= 0.90
    assert all(pair.twist_score <= 0.05 for pair in proposals[0].pairs)


def test_close_unequal_boundary_sampling_still_covers_both_faces() -> None:
    document = ClothDocument()
    first = _add_polygon_patch(document, _subdivided_rectangle(0, 30, 0, 60, z=0, steps=4), "coarse")
    second = _add_polygon_patch(document, _subdivided_rectangle(0, 30, 0, 60, z=18, steps=17), "dense")

    proposals = analyze_textile_close_groups(document, ((first,), (second,)))

    assert proposals
    assert _coverage(proposals[0]) >= 0.85
    assert sum(pair.segment_count for pair in proposals[0].pairs) >= 12


def test_close_rejects_an_ambiguous_nonplanar_correspondence_at_a_touching_corner() -> None:
    document = ClothDocument()
    first = _add_polygon_patch(document, ((0, 0, 0), (30, 0, 0), (30, 30, 0), (0, 30, 0)), "first")
    # One corner touches the first loop; the remaining rim is offset in Z.
    second = _add_polygon_patch(document, ((0, 0, 0), (30, 0, 12), (30, 30, 12), (0, 30, 12)), "second")

    proposals = analyze_textile_close_groups(document, ((first,), (second,)))

    assert proposals == ()


def test_close_open_polylines_uses_the_complete_drawn_rails() -> None:
    document = ClothDocument()
    first_ids = [document.add_point((index * 10.0, 0.0, 0.0), point_id=f"a{index}").id for index in range(6)]
    second_ids = [document.add_point((index * 10.0, 20.0, 3.0), point_id=f"b{index}").id for index in range(6)]
    first_curve = document.add_polyline(first_ids, curve_id="rail_a")
    second_curve = document.add_polyline(second_ids, curve_id="rail_b")

    proposals = analyze_textile_close_groups(document, (), (first_curve.id, second_curve.id))

    assert proposals
    assert proposals[0].pairs[0].segment_count >= 7
    assert proposals[0].pairs[0].first_rail[0] == (0.0, 0.0, 0.0)
    assert proposals[0].pairs[0].first_rail[-1] == (50.0, 0.0, 0.0)


def test_close_three_groups_still_builds_a_connected_minimum_graph() -> None:
    document = ClothDocument()
    patch_ids = []
    for index, z in enumerate((0.0, 20.0, 45.0)):
        patch_ids.append(_add_polygon_patch(document, _subdivided_rectangle(0, 20, 0, 30, z=z, steps=6), f"p{index}"))

    proposals = analyze_textile_close_groups(document, tuple((patch_id,) for patch_id in patch_ids))

    assert proposals
    assert len(proposals[0].pairs) == 2
    assert {pair.first_patch_id for pair in proposals[0].pairs} | {pair.second_patch_id for pair in proposals[0].pairs} == {
        "group:0", "group:1", "group:2"
    }


def test_close_does_not_offer_a_one_segment_local_bridge_as_primary_for_detailed_faces() -> None:
    document = ClothDocument()
    first = _add_polygon_patch(document, _subdivided_rectangle(0, 10, 0, 200, steps=24), "left")
    second = _add_polygon_patch(document, _subdivided_rectangle(35, 45, 0, 200, steps=24), "right")

    proposals = analyze_textile_close_groups(document, ((first,), (second,)))

    assert proposals
    assert proposals[0].id != "close_local_bridge"
    assert sum(pair.segment_count for pair in proposals[0].pairs) > 1
    assert _coverage(proposals[0]) >= 0.35


def test_close_uniform_parallel_loops_do_not_repeat_an_equivalent_full_proposal() -> None:
    document = ClothDocument()
    first = _add_polygon_patch(document, _subdivided_rectangle(0, 20, 0, 40, z=0, steps=10), "first")
    second = _add_polygon_patch(document, _subdivided_rectangle(0, 20, 0, 40, z=30, steps=10), "second")

    proposals = analyze_textile_close_groups(document, ((first,), (second,)))

    assert proposals
    assert proposals[0].id == "close_complete_boundary"
    assert len([proposal for proposal in proposals if _coverage(proposal) >= 0.90]) == 1


def _add_ring_patch(document: ClothDocument, patch_id: str, z: float) -> str:
    outer = ((0, 0, z), (40, 0, z), (40, 40, z), (0, 40, z))
    inner = ((10, 10, z), (30, 10, z), (30, 30, z), (10, 30, z))
    outer_ids = []
    inner_ids = []
    for prefix, positions, target in (("o", outer, outer_ids), ("i", inner, inner_ids)):
        points = [document.add_point(position, point_id=f"{patch_id}_{prefix}p{index}").id for index, position in enumerate(positions)]
        for index, point_id in enumerate(points):
            target.append(
                document.add_line(
                    point_id,
                    points[(index + 1) % len(points)],
                    curve_id=f"{patch_id}_{prefix}c{index}",
                ).id
            )
    return document.add_patch(outer_ids, hole_curve_loops=(inner_ids,), patch_id=patch_id).id


def test_close_two_annular_groups_pairs_outer_and_inner_loops() -> None:
    document = ClothDocument()
    first = _add_ring_patch(document, "ring_a", 0.0)
    second = _add_ring_patch(document, "ring_b", 20.0)

    proposals = analyze_textile_close_groups(document, ((first,), (second,)))

    assert proposals
    primary = proposals[0]
    assert primary.id == "close_complete_multiloop"
    assert len(primary.pairs) >= 2
    assert _coverage(primary) >= 0.95
    assert all(pair.strategy.startswith("multi_loop_") for pair in primary.pairs)
    assert "multi-loop" in primary.message.lower()

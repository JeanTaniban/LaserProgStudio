from laserprog_studio.planar_tools import (
    FixedPlanarView,
    LockedPlaneSpec,
    PlanarPolygonDraft,
    clamp_polygon_point_candidate,
    make_extruded_polygon_mesh,
    polygon_close_is_valid,
    validate_open_polygon_trace,
)


def _plane():
    return LockedPlaneSpec(view=FixedPlanarView.TOP, normal=(0.0, 0.0, 1.0), u_axis=(1.0, 0.0, 0.0), v_axis=(0.0, 1.0, 0.0), depth=0.0)


def test_open_polygon_trace_rejects_crossing_new_segment():
    # The trailing segment (10,0)->(0,10) crosses the existing segment
    # (0,0)->(10,10), so the open draft should warn before closure.
    result = validate_open_polygon_trace([(0, 0), (10, 10), (10, 0), (0, 10)])
    assert not result.ok
    assert "self-intersecting" in result.message()


def test_polygon_candidate_is_clamped_before_self_crossing():
    points = [(0, 0), (10, 10), (10, 0)]
    result = clamp_polygon_point_candidate(points, (0, 10), anchor=(10, 0))
    assert result.was_clamped
    assert result.valid
    assert result.point != result.raw_point
    assert validate_open_polygon_trace(points + [result.point]).ok


def test_polygon_close_validation_rejects_bow_tie():
    result = polygon_close_is_valid([(0, 0), (10, 10), (0, 10), (10, 0)], extrusion_depth=5)
    assert not result.ok
    assert "self-intersecting" in result.message()


def test_planar_polygon_draft_refuses_invalid_close_and_allows_valid_mesh():
    draft = PlanarPolygonDraft(_plane(), extrusion_depth=4)
    for p in [(0, 0), (10, 10), (0, 10), (10, 0)]:
        draft.add_point_plane(p)
    assert not draft.close_polygon()
    draft.reset()
    for p in [(0, 0), (10, 0), (10, 10), (0, 10)]:
        draft.add_point_plane(p)
    assert draft.close_polygon()
    mesh = make_extruded_polygon_mesh(draft)
    assert len(mesh.vertices) == 8
    assert len(mesh.triangles) >= 8

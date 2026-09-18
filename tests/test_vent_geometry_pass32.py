from collections import Counter

from laserprog_studio.planar_tools.contracts import FixedPlanarView, LockedPlaneSpec, VentSectionKind
from laserprog_studio.planar_tools.mesh_generation import make_vent_path_mesh
from laserprog_studio.planar_tools.vent_model import VentPathDraft, VentSectionSpec


def _plane():
    return LockedPlaneSpec(FixedPlanarView.TOP, (0, 0, 1), (1, 0, 0), (0, 1, 0), 0.0)


def _rect_vent(**kwargs):
    return VentPathDraft(
        _plane(),
        section=VentSectionSpec(VentSectionKind.RECTANGLE, area=100.0, width=10.0, height=10.0),
        wall_thickness=3.0,
        **kwargs,
    )


def _bad_edge_count(mesh) -> int:
    counts = Counter()
    for tri in mesh.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return sum(1 for count in counts.values() if count != 2)


def test_rectangular_vent_defaults_to_clean_waypoint_mode():
    draft = _rect_vent()
    assert draft.compact_wall_fusion is True
    assert draft.clearance_policy().allows_shared_walls is True
    assert draft.clearance_policy().min_centerline_spacing == 13.0
    assert draft.minimum_bend_radius() == 0.0
    assert draft.snap_grid_step() == 4.0


def test_clean_u_path_is_valid_and_mesh_is_closed():
    draft = _rect_vent(only_walls=True)
    draft.waypoints = [(0, 0), (40, 0), (40, 13), (0, 13)]
    validation = draft.validation_result()
    assert validation.ok, validation.message()
    mesh = make_vent_path_mesh(draft)
    assert _bad_edge_count(mesh) == 0


def test_close_parallel_passes_are_not_rejected_by_width_spacing():
    draft = _rect_vent()
    draft.waypoints = [(0, 0), (40, 0), (40, 8), (0, 8)]
    validation = draft.validation_result()
    assert validation.ok


def test_add_candidate_touch_safety_is_removed_but_self_crossing_still_refuses():
    draft = _rect_vent()
    draft.waypoints = [(0, 0), (40, 0), (40, 13), (0, 13), (0, 26)]
    result = draft.clamp_waypoint_candidate((20, 0), anchor=draft.waypoints[-1])
    assert not result.valid
    assert not result.was_clamped
    assert result.point == (20.0, 0.0)
    assert "self-intersects" in result.message
    assert "centerline" not in result.message

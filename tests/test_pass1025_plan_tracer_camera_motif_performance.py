from __future__ import annotations

from laserprog_studio.application.camera_motion_diagnostics import CameraState, classify_camera_motion
from laserprog_studio.application.projected_drawing_2d import _compile_scene
from laserprog_studio.application.projected_face_triangulation import (
    clear_triangulation_caches,
    triangulate_polygon_cells,
    triangulate_polygon_with_holes_cells,
    triangulation_cache_snapshot,
)
from laserprog_studio.tool_core.projected_drawing import ProjectedFace, ProjectedFaceStyle


def _camera(
    *,
    position=(0.0, 0.0, 10.0),
    focal_point=(0.0, 0.0, 0.0),
    view_up=(0.0, 1.0, 0.0),
    parallel_scale=10.0,
    view_angle=30.0,
    parallel_projection=True,
) -> CameraState:
    return CameraState(
        position=position,
        focal_point=focal_point,
        view_up=view_up,
        parallel_scale=parallel_scale,
        view_angle=view_angle,
        parallel_projection=parallel_projection,
    )


def test_camera_motion_diagnostics_separate_pan_zoom_and_orbit() -> None:
    base = _camera()
    assert classify_camera_motion(None, base) == "initial"
    assert classify_camera_motion(base, base) == "static"
    assert classify_camera_motion(
        base,
        _camera(position=(2.0, 3.0, 10.0), focal_point=(2.0, 3.0, 0.0)),
    ) == "pan"
    assert classify_camera_motion(base, _camera(parallel_scale=7.5)) == "zoom"
    assert classify_camera_motion(
        base,
        _camera(position=(10.0, 0.0, 0.0), view_up=(0.0, 0.0, 1.0)),
    ) == "orbit"
    assert classify_camera_motion(
        base,
        _camera(position=(10.0, 0.0, 0.0), view_up=(0.0, 0.0, 1.0), parallel_scale=7.5),
    ) == "mixed"


def test_face_with_holes_reuses_geometry_triangulation_for_style_only_compile() -> None:
    outer = ((0.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 100.0, 0.0), (0.0, 100.0, 0.0))
    holes = tuple(
        (
            (x, y, 0.0),
            (x + 5.0, y, 0.0),
            (x + 5.0, y + 5.0, 0.0),
            (x, y + 5.0, 0.0),
        )
        for y in (10.0, 30.0, 50.0, 70.0)
        for x in (10.0, 30.0, 50.0, 70.0)
    )
    clear_triangulation_caches()

    normal = ProjectedFace(id="motif", vertices=outer, holes=holes)
    first_batches, _ = _compile_scene((normal,))
    after_first = triangulation_cache_snapshot()
    assert after_first["holes_misses"] == 1
    assert after_first["holes_hits"] == 0

    hovered = ProjectedFace(
        id="motif",
        vertices=outer,
        holes=holes,
        style=ProjectedFaceStyle(
            fill_color="#FFCC55",
            fill_opacity=0.35,
            outline_color="#FFFFFF",
            outline_width_px=2.0,
        ),
    )
    second_batches, _ = _compile_scene((hovered,))
    after_second = triangulation_cache_snapshot()

    assert after_second["holes_misses"] == 1
    assert after_second["holes_hits"] == 1
    assert sum(len(batch.cells) for batch in first_batches if batch.key.kind == "faces") == sum(
        len(batch.cells) for batch in second_batches if batch.key.kind == "faces"
    )


def test_canonical_hole_cache_survives_ring_rotation_winding_and_hole_order() -> None:
    outer = ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 20.0, 0.0), (0.0, 20.0, 0.0))
    holes = (
        ((2.0, 2.0, 0.0), (6.0, 2.0, 0.0), (6.0, 6.0, 0.0), (2.0, 6.0, 0.0)),
        ((12.0, 12.0, 0.0), (16.0, 12.0, 0.0), (16.0, 16.0, 0.0), (12.0, 16.0, 0.0)),
    )
    clear_triangulation_caches()
    first = triangulate_polygon_with_holes_cells(outer, holes)
    assert first

    transformed_outer = tuple(reversed((*outer[2:], *outer[:2])))
    transformed_holes = tuple(
        tuple(reversed((*ring[1:], ring[0])))
        for ring in reversed(holes)
    )
    second = triangulate_polygon_with_holes_cells(transformed_outer, transformed_holes)
    assert second
    snapshot = triangulation_cache_snapshot()
    assert snapshot["holes_misses"] == 2  # raw declarations differ
    assert snapshot["holes_canonical_misses"] == 1
    assert snapshot["holes_canonical_hits"] == 1

    flattened = transformed_outer + tuple(point for ring in transformed_holes for point in ring)
    triangle_area = 0.0
    for a, b, c in second:
        pa, pb, pc = flattened[a], flattened[b], flattened[c]
        triangle_area += abs((pb[0] - pa[0]) * (pc[1] - pa[1]) - (pb[1] - pa[1]) * (pc[0] - pa[0])) * 0.5
    assert triangle_area == 368.0

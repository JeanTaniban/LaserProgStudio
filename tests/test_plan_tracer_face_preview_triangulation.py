from __future__ import annotations

from laserprog_studio.application._preview_face_triangulation import _triangulate_preview_face_points


def _triangle_area_2d(points: list[tuple[float, float, float]], faces: list[int]) -> float:
    total = 0.0
    index = 0
    while index < len(faces):
        count = faces[index]
        assert count == 3
        a, b, c = faces[index + 1 : index + 4]
        pa, pb, pc = points[a], points[b], points[c]
        total += abs(
            (pb[0] - pa[0]) * (pc[1] - pa[1])
            - (pb[1] - pa[1]) * (pc[0] - pa[0])
        ) * 0.5
        index += 4
    return total


def test_preview_face_triangulation_handles_concave_polygon_without_vtk_fan_artifact() -> None:
    # This L-shaped cell is the minimal version of the visual bug: passing this
    # as one PolyData polygon lets VTK draw a diagonal across the concavity.
    outer = (
        (0.0, 0.0, 0.0),
        (4.0, 0.0, 0.0),
        (4.0, 1.0, 0.0),
        (1.0, 1.0, 0.0),
        (1.0, 4.0, 0.0),
        (0.0, 4.0, 0.0),
    )

    result = _triangulate_preview_face_points(outer)

    assert result is not None
    points, faces = result
    assert len(faces) % 4 == 0
    assert len(faces) // 4 >= 3
    assert abs(_triangle_area_2d(points, faces) - 7.0) <= 1.0e-6


def test_preview_face_triangulation_keeps_holes_empty() -> None:
    outer = (
        (0.0, 0.0, 0.0),
        (10.0, 0.0, 0.0),
        (10.0, 10.0, 0.0),
        (0.0, 10.0, 0.0),
    )
    hole = (
        (3.0, 3.0, 0.0),
        (7.0, 3.0, 0.0),
        (7.0, 7.0, 0.0),
        (3.0, 7.0, 0.0),
    )

    result = _triangulate_preview_face_points(outer, (hole,))

    assert result is not None
    points, faces = result
    assert abs(_triangle_area_2d(points, faces) - 84.0) <= 1.0e-6

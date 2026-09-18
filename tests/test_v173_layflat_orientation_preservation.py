from __future__ import annotations

import itertools
import math

from laserprog_studio.fabrication.layflat_core import (
    PieceGroup,
    _flat_orientation_frame,
    orient_piece_flat,
    pack_pieces_length_constrained,
    repair_triangle_winding,
    rotate_piece_xy_90,
)


def _triple(a, b, c, d) -> float:
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    ad = (d[0] - a[0], d[1] - a[1], d[2] - a[2])
    cross = (
        ac[1] * ad[2] - ac[2] * ad[1],
        ac[2] * ad[0] - ac[0] * ad[2],
        ac[0] * ad[1] - ac[1] * ad[0],
    )
    return ab[0] * cross[0] + ab[1] * cross[1] + ab[2] * cross[2]


def _normal(vertices, tri):
    a, b, c = (vertices[i] for i in tri)
    ab = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
    ac = (c[0] - a[0], c[1] - a[1], c[2] - a[2])
    return (
        ab[1] * ac[2] - ab[2] * ac[1],
        ab[2] * ac[0] - ab[0] * ac[2],
        ab[0] * ac[1] - ab[1] * ac[0],
    )


def test_v173_every_flat_axis_frame_is_a_proper_rotation() -> None:
    # Exercise all six distinct dimension orderings. The old implementation
    # produced determinant -1 for half of these cases.
    for dims in itertools.permutations((1.0, 2.0, 4.0)):
        axes, signs = _flat_orientation_frame(list(dims))
        det = 1.0
        inversions = sum(axes[i] > axes[j] for i in range(3) for j in range(i + 1, 3))
        det *= -1.0 if inversions % 2 else 1.0
        det *= signs[0] * signs[1] * signs[2]
        assert det == 1.0
        assert signs[2] == 1.0


def test_v173_orient_piece_flat_preserves_mesh_handedness_for_all_axis_orders() -> None:
    for dx, dy, dz in itertools.permutations((1.0, 2.0, 4.0)):
        vertices = [(0.0, 0.0, 0.0), (dx, 0.0, 0.0), (0.0, dy, 0.0), (0.0, 0.0, dz)]
        before = _triple(*vertices)
        piece = PieceGroup(name="chiral", vertices=list(vertices), triangles=[])
        orient_piece_flat(piece)
        after = _triple(*piece.vertices)
        assert before > 0.0
        assert after > 0.0
        assert math.isclose(abs(after), abs(before), rel_tol=1e-9, abs_tol=1e-9)


def test_v173_open_sheet_keeps_its_visible_side_when_laid_flat() -> None:
    # Three source sheets, with normals along +X, +Y and +Z respectively.
    cases = [
        (
            [(0, 0, 0), (0, 3, 0), (0, 3, 2), (0, 0, 2)],
            [(0, 1, 2), (0, 2, 3)],
        ),
        (
            [(0, 0, 0), (2, 0, 0), (2, 0, 3), (0, 0, 3)],
            [(0, 2, 1), (0, 3, 2)],
        ),
        (
            [(0, 0, 0), (3, 0, 0), (3, 2, 0), (0, 2, 0)],
            [(0, 1, 2), (0, 2, 3)],
        ),
    ]
    for vertices, triangles in cases:
        piece = PieceGroup(name="sheet", vertices=[tuple(map(float, v)) for v in vertices], triangles=list(triangles))
        orient_piece_flat(piece)
        for tri in piece.triangles:
            assert _normal(piece.vertices, tri)[2] > 0.0


def test_v173_xy_packing_rotation_preserves_handedness_and_triangle_order() -> None:
    vertices = [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 2.0, 0.0), (0.0, 0.0, 1.0)]
    triangles = [(0, 1, 2)]
    piece = PieceGroup(
        name="marker",
        vertices=list(vertices),
        triangles=list(triangles),
        flat_width=3.0,
        flat_depth=2.0,
        flat_height=1.0,
    )
    before = _triple(*vertices)
    rotate_piece_xy_90(piece)
    assert _triple(*piece.vertices) > 0.0
    assert math.isclose(abs(_triple(*piece.vertices)), abs(before), rel_tol=1e-9)
    assert piece.triangles == triangles


def test_v173_open_component_winding_repair_does_not_reverse_the_seed_side() -> None:
    # This open tilted quad has a non-zero pseudo-volume, which used to trigger
    # the closed-solid orientation rule and reverse the whole sheet.
    vertices = [(1.0, 0.0, 1.0), (3.0, 0.0, 1.0), (3.0, 2.0, 2.0), (1.0, 2.0, 2.0)]
    triangles = [(0, 1, 2), (0, 2, 3)]
    piece = PieceGroup(name="open", vertices=vertices, triangles=list(triangles))
    before = _normal(piece.vertices, piece.triangles[0])
    repair_triangle_winding(piece)
    after = _normal(piece.vertices, piece.triangles[0])
    assert sum(a * b for a, b in zip(before, after)) > 0.0


def test_v173_packing_rotation_never_mirrors_a_piece() -> None:
    vertices = [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 0.5)]
    piece = PieceGroup(
        name="packed",
        vertices=list(vertices),
        triangles=[],
        flat_width=4.0,
        flat_depth=1.0,
        flat_height=0.5,
    )
    before = _triple(*vertices)
    packed = pack_pieces_length_constrained([piece], spacing=0.0, max_length=1.5, allow_rotation=True)
    assert len(packed) == 1
    assert _triple(*packed[0].vertices) > 0.0
    assert math.isclose(abs(_triple(*packed[0].vertices)), abs(before), rel_tol=1e-9)


def test_v173_many_dimension_sets_never_change_chirality() -> None:
    # Deterministic stress set around near-ties and very different scales.
    dimension_sets = []
    for i in range(1, 41):
        a = 0.1 + i * 0.037
        b = 1.0 + (i % 7) * 0.113
        c = 5.0 + (i % 11) * 0.271
        dimension_sets.extend(itertools.permutations((a, b, c)))
    for dx, dy, dz in dimension_sets:
        vertices = [(0.0, 0.0, 0.0), (dx, 0.0, 0.0), (0.0, dy, 0.0), (0.0, 0.0, dz)]
        piece = PieceGroup(name="stress", vertices=list(vertices), triangles=[])
        before = _triple(*vertices)
        orient_piece_flat(piece)
        after = _triple(*piece.vertices)
        assert before * after > 0.0
        assert math.isclose(abs(after), abs(before), rel_tol=1e-9, abs_tol=1e-9)

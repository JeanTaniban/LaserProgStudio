# -*- coding: utf-8 -*-
from __future__ import annotations

import math

import pytest

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tooling.folding.geometry import (
    arbitrary_face_plane,
    deform_vertices,
    fold_angle_from_handle,
    living_hinge_pose,
    normalized_fold_angle_deg,
    sample_curve,
    unwrap_fold_angle_deg,
)
from laserprog_studio.tooling.folding.models import FoldingCurve, FoldingMode
from laserprog_studio.tooling.folding.panel import build_folding_panel
from laserprog_studio.tooling.folding.serialization import attach_folding_source, restore_folding_source


def _plane():
    return arbitrary_face_plane((0.0, 0.0, 0.0), (0.0, 0.0, 1.0))


def _curve(angle: float) -> FoldingCurve:
    return FoldingCurve(
        start=(0.0, 0.0, 0.0),
        end=(10.0, 0.0, 0.0),
        mode=FoldingMode.LIVING_HINGE.value,
        fold_angle_deg=angle,
        shape_angles_deg=(0.0, 0.0, 0.0),
    )


def _mesh() -> WorkMesh:
    return WorkMesh(
        name="extended-angle hinge",
        vertices=[
            (-4.0, -2.0, 0.0),
            (-4.0, 2.0, 0.0),
            (2.5, -2.0, 0.0),
            (2.5, 2.0, 0.0),
            (7.5, -2.0, 0.0),
            (7.5, 2.0, 0.0),
            (12.0, -2.0, 0.0),
            (12.0, 2.0, 0.0),
            (16.0, -2.0, 1.0),
            (16.0, 2.0, 1.0),
        ],
        triangles=[
            (0, 2, 1),
            (1, 2, 3),
            (2, 4, 3),
            (3, 4, 5),
            (4, 6, 5),
            (5, 6, 7),
        ],
    )


def test_angle_range_preserves_multi_turn_values_and_clamps_only_at_720() -> None:
    assert normalized_fold_angle_deg(270.0) == pytest.approx(270.0)
    assert normalized_fold_angle_deg(-450.0) == pytest.approx(-450.0)
    assert normalized_fold_angle_deg(900.0) == pytest.approx(720.0)
    assert normalized_fold_angle_deg(-900.0) == pytest.approx(-720.0)


def test_terminal_handle_unwraps_continuously_across_half_turns() -> None:
    assert unwrap_fold_angle_deg(-179.0, 179.0) == pytest.approx(181.0)
    assert unwrap_fold_angle_deg(179.0, -179.0) == pytest.approx(-181.0)
    assert unwrap_fold_angle_deg(-179.0, 539.0) == pytest.approx(541.0)

    curve = _curve(179.0)
    pose = living_hinge_pose(_plane(), curve)
    raw = math.radians(-179.0)
    point = tuple(
        pose.end_center[index]
        + math.cos(raw) * (1.0, 0.0, 0.0)[index]
        + math.sin(raw) * (0.0, 0.0, 1.0)[index]
        for index in range(3)
    )
    assert fold_angle_from_handle(_plane(), curve, point) == pytest.approx(181.0)


def test_270_degree_neutral_line_keeps_its_length() -> None:
    points = sample_curve(_plane(), _curve(270.0), count=10_001)
    length = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
    assert length == pytest.approx(10.0, rel=2.0e-10, abs=2.0e-10)


def test_450_degree_fold_keeps_the_outer_region_rigid() -> None:
    source = [
        (-3.0, -2.0, 0.0),
        (-1.0, 3.0, 1.0),
        (12.0, -2.0, 0.0),
        (16.0, 3.0, 1.0),
    ]
    result = deform_vertices(source, _plane(), _curve(450.0))
    assert result[0] == pytest.approx(source[0], abs=1.0e-10)
    assert result[1] == pytest.approx(source[1], abs=1.0e-10)
    assert math.dist(result[2], result[3]) == pytest.approx(math.dist(source[2], source[3]), rel=1.0e-10, abs=1.0e-10)


def test_extended_angle_round_trips_and_corrupt_values_are_clamped() -> None:
    mesh = _mesh()
    folded = attach_folding_source(mesh, source_mesh=mesh, plane=_plane(), curve=_curve(450.0))
    restored = restore_folding_source(folded)
    assert restored is not None
    assert restored[2].fold_angle_deg == pytest.approx(450.0)

    folded.metadata["folding_source"]["curve"]["fold_angle_deg"] = 5000.0
    restored = restore_folding_source(folded)
    assert restored is not None
    assert restored[2].fold_angle_deg == pytest.approx(720.0)


def test_inspector_exposes_the_extended_numeric_range() -> None:
    panel = build_folding_panel(on_value_changed=lambda *_args: None, on_action=lambda *_args: None)
    angle = next(field for section in panel.sections for field in section.fields if field.id == "folding_angle")
    assert angle.min_value == pytest.approx(-720.0)
    assert angle.max_value == pytest.approx(720.0)

# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np

import _path_setup  # noqa: F401
from laserprog_studio.geometry_ops.image_mask_relief_contour import (
    _ambiguous_case_pairs,
    _bilinear_sample,
)


def test_asymptotic_decider_beats_arithmetic_center_for_case_5() -> None:
    # Relative to threshold=100:
    # TL=-6, TR=+11, BR=-6, BL=+2.
    # The arithmetic center is positive, but the bilinear determinant is +14,
    # so TR/BL must remain disconnected.
    values = (94.0, 111.0, 94.0, 102.0)
    assert sum(values) / 4.0 > 100.0
    assert _ambiguous_case_pairs(5, values, 100.0) == ((0, 1), (3, 2))


def test_asymptotic_decider_connects_case_5_when_bilinear_saddle_is_material() -> None:
    values = (94.0, 108.0, 94.0, 108.0)
    assert _ambiguous_case_pairs(5, values, 100.0) == ((0, 3), (1, 2))


def test_asymptotic_decider_keeps_exact_diagonal_tie_disconnected() -> None:
    assert _ambiguous_case_pairs(5, (0.0, 200.0, 0.0, 200.0), 100.0) == ((0, 1), (3, 2))
    assert _ambiguous_case_pairs(10, (200.0, 0.0, 200.0, 0.0), 100.0) == ((0, 3), (1, 2))


def test_bilinear_sample_matches_continuous_scalar_field() -> None:
    field = np.asarray(
        [
            [0.0, 100.0],
            [200.0, 300.0],
        ],
        dtype=np.float64,
    )
    assert _bilinear_sample(field, 0.0, 0.0) == 0.0
    assert _bilinear_sample(field, 1.0, 1.0) == 300.0
    assert abs(_bilinear_sample(field, 0.5, 0.5) - 150.0) <= 1.0e-12
    assert abs(_bilinear_sample(field, 0.25, 0.75) - 125.0) <= 1.0e-12

# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np

import _path_setup  # noqa: F401
from laserprog_studio.geometry_ops.image_mask_relief_loading import _otsu_threshold, _resolve_activity_threshold
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


def test_otsu_uses_midpoint_of_equal_optimum_plateau() -> None:
    hist = [0] * 256
    hist[0] = 100
    hist[255] = 100
    assert _otsu_threshold(hist) == 127


def test_otsu_midpoint_avoids_dark_peak_bias_on_separated_bands() -> None:
    hist = [0] * 256
    hist[20] = 50
    hist[220] = 50
    value = _otsu_threshold(hist)
    assert 119 <= value <= 121


def test_shared_threshold_contract_places_otsu_on_bin_boundary() -> None:
    hist = [0] * 256
    hist[0] = 50
    hist[255] = 50
    threshold_level, threshold_norm = _resolve_activity_threshold(
        hist,
        binary_threshold=0.5,
        levels=50,
    )
    assert threshold_level == 127.5
    assert abs(threshold_norm - 0.5) <= 1.0e-12


def test_shared_threshold_contract_keeps_explicit_threshold_continuous() -> None:
    hist = [0] * 256
    threshold_level, threshold_norm = _resolve_activity_threshold(
        hist,
        binary_threshold=0.7,
        levels=None,
    )
    assert abs(threshold_level - 178.5) <= 1.0e-12
    assert abs(threshold_norm - 0.7) <= 1.0e-12

# -*- coding: utf-8 -*-
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

import _path_setup  # noqa: F401
from laserprog_studio.geometry_ops.image_mask_relief_loading import _otsu_threshold, _resolve_activity_threshold
from laserprog_studio.geometry_ops.image_mask_relief_contour import (
    _ambiguous_case_pairs,
    _bilinear_sample,
    _topology_correspondence_safe,
    _cached_activity_field,
    _cached_raw_footprint_wkb,
    build_binary_mask_footprint,
    clear_mask_contour_caches,
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

def test_mask_contour_cache_reuses_raw_vectorization_across_smooth_values(tmp_path) -> None:
    clear_mask_contour_caches()
    path = tmp_path / "cached.png"
    img = Image.new("L", (256, 128), 255)
    ImageDraw.Draw(img).ellipse((20, 12, 236, 116), fill=0)
    img.save(path)

    build_binary_mask_footprint(path, levels=50, smooth=0, max_grid_size=128)
    activity_after_first = _cached_activity_field.cache_info()
    raw_after_first = _cached_raw_footprint_wkb.cache_info()

    build_binary_mask_footprint(path, levels=50, smooth=100, max_grid_size=128)
    activity_after_second = _cached_activity_field.cache_info()
    raw_after_second = _cached_raw_footprint_wkb.cache_info()

    assert raw_after_first.misses == 1
    assert raw_after_second.hits >= raw_after_first.hits + 1
    assert activity_after_second.hits >= activity_after_first.hits + 1


def test_mask_contour_cache_invalidates_when_source_file_changes(tmp_path) -> None:
    clear_mask_contour_caches()
    path = tmp_path / "changing.png"
    Image.new("L", (64, 64), 255).save(path)

    try:
        build_binary_mask_footprint(path, levels=50, smooth=0, max_grid_size=64)
    except ValueError:
        # Empty material is expected; activity cache still has to be populated.
        pass
    first = _cached_activity_field.cache_info()

    img = Image.new("L", (65, 64), 255)
    ImageDraw.Draw(img).rectangle((8, 8, 56, 55), fill=0)
    img.save(path)
    build_binary_mask_footprint(path, levels=50, smooth=0, max_grid_size=64)
    second = _cached_activity_field.cache_info()

    assert second.misses >= first.misses + 1

def test_topology_correspondence_rejects_relocated_hole_with_same_counts() -> None:
    from shapely.geometry import Polygon

    shell = [(0, 0), (20, 0), (20, 20), (0, 20)]
    reference = Polygon(shell, [[(3, 3), (7, 3), (7, 7), (3, 7)]])
    relocated = Polygon(shell, [[(13, 13), (17, 13), (17, 17), (13, 17)]])
    nearby = Polygon(shell, [[(3.2, 3.1), (7.0, 3.1), (7.0, 7.0), (3.2, 7.0)]])

    assert _topology_correspondence_safe(reference, relocated) is False
    assert _topology_correspondence_safe(reference, nearby) is True


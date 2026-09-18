from __future__ import annotations

from pathlib import Path

from _image_mask_relief_source import read_image_mask_relief_source

ROOT = Path(__file__).resolve().parents[1]


def test_import_2d_mask_dialog_contains_live_preview_controls() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "controllers" / "image_mask_import.py").read_text(encoding="utf-8")
    assert "Preview — black = 10 mm material, white = empty" in source
    assert "render_mask_preview_image" in source
    assert "levels_slider.valueChanged.connect" in source
    assert "smooth_slider.valueChanged.connect" in source
    assert "invert_check.toggled.connect" in source
    assert "file_edit.textChanged.connect" in source


def test_mask_smoothing_is_vector_only_not_gaussian_blur() -> None:
    source = read_image_mask_relief_source(ROOT)
    assert "ImageFilter" not in source
    assert "GaussianBlur" not in source
    assert "Smoothing is applied only after the binary mask has been built" in source

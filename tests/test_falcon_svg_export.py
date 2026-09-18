from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401

from shapely.geometry import Polygon

from laserprog_studio.engraving.export_2d import Instance2D, RenderConfig, export_falcon_svg


def test_export_falcon_svg_is_real_size_and_layered(tmp_path: Path) -> None:
    cfg = RenderConfig(dpi=254, page_margin_ratio=0.0, contour_width_mm=0.2, min_output_px=10)
    instances = [
        Instance2D("outline", "#00C853", Polygon([(0, 0), (10, 0), (10, 5), (0, 5)]), 3.0),
        Instance2D("fill", "#E53935", Polygon([(2, 1), (8, 1), (8, 4), (2, 4)]), 3.0),
    ]

    out = export_falcon_svg(instances, cfg, tmp_path / "falcon.svg")
    text = out.read_text(encoding="utf-8")

    assert 'width="10mm"' in text
    assert 'height="5mm"' in text
    assert 'viewBox="0 0 10 5"' in text
    assert 'id="falcon_outline_cut"' in text
    assert 'stroke="#00C853"' in text
    assert 'stroke-width="0.2"' in text
    assert 'id="falcon_fill_engrave"' in text
    assert 'fill="#E53935"' in text
    assert 'fill-rule="evenodd"' in text
    assert 'id="outline_001"' in text
    assert 'id="fill_001"' in text


def test_export_falcon_svg_splits_cut_holes_into_plain_paths(tmp_path: Path) -> None:
    cfg = RenderConfig(dpi=254, page_margin_ratio=0.0, contour_width_mm=0.2, min_output_px=10)
    outline_with_hole = Polygon(
        [(0, 0), (20, 0), (20, 20), (0, 20)],
        holes=[[(5, 5), (15, 5), (15, 15), (5, 15)]],
    )
    instances = [Instance2D("outline", "#00C853", outline_with_hole, 3.0)]

    out = export_falcon_svg(instances, cfg, tmp_path / "falcon_hole.svg")
    text = out.read_text(encoding="utf-8")

    assert 'cut_path_mode":"one_svg_path_per_ring' in text
    assert text.count('id="outline_') == 2
    assert 'transform=' not in text
    assert 'matrix(' not in text
    # Cut paths must be plain independent paths: one M command per element, not
    # one compound path containing both the exterior and the hole.
    outline_lines = [line for line in text.splitlines() if 'id="outline_' in line]
    assert outline_lines
    assert all(line.count('M ') == 1 for line in outline_lines)



def test_export_falcon_svg_removes_redundant_cut_vertices_and_duplicate_paths(tmp_path: Path) -> None:
    cfg = RenderConfig(dpi=254, page_margin_ratio=0.0, contour_width_mm=0.2, min_output_px=10)
    # Duplicate identical outline instances and repeated collinear vertices used
    # to be exported as repeated path data.  That is visually harmless, but CAM
    # software can cut the same contour twice or reorder the path optimisation.
    noisy = Polygon([(0, 0), (5, 0), (10, 0), (10, 5), (10, 10), (0, 10), (0, 0)])
    instances = [
        Instance2D("outline_a", "#00C853", noisy, 3.0),
        Instance2D("outline_b", "#00C853", noisy, 3.0),
    ]

    out = export_falcon_svg(instances, cfg, tmp_path / "falcon_noisy.svg")
    text = out.read_text(encoding="utf-8")
    outline_lines = [line for line in text.splitlines() if 'id="outline_' in line]

    assert len(outline_lines) == 1
    assert outline_lines[0].count('M ') == 1
    # No explicit L back to the starting point before Z; Z closes the path once.
    assert 'L 0 10 Z' not in outline_lines[0]
    assert 'transform=' not in text
    assert 'matrix(' not in text

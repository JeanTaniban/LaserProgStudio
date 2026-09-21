# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

import _path_setup  # noqa: F401
from laserprog_studio.geometry_ops.image_mask_relief import build_mask_relief_mesh
from laserprog_studio.geometry_ops.image_mask_relief_contour import build_binary_mask_footprint
from laserprog_studio.geometry_ops.manifold_contract import construct_manifold, manifold_is_valid


def _parts(geometry):
    if geometry.geom_type == "Polygon":
        return [geometry]
    return [g for g in getattr(geometry, "geoms", ()) if g.geom_type == "Polygon"]


def _signature(geometry):
    parts = _parts(geometry)
    return len(parts), tuple(sorted(len(poly.interiors) for poly in parts))


def _assert_direct_manifold(mesh) -> None:
    import manifold3d as m3d
    import numpy as np

    construction = construct_manifold(
        m3d,
        vertices=np.asarray(mesh.vertices, dtype=np.float64),
        triangles=np.asarray(mesh.triangles, dtype=np.int32),
        merge=False,
        prefer_64bit=True,
    )
    assert manifold_is_valid(construction.manifold, m3d), str(construction.status)


def test_full_black_mask_reaches_physical_image_bounds(tmp_path: Path) -> None:
    path = tmp_path / "full.png"
    Image.new("L", (32, 20), 0).save(path)

    fp = build_binary_mask_footprint(path, pixel_size_mm=2.0, levels=50, smooth=0, max_grid_size=0)

    assert fp.geometry.is_valid
    minx, miny, maxx, maxy = fp.geometry.bounds
    assert abs(minx + 32.0) <= 1e-9
    assert abs(maxx - 32.0) <= 1e-9
    assert abs(miny + 20.0) <= 1e-9
    assert abs(maxy - 20.0) <= 1e-9


def test_one_pixel_hole_survives_maximum_smooth(tmp_path: Path) -> None:
    path = tmp_path / "one_pixel_hole.png"
    img = Image.new("L", (21, 21), 0)
    img.putpixel((10, 10), 255)
    img.save(path)

    raw = build_binary_mask_footprint(path, levels=50, smooth=0, max_grid_size=0)
    smooth = build_binary_mask_footprint(path, levels=50, smooth=100, max_grid_size=0)

    assert _signature(raw.geometry) == (1, (1,))
    assert _signature(smooth.geometry) == _signature(raw.geometry)

    mesh = build_mask_relief_mesh(
        path,
        max_height_mm=5.0,
        pixel_size_mm=1.0,
        binary=True,
        levels=50,
        smooth=100,
        max_grid_size=0,
    ).mesh
    _assert_direct_manifold(mesh)


def test_one_pixel_gap_between_islands_is_not_closed_by_smooth(tmp_path: Path) -> None:
    path = tmp_path / "gap.png"
    img = Image.new("L", (31, 15), 255)
    draw = ImageDraw.Draw(img)
    draw.rectangle((2, 2, 14, 12), fill=0)
    draw.rectangle((16, 2, 28, 12), fill=0)
    img.save(path)

    raw = build_binary_mask_footprint(path, levels=50, smooth=0, max_grid_size=0)
    smooth = build_binary_mask_footprint(path, levels=50, smooth=100, max_grid_size=0)

    assert _signature(raw.geometry)[0] == 2
    assert _signature(smooth.geometry) == _signature(raw.geometry)


def test_diagonal_checkerboard_stays_disconnected_and_manifold(tmp_path: Path) -> None:
    path = tmp_path / "checker.png"
    img = Image.new("L", (8, 8), 255)
    for y in range(8):
        for x in range(8):
            if (x + y) % 2 == 0:
                img.putpixel((x, y), 0)
    img.save(path)

    fp = build_binary_mask_footprint(path, levels=50, smooth=0, max_grid_size=0)
    assert fp.geometry.is_valid
    assert len(_parts(fp.geometry)) == 32

    mesh = build_mask_relief_mesh(
        path,
        max_height_mm=3.0,
        pixel_size_mm=1.0,
        binary=True,
        levels=50,
        smooth=0,
        max_grid_size=0,
    ).mesh
    _assert_direct_manifold(mesh)


def test_levels_monotonically_increases_kept_material(tmp_path: Path) -> None:
    path = tmp_path / "gradient.png"
    img = Image.new("L", (128, 32), 255)
    for x in range(128):
        value = int(round(255.0 * x / 127.0))
        for y in range(32):
            img.putpixel((x, y), value)
    img.save(path)

    areas = [
        float(build_binary_mask_footprint(path, levels=level, smooth=0, max_grid_size=0).geometry.area)
        for level in (20, 35, 50, 65, 80)
    ]
    assert areas == sorted(areas)


def test_jpeg_low_contrast_shape_remains_single_valid_component(tmp_path: Path) -> None:
    path = tmp_path / "low_contrast.jpg"
    img = Image.new("L", (160, 96), 225)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((24, 18, 136, 78), radius=18, fill=150)
    # Add a weak second tone so the input is not a trivial two-bin histogram.
    draw.ellipse((62, 32, 98, 68), fill=175)
    img.save(path, quality=55)

    fp = build_binary_mask_footprint(path, levels=50, smooth=35, max_grid_size=0)

    assert fp.geometry.is_valid
    assert _signature(fp.geometry)[0] == 1
    assert float(fp.geometry.area) > 1000.0


def test_analysis_resolution_does_not_change_physical_frame(tmp_path: Path) -> None:
    path = tmp_path / "large.png"
    img = Image.new("L", (1024, 512), 255)
    ImageDraw.Draw(img).rectangle((0, 0, 1023, 511), fill=0)
    img.save(path)

    bounds = []
    for limit in (128, 256, 512):
        fp = build_binary_mask_footprint(path, pixel_size_mm=1.0, levels=50, smooth=0, max_grid_size=limit)
        bounds.append(tuple(round(float(v), 6) for v in fp.geometry.bounds))

    assert bounds[0] == bounds[1] == bounds[2]

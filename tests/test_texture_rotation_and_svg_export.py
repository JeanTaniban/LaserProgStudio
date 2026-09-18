# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import base64
import re

import _path_setup  # noqa: F401
from PIL import Image

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams, apply_texture_projection, compute_projected_uvs
from laserprog_studio.engraving.texture_layer import export_texture_layer_svg


def test_rotated_ratio_preserving_uvs_are_not_sheared() -> None:
    mesh = WorkMesh(
        name="rect",
        vertices=[(0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
    )
    uvs = compute_projected_uvs(
        mesh,
        projection_mode="planar",
        preserve_aspect=True,
        image_width=400,
        image_height=100,
        rotation_deg=37.0,
    )
    # Face is 20x10 and image aspect is 4:1. v40 starts in fit-inside mode, so the tile is 20x5.
    tile_w, tile_h = 20.0, 5.0
    local = [((u - 0.5) * tile_w, (v - 0.5) * tile_h) for u, v in uvs]

    def dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    assert abs(dist(local[0], local[1]) - 20.0) < 1e-6
    assert abs(dist(local[1], local[2]) - 10.0) < 1e-6


def test_face_decal_does_not_include_opposite_cube_face() -> None:
    mesh = WorkMesh(
        name="cube",
        vertices=[
            (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
            (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
        ],
        triangles=[
            (0, 1, 2), (0, 2, 3),
            (4, 6, 5), (4, 7, 6),
            (0, 4, 5), (0, 5, 1),
            (1, 5, 6), (1, 6, 2),
            (2, 6, 7), (2, 7, 3),
            (3, 7, 4), (3, 4, 0),
        ],
    )
    params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=Path("demo.png"),
        projection_mode="box",
        coverage_angle_deg=1.0,
        seed_face_index=2,
        projection_origin=(0, 0, 1),
        projection_normal=(0, 0, 1),
        image_width=100,
        image_height=100,
    )
    out = apply_texture_projection([mesh], [0], params)
    decal = out[1]
    assert len(decal.triangles) == 2
    assert all(v[2] > 1.0 for v in decal.vertices)


def test_texture_layer_svg_embeds_real_size_png(tmp_path: Path) -> None:
    img = Image.new("RGB", (16, 8), "white")
    for x in range(8):
        for y in range(8):
            img.putpixel((x, y), (0, 0, 0))
    cfg = SimpleNamespace(dpi=100, page_margin_ratio=0.0, min_output_px=100)
    out = export_texture_layer_svg(img, bounds=(0, 0, 20, 10), cfg=cfg, out=tmp_path / "texture.svg")
    text = out.read_text(encoding="utf-8")
    assert 'width="20mm"' in text
    assert 'height="10mm"' in text
    assert 'id="falcon_texture_engrave"' in text
    match = re.search(r"data:image/png;base64,([A-Za-z0-9+/=]+)", text)
    assert match is not None
    assert base64.b64decode(match.group(1)).startswith(b"\x89PNG")

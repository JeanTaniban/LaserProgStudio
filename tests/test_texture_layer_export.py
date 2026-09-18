# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import _path_setup  # noqa: F401
from PIL import Image

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams, apply_texture_projection
from laserprog_studio.engraving.texture_layer import render_texture_layer_from_meshes, render_texture_cut_outline_mask, export_texture_cut_contours_svg


def test_texture_layer_renders_decal_bitmap(tmp_path: Path) -> None:
    tex = tmp_path / "tex.png"
    img = Image.new("RGB", (8, 8), "white")
    # One black quadrant is enough to prove that the texture layer is not blank.
    for y in range(4):
        for x in range(4):
            img.putpixel((x, y), (0, 0, 0))
    img.save(tex)

    mesh = WorkMesh(
        name="plate",
        vertices=[(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#E53935",
    )
    params = TextureProjectionParams(
        texture_id="tex_demo",
        texture_path=tex,
        projection_mode="planar",
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=8,
        image_height=8,
    )
    meshes = apply_texture_projection([mesh], [0], params)
    cfg = SimpleNamespace(dpi=100, page_margin_ratio=0.0, min_output_px=100)
    out = render_texture_layer_from_meshes(meshes, texture_assets_by_id={}, bounds=(0, 0, 10, 10), cfg=cfg)
    assert out.size[0] >= 100 and out.size[1] >= 100
    pixels = list(out.convert("L").getdata())
    assert min(pixels) < 250



def test_cut_usage_renders_to_cut_filter_and_traces_svg(tmp_path: Path) -> None:
    tex = tmp_path / "cut_tex.png"
    img = Image.new("RGB", (10, 10), "white")
    for y in range(2, 8):
        for x in range(2, 8):
            img.putpixel((x, y), (70, 70, 70))
    img.save(tex)

    mesh = WorkMesh(
        name="plate",
        vertices=[(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#E53935",
    )
    params = TextureProjectionParams(
        texture_id="tex_cut",
        texture_path=tex,
        projection_mode="planar",
        usage="cut",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=10,
        image_height=10,
    )
    meshes = apply_texture_projection([mesh], [0], params)
    decal = meshes[1]
    assert decal.engraving.texture_usage == "cut"
    cfg = SimpleNamespace(dpi=100, page_margin_ratio=0.0, min_output_px=100, contour_width_mm=0.1)
    engrave_layer = render_texture_layer_from_meshes(meshes, texture_assets_by_id={}, bounds=(0, 0, 10, 10), cfg=cfg, usage_filter="engrave")
    cut_layer = render_texture_layer_from_meshes(meshes, texture_assets_by_id={}, bounds=(0, 0, 10, 10), cfg=cfg, usage_filter="cut")
    assert min(engrave_layer.convert("L").getdata()) == 255
    assert min(cut_layer.convert("L").getdata()) < 245
    out = export_texture_cut_contours_svg(cut_layer, bounds=(0, 0, 10, 10), cfg=cfg, out=tmp_path / "cut.svg")
    text = out.read_text(encoding="utf-8")
    assert 'id="falcon_texture_cut"' in text
    assert '<path id="texture_cut_' in text


def test_cut_outline_preview_mask_keeps_only_binary_boundaries() -> None:
    img = Image.new("RGB", (8, 8), "white")
    for y in range(2, 6):
        for x in range(2, 6):
            img.putpixel((x, y), (80, 80, 80))
    out = render_texture_cut_outline_mask(img, threshold=245).convert("L")
    # Exterior stays white, interior of the filled square becomes white again,
    # and only the non-white/white frontier remains black.
    assert out.getpixel((0, 0)) == 255
    assert out.getpixel((3, 3)) == 255
    assert out.getpixel((2, 2)) == 0
    assert out.getpixel((5, 5)) == 0


def test_texture_projection_attach_to_mesh_modifies_real_mesh_not_decal(tmp_path: Path) -> None:
    tex = tmp_path / "attach.png"
    Image.new("RGB", (4, 4), "black").save(tex)
    mesh = WorkMesh(
        name="plate",
        vertices=[(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#B8B8B8",
    )
    params = TextureProjectionParams(
        texture_id="tex_attach",
        texture_path=tex,
        projection_mode="planar",
        usage="engrave",
        seed_face_index=0,
        projection_origin=(5, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=4,
        image_height=4,
        attach_to_mesh=True,
    )
    meshes = apply_texture_projection([mesh], [0], params)
    assert len(meshes) == 1
    assert not bool(getattr(meshes[0], "is_texture_decal", False))
    assert getattr(meshes[0], "uvs", None) is not None
    assert meshes[0].texture_projections[0].placement == "mesh"
    assert bool(getattr(meshes[0], "texture_attached_to_mesh", False))


def test_repeated_texture_export_tiles_beyond_single_image(tmp_path: Path) -> None:
    tex = tmp_path / "repeat.png"
    img = Image.new("RGB", (2, 2), "white")
    img.putpixel((0, 0), (0, 0, 0))
    img.save(tex)
    mesh = WorkMesh(
        name="wide_plate",
        vertices=[(0, 0, 0), (30, 0, 0), (30, 10, 0), (0, 10, 0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#B8B8B8",
    )
    params = TextureProjectionParams(
        texture_id="tex_repeat",
        texture_path=tex,
        projection_mode="planar",
        usage="engrave",
        seed_face_index=0,
        projection_origin=(15, 5, 0),
        projection_normal=(0, 0, 1),
        image_width=2,
        image_height=2,
        repeat=True,
        scale=0.25,
    )
    meshes = apply_texture_projection([mesh], [0], params)
    cfg = SimpleNamespace(dpi=100, page_margin_ratio=0.0, min_output_px=120)
    out = render_texture_layer_from_meshes(meshes, texture_assets_by_id={}, bounds=(0, 0, 30, 10), cfg=cfg)
    gray = out.convert("L")
    # Several dark regions should exist across the wide output, not just a single source stamp.
    w, h = gray.size
    dark_columns = [x for x in range(w) if min(gray.getpixel((x, y)) for y in range(h)) < 245]
    assert dark_columns
    assert max(dark_columns) - min(dark_columns) > w * 0.35

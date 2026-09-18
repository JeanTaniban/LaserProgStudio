# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "src" / "laserprog_studio" / "geometry_ops"


def _source(name: str) -> str:
    return (GEOM / name).read_text(encoding="utf-8")


def test_texture_projection_facade_is_small_and_backward_compatible() -> None:
    source = _source("texture_projection.py")

    assert "Stable aggregate import" in source
    assert "TextureProjectionParams" in source
    assert "apply_texture_projection" in source
    assert "compute_projected_uvs" in source
    assert "_is_texture_decal" in source
    assert "_store_texture_edit_frame" in source
    assert len(source.splitlines()) < 100


def test_texture_projection_geometry_is_split_by_responsibility() -> None:
    modules = {
        "texture_projection_types.py": ("class TextureProjectionParams", "@dataclass"),
        "texture_projection_vector.py": ("def _uv_from_plane_coords", "def _apply_uv_transform"),
        "texture_projection_faces.py": ("def _selected_face_ids_for_anchor", "def _store_texture_edit_frame"),
        "texture_projection_uv.py": ("def compute_projected_uvs", "def _uvs_from_projected_coords"),
        "texture_projection_decal.py": ("def _make_anchor_texture_decal", "def _clear_mesh_texture_metadata"),
        "texture_projection_operations.py": ("def apply_texture_projection_to_mesh", "def clear_texture_projection"),
    }
    for module_name, snippets in modules.items():
        source = _source(module_name)
        assert len(source.splitlines()) < 400
        for snippet in snippets:
            assert snippet in source


def test_pass12_documentation_exists() -> None:
    assert (ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_12.md").exists()

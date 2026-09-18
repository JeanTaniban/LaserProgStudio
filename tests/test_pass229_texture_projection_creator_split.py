# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def test_texture_projection_creator_tool_is_a_small_public_facade() -> None:
    source_path = Path("src/laserprog_studio/tooling/texture_projection_creator_tool.py")
    source = source_path.read_text(encoding="utf-8")

    assert len(source.splitlines()) < 470
    assert "class TextureProjectionCreatorTool" in source
    assert "class TextureProjectionTool" in source
    assert "TextureProjectorRuntime" in source
    assert "build_texture_projection_panel" in source
    assert "texture_project_operation" in source
    assert "def texture_params_from_values" not in source


def test_texture_projection_creator_runtime_ownership_is_split_by_responsibility() -> None:
    base = Path("src/laserprog_studio/tooling")
    expected_modules = {
        "_texture_projection_constants.py",
        "_texture_projection_geometry.py",
        "_texture_projection_operations.py",
        "_texture_projection_panel.py",
        "_texture_projection_params.py",
        "_texture_projection_projector.py",
    }

    assert expected_modules <= {path.name for path in base.glob("_texture_projection_*.py")}
    assert "def texture_params_from_values" in (base / "_texture_projection_params.py").read_text(encoding="utf-8")
    assert "class TextureProjectorRuntime" in (base / "_texture_projection_projector.py").read_text(encoding="utf-8")

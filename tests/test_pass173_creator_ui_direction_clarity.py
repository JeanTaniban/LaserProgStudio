# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.gizmos import (
    creator_ui_direction_layers,
    creator_ui_direction_markdown,
)
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool


def test_creator_ui_direction_is_public_and_unambiguous() -> None:
    layers = creator_ui_direction_layers()
    assert tuple(layer.id for layer in layers) == (
        "tool_core_analysis",
        "ui_catalog",
        "ui_motifs",
        "gizmo_catalog_tool",
        "creator_viewport_renderer",
    )

    markdown = creator_ui_direction_markdown()
    assert "Tool Core Analysis -> tool_api.ui_catalog / tool_api.ui_motifs -> Gizmo catalog -> Creator tools" in markdown
    assert "gizmo_catalog` is a viewer" in markdown
    assert "catalog tools do not hand-build samples" in markdown
    assert "Direct `ctx.gizmos.create_handle(...)` calls are low-level escape hatches" in markdown



def test_gizmo_catalog_source_is_a_projected_api_viewer_not_a_private_renderer() -> None:
    source = Path("src/laserprog_studio/tooling/gizmo_catalog_tool.py").read_text(encoding="utf-8")
    assert "ctx.projected_drawing" in source
    assert "import vtk" not in source
    assert "import vtk" not in source
    assert "PySide" not in source
    assert "pyvista" not in source.lower()
    assert "build_creator_ui_motifs" not in source
    assert GizmoCatalogCreatorTool.label == "Gizmo catalog"


def test_creator_ui_direction_docs_distinguish_interactive_motifs_from_projected_drawing() -> None:
    direction = Path("docs/tool_creator/00_creator_ui_direction.md").read_text(encoding="utf-8")
    catalog = Path("docs/tool_creator/16_gizmo_catalog_tool.md").read_text(encoding="utf-8")
    overlays = Path("docs/tool_creator/06_overlay_preview_gizmos.md").read_text(encoding="utf-8")
    readme = Path("docs/tool_creator/README.md").read_text(encoding="utf-8")

    assert "Tool Core Analysis" in direction
    assert "projected drawing" in catalog.lower()
    assert "only `ctx.projected_drawing` owns viewport content" in catalog.lower()
    assert "no family presets" in catalog.lower()
    assert "projected drawing 2D" in overlays
    assert "Gizmo catalog" in readme
    assert "reserved for the separate projected drawing 2D renderer" in readme


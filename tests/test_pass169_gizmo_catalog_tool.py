# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from laserprog_studio.tool_api.gizmos import gizmo_ui_catalog_markdown, iter_gizmo_ui_families
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool, GizmoCatalogTool
from laserprog_studio.tooling.ids import TOOL_GIZMO_CATALOG
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec
from laserprog_studio.ui.toolbar_catalog import get_toolbar_item_spec


@dataclass
class _AppCtx:
    tool_context: ToolContext
    active_scene: object | None = None
    owner: object | None = None


def test_gizmo_catalog_metadata_is_public_and_documented() -> None:
    families = iter_gizmo_ui_families()

    assert tuple(family.id for family in families) == ("actor_kinds", "actor_interactions", "visual_states", "point_styles", "line_styles", "manipulators", "previews", "overlays")
    assert any(item.id == "translate_arrow" for family in families for item in family.items)
    assert any(item.api.startswith("ctx.gizmos.translate") for family in families for item in family.items)
    assert any(item.id == "preview" for family in families if family.id == "line_styles" for item in family.items)
    assert any(item.id == "grabbable" for family in families if family.id == "actor_interactions" for item in family.items)

    markdown = gizmo_ui_catalog_markdown()
    assert "Creator API UI/Gizmo catalog" in markdown
    assert "ctx.overlay.show_window" in markdown


def test_gizmo_catalog_is_registered_as_creator_tool_and_palette_item() -> None:
    spec = get_tool_spec(TOOL_GIZMO_CATALOG)
    panel = get_tool_panel_spec(TOOL_GIZMO_CATALOG)
    toolbar = get_toolbar_item_spec("tool:gizmo_catalog")
    runtime = get_studio_tool(TOOL_GIZMO_CATALOG)

    assert spec is not None
    assert spec.panel_index == 33
    assert spec.selection_policy == "none"
    assert isinstance(runtime, GizmoCatalogTool)
    assert isinstance(runtime.creator, GizmoCatalogCreatorTool)
    assert panel is not None and panel.builder == "panel_declarative_creator_tool"
    assert toolbar is not None
    assert toolbar.code == "GZM"
    assert toolbar.default_visible is False



def test_gizmo_catalog_open_builds_only_projected_drawing_content() -> None:
    ctx = ToolContext()
    runtime = get_studio_tool(TOOL_GIZMO_CATALOG)

    runtime.on_open(_AppCtx(tool_context=ctx))

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "gizmo.catalog"
    assert set(ctx.inspector.panel.field_ids()) == {
        "catalog_test",
        "show_projected_drawing_2d",
        "projected_drawing_report",
        "interaction_report",
        "visible_report",
        "benchmark_report",
        "benchmark_file",
        "catalog_actions",
        "benchmark_actions",
    }
    snapshot = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert (len(snapshot.points), len(snapshot.lines), len(snapshot.faces), len(snapshot.handles)) == (1, 2, 1, 3)
    all_world_points = [point.position for point in snapshot.points]
    all_world_points.extend(world for line in snapshot.lines for world in line.points)
    all_world_points.extend(world for face in snapshot.faces for world in face.vertices)
    all_world_points.extend(handle.position for handle in snapshot.handles)
    assert all(world[2] == 0.0 for world in all_world_points)
    assert ctx.gizmos.handles(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert ctx.transform_gizmos.handles(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert ctx.preview.items(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert len(ctx.selection.actors(owner_tool=TOOL_GIZMO_CATALOG)) == len(snapshot.primitives)
    assert not any(window.owner_tool == TOOL_GIZMO_CATALOG for window in ctx.overlay.windows.values())

    ctx.inspector.update_value("show_projected_drawing_2d", False)
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).visible is False
    ctx.inspector.trigger("show_all")
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).visible is True

    runtime.on_close(_AppCtx(tool_context=ctx))
    assert ctx.inspector.panel is None
    assert ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG).primitives == ()


def test_gizmo_catalog_docs_and_tool_source_use_only_projected_drawing_api() -> None:
    source = Path("src/laserprog_studio/tooling/gizmo_catalog_tool.py").read_text(encoding="utf-8")
    docs = Path("docs/tool_creator/16_gizmo_catalog_tool.md").read_text(encoding="utf-8")

    assert "ctx.projected_drawing" in source
    assert "build_creator_ui_motifs" not in source
    assert "iter_creator_ui_families" not in source
    assert "PySide6" not in source
    assert "pyvista" not in source.lower()
    assert "import vtk" not in source
    assert "Handle shapes" in docs
    assert "Actor kinds" in docs
    assert "Drag arrows" in docs


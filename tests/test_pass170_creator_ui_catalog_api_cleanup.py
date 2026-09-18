# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api import styles, ui_catalog
from laserprog_studio.tool_api.gizmos import creator_ui_catalog_markdown, iter_creator_ui_families, recommendations_for_tool
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool
from laserprog_studio.tooling.ids import TOOL_GIZMO_CATALOG


def test_creator_ui_catalog_is_single_public_vocabulary() -> None:
    families = iter_creator_ui_families()
    assert tuple(family.id for family in families) == (
        "actor_kinds",
        "actor_interactions",
        "visual_states",
        "point_styles",
        "line_styles",
        "manipulators",
        "previews",
        "overlays",
    )
    assert ui_catalog.get_creator_ui_family("point_styles") is not None
    assert ui_catalog.get_creator_ui_family(ui_catalog.CreatorUiFamilyId.LINE_STYLES) is not None

    ids_by_family = {family.id: {item.id for item in family.items} for family in families}
    assert ids_by_family["point_styles"] == {style.id for style in styles.list_point_styles()}
    assert ids_by_family["line_styles"] == {style.id for style in styles.list_line_styles()}
    assert {"point", "line", "circle", "arc", "polyline", "custom"}.issubset(ids_by_family["actor_kinds"])
    assert {"fixed", "selectable", "grabbable"} == ids_by_family["actor_interactions"]
    assert {"auto", "hover", "selected", "grabbed", "disabled"}.issubset(ids_by_family["visual_states"])


def test_recommendations_only_reference_official_styles() -> None:
    point_style_ids = {style.id for style in styles.list_point_styles()}
    line_style_ids = {style.id for style in styles.list_line_styles()}
    family_ids = {family.id for family in iter_creator_ui_families()}
    assert "line_styles" in family_ids

    for recommendation in ui_catalog.iter_tool_ui_recommendations():
        assert set(recommendation.point_styles).issubset(point_style_ids)
        assert set(recommendation.line_styles).issubset(line_style_ids)

    texture = recommendations_for_tool("texture_projector")
    assert texture is not None
    assert "target" in texture.point_styles
    assert "preview" in texture.line_styles


def test_catalog_markdown_documents_api_not_diagnostic_internals() -> None:
    markdown = creator_ui_catalog_markdown()
    assert "Creator API UI/Gizmo catalog" in markdown
    assert "Actor interactions" in markdown
    assert "Line styles" in markdown
    assert "ctx.gizmos.translate" in markdown
    assert "tool_core/diagnostic" not in markdown



def test_gizmo_catalog_tool_is_decoupled_from_the_legacy_motif_catalog() -> None:
    source = Path("src/laserprog_studio/tooling/gizmo_catalog_tool.py").read_text(encoding="utf-8")
    assert "tool_core.gizmos.catalog" not in source
    assert "iter_creator_ui_families" not in source
    assert "build_creator_ui_motifs" not in source
    assert "ctx.projected_drawing" in source

    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)
    snapshot = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert (len(snapshot.points), len(snapshot.lines), len(snapshot.faces), len(snapshot.handles)) == (1, 2, 1, 3)
    assert len(ctx.selection.actors(owner_tool=TOOL_GIZMO_CATALOG)) == len(snapshot.primitives)
    assert ctx.gizmos.handles(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert ctx.preview.items(owner_tool=TOOL_GIZMO_CATALOG) == ()
    field_ids = set(ctx.inspector.panel.field_ids())
    assert "catalog_test" in field_ids
    assert "show_projected_drawing_2d" in field_ids
    assert not any(field_id.startswith("show_actor_") for field_id in field_ids)
    assert not any(field_id.startswith("show_point_styles") for field_id in field_ids)


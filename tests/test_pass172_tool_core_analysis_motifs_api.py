# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_api.gizmos import (
    apply_creator_ui_motif_visibility,
    build_creator_ui_motifs,
    iter_creator_ui_motif_families,
)
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.gizmo_catalog_tool import GizmoCatalogCreatorTool
from laserprog_studio.tooling.ids import TOOL_GIZMO_CATALOG


def test_tool_core_analysis_visual_motifs_are_public_api() -> None:
    families = tuple(family.id for family in iter_creator_ui_motif_families())
    assert families == (
        "actor_kinds",
        "actor_interactions",
        "visual_states",
        "point_styles",
        "line_styles",
        "manipulators",
        "previews",
        "overlays",
    )

    ctx = ToolContext()
    snapshot = build_creator_ui_motifs(ctx, owner_tool="test.pass172")

    assert snapshot.actors >= 6
    assert snapshot.handles >= 90
    assert snapshot.previews >= 60
    assert snapshot.labels >= 20
    assert {handle.style_id for handle in ctx.gizmos.handles(owner_tool="test.pass172")} >= {"minimal", "target", "translate_arrow"}
    assert any(str(item.id).startswith("test.pass172:actor_kinds:") for item in ctx.preview.items(owner_tool="test.pass172"))
    assert any(str(item.id).startswith("test.pass172:previews:") for item in ctx.preview.items(owner_tool="test.pass172"))
    assert {window.id for window in ctx.overlay.windows.values() if window.owner_tool == "test.pass172"} >= {
        "test.pass172:overlay:palette",
        "test.pass172:overlay:popover",
        "test.pass172:overlay:tooltip",
    }


def test_motif_visibility_hides_only_official_family_without_rebuilding_a_fake_ui() -> None:
    ctx = ToolContext()
    build_creator_ui_motifs(ctx, owner_tool="test.pass172")

    apply_creator_ui_motif_visibility(ctx, owner_tool="test.pass172", visible_by_family={"point_styles": False})

    point_style_handles = [
        handle
        for handle in ctx.gizmos.handles(owner_tool="test.pass172")
        if str(handle.kind).startswith("catalog:point_styles:")
    ]
    actor_handles = [
        handle
        for handle in ctx.gizmos.handles(owner_tool="test.pass172")
        if str(handle.kind).startswith("catalog:actor_kinds:")
    ]
    assert point_style_handles and all(not handle.visible for handle in point_style_handles)
    assert actor_handles and any(handle.visible for handle in actor_handles)



def test_gizmo_catalog_is_now_a_projected_drawing_only_viewer() -> None:
    source = Path("src/laserprog_studio/tooling/gizmo_catalog_tool.py").read_text(encoding="utf-8")
    assert "build_creator_ui_motifs" not in source
    assert "ctx.projected_drawing" in source
    assert "draw2d.point" in source
    assert "draw2d.line" in source
    assert "draw2d.face" in source

    ctx = ToolContext()
    tool = GizmoCatalogCreatorTool()
    tool.on_open(ctx)
    snapshot = ctx.projected_drawing.snapshot(TOOL_GIZMO_CATALOG)
    assert snapshot.primitives
    assert ctx.gizmos.handles(owner_tool=TOOL_GIZMO_CATALOG) == ()
    assert ctx.preview.items(owner_tool=TOOL_GIZMO_CATALOG) == ()


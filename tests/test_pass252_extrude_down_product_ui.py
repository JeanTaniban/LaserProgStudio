# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.extrude_down_tool import ExtrudeDownCreatorTool
from laserprog_studio.tooling.ids import TOOL_MOD_EXTRUDE_DOWN
from laserprog_studio.tooling.mesh_extrude_down import (
    CUSTOM_PRESET_ID,
    EXTRUDE_DOWN_FEEDBACK_WINDOW_ID,
    selected_indices_text,
    validate_extrude_down_targets,
)
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _box_mesh(name: str = "solid") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (-1.0, -1.0, 0.0),
            (1.0, -1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 1.0, 0.0),
            (-1.0, -1.0, 10.0),
            (1.0, -1.0, 10.0),
            (1.0, 1.0, 10.0),
            (-1.0, 1.0, 10.0),
        ],
        triangles=[
            (0, 1, 2),
            (0, 2, 3),
            (4, 6, 5),
            (4, 7, 6),
            (0, 4, 5),
            (0, 5, 1),
            (1, 5, 6),
            (1, 6, 2),
            (2, 6, 7),
            (2, 7, 3),
            (3, 7, 4),
            (3, 4, 0),
        ],
        color="#AABBCC",
    )


def _ctx_with_meshes() -> tuple[ToolContext, ModelStore]:
    ctx = ToolContext()
    store = ModelStore()
    store.set_meshes([_box_mesh("a"), _box_mesh("b")], push_undo=False)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    return ctx, store


def test_pass252_extrude_down_has_product_presets_preflight_apply_and_overlay() -> None:
    spec = get_tool_spec(TOOL_MOD_EXTRUDE_DOWN)
    panel_spec = get_tool_panel_spec(TOOL_MOD_EXTRUDE_DOWN)
    assert spec is not None
    assert spec.selection_policy == "multi"
    assert panel_spec is not None
    assert panel_spec.builder == "panel_declarative_creator_tool"

    ctx, _store = _ctx_with_meshes()
    tool = ExtrudeDownCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "modifier.extrude_down"
    assert ctx.inspector.panel.auto_preview is not None
    assert ctx.inspector.panel.auto_preview.action_id == "preview"
    assert ctx.workflow.describe()["steps"][1]["id"] == "tune"
    assert EXTRUDE_DOWN_FEEDBACK_WINDOW_ID in ctx.overlay.windows
    assert "Ready to extrude 1 part" in ctx.inspector.value("preflight_check")
    assert selected_indices_text((0, 2)) == "00, 02"

    ctx.inspector.update_value("extrude_down_preset", "mid_body")
    assert ctx.inspector.value("plane_ratio") == 50.0
    assert ctx.inspector.value("plane_z") == 5.0
    assert "middle" in ctx.inspector.value("preset_note")

    ctx.inspector.update_value("plane_z", 4.0)
    assert ctx.inspector.value("extrude_down_preset") == CUSTOM_PRESET_ID


def test_pass252_extrude_down_preflight_blocks_empty_selection() -> None:
    ctx, _store = _ctx_with_meshes()
    tool = ExtrudeDownCreatorTool()
    tool.open(ctx)
    ctx.scene_selection.clear()
    tool.on_scene_selection_changed(ctx)

    check = validate_extrude_down_targets(ctx, ctx.inspector.values())
    assert not check.ok
    assert "Select one or more parts" in check.message

    ctx.inspector.trigger("preview")
    assert "Select one or more parts" in ctx.inspector.value("preflight_check")
    assert ctx.inspector.field_state("preflight_check").error


def test_pass252_extrude_down_previews_and_applies_support() -> None:
    ctx, store = _ctx_with_meshes()
    tool = ExtrudeDownCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("extrude_down_preset", "low_foot")

    before_triangles = len(store.committed_meshes[0].triangles)
    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert len(store.preview_meshes[0].triangles) > before_triangles
    assert store.preview_meshes[0].name == "a extruded down"
    assert "Extrude-down preview ready" in ctx.inspector.value("extrude_down_report")
    assert ctx.inspector.field_state("preflight_check").error is None

    ctx.inspector.trigger("apply_extrude_down")
    assert not store.has_preview
    assert store.committed_meshes[0].name == "a extruded down"
    assert len(store.committed_meshes[0].triangles) > before_triangles

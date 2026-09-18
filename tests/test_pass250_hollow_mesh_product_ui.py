# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MOD_HOLLOW
from laserprog_studio.tooling.mesh_hollow import (
    CUSTOM_PRESET_ID,
    HOLLOW_FEEDBACK_WINDOW_ID,
    hollow_preset_note,
    validate_hollow_targets,
)
from laserprog_studio.tooling.hollow_tool import HollowCreatorTool
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _closed_mesh(name: str = "solid") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (0.0, 0.0, 0.0),
            (10.0, 0.0, 0.0),
            (0.0, 10.0, 0.0),
            (0.0, 0.0, 10.0),
        ],
        triangles=[(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
        color="#CCCCCC",
    )


def _ctx_with_meshes() -> tuple[ToolContext, ModelStore]:
    ctx = ToolContext()
    store = ModelStore()
    store.set_meshes([_closed_mesh("a"), _closed_mesh("b")], push_undo=False)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    return ctx, store


def test_pass250_hollow_mesh_has_product_presets_preflight_and_overlay() -> None:
    spec = get_tool_spec(TOOL_MOD_HOLLOW)
    panel_spec = get_tool_panel_spec(TOOL_MOD_HOLLOW)
    assert spec is not None
    assert spec.selection_policy == "multi"
    assert panel_spec is not None
    assert panel_spec.builder == "panel_declarative_creator_tool"

    ctx, _store = _ctx_with_meshes()
    tool = HollowCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "modifier.hollow"
    assert ctx.inspector.panel.auto_preview is not None
    assert ctx.inspector.panel.auto_preview.action_id == "preview"
    assert ctx.workflow.describe()["steps"][1]["id"] == "tune"
    assert HOLLOW_FEEDBACK_WINDOW_ID in ctx.overlay.windows
    assert "Ready to hollow 1 part" in ctx.inspector.value("preflight_check")

    ctx.inspector.update_value("hollow_preset", "strong_wall")
    assert ctx.inspector.value("thickness_mm") == 3.2
    assert "Thicker wall" in ctx.inspector.value("preset_note")

    ctx.inspector.update_value("thickness_mm", 1.4)
    assert ctx.inspector.value("hollow_preset") == CUSTOM_PRESET_ID
    assert ctx.inspector.value("preset_note") == hollow_preset_note(CUSTOM_PRESET_ID)


def test_pass250_hollow_mesh_preflight_blocks_empty_selection() -> None:
    ctx, _store = _ctx_with_meshes()
    tool = HollowCreatorTool()
    tool.open(ctx)
    ctx.scene_selection.clear()
    tool.on_scene_selection_changed(ctx)

    check = validate_hollow_targets(ctx, ctx.inspector.values())
    assert not check.ok
    assert "Select one or more closed parts" in check.message

    ctx.inspector.trigger("preview")
    assert "Select one or more closed parts" in ctx.inspector.value("preflight_check")
    assert ctx.inspector.field_state("preflight_check").error


def test_pass250_hollow_mesh_previews_and_applies_shell() -> None:
    ctx, store = _ctx_with_meshes()
    tool = HollowCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("hollow_preset", "thin_shell")

    before_triangles = len(store.committed_meshes[0].triangles)
    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert len(store.preview_meshes[0].triangles) > before_triangles
    assert store.preview_meshes[0].name == "a hollow"
    assert "Hollow preview ready" in ctx.inspector.value("hollow_report")
    assert ctx.inspector.field_state("preflight_check").error is None

    ctx.inspector.trigger("apply_hollow")
    assert not store.has_preview
    assert store.committed_meshes[0].name == "a hollow"
    assert len(store.committed_meshes[0].triangles) > before_triangles

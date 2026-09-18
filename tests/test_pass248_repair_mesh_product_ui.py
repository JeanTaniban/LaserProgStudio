# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MOD_REPAIR
from laserprog_studio.tooling.mesh_repair import (
    CUSTOM_PRESET_ID,
    REPAIR_FEEDBACK_WINDOW_ID,
    repair_preset_note,
    validate_repair_targets,
)
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.tooling.repair_tool import RepairMeshCreatorTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _dirty_mesh(name: str = "dirty") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
        ],
        triangles=[(0, 1, 2), (0, 1, 2), (0, 2, 3)],
        color="#CC8844",
    )


def _ctx_with_meshes() -> tuple[ToolContext, ModelStore]:
    ctx = ToolContext()
    store = ModelStore()
    store.set_meshes([_dirty_mesh("a"), _dirty_mesh("b")], push_undo=False)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    return ctx, store


def test_pass248_repair_mesh_has_product_presets_and_overlay() -> None:
    spec = get_tool_spec(TOOL_MOD_REPAIR)
    panel_spec = get_tool_panel_spec(TOOL_MOD_REPAIR)
    assert spec is not None
    assert spec.selection_policy == "multi"
    assert panel_spec is not None
    assert panel_spec.builder == "panel_declarative_creator_tool"

    ctx, _store = _ctx_with_meshes()
    tool = RepairMeshCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "modifier.repair"
    assert ctx.inspector.panel.auto_preview is not None
    assert ctx.inspector.panel.auto_preview.action_id == "preview"
    assert ctx.workflow.describe()["steps"][1]["id"] == "tune"
    assert REPAIR_FEEDBACK_WINDOW_ID in ctx.overlay.windows
    assert "Ready to repair 1 part" in ctx.inspector.value("preflight_check")

    ctx.inspector.update_value("repair_preset", "aggressive_print_fix")
    assert ctx.inspector.value("tolerance_mm") == 0.05
    assert "Stronger cleanup" in ctx.inspector.value("preset_note")

    ctx.inspector.update_value("tolerance_mm", 0.02)
    assert ctx.inspector.value("repair_preset") == CUSTOM_PRESET_ID
    assert ctx.inspector.value("preset_note") == repair_preset_note(CUSTOM_PRESET_ID)


def test_pass248_repair_mesh_preflight_blocks_empty_selection() -> None:
    ctx, _store = _ctx_with_meshes()
    tool = RepairMeshCreatorTool()
    tool.open(ctx)
    ctx.scene_selection.clear()
    tool.on_scene_selection_changed(ctx)

    check = validate_repair_targets(ctx, ctx.inspector.values())
    assert not check.ok
    assert "Select one or more parts" in check.message

    ctx.inspector.trigger("preview")
    assert "Select one or more parts" in ctx.inspector.value("preflight_check")
    assert ctx.inspector.field_state("preflight_check").error


def test_pass248_repair_mesh_previews_and_applies_repaired_part() -> None:
    ctx, store = _ctx_with_meshes()
    tool = RepairMeshCreatorTool()
    tool.open(ctx)

    before_triangles = len(store.committed_meshes[0].triangles)
    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert len(store.preview_meshes[0].triangles) <= before_triangles
    assert store.preview_meshes[0].name == "a"
    assert store.preview_meshes[0].color == "#CC8844"
    assert "Repair preview ready" in ctx.inspector.value("repair_report")
    assert ctx.inspector.field_state("preflight_check").error is None

    ctx.inspector.trigger("apply_repair")
    assert not store.has_preview
    assert len(store.committed_meshes[0].triangles) <= before_triangles

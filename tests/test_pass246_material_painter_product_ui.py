# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.material import MeshMaterial
from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MATERIAL
from laserprog_studio.tooling.material_tool import MaterialCreatorTool
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _mesh(name: str) -> WorkMesh:
    return WorkMesh(name=name, vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)], triangles=[(0, 1, 2)], color="#B8B8B8")


def test_pass246_material_painter_is_declarative_with_presets_and_feedback() -> None:
    spec = get_tool_spec(TOOL_MATERIAL)
    panel_spec = get_tool_panel_spec(TOOL_MATERIAL)

    assert spec is not None
    assert spec.selection_policy == "multi"
    assert spec.open_without_initial_selection is True
    assert panel_spec is not None
    assert panel_spec.builder == "panel_declarative_creator_tool"

    ctx = ToolContext()
    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((1,), active_index=1)

    tool = MaterialCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "material.painter"
    assert ctx.inspector.panel.auto_preview is not None
    assert ctx.inspector.panel.auto_preview.action_id == "preview"
    assert ctx.workflow.describe()["steps"][0]["requirement"] == "scene_objects"
    assert set(ctx.modes.describe(owner_tool=TOOL_MATERIAL)["tools"][0]["modes"]) == {"paint", "all"}
    assert "material.painter.feedback" in ctx.overlay.windows

    ctx.inspector.update_value("preset_id", "anodized_aluminum")
    assert ctx.inspector.value("material_name") == "Anodized aluminum"
    assert ctx.inspector.value("metallic") > 0.5
    assert "Metal look" in ctx.inspector.value("preset_note")

    ctx.inspector.update_value("material_color", "#123456")
    assert ctx.inspector.value("preset_id") == "custom"
    assert ctx.inspector.value("material_color") == "#123456"


def test_pass246_material_painter_previews_selected_and_all_targets() -> None:
    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = MaterialCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("material_name", "Matthis blue")
    ctx.inspector.update_value("material_color", "#0055CC")
    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert isinstance(store.preview_meshes[0].material, MeshMaterial)
    assert store.preview_meshes[0].material.name == "Matthis blue"
    assert store.preview_meshes[0].material.base_color == "#0055CC"
    assert store.preview_meshes[1].material is None
    assert ctx.inspector.field_state("apply_check").error is None

    ctx.inspector.trigger("apply_material")
    assert not store.has_preview
    assert store.committed_meshes[0].material.base_color == "#0055CC"

    ctx.inspector.update_value("target_scope", "all")
    ctx.inspector.update_value("preset_id", "birch_plywood")
    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert all(mesh.material and mesh.material.name == "Birch plywood" for mesh in store.preview_meshes)
    assert ctx.modes.describe(owner_tool=TOOL_MATERIAL)["tools"][0]["active"] == "all"


def test_pass246_material_painter_blocks_empty_selected_target() -> None:
    store = ModelStore()
    store.set_meshes([_mesh("a")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)

    tool = MaterialCreatorTool()
    tool.open(ctx)
    assert ctx.inspector.trigger("preview").action_id == "preview"

    assert not store.has_preview
    assert "Select at least one part" in ctx.inspector.value("apply_check")
    assert ctx.inspector.field_state("apply_check").error

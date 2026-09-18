# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MOD_SIMPLIFY
from laserprog_studio.tooling.mesh_simplify import (
    CUSTOM_PRESET_ID,
    SIMPLIFY_FEEDBACK_WINDOW_ID,
    simplify_preset_note,
    validate_simplify_targets,
)
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.tooling.simplify_tool import SimplifyCreatorTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _mesh(name: str = "dense") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (1.0, 1.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.5, 0.5, 1.0),
        ],
        triangles=[(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4), (0, 1, 2), (0, 2, 3)],
        color="#88AACC",
    )


def _ctx_with_meshes() -> tuple[ToolContext, ModelStore]:
    ctx = ToolContext()
    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    return ctx, store


def test_pass249_simplify_mesh_has_presets_preflight_and_overlay() -> None:
    spec = get_tool_spec(TOOL_MOD_SIMPLIFY)
    panel_spec = get_tool_panel_spec(TOOL_MOD_SIMPLIFY)
    assert spec is not None
    assert spec.selection_policy == "multi"
    assert panel_spec is not None
    assert panel_spec.builder == "panel_declarative_creator_tool"

    ctx, _store = _ctx_with_meshes()
    tool = SimplifyCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "modifier.simplify"
    assert ctx.inspector.panel.auto_preview is not None
    assert ctx.inspector.panel.auto_preview.action_id == "preview"
    assert ctx.workflow.describe()["steps"][1]["id"] == "tune"
    assert SIMPLIFY_FEEDBACK_WINDOW_ID in ctx.overlay.windows
    assert "Ready to simplify 1 part" in ctx.inspector.value("preflight_check")

    ctx.inspector.update_value("simplify_preset", "viewport_proxy")
    assert ctx.inspector.value("reduction_percent") == 75.0
    assert ctx.inspector.value("preserve_topology") is False
    assert "Strong visual" in ctx.inspector.value("preset_note")

    ctx.inspector.update_value("reduction_percent", 40.0)
    assert ctx.inspector.value("simplify_preset") == CUSTOM_PRESET_ID
    assert ctx.inspector.value("preset_note") == simplify_preset_note(CUSTOM_PRESET_ID)


def test_pass249_simplify_mesh_preflight_blocks_empty_selection() -> None:
    ctx, _store = _ctx_with_meshes()
    tool = SimplifyCreatorTool()
    tool.open(ctx)
    ctx.scene_selection.clear()
    tool.on_scene_selection_changed(ctx)

    check = validate_simplify_targets(ctx, ctx.inspector.values())
    assert not check.ok
    assert "Select one or more parts" in check.message

    ctx.inspector.trigger("preview")
    assert "Select one or more parts" in ctx.inspector.value("preflight_check")
    assert ctx.inspector.field_state("preflight_check").error


def test_pass249_simplify_mesh_previews_and_applies_selected_part(monkeypatch) -> None:
    import laserprog_studio.tooling.simplify_tool as simplify_module

    def fake_simplify(meshes, selected, *, reduction, preserve_topology):
        out = list(meshes)
        for index in selected:
            item = out[int(index)]
            item.triangles = item.triangles[:3]
            item.name = f"{item.name} simplified"
        return SimpleNamespace(ok=True, meshes=out, warnings=(f"ratio={reduction:.2f}; preserve={preserve_topology}",), errors=())

    monkeypatch.setattr(simplify_module, "simplify_selected_meshes", fake_simplify)

    ctx, store = _ctx_with_meshes()
    tool = SimplifyCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("simplify_preset", "print_safe")

    before_triangles = len(store.committed_meshes[0].triangles)
    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert len(store.preview_meshes[0].triangles) < before_triangles
    assert store.preview_meshes[0].name == "a simplified"
    assert "Simplify preview ready" in ctx.inspector.value("simplify_report")
    assert ctx.inspector.field_state("preflight_check").error is None

    ctx.inspector.trigger("apply_simplify")
    assert not store.has_preview
    assert store.committed_meshes[0].name == "a simplified"
    assert len(store.committed_meshes[0].triangles) == 3

# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MOD_SPLIT
from laserprog_studio.tooling.mesh_split import (
    CUSTOM_PRESET_ID,
    SPLIT_FEEDBACK_WINDOW_ID,
    selected_indices_text,
    split_preset_note,
    validate_split_targets,
)
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.tooling.split_tool import SplitPlaneCreatorTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def _split_mesh(name: str = "solid") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (-1.0, -1.0, -1.0),
            (1.0, -1.0, -1.0),
            (1.0, 1.0, -1.0),
            (-1.0, 1.0, -1.0),
            (-1.0, -1.0, 1.0),
            (1.0, -1.0, 1.0),
            (1.0, 1.0, 1.0),
            (-1.0, 1.0, 1.0),
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
    store.set_meshes([_split_mesh("a"), _split_mesh("b")], push_undo=False)
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)
    return ctx, store


def test_pass251_split_mesh_has_product_presets_preflight_and_overlay() -> None:
    spec = get_tool_spec(TOOL_MOD_SPLIT)
    panel_spec = get_tool_panel_spec(TOOL_MOD_SPLIT)
    assert spec is not None
    assert spec.selection_policy == "multi"
    assert panel_spec is not None
    assert panel_spec.builder == "panel_declarative_creator_tool"

    ctx, _store = _ctx_with_meshes()
    tool = SplitPlaneCreatorTool()
    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "modifier.split"
    assert ctx.inspector.panel.auto_preview is not None
    assert ctx.inspector.panel.auto_preview.action_id == "preview"
    assert ctx.workflow.describe()["steps"][1]["id"] == "tune"
    assert SPLIT_FEEDBACK_WINDOW_ID in ctx.overlay.windows
    assert "Ready to split 1 part" in ctx.inspector.value("preflight_check")
    assert selected_indices_text((0, 2)) == "00, 02"

    ctx.inspector.update_value("split_preset", "center_x")
    assert ctx.inspector.value("ry_deg") == 90.0
    assert "vertical YZ" in ctx.inspector.value("preset_note")

    ctx.inspector.update_value("offset_mm", 3.0)
    assert ctx.inspector.value("split_preset") == CUSTOM_PRESET_ID
    assert ctx.inspector.value("preset_note") == split_preset_note(CUSTOM_PRESET_ID)


def test_pass251_split_mesh_preflight_blocks_empty_selection() -> None:
    ctx, _store = _ctx_with_meshes()
    tool = SplitPlaneCreatorTool()
    tool.open(ctx)
    ctx.scene_selection.clear()
    tool.on_scene_selection_changed(ctx)

    check = validate_split_targets(ctx, ctx.inspector.values())
    assert not check.ok
    assert "Select one or more parts" in check.message

    ctx.inspector.trigger("preview")
    assert "Select one or more parts" in ctx.inspector.value("preflight_check")
    assert ctx.inspector.field_state("preflight_check").error


def test_pass251_split_mesh_previews_and_applies_plane(monkeypatch) -> None:
    import laserprog_studio.tooling.split_tool as split_module

    def fake_split(meshes, selected, *, origin, normal, tolerance):
        out = list(meshes)
        original = out[selected[0]]
        first = _split_mesh(f"{original.name} split A")
        second = _split_mesh(f"{original.name} split B")
        out[selected[0]] = first
        out.append(second)
        return out, (selected[0], len(out) - 1), 1, 2

    monkeypatch.setattr(split_module, "split_selected_meshes_by_plane", fake_split)

    ctx, store = _ctx_with_meshes()
    tool = SplitPlaneCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("split_preset", "center_y")

    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert len(store.preview_meshes) == 3
    assert store.preview_meshes[0].name == "a split A"
    assert store.preview_meshes[2].name == "a split B"
    assert "Split preview ready" in ctx.inspector.value("split_report")
    assert ctx.inspector.field_state("preflight_check").error is None

    ctx.inspector.trigger("apply_split")
    assert not store.has_preview
    assert len(store.committed_meshes) == 3
    assert store.committed_meshes[0].name == "a split A"

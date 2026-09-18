# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cavity_volume_tool import CavityVolumeCreatorTool
from laserprog_studio.tooling.hollow_tool import HollowCreatorTool
from laserprog_studio.tooling.simplify_tool import SimplifyCreatorTool


def _mesh(name: str = "part") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[
            (0.0, 0.0, 0.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
        ],
        triangles=[(0, 2, 1), (0, 1, 3), (1, 2, 3), (2, 0, 3)],
        color="#CCC",
    )


def test_scene_selection_prefers_live_host_selection_over_empty_model_store() -> None:
    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    owner = SimpleNamespace(selected_indices=[1], active_index=1, mesh_list=None)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)

    assert store.selected_mesh_indices == []
    assert ctx.scene_selection.selected_indices() == (1,)
    assert store.selected_mesh_indices == [1]

    owner.selected_indices = []
    owner.active_index = None
    assert ctx.scene_selection.selected_indices() == ()
    assert store.selected_mesh_indices == []


def test_simplify_preview_uses_selection_made_after_tool_open(monkeypatch) -> None:
    import laserprog_studio.tooling.simplify_tool as simplify_module

    def fake_simplify(meshes, selected_indices, *, reduction, preserve_topology):
        out = list(meshes)
        for idx in selected_indices:
            out[int(idx)].name = f"{out[int(idx)].name} simplified"
            out[int(idx)].triangles = out[int(idx)].triangles[:2]
        return SimpleNamespace(ok=True, meshes=out, warnings=(), errors=())

    monkeypatch.setattr(simplify_module, "simplify_selected_meshes", fake_simplify)

    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    owner = SimpleNamespace(selected_indices=[], active_index=None, mesh_list=None)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)

    tool = SimplifyCreatorTool()
    tool.open(ctx)
    assert ctx.inspector.value("selection_summary") == "No mesh selected."

    owner.selected_indices = [1]
    owner.active_index = 1
    tool.on_scene_selection_changed(ctx)

    assert ctx.inspector.value("selection_summary") == "01"
    assert ctx.inspector.trigger("preview").action_id == "preview"
    assert store.has_preview
    assert store.preview_meshes[1].name == "b simplified"


def test_hollow_preview_uses_selection_made_after_tool_open(monkeypatch) -> None:
    import laserprog_studio.tooling.hollow_tool as hollow_module

    def fake_hollow(meshes, selected_indices, *, thickness):
        out = list(meshes)
        for idx in selected_indices:
            out[int(idx)].name = f"{out[int(idx)].name} hollow"
            out[int(idx)].triangles = list(out[int(idx)].triangles) + [(0, 1, 2)]
        return SimpleNamespace(ok=True, meshes=out, warnings=(), errors=())

    monkeypatch.setattr(hollow_module, "hollow_selected_meshes", fake_hollow)

    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    owner = SimpleNamespace(selected_indices=[], active_index=None, mesh_list=None)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)

    tool = HollowCreatorTool()
    tool.open(ctx)
    owner.selected_indices = [0]
    owner.active_index = 0
    tool.on_scene_selection_changed(ctx)

    assert ctx.inspector.value("selection_summary") == "00"
    assert ctx.inspector.trigger("preview").action_id == "preview"
    assert store.has_preview
    assert store.preview_meshes[0].name == "a hollow"


def test_cavity_panel_selection_summary_updates_from_host_selection() -> None:
    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    owner = SimpleNamespace(selected_indices=[], active_index=None, mesh_list=None)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)

    tool = CavityVolumeCreatorTool()
    tool.open(ctx)
    assert ctx.inspector.value("selection_summary") == "No scene object selected."

    owner.selected_indices = [0, 1]
    owner.active_index = 1
    tool.on_scene_selection_changed(ctx)

    assert ctx.inspector.value("selection_summary") == "00, 01"
    assert "Click Measure" in ctx.inspector.value("volume_report")

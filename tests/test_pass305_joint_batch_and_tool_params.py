# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from pathlib import Path

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_api import inspector
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.joint_tool import JointCreatorTool


def _mesh(name: str, x: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(x, 0.0, 0.0), (x + 1.0, 0.0, 0.0), (x, 1.0, 0.0)],
        triangles=[(0, 1, 2)],
        color="#CCC",
    )


def test_pass305_inspector_persists_owner_tool_parameters(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LASERPROG_TOOL_PARAMETER_PREFERENCES", str(tmp_path / "tool_params.json"))
    panel = inspector.panel(
        "Persisted",
        id="persisted.panel",
        owner_tool="tool.persisted",
        sections=[inspector.section("Values", [inspector.float_field("width", "Width", default=10.0), inspector.bool_field("flag", "Flag", default=False)])],
    )

    ctx = ToolContext()
    ctx.inspector.set_panel(panel)
    ctx.inspector.update_value("width", 42.5)
    ctx.inspector.update_value("flag", True)

    reopened = ToolContext()
    reopened.inspector.set_panel(panel)

    assert reopened.inspector.value("width") == 42.5
    assert reopened.inspector.value("flag") is True


def test_pass305_unowned_test_panels_do_not_persist_by_panel_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LASERPROG_TOOL_PARAMETER_PREFERENCES", str(tmp_path / "tool_params.json"))
    panel = inspector.panel("Scratch", id="scratch.panel", sections=[inspector.section("Values", [inspector.float_field("width", "Width", default=10.0)])])

    ctx = ToolContext()
    ctx.inspector.set_panel(panel)
    ctx.inspector.update_value("width", 99.0)

    reopened = ToolContext()
    reopened.inspector.set_panel(panel)

    assert reopened.inspector.value("width") == 10.0


def test_pass305_joint_preview_batches_multiple_pairs_before_single_apply(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LASERPROG_TOOL_PARAMETER_PREFERENCES", str(tmp_path / "tool_params.json"))
    import laserprog_studio.tooling.joint_tool as joint_module

    def fake_joint(mesh_a: WorkMesh, mesh_b: WorkMesh, **_kwargs):
        a = copy.deepcopy(mesh_a)
        b = copy.deepcopy(mesh_b)
        a.name = f"{a.name}|joint"
        b.name = f"{b.name}|joint"
        return a, b

    monkeypatch.setattr(joint_module, "apply_tab_slot_simple", fake_joint)

    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b", 2.0), _mesh("c", 4.0), _mesh("d", 6.0)], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = JointCreatorTool()
    tool.open(ctx)

    ctx.scene_selection.select_indices((0, 1), active_index=1)
    tool.on_scene_selection_changed(ctx)
    assert ctx.inspector.trigger("preview").action_id == "preview"
    assert store.has_preview
    assert [mesh.name for mesh in store.preview_meshes] == ["a|joint", "b|joint", "c", "d"]

    ctx.scene_selection.select_indices((2, 3), active_index=3)
    tool.on_scene_selection_changed(ctx)
    ctx.inspector.trigger("preview")

    assert store.has_preview
    assert [mesh.name for mesh in store.preview_meshes] == ["a|joint", "b|joint", "c|joint", "d|joint"]
    assert "Staged joints: 2" in ctx.inspector.value("joint_report")

    assert tool.on_apply(ctx) is True
    assert [mesh.name for mesh in store.committed_meshes] == ["a|joint", "b|joint", "c|joint", "d|joint"]

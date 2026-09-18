# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MOD_SIMPLIFY
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.tooling.simplify_tool import SimplifyCreatorTool, SimplifyTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec

ROOT = Path(__file__).resolve().parents[1]


def _mesh(name: str, triangles: int = 4) -> WorkMesh:
    vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
    tri = [(0, 1, 2), (0, 2, 3), (0, 1, 3), (1, 2, 3)][:triangles]
    return WorkMesh(name=name, vertices=vertices, triangles=tri, color="#CCC")


def test_simplify_uses_creator_runtime_and_declarative_panel() -> None:
    tool = get_studio_tool(TOOL_MOD_SIMPLIFY)
    spec = get_tool_spec(TOOL_MOD_SIMPLIFY)
    panel = get_tool_panel_spec(TOOL_MOD_SIMPLIFY)

    assert spec is not None
    assert spec.open_hook is None
    assert spec.close_hook is None
    assert isinstance(tool, SimplifyTool)
    assert isinstance(tool.creator, SimplifyCreatorTool)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"


def test_simplify_stages_preview_and_apply_commits(monkeypatch) -> None:
    import laserprog_studio.tooling.simplify_tool as simplify_module

    def fake_simplify(meshes, selected_indices, *, reduction, preserve_topology):
        out = list(meshes)
        for idx in selected_indices:
            out[int(idx)].triangles = out[int(idx)].triangles[:2]
            out[int(idx)].name = f"{out[int(idx)].name} simplified"
        return SimpleNamespace(ok=True, meshes=out, warnings=(f"reduction={reduction:.2f}; preserve={preserve_topology}",), errors=())

    monkeypatch.setattr(simplify_module, "simplify_selected_meshes", fake_simplify)

    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((1,))

    tool = SimplifyCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("reduction_percent", 60.0)
    ctx.inspector.update_value("preserve_topology", False)

    assert ctx.inspector.trigger("preview").action_id == "preview"
    assert store.has_preview
    assert "Simplify preview ready" in ctx.inspector.value("simplify_report")
    assert len(store.preview_meshes[1].triangles) == 2
    assert len(store.committed_meshes[1].triangles) == 4

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert store.committed_meshes[1].name == "b simplified"
    assert len(store.committed_meshes[1].triangles) == 2


def test_simplify_legacy_ui_paths_are_removed() -> None:
    src_root = ROOT / "src" / "laserprog_studio"
    forbidden = (
        "panel_simplify_modifier",
        "_panel_simplify_modifier",
        "generate_simplify_modifier_preview",
        "_initialize_simplify_modifier_from_selection",
        "_clear_simplify_modifier_preview_state",
        "_on_simplify_params_changed",
        "_schedule_simplify_preview",
        "_run_simplify_preview_if_current",
        "_update_simplify_report",
        "_simplify_selected_indices",
        "simplify_slider",
        "simplify_preserve_topology",
        "simplify_strength_label",
    )
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"legacy token {token!r} remains in {path}"


def test_simplify_creator_tool_is_owner_isolated() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "tooling" / "simplify_tool.py").read_text(encoding="utf-8")
    forbidden = ("ctx.owner", "getattr(ctx, \"owner\"", "mesh_list", "selected_indices =")
    for token in forbidden:
        assert token not in source

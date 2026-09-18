# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.hollow_tool import HollowCreatorTool, HollowTool
from laserprog_studio.tooling.ids import TOOL_MOD_HOLLOW
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec

ROOT = Path(__file__).resolve().parents[1]


def _tetra(name: str = "tetra") -> WorkMesh:
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


def test_hollow_uses_creator_runtime_and_declarative_panel() -> None:
    tool = get_studio_tool(TOOL_MOD_HOLLOW)
    spec = get_tool_spec(TOOL_MOD_HOLLOW)
    panel = get_tool_panel_spec(TOOL_MOD_HOLLOW)

    assert spec is not None
    assert spec.open_hook is None
    assert spec.close_hook is None
    assert isinstance(tool, HollowTool)
    assert isinstance(tool.creator, HollowCreatorTool)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"


def test_hollow_stages_preview_and_apply_commits() -> None:
    store = ModelStore()
    store.set_meshes([_tetra("solid")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,))

    tool = HollowCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("thickness_mm", 0.1)

    assert ctx.inspector.trigger("preview").action_id == "preview"
    assert store.has_preview
    assert "Hollow preview ready" in ctx.inspector.value("hollow_report")
    assert len(store.preview_meshes[0].triangles) > len(store.committed_meshes[0].triangles)

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert "hollow" in store.committed_meshes[0].name.lower()
    assert len(store.committed_meshes[0].triangles) > 4


def test_hollow_legacy_ui_paths_are_removed() -> None:
    src_root = ROOT / "src" / "laserprog_studio"
    forbidden = (
        "panel_hollow_modifier",
        "_panel_hollow_modifier",
        "generate_hollow_modifier_preview",
        "_initialize_hollow_modifier_from_selection",
        "_clear_hollow_modifier_state",
        "_on_hollow_params_changed",
        "_schedule_hollow_preview",
        "_run_hollow_preview_if_current",
        "_update_hollow_report",
        "_hollow_selected_indices",
        "hollow_thickness",
    )
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"legacy token {token!r} remains in {path}"


def test_hollow_creator_tool_is_owner_isolated() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "tooling" / "hollow_tool.py").read_text(encoding="utf-8")
    forbidden = ("ctx.owner", "getattr(ctx, \"owner\"", "mesh_list", "selected_indices =")
    for token in forbidden:
        assert token not in source

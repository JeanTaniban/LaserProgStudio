# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_MOD_REPAIR
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.tooling.repair_tool import RepairMeshCreatorTool, RepairMeshTool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec

ROOT = Path(__file__).resolve().parents[1]


def _open_plate(name: str = "open_plate") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)],
        triangles=[(0, 1, 2), (0, 2, 3), (0, 1, 2)],
        color="#AAA",
    )


def test_repair_uses_creator_runtime_and_declarative_panel() -> None:
    tool = get_studio_tool(TOOL_MOD_REPAIR)
    spec = get_tool_spec(TOOL_MOD_REPAIR)
    panel = get_tool_panel_spec(TOOL_MOD_REPAIR)

    assert spec is not None
    assert spec.open_hook is None
    assert spec.close_hook is None
    assert isinstance(tool, RepairMeshTool)
    assert isinstance(tool.creator, RepairMeshCreatorTool)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"


def test_repair_stages_preview_and_apply_commits_repaired_mesh() -> None:
    store = ModelStore()
    store.set_meshes([_open_plate("a"), _open_plate("b")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((1,))

    tool = RepairMeshCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("tolerance_mm", 0.001)
    ctx.inspector.update_value("fill_holes", False)
    ctx.inspector.update_value("remove_tiny_faces", True)

    assert ctx.inspector.trigger("preview").action_id == "preview"
    assert store.has_preview
    assert "Repair preview ready" in ctx.inspector.value("repair_report")
    assert len(store.preview_meshes[1].triangles) >= 1
    assert store.committed_meshes[1].triangles == [(0, 1, 2), (0, 2, 3), (0, 1, 2)]

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert len(store.committed_meshes[1].triangles) <= 2
    assert store.committed_meshes[1].name == "b"
    assert store.committed_meshes[1].color == "#AAA"


def test_repair_legacy_ui_paths_are_removed() -> None:
    src_root = ROOT / "src" / "laserprog_studio"
    assert not (src_root / "controllers" / "mesh_repair_tool.py").exists()

    forbidden = (
        "MeshRepairToolMixin",
        "panel_repair_modifier",
        "preview_repair_selected_meshes",
        "_initialize_repair_modifier_from_selection",
        "_clear_repair_modifier_preview_state",
        "repair_tolerance",
        "repair_fill_holes",
        "repair_remove_tiny",
    )
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"legacy token {token!r} remains in {path}"


def test_repair_creator_tool_is_owner_isolated() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "tooling" / "repair_tool.py").read_text(encoding="utf-8")
    forbidden = ("ctx.owner", "getattr(ctx, \"owner\"", "mesh_list", "selected_indices =")
    for token in forbidden:
        assert token not in source

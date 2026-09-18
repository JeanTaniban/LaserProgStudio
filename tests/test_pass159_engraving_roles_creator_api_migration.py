# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.engraving.roles import FILL_COLOR, OUTLINE_COLOR, role_from_color_hint_or_ignore
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.engraving_roles_tool import EngravingRolesCreatorTool, EngravingRolesTool
from laserprog_studio.tooling.ids import TOOL_ENGRAVING
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec

ROOT = Path(__file__).resolve().parents[1]


def _mesh(name: str) -> WorkMesh:
    return WorkMesh(name, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(0, 1, 2)])


def test_engraving_roles_uses_creator_runtime_and_declarative_panel() -> None:
    tool = get_studio_tool(TOOL_ENGRAVING)
    spec = get_tool_spec(TOOL_ENGRAVING)
    panel = get_tool_panel_spec(TOOL_ENGRAVING)

    assert spec is not None
    assert spec.open_hook is None
    assert spec.close_hook is None
    assert isinstance(tool, EngravingRolesTool)
    assert isinstance(tool.creator, EngravingRolesCreatorTool)
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"


def test_engraving_roles_stages_preview_and_apply_commits_roles() -> None:
    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((1,))

    tool = EngravingRolesCreatorTool()
    tool.open(ctx)
    ctx.inspector.update_value("role", "fill")

    assert tool.assign_selected(ctx) is True
    assert store.has_preview
    assert role_from_color_hint_or_ignore((store.preview_meshes or [])[1].color) == "fill"
    assert (store.preview_meshes or [])[1].color == FILL_COLOR
    assert (store.committed_meshes or [])[1].color != FILL_COLOR

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert store.committed_meshes[1].color == FILL_COLOR
    assert getattr(store.committed_meshes[1].engraving, "role", "") == "fill"


def test_engraving_roles_click_assignment_uses_adapter_without_owner_methods() -> None:
    store = ModelStore()
    store.set_meshes([_mesh("a"), _mesh("b")], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = EngravingRolesTool(get_tool_spec(TOOL_ENGRAVING))
    tool.creator.open(ctx)

    assert tool.assign_index(type("C", (), {"tool_context": ctx})(), 0, "outline") is True
    assert store.has_preview
    assert (store.preview_meshes or [])[0].color == OUTLINE_COLOR


def test_engraving_roles_retired_ui_paths_are_removed() -> None:
    src_root = ROOT / "src" / "laserprog_studio"
    assert not (src_root / "controllers" / "engraving_roles.py").exists()

    forbidden = (
        "EngravingRolesMixin",
        "panel_engraving_tool",
        "apply_engraving_role_to_index",
        "apply_engraving_role_to_active",
        "apply_engraving_role_to_all",
        "_on_engraving_role_changed",
        "ENGRAVING_ROLE_DEFINITIONS",
        "_current_engraving_role",
    )
    for path in src_root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"retired token {token!r} remains in {path}"


def test_engraving_roles_creator_tool_is_owner_isolated() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "tooling" / "engraving_roles_tool.py").read_text(encoding="utf-8")
    forbidden = ("ctx.owner", "getattr(ctx, \"owner\"", "mesh_list", "selected_indices =")
    for token in forbidden:
        assert token not in source

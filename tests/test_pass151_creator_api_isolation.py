# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_api import TOOL_API_VERSION, ToolContext, ViewFacade
from laserprog_studio.tooling.box_tool import BoxCreatorTool
from laserprog_studio.tooling.primitive_tool import PrimitiveCreatorTool


class _OwnerWithLazyStore:
    def __init__(self) -> None:
        self.model_store = None
        self.ensure_calls = 0
        self.focused_bounds = None
        self.focused_index = None

    def _ensure_model_store(self) -> None:
        self.ensure_calls += 1
        self.model_store = ModelStore()

    def focus_camera_on_bounds(self, bounds, label="zone") -> None:
        self.focused_bounds = (tuple(bounds), label)

    def focus_camera_on_index(self, index: int) -> None:
        self.focused_index = int(index)


class _ProjectStore:
    def __init__(self, active_scene) -> None:
        self.active_scene = active_scene


class _OwnerWithProjectScene:
    def __init__(self, scene) -> None:
        self.project_store = _ProjectStore(scene)


def _mesh(name: str = "seed") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        triangles=[(0, 1, 2)],
    )


def test_pass151_tool_api_exposes_isolation_facades() -> None:
    ctx = ToolContext()

    assert TOOL_API_VERSION == "0.13.0"
    assert hasattr(ctx.document, "ensure")
    assert hasattr(ctx.scene_selection, "select_indices")
    assert hasattr(ctx.scene_selection, "select_last")
    assert isinstance(ctx.view, ViewFacade)


def test_pass151_document_ensure_binds_owner_without_tool_side_owner_access() -> None:
    owner = _OwnerWithLazyStore()
    ctx = ToolContext(owner=owner)

    assert ctx.document.available is False
    assert ctx.document.ensure() is True

    assert owner.ensure_calls == 1
    assert ctx.document.available is True
    assert isinstance(ctx.document.raw, _OwnerWithLazyStore)


def test_pass151_document_ensure_prefers_active_project_scene() -> None:
    store = ModelStore()
    owner = _OwnerWithProjectScene(store)
    ctx = ToolContext(owner=owner)

    assert ctx.document.ensure() is True
    assert ctx.document.raw is store


def test_pass151_scene_selection_and_view_cover_previous_owner_calls() -> None:
    owner = _OwnerWithLazyStore()
    owner.model_store = ModelStore()
    owner.model_store.set_meshes([_mesh("a"), _mesh("b")])
    ctx = ToolContext(owner=owner)
    assert ctx.document.ensure()

    selected = ctx.scene_selection.select_indices((1,))
    focused = ctx.view.focus_index(1)

    assert selected == (1,)
    assert ctx.scene_selection.selected_indices() == (1,)
    assert focused is True
    assert owner.focused_index == 1


def test_pass151_migrated_tools_do_not_reach_into_ctx_owner() -> None:
    for path in (
        Path("src/laserprog_studio/tooling/primitive_tool.py"),
        Path("src/laserprog_studio/tooling/box_tool.py"),
    ):
        source = path.read_text(encoding="utf-8")
        assert "ctx.owner" not in source
        assert 'getattr(ctx, "owner"' not in source
        assert "focus_camera_on" not in source
        assert "mesh_list" not in source
        assert "selected_indices =" not in source


def test_pass151_primitive_stages_with_only_creator_api_services() -> None:
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = PrimitiveCreatorTool()
    tool.open(ctx)

    assert tool._stage_preview(ctx) is True

    assert store.has_preview
    assert ctx.scene_selection.selected_indices() == (0,)
    assert ctx.workflow.active_step.id == "preview"


def test_pass151_box_stages_with_only_creator_api_services() -> None:
    store = ModelStore()
    store.set_meshes([_mesh("seed")])
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = BoxCreatorTool()
    tool.open(ctx)

    assert tool._stage_preview(ctx) is True

    assert store.has_preview
    assert ctx.scene_selection.selected_indices() == tuple(range(1, 7))
    assert ctx.workflow.active_step.id == "preview"

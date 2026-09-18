# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.domain.work_model import ModelStore
from laserprog_studio.fabrication.box_generator import box_metadata, build_box_meshes
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.app_services import OperationResult
from laserprog_studio.tooling.box_tool import BoxCreatorTool, BoxTool
from laserprog_studio.tooling.ids import TOOL_BOX
from laserprog_studio.tooling.registry import get_studio_tool
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec


def test_box_runtime_is_creator_api_adapter() -> None:
    tool = get_studio_tool(TOOL_BOX)

    assert isinstance(tool, BoxTool)
    assert isinstance(tool.creator, BoxCreatorTool)
    assert tool.spec.panel_index == 2
    assert get_tool_panel_spec(TOOL_BOX).builder == "panel_declarative_creator_tool"


def test_box_fabrication_backend_builds_tagged_meshes_without_application_dependency() -> None:
    boards, meshes, metrics = build_box_meshes(120.0, 80.0, 60.0, 3.0, "front_back_wrap", "top_bottom_wrap", "top_bottom_wrap", group_id="box-test")

    assert len(boards) == 6
    assert len(meshes) == 6
    assert metrics.inner_volume_l > 0.0
    assert {mesh.name for mesh in meshes} == {"bottom", "top", "front", "back", "left", "right"}
    assert {box_metadata(mesh)["group_id"] for mesh in meshes} == {"box-test"}


def test_box_creator_open_registers_declarative_panel_and_operation() -> None:
    ctx = ToolContext()
    ctx.document.bind(ModelStore())
    tool = BoxCreatorTool()

    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "box.generator"
    assert "width" in ctx.inspector.panel.field_ids()
    assert "box_report" in ctx.inspector.panel.field_ids()
    result = ctx.operations.box_generate(params=ctx.inspector.values())
    assert isinstance(result, OperationResult)
    assert result.ok
    assert len(result.meshes) == 6
    assert "Internal volume" in result.report


def test_box_creator_stages_preview_and_apply_commits_to_document() -> None:
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = BoxCreatorTool()
    tool.open(ctx)

    ctx.inspector.update_values({"width": 90.0, "depth": 70.0, "height": 50.0, "thickness": 2.5}, notify=True)
    assert "Internal volume" in str(ctx.inspector.value("box_report"))

    assert tool._stage_preview(ctx) is True
    assert store.has_preview
    assert len(store.preview_meshes or []) == 6
    assert all(box_metadata(mesh) for mesh in (store.preview_meshes or []))

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert len(store.committed_meshes) == 6
    assert all(box_metadata(mesh) for mesh in store.committed_meshes)


def test_pass150_docs_record_box_creator_api_migration() -> None:
    doc = Path("docs/archive/passes/source_cleanup_pass10.md").read_text(encoding="utf-8")
    assert "BoxCreatorTool" in doc
    assert "ctx.operations.box_generate" in doc

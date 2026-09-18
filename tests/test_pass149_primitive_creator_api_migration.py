# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import ModelStore
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.app_services import OperationResult
from laserprog_studio.tooling.ids import TOOL_PRIMITIVE
from laserprog_studio.tooling.primitive_tool import PrimitiveCreatorTool, PrimitiveTool
from laserprog_studio.tooling.registry import get_studio_tool


def test_primitive_runtime_is_creator_api_adapter():
    tool = get_studio_tool(TOOL_PRIMITIVE)

    assert isinstance(tool, PrimitiveTool)
    assert isinstance(tool.creator, PrimitiveCreatorTool)
    assert tool.spec.panel_index == 1


def test_primitive_creator_open_registers_declarative_panel_and_operation():
    ctx = ToolContext()
    ctx.document.bind(ModelStore())
    tool = PrimitiveCreatorTool()

    tool.open(ctx)

    assert ctx.inspector.panel is not None
    assert ctx.inspector.panel.id == "primitive.generator"
    assert "primitive_id" in ctx.inspector.panel.field_ids()
    result = ctx.operations.primitive_generate(params=ctx.inspector.values())
    assert isinstance(result, OperationResult)
    assert result.ok
    assert result.meshes[0].name.startswith("box_")


def test_primitive_creator_stages_preview_and_apply_commits_to_document():
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = PrimitiveCreatorTool()
    tool.open(ctx)

    ctx.inspector.update_values({"primitive_id": "sphere", "size": (12.0, 12.0, 12.0)}, notify=True)
    assert ctx.inspector.value("triangle_estimate").endswith("triangles")

    assert tool._stage_preview(ctx) is True
    assert store.has_preview
    assert len(store.preview_meshes or []) == 1
    assert (store.preview_meshes or [])[0].name.startswith("sphere_")

    assert tool.apply(ctx) is True
    assert not store.has_preview
    assert len(store.committed_meshes) == 1
    assert store.committed_meshes[0].name.startswith("sphere_")

# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

from _path_setup import ROOT  # noqa: F401

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.app_services.operations import OperationManager
from laserprog_studio.tooling.texture_projection_creator_tool import TextureProjectionCreatorTool

from scripts.audit_tool_product_quality import collect_tool_product_records


def _textured_square(name: str = "panel") -> WorkMesh:
    mesh = WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 10.0, 0.0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
        color="#CCC",
    )
    mesh.uvs = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    mesh.texture_projections = [{"texture_id": "tex_existing", "texture_path": "old.png"}]
    mesh.material = {"texture_id": "tex_existing", "texture_path": "old.png"}
    return mesh


def test_texture_projection_clear_action_uses_public_operation_facade() -> None:
    store = ModelStore()
    store.set_meshes([_textured_square()], push_undo=False)
    ctx = ToolContext()
    ctx.document.bind(store)
    ctx.scene_selection.select_indices((0,), active_index=0)

    tool = TextureProjectionCreatorTool()
    tool.open(ctx)

    assert hasattr(OperationManager, "texture_clear")
    assert ctx.inspector.trigger("clear").action_id == "clear"

    assert store.has_preview
    assert len(store.preview_meshes) == 1
    assert store.preview_meshes[0].texture_projections == []
    assert store.preview_meshes[0].uvs is None
    assert "Texture clear preview ready" in ctx.inspector.value("texture_report")


def test_product_audit_guards_registered_operation_facades() -> None:
    records = collect_tool_product_records()

    assert all(record.operation_facade_issues == () for record in records)

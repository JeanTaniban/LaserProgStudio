# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from laserprog_studio.domain.work_model import WorkMesh

from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_api import (
    CreatorStudioToolAdapter,
    CreatorTool,
    OperationResult,
    ToolContext,
    inspector,
    register_tool,
)
from laserprog_studio.tooling.registry import get_studio_tool, unregister_tool_spec


def _mesh(name: str = "mesh") -> WorkMesh:
    return WorkMesh(name=name, vertices=[(0, 0, 0), (1, 0, 0), (0, 1, 0)], triangles=[(0, 1, 2)])


def test_pass126_document_facade_scene_selection_and_preview_session_are_tool_ready() -> None:
    scene = SceneDocument.from_meshes("main", [_mesh("a"), _mesh("b")])
    ctx = ToolContext()
    ctx.document.bind(scene)

    assert [obj.name for obj in ctx.document.objects()] == ["a", "b"]
    added = ctx.document.add_mesh(_mesh("c"), label="Add c")
    assert added.name == "c"
    assert len(ctx.document.objects()) == 3

    ctx.scene_selection.set_selected([0, 2])
    assert [obj.name for obj in ctx.scene_selection.selected_objects()] == ["a", "c"]
    assert ctx.scene_selection.active_object().name == "c"

    session = ctx.preview_session.start(owner_tool="tool.preview", label="Replace selected")
    replacement = _mesh("c.preview")
    session.replace_object_preview(added.id, replacement)
    assert scene.model_store.has_preview
    assert ctx.document.objects()[2].name == "c.preview"

    assert session.apply(label="Apply replacement")
    assert not scene.model_store.has_preview
    assert ctx.document.objects(include_preview=False)[2].name == "c.preview"

    removed = ctx.document.remove_object(0)
    assert removed.name == "a"
    assert [obj.name for obj in ctx.document.objects()] == ["b", "c.preview"]


def test_pass126_operation_manager_preview_apply_jobs_status_and_picking_are_available() -> None:
    class PickScene:
        def pick_object_at(self, screen_pos, **_filters):
            return {"kind": "object", "object_id": "picked", "object_index": 0, "world_pos": (1, 2, 3)}

    scene = SceneDocument.from_meshes("main", [_mesh("input")])
    ctx = ToolContext(scene=PickScene())
    ctx.document.bind(scene)

    def duplicate(inputs, params, _ctx):
        scale = float(params.get("scale", 1.0))
        mesh = _mesh(f"generated-{scale:g}")
        return OperationResult.success([*inputs, mesh], report="generated")

    ctx.operations.register("duplicate", duplicate)
    result = ctx.operations.run_preview(
        "duplicate",
        inputs=ctx.document.meshes(include_preview=False),
        params={"scale": 2.0},
        owner_tool="tool.ops",
    )
    assert result.ok
    assert scene.model_store.has_preview
    assert ctx.status.latest().message == "generated"
    assert ctx.preview_session.apply(label="Apply generated")
    assert [obj.name for obj in ctx.document.objects()] == ["input", "generated-2"]

    job = ctx.jobs.start("count", lambda progress: (progress(0.5, "half"), "done")[-1])
    assert job.state.value == "done"
    assert job.result == "done"
    assert ctx.status.latest().message == "count: done"

    hit = ctx.pick.object_at((10.0, 20.0))
    assert hit.hit
    assert hit.object_id == "picked"
    assert hit.world_pos == (1.0, 2.0, 3.0)


def test_pass126_creator_studio_tool_adapter_and_declarative_panel_runtime() -> None:
    class DemoCreator(CreatorTool):
        id = "com.example.pass126"
        label = "Pass126 Demo"

        def on_open(self, ctx: ToolContext) -> None:
            ctx.inspector.set_panel(
                inspector.panel(
                    "Runtime Panel",
                    id=self.id,
                    owner_tool=self.id,
                    sections=[
                        inspector.section(
                            "Inputs",
                            [
                                inspector.vector3_field("origin", "Origin", default=(1, 2, 3)),
                                inspector.slider_field("amount", "Amount", default=0.5, min_value=0.0, max_value=1.0),
                                inspector.readonly_field("report", "Report", default="Ready"),
                            ],
                        )
                    ],
                )
            )

    extension = register_tool(
        id="com.example.pass126",
        label="Pass126 Demo",
        runtime=DemoCreator(),
        toolbar_visibility="hidden",
        replace=True,
    )
    try:
        runtime = get_studio_tool("com.example.pass126")
        assert isinstance(runtime, CreatorStudioToolAdapter)
        ctx = ToolContext(document=SceneDocument.from_meshes("main", [_mesh("a")]))

        @dataclass
        class AppCtx:
            tool_context: ToolContext
            active_scene: SceneDocument

        app_ctx = AppCtx(tool_context=ctx, active_scene=ctx.document.raw)
        runtime.on_open(app_ctx)
        assert ctx.inspector.panel.title == "Runtime Panel"
        assert ctx.inspector.value("origin") == (1.0, 2.0, 3.0)
        assert ctx.inspector.value("amount") == 0.5
        assert ctx.inspector.field_state("report").readonly is True
        runtime.on_close(app_ctx)
        assert ctx.inspector.panel is None
        assert extension.tool.id == "com.example.pass126"
    finally:
        unregister_tool_spec("com.example.pass126")

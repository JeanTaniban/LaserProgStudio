# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.tool_api import TOOL_API_VERSION, ToolContext, inspector, workflow
from laserprog_studio.tool_api.surface import active_import_paths, public_api_summary
from laserprog_studio.tool_core.app_services import OperationResult


def test_pass148_creator_api_version_and_workflow_domain_are_public() -> None:
    assert TOOL_API_VERSION == "0.13.0"
    assert "laserprog_studio.tool_api.workflow" in active_import_paths()
    assert public_api_summary()["active_domains"] == 8
    assert workflow.ToolWorkflowManager
    assert workflow.ToolModeManager


def test_pass148_inspector_has_richer_fields_for_advanced_tools() -> None:
    clicked: list[str] = []
    ctx = ToolContext()
    ctx.inspector.set_panel(
        inspector.panel(
            "Advanced Tool",
            id="pass148.panel",
            sections=[
                inspector.section(
                    "Inputs",
                    [
                        inspector.title("title", "Placement"),
                        inspector.vector2_field("uv", "UV", default=(0.1, 0.2)),
                        inspector.vector3_field("origin", "Origin", default=(1, 2, 3)),
                        inspector.file_field("image", "Image", default="mask.png"),
                        inspector.font_field("font", "Font", default="Inter"),
                        inspector.help_text("hint", "Pick a face, then preview."),
                        inspector.separator("sep"),
                    ],
                ),
                inspector.section(
                    "Actions",
                    [
                        inspector.button_row(
                            "actions",
                            "Actions",
                            buttons=(("preview", "Preview"), ("apply", "Apply")),
                            on_click=lambda event: clicked.append(event.action_id),
                        )
                    ],
                ),
            ],
        )
    )

    assert ctx.inspector.values() == {
        "uv": (0.1, 0.2),
        "origin": (1.0, 2.0, 3.0),
        "image": "mask.png",
        "font": "Inter",
    }
    assert ctx.inspector.update_value("uv", "0.5, 0.75") == (0.5, 0.75)
    assert ctx.inspector.update_value("font", "DejaVu Sans") == "DejaVu Sans"
    ctx.inspector.trigger("preview")
    ctx.inspector.trigger("apply")
    assert clicked == ["preview", "apply"]
    assert "hint" not in ctx.inspector.values()


def test_pass148_workflow_and_modes_cover_multistep_interactive_tools() -> None:
    ctx = ToolContext()
    state = ctx.workflow.start(
        "tool.joint",
        [
            ctx.workflow.require_scene_object("pick_a", "Pick A"),
            ctx.workflow.require_scene_object("pick_b", "Pick B"),
            ctx.workflow.step("preview", "Preview"),
        ],
    )
    assert state.active_id == "pick_a"
    ctx.workflow.record_active({"object_index": 0})
    ctx.workflow.record_active({"object_index": 1})
    assert ctx.workflow.active_step.id == "preview"
    ctx.workflow.complete()
    assert ctx.workflow.describe()["completed"] is True

    ctx.modes.register(
        "tool.planar",
        [
            ctx.modes.define("add", "Add"),
            ctx.modes.define("edit", "Edit"),
            ctx.modes.define("delete", "Delete"),
        ],
    )
    ctx.modes.set("tool.planar", "edit")
    assert ctx.modes.active("tool.planar").id == "edit"

    ctx.cleanup_tool("tool.joint")
    assert ctx.workflow.describe()["active"] is False
    ctx.cleanup_tool("tool.planar")
    assert ctx.modes.describe("tool.planar")["tools"] == []


def test_pass148_operation_manager_exposes_named_tool_operations() -> None:
    ctx = ToolContext()
    calls: list[str] = []

    def make_operation(name: str):
        def _op(inputs, params, _ctx):
            calls.append(name)
            return OperationResult.success([f"{name}:{len(tuple(inputs))}:{params.get('mode', '')}"], report=name)

        return _op

    for name in (
        "box_generate",
        "layflat",
        "joint_build",
        "split_plane",
        "texture_project",
        "relief_text",
        "acoustic_diffuser",
        "cavity_volume",
    ):
        ctx.operations.register(name, make_operation(name))

    assert ctx.operations.box_generate(params={"mode": "box"}).meshes == ("box_generate:0:box",)
    assert ctx.operations.layflat(inputs=["mesh"], params={"mode": "flat"}).meshes == ("layflat:1:flat",)
    assert ctx.operations.joint_build(inputs=["a", "b"]).ok
    assert ctx.operations.split_plane(inputs=["mesh"]).ok
    assert ctx.operations.texture_project(inputs=["mesh"]).ok
    assert ctx.operations.relief_text(inputs=["mesh"]).ok
    assert ctx.operations.acoustic_diffuser().ok
    assert ctx.operations.cavity_volume(inputs=["mesh"]).ok
    assert calls == [
        "box_generate",
        "layflat",
        "joint_build",
        "split_plane",
        "texture_project",
        "relief_text",
        "acoustic_diffuser",
        "cavity_volume",
    ]

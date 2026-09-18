"""Pass126 example: modifier-style tool using the complete creator API.

This file is intentionally Qt/PyVista-free. It demonstrates the shape expected
for future migrations of Simplify, Repair, Hollow, Split, Relief, etc.
"""
from __future__ import annotations

from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorTool, ToolContext, ToolManifest, register_tool, require_tool_api
from laserprog_studio.tool_api.visual import inspector

TOOL_ID = "com.example.modifier_preview_shell"
require_tool_api("0.8.0", max_major=0)
TOOL_MANIFEST = ToolManifest(
    id=TOOL_ID,
    label="Modifier Preview Shell",
    entrypoint="examples.tool_creator.modifier_preview_shell:create_tool",
    api_min="0.8.0",
    permissions=("scene:read", "scene:write", "preview:write"),
)


class ModifierPreviewShell(CreatorTool):
    id = TOOL_ID
    label = "Modifier Preview Shell"

    def on_open(self, ctx: ToolContext) -> None:
        ctx.inspector.set_panel(
            inspector.panel(
                "Modifier Preview Shell",
                id=self.id,
                owner_tool=self.id,
                sections=[
                    inspector.section(
                        "Parameters",
                        [
                            inspector.slider_field("amount", "Amount", default=0.5, min_value=0.0, max_value=1.0),
                            inspector.readonly_field("report", "Report", default="Ready"),
                        ],
                    ),
                    inspector.section(
                        "Actions",
                        [
                            inspector.button("preview", "Preview", on_click=lambda _event: self.preview(ctx)),
                            inspector.button("apply", "Apply", on_click=lambda _event: ctx.preview_session.apply(label="Modifier shell applied")),
                            inspector.button("cancel", "Cancel", on_click=lambda _event: ctx.preview_session.cancel()),
                        ],
                    ),
                ],
            )
        )
        ctx.operations.register("modifier_shell_identity", self._identity_operation, replace=True)

    def preview(self, ctx: ToolContext) -> OperationResult:
        selected = ctx.scene_selection.selected_meshes() or ctx.document.meshes(include_preview=False)
        result = ctx.operations.run_preview(
            "modifier_shell_identity",
            inputs=selected,
            params=ctx.inspector.values(),
            owner_tool=self.id,
            label="Modifier shell preview",
        )
        ctx.inspector.update_value("report", result.report or ("OK" if result.ok else "Failed"), notify=False)
        return result

    def _identity_operation(self, inputs, params, ctx: ToolContext) -> OperationResult:
        amount = float(params.get("amount", 0.5))
        ctx.status.progress("Building preview", amount)
        return OperationResult.success(inputs, report=f"Preview rebuilt with amount={amount:.2f}")


def create_tool() -> ModifierPreviewShell:
    return ModifierPreviewShell()


def register() -> object:
    TOOL_MANIFEST.validate_runtime()
    return register_tool(
        id=TOOL_ID,
        label="Modifier Preview Shell",
        runtime=create_tool(),
        selection_policy="multi",
        toolbar_visibility="palette",
        panel_index=930,
        description="Example modifier-style creator API tool.",
        replace=True,
    )

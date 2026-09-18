"""Application SDK demo tool.

This example intentionally uses only ``laserprog_studio.tool_api``. It shows the
services required to migrate real Studio tools: document changes, planar sketch
mesh generation, material/texture/engraving metadata, high-level gizmos and a
previewable operation.
"""
from __future__ import annotations

from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorTool, ToolContext, require_tool_api
from laserprog_studio.tool_api.visual import inspector

require_tool_api("0.8.0", max_major=0)


class ApplicationSdkDemoTool(CreatorTool):
    id = "com.example.application_sdk_demo"
    label = "Application SDK Demo"

    def on_open(self, ctx: ToolContext) -> None:
        ctx.inspector.set_panel(
            inspector.panel(
                "Application SDK Demo",
                id=self.id,
                owner_tool=self.id,
                sections=[
                    inspector.section(
                        "Planar plate",
                        [
                            inspector.float_field("width", "Width", default=40.0, min_value=1.0),
                            inspector.float_field("height", "Height", default=20.0, min_value=1.0),
                            inspector.button("preview", "Preview plate"),
                            inspector.button("apply", "Apply preview"),
                        ],
                    ),
                    inspector.section(
                        "Metadata",
                        [
                            inspector.color_field("color", "Material color", default="#D8B16A"),
                            inspector.choice_field("role", "Engraving role", default="outline", choices=("outline", "fill", "ignore")),
                        ],
                    ),
                ],
            )
        )
        ctx.gizmos.plane(id="workplane", owner_tool=self.id, origin=(0, 0, 0), normal=(0, 0, 1))

        def make_plate(inputs, params, _ctx):
            width = float(params.get("width", 40.0))
            height = float(params.get("height", 20.0))
            _ctx.planar.clear()
            _ctx.planar.set_plane(origin=(0, 0, 0), normal=(0, 0, 1))
            p1 = _ctx.planar.add_point(plane_pos=(0, 0))
            p2 = _ctx.planar.add_point(plane_pos=(width, 0))
            p3 = _ctx.planar.add_point(plane_pos=(width, height))
            p4 = _ctx.planar.add_point(plane_pos=(0, height))
            _ctx.planar.add_line(p1.id, p2.id)
            _ctx.planar.add_line(p2.id, p3.id)
            _ctx.planar.add_line(p3.id, p4.id)
            _ctx.planar.add_line(p4.id, p1.id)
            mesh = _ctx.planar.generate_mesh(name="SDK plate")
            return OperationResult.success([*_ctx.document.meshes(include_preview=False), mesh], report="Plate preview ready")

        ctx.operations.register("sdk_plate", make_plate, replace=True)

    def on_event(self, event, ctx: ToolContext) -> bool:
        return False

    def on_apply(self, ctx: ToolContext) -> bool:
        values = ctx.inspector.values()
        result = ctx.operations.preview("sdk_plate", params=values, owner_tool=self.id)
        if not result.ok:
            return False
        return True

    def apply_metadata_to_last(self, ctx: ToolContext) -> None:
        objects = ctx.document.objects(include_preview=False)
        if not objects:
            return
        target = objects[-1]
        values = ctx.inspector.values()
        material = ctx.materials.create("SDK material", base_color=values.get("color", "#D8B16A"))
        ctx.materials.assign(target.id, material)
        ctx.engraving.assign_role(target.id, values.get("role", "outline"))

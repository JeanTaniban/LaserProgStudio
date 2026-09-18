# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.primitives import (
    build_primitive_mesh,
    estimate_primitive_tool_triangles,
    primitive_tool_defaults,
    validate_primitive_tool_values,
)
from types import SimpleNamespace

from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import ButtonRow, ChoiceField, ColorField, HelpText, InspectorActionEvent, IntField, Panel, ReadonlyField, Section, Vector3Field

from .base import ToolSpec
from .preview_staleness import cancel_tool_preview_if_active


inspector = SimpleNamespace(
    panel=Panel,
    section=Section,
    choice_field=ChoiceField,
    readonly_field=ReadonlyField,
    vector3_field=Vector3Field,
    color_field=ColorField,
    int_field=IntField,
    help_text=HelpText,
    button_row=ButtonRow,
)


TOOL_ID = "primitive"


class PrimitiveCreatorTool(CreatorTool):
    """Built-in primitive generator implemented with the public Creator API.

    This is the first real built-in migration target: it owns its declarative
    inspector panel, generates meshes through ``ctx.operations`` and stages the
    result through the same preview/document services external tools use.
    """

    id = TOOL_ID
    label = "Primitives"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("configure", "Configure primitive", help="Configure primitive parameters."),
                ctx.workflow.step("preview", "Stage preview", help="Stage the generated mesh as preview.", optional=True),
            ),
        )
        ctx.operations.register("primitive_generate", self._operation_generate, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_dynamic_fields(ctx)
        ctx.status.info("Primitive tool ready. Configure the shape, then stage a preview.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.cancel())

    def on_apply(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.apply(label="Primitive applied", operation_type="primitive"))

    def _panel(self, ctx: Any):
        defaults = primitive_tool_defaults()
        return inspector.panel(
            "Primitives",
            id="primitive.generator",
            owner_tool=self.id,
            description="Create parametric base meshes through the Creator API.",
            sections=(
                inspector.section(
                    "Shape",
                    fields=(
                        inspector.choice_field(
                            "primitive_id",
                            "Type",
                            default=str(defaults["primitive_id"]),
                            choices=(
                                ("box", "Box/Cube"),
                                ("cylinder", "Cylinder"),
                                ("sphere", "Sphere"),
                                ("cone", "Cone"),
                                ("pyramid", "Pyramid"),
                                ("triangular_prism", "Triangular prism"),
                                ("hex_prism", "Hex prism"),
                                ("custom", "Custom"),
                            ),
                            on_change=lambda _field, _value: self._on_values_changed(ctx),
                        ),
                        inspector.choice_field(
                            "custom_kind",
                            "Custom shape",
                            default=str(defaults["custom_kind"]),
                            choices=(("cylinder", "Cylinder"), ("sphere", "Sphere"), ("cone", "Cone")),
                            on_change=lambda _field, _value: self._on_values_changed(ctx),
                        ),
                        inspector.readonly_field("triangle_estimate", "Estimate", default="12 triangles"),
                    ),
                ),
                inspector.section(
                    "Dimensions",
                    fields=(
                        inspector.vector3_field("size", "Size", default=(40.0, 40.0, 40.0), unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        inspector.vector3_field("position", "Position", default=(0.0, 0.0, 0.0), unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        inspector.color_field("color", "Color", default=str(defaults["color"]), tooltip="Display color stored on the generated mesh.", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                    ),
                ),
                inspector.section(
                    "Resolution",
                    fields=(
                        inspector.int_field("segments", "Sides", default=int(defaults["segments"]), min_value=3, max_value=512, step=1, on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        inspector.int_field("theta_resolution", "Segments H", default=int(defaults["theta_resolution"]), min_value=3, max_value=512, step=1, on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        inspector.int_field("phi_resolution", "Segments V", default=int(defaults["phi_resolution"]), min_value=3, max_value=256, step=1, on_change=lambda _field, _value: self._on_values_changed(ctx)),
                    ),
                ),
                inspector.section(
                    "Preview",
                    fields=(
                        inspector.help_text("primitive_help", "Stage a preview, then use the global Apply button to commit it to the scene."),
                        inspector.button_row(
                            "primitive_actions",
                            "Actions",
                            buttons=(("stage_preview", "Add to preview"), ("reset_values", "Reset")),
                            callbacks={
                                "stage_preview": lambda event: self._stage_preview(ctx, event),
                                "reset_values": lambda event: self._reset_values(ctx, event),
                            },
                        ),
                    ),
                ),
            ),
        )

    def values(self, ctx: Any) -> dict[str, object]:
        return self._primitive_values(ctx.inspector.values())

    def build_mesh(self, ctx: Any):
        return build_primitive_mesh(self.values(ctx), name_index=self._next_name_index(ctx))

    def estimate_triangles(self, ctx: Any) -> int:
        return estimate_primitive_tool_triangles(self.values(ctx))

    def _operation_generate(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        values = self._primitive_values(params or ctx.inspector.values())
        mesh = build_primitive_mesh(values, name_index=self._next_name_index(ctx))
        return OperationResult.success((mesh,), report=f"Generated primitive: {mesh.name}", metadata={"primitive_values": values})

    def _stage_preview(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if not ctx.document.ensure() or not ctx.document.available:
            ctx.status.error("Primitive preview needs an active document before staging meshes.")
            return False
        values = self._primitive_values(event.values if event is not None else ctx.inspector.values())
        result = ctx.operations.primitive_generate(params=values, preview=False, owner_tool=self.id)
        if not result.ok or not result.meshes:
            return False
        mesh = result.meshes[0]
        meshes = [*ctx.document.meshes(include_preview=False), mesh]
        session = ctx.preview_session.start(owner_tool=self.id, label=f"Primitive added: {mesh.name}")
        session.show_meshes(meshes)
        ctx.scene_selection.select_indices((len(meshes) - 1,))
        ctx.workflow.goto("preview")
        ctx.status.info("Primitive staged. Use Apply to keep it or Cancel to discard it.")
        return True

    def _reset_values(self, ctx: Any, _event: InspectorActionEvent | None = None) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Primitive preview discarded because parameters were reset.")
        defaults = primitive_tool_defaults()
        ctx.inspector.update_values(
            {
                "primitive_id": defaults["primitive_id"],
                "custom_kind": defaults["custom_kind"],
                "size": (defaults["size_x"], defaults["size_y"], defaults["size_z"]),
                "position": (defaults["pos_x"], defaults["pos_y"], defaults["pos_z"]),
                "color": defaults["color"],
                "segments": defaults["segments"],
                "theta_resolution": defaults["theta_resolution"],
                "phi_resolution": defaults["phi_resolution"],
            },
            notify=False,
        )
        self._sync_dynamic_fields(ctx)
        ctx.status.info("Primitive parameters reset.")

    def _on_values_changed(self, ctx: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Primitive preview discarded because parameters changed.")
        self._sync_dynamic_fields(ctx)
        try:
            ctx.status.info(f"Primitive estimate: {self.estimate_triangles(ctx)} triangles")
        except Exception:
            pass

    def _sync_dynamic_fields(self, ctx: Any) -> None:
        values = ctx.inspector.values()
        primitive_id = str(values.get("primitive_id", "box"))
        custom_kind = str(values.get("custom_kind", "cylinder"))
        effective = custom_kind if primitive_id == "custom" else primitive_id
        ctx.inspector.set_visible("custom_kind", primitive_id == "custom")
        ctx.inspector.set_visible("segments", effective in {"cylinder", "cone"})
        ctx.inspector.set_visible("theta_resolution", effective == "sphere")
        ctx.inspector.set_visible("phi_resolution", effective == "sphere")
        estimate = estimate_primitive_tool_triangles(self._primitive_values(values))
        ctx.inspector.set_display_value("triangle_estimate", f"{estimate} triangles")

    def _primitive_values(self, raw: dict[str, Any]) -> dict[str, object]:
        size = raw.get("size", (40.0, 40.0, 40.0))
        position = raw.get("position", (0.0, 0.0, 0.0))
        sx, sy, sz = tuple(size)
        px, py, pz = tuple(position)
        values = {
            "primitive_id": raw.get("primitive_id", "box"),
            "custom_kind": raw.get("custom_kind", "cylinder"),
            "size_x": sx,
            "size_y": sy,
            "size_z": sz,
            "pos_x": px,
            "pos_y": py,
            "pos_z": pz,
            "color": raw.get("color", "#B8B8B8"),
            "segments": raw.get("segments", 64),
            "theta_resolution": raw.get("theta_resolution", 64),
            "phi_resolution": raw.get("phi_resolution", 32),
        }
        return validate_primitive_tool_values(values)

    def _next_name_index(self, ctx: Any) -> int:
        try:
            return len(ctx.document.meshes(include_preview=False)) + 1
        except Exception:
            return 1



class PrimitiveTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in primitive CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=PrimitiveCreatorTool())

    def build_mesh(self, context: Any):
        return self.creator.build_mesh(self.tool_context(context))

    def estimate_triangles(self, context: Any) -> int:
        return self.creator.estimate_triangles(self.tool_context(context))


__all__ = ["PrimitiveCreatorTool", "PrimitiveTool"]

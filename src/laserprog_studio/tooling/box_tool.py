# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.fabrication.box_generator import (
    CORNER_JOINT_OPTIONS,
    DEFAULT_SETTINGS,
    TOP_FRONT_JOINT_OPTIONS,
    TOP_SIDE_JOINT_OPTIONS,
    build_box_meshes,
    compute_box_metrics,
    format_box_metrics_report,
    make_box_boards,
    option_value,
)
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import ButtonRow, ChoiceField, FloatField, HelpText, InspectorActionEvent, Panel, ReadonlyField, Section, Title
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .preview_staleness import cancel_tool_preview_if_active
from .ids import TOOL_BOX


class BoxCreatorTool(CreatorTool):
    """Built-in Box generator implemented with the public Creator API.

    The tool now owns its inspector panel and registers the stable
    ``ctx.operations.box_generate`` backend.  The Qt field mirrors remain only as
    window-field mirrors for existing tests/controllers.
    """

    id = TOOL_BOX
    label = "Box generator"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("configure", "Configure box", help="Set external dimensions and wrapping joints."),
                ctx.workflow.step("preview", "Stage preview", help="Preview the generated six-board box before applying it.", optional=True),
            ),
        )
        ctx.operations.register("box_generate", self._operation_generate, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_report(ctx)
        ctx.status.info("Box generator ready. Configure the dimensions, then stage a preview.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.cancel())

    def on_apply(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.apply(label="Box generator applied", operation_type="box_generator"))

    def values(self, ctx: Any) -> dict[str, object]:
        return self._box_values(ctx.inspector.values())

    def build_meshes(self, ctx: Any):
        values = self.values(ctx)
        _boards, meshes, _metrics = build_box_meshes(**values)
        return tuple(meshes)

    def metrics_report(self, ctx: Any) -> str:
        values = self.values(ctx)
        boards = make_box_boards(**values)
        metrics = compute_box_metrics(boards=boards, **values)
        return format_box_metrics_report(
            boards,
            metrics,
            str(values["corner_joint"]),
            str(values["top_front_joint"]),
            str(values["top_side_joint"]),
        )

    def _panel(self, ctx: Any):
        defaults = DEFAULT_SETTINGS
        return Panel(
            "Box generator",
            id="box.generator",
            owner_tool=self.id,
            description="Generate a six-board rectangular box through the Creator API.",
            sections=(
                Section(
                    "Dimensions",
                    fields=(
                        FloatField("width", "Width X", default=float(defaults["outer_width_mm"]), min_value=1.0, max_value=10000.0, step=1.0, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        FloatField("depth", "Depth Y", default=float(defaults["outer_depth_mm"]), min_value=1.0, max_value=10000.0, step=1.0, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        FloatField("height", "Height Z", default=float(defaults["outer_height_mm"]), min_value=1.0, max_value=10000.0, step=1.0, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        FloatField("thickness", "Thickness", default=float(defaults["wood_thickness_mm"]), min_value=0.1, max_value=1000.0, step=0.5, unit="mm", on_change=lambda _field, _value: self._on_values_changed(ctx)),
                    ),
                ),
                Section(
                    "Wrapping joints",
                    fields=(
                        ChoiceField("corner_joint", "Corners", default=str(defaults["corner_joint"]), choices=tuple(CORNER_JOINT_OPTIONS.items()), on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        ChoiceField("top_front_joint", "Top ↔ front", default=str(defaults["top_front_joint"]), choices=tuple(TOP_FRONT_JOINT_OPTIONS.items()), on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        ChoiceField("top_side_joint", "Top ↔ sides", default=str(defaults["top_side_joint"]), choices=tuple(TOP_SIDE_JOINT_OPTIONS.items()), on_change=lambda _field, _value: self._on_values_changed(ctx)),
                        HelpText("box_wrap_help", "A wrapping face keeps its full size. An inset face is shortened by 2 × material thickness."),
                    ),
                ),
                Section(
                    "Report",
                    fields=(
                        ReadonlyField("box_report", "Metrics", default="Volumes and board surface will appear here."),
                    ),
                ),
                Section(
                    "Preview",
                    fields=(
                        Title("box_preview_title", "Stage generated boards"),
                        HelpText("box_preview_help", "Stage a preview, then use the global Apply button to commit the generated boards to the scene."),
                        ButtonRow(
                            "box_actions",
                            "Actions",
                            buttons=(("stage_preview", "Generate preview"), ("reset_values", "Reset")),
                            callbacks={
                                "stage_preview": lambda event: self._stage_preview(ctx, event),
                                "reset_values": lambda event: self._reset_values(ctx, event),
                            },
                        ),
                    ),
                ),
            ),
        )

    def _operation_generate(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        values = self._box_values(params or ctx.inspector.values())
        boards, meshes, metrics = build_box_meshes(**values)
        report = format_box_metrics_report(
            boards,
            metrics,
            str(values["corner_joint"]),
            str(values["top_front_joint"]),
            str(values["top_side_joint"]),
        )
        return OperationResult.success(
            tuple(meshes),
            report=report,
            metadata={
                "box_values": values,
                "board_count": len(boards),
                "outer_volume_l": metrics.outer_volume_l,
                "inner_volume_l": metrics.inner_volume_l,
                "board_cut_area_m2": metrics.board_cut_area_m2,
            },
        )

    def _stage_preview(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if not ctx.document.ensure() or not ctx.document.available:
            ctx.status.error("Box preview needs an active document before staging boards.")
            return False
        values = self._box_values(event.values if event is not None else ctx.inspector.values())
        result = ctx.operations.box_generate(params=values, preview=False, owner_tool=self.id)
        if not result.ok or not result.meshes:
            ctx.status.error("Box preview failed: " + "; ".join(result.errors))
            return False
        base_meshes = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        meshes = [*base_meshes, *result.meshes]
        session = ctx.preview_session.start(owner_tool=self.id, label="Box generator append preview")
        session.show_meshes(meshes)
        ctx.scene_selection.select_indices(range(len(base_meshes), len(meshes)))
        ctx.workflow.goto("preview")
        ctx.status.info(
            "Box staged: "
            f"{len(result.meshes)} boards | internal={float(result.metadata.get('inner_volume_l', 0.0)):.4f} L "
            f"| sheet={float(result.metadata.get('board_cut_area_m2', 0.0)):.4f} m²"
        )
        return True

    def _reset_values(self, ctx: Any, _event: InspectorActionEvent | None = None) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Box preview discarded because parameters were reset.")
        defaults = DEFAULT_SETTINGS
        ctx.inspector.update_values(
            {
                "width": defaults["outer_width_mm"],
                "depth": defaults["outer_depth_mm"],
                "height": defaults["outer_height_mm"],
                "thickness": defaults["wood_thickness_mm"],
                "corner_joint": defaults["corner_joint"],
                "top_front_joint": defaults["top_front_joint"],
                "top_side_joint": defaults["top_side_joint"],
            },
            notify=False,
        )
        self._sync_report(ctx)
        ctx.status.info("Box parameters reset.")

    def _on_values_changed(self, ctx: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Box preview discarded because parameters changed.")
        self._sync_report(ctx)

    def _sync_report(self, ctx: Any) -> None:
        try:
            report = self.metrics_report(ctx)
            ctx.inspector.set_display_value("box_report", report)
            ctx.inspector.clear_error("box_report")
        except Exception as exc:
            try:
                ctx.inspector.set_display_value("box_report", f"Invalid parameters: {exc}")
                ctx.inspector.set_error("box_report", str(exc))
            except Exception:
                pass

    def _box_values(self, raw: dict[str, Any]) -> dict[str, object]:
        values = {
            "width": float(raw.get("width", DEFAULT_SETTINGS["outer_width_mm"])),
            "depth": float(raw.get("depth", DEFAULT_SETTINGS["outer_depth_mm"])),
            "height": float(raw.get("height", DEFAULT_SETTINGS["outer_height_mm"])),
            "thickness": float(raw.get("thickness", DEFAULT_SETTINGS["wood_thickness_mm"])),
            "corner_joint": option_value(str(raw.get("corner_joint", DEFAULT_SETTINGS["corner_joint"])), CORNER_JOINT_OPTIONS),
            "top_front_joint": option_value(str(raw.get("top_front_joint", DEFAULT_SETTINGS["top_front_joint"])), TOP_FRONT_JOINT_OPTIONS),
            "top_side_joint": option_value(str(raw.get("top_side_joint", DEFAULT_SETTINGS["top_side_joint"])), TOP_SIDE_JOINT_OPTIONS),
        }
        # Validate through the fabrication backend so the Creator tool and panel
        # bridge report exactly the same errors.
        make_box_boards(**values)
        return values



class BoxTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Box CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=BoxCreatorTool())

    def build_meshes(self, context: Any):
        return self.creator.build_meshes(self.tool_context(context))

    def metrics_report(self, context: Any) -> str:
        return self.creator.metrics_report(self.tool_context(context))


__all__ = ["BoxCreatorTool", "BoxTool"]

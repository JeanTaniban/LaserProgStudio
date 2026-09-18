# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.geometry_ops.cavity_volume import (
    CavityVolumeReport,
    combine_meshes_for_cavity_measurement,
    measure_box_generator_selection,
    measure_cavity_volume,
)
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.scene import ToolServiceError
from laserprog_studio.tool_api.inspector import ButtonRow, HelpText, InspectorActionEvent, Panel, ReadonlyField, Section, Title
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_VOLUME_MEASURE


def _fmt_liters(value: float) -> str:
    if abs(value) >= 100.0:
        return f"{value:.2f} L"
    if abs(value) >= 10.0:
        return f"{value:.3f} L"
    return f"{value:.4f} L"


def _fmt_mm3(value: float) -> str:
    return f"{value:,.0f} mm³".replace(",", " ")


def format_cavity_volume_report(report: CavityVolumeReport, *, selected_index: int | str | None) -> str:
    """Format a measured cavity report for the Creator inspector."""

    index_text = "—" if selected_index is None else str(selected_index)
    lines = [
        f"Part(s): {index_text} - {report.mesh_name}",
        f"Cavity: {_fmt_liters(report.cavity_volume_liters)}",
        f"Cavity: {_fmt_mm3(report.cavity_volume_mm3)}",
        f"Approx. outer volume: {_fmt_liters(report.outer_volume_liters)}",
        f"Estimated material: {_fmt_liters(report.solid_volume_liters_estimate)}",
        f"Closed shells: {report.closed_shell_count}/{report.shell_count}  |  Cavities: {report.cavity_count}",
    ]
    if report.warning:
        lines.extend(("", f"⚠ {report.warning}"))
    return "\n".join(lines)


class CavityVolumeCreatorTool(CreatorTool):
    """Selection-based cavity volume measurement implemented with Creator API.

    The tool deliberately has no direct Qt panel/controller dependency: selected
    meshes come from ``ctx.scene_selection``, computation is exposed through
    ``ctx.operations.cavity_volume`` and the right inspector is entirely
    declarative.
    """

    id = TOOL_VOLUME_MEASURE
    label = "Cavity volume"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects("select", "Select closed parts", help="Select one fused part, or multiple parts forming a closed volume."),
                ctx.workflow.step("measure", "Measure", help="Measure the current selection through ctx.operations.cavity_volume.", optional=True),
            ),
        )
        ctx.operations.register("cavity_volume", self._operation_measure, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_report(ctx, auto=True)
        ctx.status.info("Cavity volume ready. Select one or more closed parts, then measure.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        ctx.inspector.clear()
        return True

    def on_apply(self, ctx: Any) -> bool:  # measurement tools do not mutate the document
        ctx.status.info("Cavity volume is a measurement tool; there is nothing to apply.")
        return False

    def on_scene_selection_changed(self, ctx: Any) -> None:
        ctx.inspector.set_display_value("selection_summary", self._selection_summary(ctx))
        if ctx.scene_selection.selected_indices():
            ctx.inspector.set_display_value("volume_report", "Selection changed. Click Measure selected cavity to update the report.")
            ctx.inspector.clear_error("volume_report")
        else:
            ctx.inspector.set_display_value("volume_report", "Select one or more parts, then measure.")
            ctx.inspector.set_error("volume_report", "No scene object selected.")
        ctx.workflow.goto("select")

    def _panel(self, ctx: Any) -> Panel:
        return Panel(
            "Cavity volume",
            id="cavity_volume.measure",
            owner_tool=self.id,
            description="Measure internal cavity volume from the current scene selection through the Creator API.",
            sections=(
                Section(
                    "Selection",
                    fields=(
                        HelpText("volume_help", "Select one watertight part, or several selected panels/walls that form one closed volume."),
                        ReadonlyField("selection_summary", "Selected", default="No valid selection."),
                    ),
                ),
                Section(
                    "Report",
                    fields=(
                        ReadonlyField("volume_report", "Measurement", default="Select one or more parts, then measure."),
                    ),
                ),
                Section(
                    "Actions",
                    fields=(
                        Title("volume_actions_title", "Measure current selection"),
                        ButtonRow(
                            "volume_actions",
                            "Actions",
                            buttons=(("measure", "Measure selected cavity"),),
                            callbacks={"measure": lambda event: self._measure_action(ctx, event)},
                        ),
                    ),
                ),
            ),
        )

    def _operation_measure(self, _inputs: tuple[Any, ...], _params: dict[str, Any], ctx: Any) -> OperationResult:
        selected_index, mesh, direct_report, error, single_shell_as_cavity = self._selected_cavity_mesh(ctx)
        if error:
            return OperationResult.failure(error, report=error, metadata={"selected_index": selected_index})
        report = direct_report if direct_report is not None else measure_cavity_volume(mesh, single_closed_shell_as_cavity=single_shell_as_cavity)
        text = format_cavity_volume_report(report, selected_index=selected_index)
        return OperationResult.success(
            (),
            report=text,
            warnings=(report.warning,) if report.warning else (),
            metadata={
                "selected_index": selected_index,
                "mesh_name": report.mesh_name,
                "cavity_volume_liters": report.cavity_volume_liters,
                "cavity_volume_mm3": report.cavity_volume_mm3,
                "outer_volume_liters": report.outer_volume_liters,
                "solid_volume_liters_estimate": report.solid_volume_liters_estimate,
                "closed_shell_count": report.closed_shell_count,
                "shell_count": report.shell_count,
                "cavity_count": report.cavity_count,
                "single_closed_shell_as_cavity": single_shell_as_cavity,
            },
        )

    def _measure_action(self, ctx: Any, _event: InspectorActionEvent | None = None) -> bool:
        return self._sync_report(ctx, auto=False)

    def _sync_report(self, ctx: Any, *, auto: bool) -> bool:
        result = ctx.operations.cavity_volume(inputs=(), params={"auto": bool(auto)}, preview=False, owner_tool=self.id)
        try:
            ctx.inspector.set_display_value("selection_summary", self._selection_summary(ctx))
            if result.ok:
                ctx.inspector.set_display_value("volume_report", result.report or "No cavity measured.")
                ctx.inspector.clear_error("volume_report")
                ctx.workflow.goto("measure")
                ctx.status.info(
                    "Cavity measured: "
                    f"{float(result.metadata.get('cavity_volume_liters', 0.0)):.6f} L "
                    f"| shells={int(result.metadata.get('closed_shell_count', 0))}/{int(result.metadata.get('shell_count', 0))}"
                )
                return True
            message = "; ".join(result.errors) or "Cavity volume measurement failed."
            ctx.inspector.set_display_value("volume_report", message)
            ctx.inspector.set_error("volume_report", message)
            if not auto:
                ctx.status.error(message)
            return False
        except Exception as exc:  # defensive UI sync guard
            ctx.status.error(f"Cavity volume report update failed: {exc}")
            return False

    def _selection_summary(self, ctx: Any) -> str:
        indices = tuple(ctx.scene_selection.selected_indices())
        if not indices:
            return "No scene object selected."
        return ", ".join(f"{int(index):02d}" for index in indices)

    def _selected_cavity_mesh(self, ctx: Any):
        meshes = tuple(ctx.document.meshes(include_preview=False))
        indices = tuple(int(i) for i in ctx.scene_selection.selected_indices())
        if not indices:
            return None, None, None, "Select one fused part, or multiple parts forming a closed volume.", False
        valid = tuple(i for i in indices if 0 <= i < len(meshes))
        if len(valid) != len(indices):
            return None, None, None, "The selection contains an invalid part.", False
        selection_text = ", ".join(f"{int(i):02d}" for i in valid)
        if len(valid) == 1:
            idx = int(valid[0])
            return f"{idx:02d}", meshes[idx], None, None, False

        box_report = measure_box_generator_selection(meshes, valid)
        if box_report is not None:
            return selection_text, None, box_report, None, False

        combined = combine_meshes_for_cavity_measurement([meshes[i] for i in valid])
        # In multi-selection mode, selected pieces may be the walls of the
        # measured volume. If welding creates exactly one watertight shell,
        # count that shell as the measured cavity volume.
        return selection_text, combined, None, None, True


class CavityVolumeTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Cavity Volume CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=CavityVolumeCreatorTool())

    def measure(self, context: Any) -> OperationResult:
        ctx = self.tool_context(context)
        return ctx.operations.cavity_volume(inputs=(), params={}, preview=False, owner_tool=TOOL_VOLUME_MEASURE)


__all__ = ["CavityVolumeCreatorTool", "CavityVolumeTool", "format_cavity_volume_report"]

# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.geometry_ops.mesh_repair import repair_work_mesh
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tool_api.inspector import (
    AutoPreview,
    BoolField,
    ButtonRow,
    ChoiceField,
    FloatField,
    HelpText,
    InspectorActionEvent,
    Panel,
    ReadonlyField,
    Section,
)

from .base import ToolSpec
from .ids import TOOL_MOD_REPAIR
from .mesh_repair import (
    REPAIR_FEEDBACK_WINDOW_ID,
    build_repair_feedback_window,
    repair_preset_choices,
    repair_preset_note,
    repair_preset_values,
    repair_settings_from_values,
    selected_indices_text,
    validate_repair_targets,
)


def format_repair_line(index: int, report: Any) -> str:
    suffix = ", trimesh" if bool(getattr(report, "trimesh_repair_used", False)) else ""
    return (
        f"{int(index)}: V {report.input_vertices}->{report.output_vertices}, "
        f"T {report.input_triangles}->{report.output_triangles}, "
        f"closed {int(report.closed_before)}->{int(report.closed_after)}, "
        f"boundary {report.boundary_edges_before}->{report.boundary_edges_after}, "
        f"nonmanifold {report.nonmanifold_edges_before}->{report.nonmanifold_edges_after}"
        f"{suffix}"
    )


def _copy_display_metadata(source: Any, repaired: Any) -> Any:
    for attr in ("name", "color", "material", "engraving", "texture_projections", "mesh_id"):
        if hasattr(source, attr):
            try:
                setattr(repaired, attr, copy.deepcopy(getattr(source, attr)))
            except Exception:
                pass
    return repaired


class RepairMeshCreatorTool(CreatorTool):
    """Product-ready mesh repair modifier built on the Creator API."""

    id = TOOL_MOD_REPAIR
    label = "Repair mesh"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects("select", "Select meshes", help="Select one or more meshes to repair."),
                ctx.workflow.step("tune", "Tune repair", help="Choose a cleanup preset or adjust repair options."),
                ctx.workflow.step("preview", "Preview repair", help="Stage repaired meshes before applying them.", optional=True),
            ),
        )
        ctx.operations.register("repair", self._operation_repair, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_selection_report(ctx, default="Choose a repair preset, then Preview.")
        ctx.status.info("Repair mesh ready. Select parts, preview, then Apply.")

    def on_close(self, ctx: Any) -> None:
        ctx.overlay.hide_window(REPAIR_FEEDBACK_WINDOW_ID)
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.cancel())
        message = "Repair preview cancelled." if changed else "No active repair preview."
        self._set_report(ctx, message, ok=True)
        self._sync_feedback(ctx, status=message)
        return changed

    def on_apply(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.apply(label="Mesh repair applied", operation_type="modifier_repair"))
        message = "Mesh repair applied." if changed else "Preview first, then apply."
        self._set_report(ctx, message, ok=changed)
        self._sync_feedback(ctx, status=message)
        return changed

    def on_event(self, event: Any, ctx: Any) -> bool:
        action_id = str(getattr(event, "action_id", "") or getattr(event, "id", ""))
        return self._handle_action_id(action_id, ctx)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        self._handle_action_id(str(button_id), ctx)

    def _handle_action_id(self, action_id: str, ctx: Any) -> bool:
        if action_id in {"repair_overlay_preview", "preview"}:
            return self._preview_action(ctx, None)
        if action_id in {"repair_overlay_apply", "apply_repair"}:
            return self._apply_action(ctx, None)
        if action_id in {"repair_overlay_cancel", "cancel_preview"}:
            return self.on_cancel(ctx)
        return False

    def on_scene_selection_changed(self, ctx: Any) -> None:
        self._sync_selection_report(ctx)
        if ctx.scene_selection.selected_indices():
            ctx.status.info("Repair selection updated. Preview to stage the selected parts.")
        ctx.workflow.goto("select")

    def _panel(self, ctx: Any) -> Panel:
        setting_change = lambda _field, _value: self._on_setting_changed(ctx)
        return Panel(
            "Repair mesh",
            id="modifier.repair",
            owner_tool=self.id,
            description="Clean selected meshes with presets, preflight checks and a non-destructive preview.",
            auto_preview=AutoPreview(
                action_id="preview",
                debounce_ms=350,
                include_fields=("repair_preset", "tolerance_mm", "fill_holes", "remove_tiny_faces"),
            ),
            sections=(
                Section(
                    "Selection",
                    fields=(
                        HelpText("repair_help", "Select one or more real parts. Helpers and texture decals are skipped automatically."),
                        ReadonlyField("selection_summary", "Selected", default="No mesh selected."),
                        ReadonlyField("preflight_check", "Check", default="No repair target checked yet."),
                    ),
                ),
                Section(
                    "Quick repair",
                    fields=(
                        ChoiceField("repair_preset", "Preset", default="balanced", choices=repair_preset_choices(), on_change=lambda _field, value: self._on_preset_change(ctx, value)),
                        ReadonlyField("preset_note", "Preset note", default=repair_preset_note("balanced")),
                    ),
                ),
                Section(
                    "Repair options",
                    fields=(
                        FloatField("tolerance_mm", "Tolerance", default=0.01, min_value=0.0001, max_value=10.0, step=0.005, unit="mm", on_change=setting_change),
                        BoolField("fill_holes", "Fill holes", default=True, on_change=setting_change),
                        BoolField("remove_tiny_faces", "Remove tiny/degenerate faces", default=True, on_change=setting_change),
                    ),
                ),
                Section(
                    "Preview and apply",
                    fields=(
                        ButtonRow(
                            "repair_actions",
                            "Actions",
                            buttons=(("preview", "Preview"), ("apply_repair", "Apply"), ("cancel_preview", "Cancel")),
                            callbacks={
                                "preview": lambda event: self._preview_action(ctx, event),
                                "apply_repair": lambda event: self._apply_action(ctx, event),
                                "cancel_preview": lambda _event: self.on_cancel(ctx),
                            },
                        ),
                        ReadonlyField("repair_report", "Report", default="Ready. Preview repair to stage selected parts."),
                    ),
                ),
            ),
        )

    def _operation_repair(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        settings = repair_settings_from_values(params)
        check = validate_repair_targets(ctx, settings)
        if not check.ok:
            return OperationResult.failure(check.message, metadata={"skipped_indices": check.skipped_indices})

        base_meshes = list(ctx.document.meshes(include_preview=False))
        meshes = [copy.deepcopy(mesh) for mesh in base_meshes]
        lines: list[str] = []
        changed_indices: list[int] = []
        skipped = list(check.skipped_indices)
        for index in check.target_indices:
            mesh = base_meshes[index]
            repaired, report = repair_work_mesh(
                mesh,
                tolerance_mm=settings.tolerance_mm,
                fill_holes=settings.fill_holes,
                remove_tiny_faces=settings.remove_tiny_faces,
            )
            meshes[index] = _copy_display_metadata(mesh, repaired)
            changed_indices.append(index)
            lines.append(format_repair_line(index, report))

        if not changed_indices:
            return OperationResult.failure("No repairable part in the selection.", report="No repairable part in the selection.")
        report_text = f"Repair preview ready. {settings.summary}.\n" + "\n".join(lines[:8])
        if len(lines) > 8:
            report_text += f"\n… +{len(lines) - 8} more"
        return OperationResult.success(
            tuple(meshes),
            report=report_text,
            metadata={
                "changed_indices": tuple(changed_indices),
                "skipped_indices": tuple(skipped),
                "selected_indices": tuple(check.target_indices),
                "line_count": len(lines),
                "settings_summary": settings.summary,
                "preset_id": settings.preset_id,
            },
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = dict(event.values if event is not None else ctx.inspector.values())
        settings = repair_settings_from_values(values)
        check = validate_repair_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if not check.ok:
            ctx.status.error(check.message)
            self._set_report(ctx, check.message, ok=False)
            self._sync_feedback(ctx, status=check.message)
            return False

        result = ctx.operations.repair(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Repair operation finished."), ok=result.ok)
        self._sync_selection_report(ctx, update_report=False)
        if not result.ok or not result.meshes:
            message = "; ".join(result.errors) or "Repair failed."
            ctx.status.error(message)
            self._sync_feedback(ctx, status=message)
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Mesh repair preview")
        session.show_meshes(result.meshes)
        selected = tuple(int(i) for i in result.metadata.get("changed_indices", ()) if isinstance(i, int) or str(i).isdigit())
        if selected:
            ctx.scene_selection.select_indices(selected, active_index=selected[-1])
        ctx.workflow.goto("preview")
        ctx.status.info("Repair preview ready. Use Apply to keep it or Cancel to discard it.")
        self._sync_feedback(ctx, status="Preview ready. Apply to keep it.")
        return True

    def _apply_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if not self._preview_action(ctx, event):
            return False
        return self.on_apply(ctx)

    def _on_preset_change(self, ctx: Any, value: Any) -> None:
        preset_id = str(value or "custom")
        for field_id, field_value in repair_preset_values(preset_id).items():
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        try:
            ctx.inspector.set_display_value("preset_note", repair_preset_note(preset_id))
        except Exception:
            pass
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Preset loaded." if preset_id != "custom" else "Custom repair settings.")

    def _on_setting_changed(self, ctx: Any) -> None:
        try:
            if ctx.inspector.value("repair_preset", "custom") != "custom":
                ctx.inspector.update_value("repair_preset", "custom", notify=False)
                ctx.inspector.set_display_value("preset_note", repair_preset_note("custom"))
        except Exception:
            pass
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Repair settings edited.")

    def _sync_selection_report(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        indices = tuple(ctx.scene_selection.selected_indices())
        summary = selected_indices_text(indices)
        ctx.inspector.set_display_value("selection_summary", summary)
        settings = repair_settings_from_values(ctx.inspector.values())
        check = validate_repair_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if default is not None and update_report:
            ctx.inspector.set_display_value("repair_report", default)
        elif update_report:
            ctx.inspector.set_display_value("repair_report", f"Selected: {summary}\n{check.message}")
        self._sync_feedback(ctx, status=check.message)

    def _sync_preflight(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("preflight_check", text)
        if ok:
            ctx.inspector.clear_error("preflight_check")
        else:
            ctx.inspector.set_error("preflight_check", text)

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("repair_report", text)
        if ok:
            ctx.inspector.clear_error("repair_report")
        else:
            ctx.inspector.set_error("repair_report", text)

    def _sync_feedback(self, ctx: Any, *, status: str) -> None:
        try:
            settings = repair_settings_from_values(ctx.inspector.values())
            selected = tuple(ctx.scene_selection.selected_indices())
            ctx.overlay.show_window(
                build_repair_feedback_window(
                    owner_tool=self.id,
                    settings=settings,
                    selected_indices=selected,
                    status=status,
                )
            )
        except Exception:
            pass


class RepairMeshTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Repair Mesh CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=RepairMeshCreatorTool())

    def preview_repair(self, context: Any) -> OperationResult:
        ctx = self.tool_context(context)
        return ctx.operations.repair(inputs=(), params=ctx.inspector.values(), preview=False, owner_tool=TOOL_MOD_REPAIR)


__all__ = ["RepairMeshCreatorTool", "RepairMeshTool", "format_repair_line"]

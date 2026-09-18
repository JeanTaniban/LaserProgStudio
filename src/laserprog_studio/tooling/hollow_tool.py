# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.geometry_ops.hollow import hollow_selected_meshes
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tool_api.inspector import (
    AutoPreview,
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
from .ids import TOOL_MOD_HOLLOW
from .mesh_hollow import (
    CUSTOM_PRESET_ID,
    HOLLOW_FEEDBACK_WINDOW_ID,
    build_hollow_feedback_window,
    hollow_preset_choices,
    hollow_preset_note,
    hollow_preset_values,
    hollow_settings_from_values,
    selected_indices_text,
    triangle_count,
    validate_hollow_targets,
)


def _format_hollow_report(*, selected_count: int, before: int, after: int | None = None, message: str = "") -> str:
    if message:
        return str(message)
    if after is None:
        return f"Selected: {int(selected_count)}\nTriangles before: {int(before)}"
    return f"Hollow preview ready.\nSelected: {int(selected_count)}\nTriangles: {int(before)} → {int(after)}"


class HollowCreatorTool(CreatorTool):
    """Product-ready hollow modifier built on the Creator API."""

    id = TOOL_MOD_HOLLOW
    label = "Hollow"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects("select", "Select closed meshes", help="Select one or more closed manifold meshes to hollow."),
                ctx.workflow.step("tune", "Tune shell", help="Choose a wall preset or adjust shell thickness."),
                ctx.workflow.step("preview", "Preview hollow", help="Stage hollowed meshes before applying them.", optional=True),
            ),
        )
        ctx.operations.register("hollow", self._operation_hollow, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_selection_report(ctx, default="Choose a hollow preset, then Preview.")
        ctx.status.info("Hollow ready. Select closed parts, preview, then Apply.")

    def on_close(self, ctx: Any) -> None:
        ctx.overlay.hide_window(HOLLOW_FEEDBACK_WINDOW_ID)
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.cancel())
        message = "Hollow preview cancelled." if changed else "No active hollow preview."
        self._set_report(ctx, message, ok=True)
        self._sync_feedback(ctx, status=message)
        return changed

    def on_apply(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.apply(label="Hollow applied", operation_type="modifier_hollow"))
        message = "Hollow applied." if changed else "Preview first, then apply."
        self._set_report(ctx, message, ok=changed)
        self._sync_feedback(ctx, status=message)
        return changed

    def on_event(self, event: Any, ctx: Any) -> bool:
        action_id = str(getattr(event, "action_id", "") or getattr(event, "id", ""))
        return self._handle_action_id(action_id, ctx)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        self._handle_action_id(str(button_id), ctx)

    def _handle_action_id(self, action_id: str, ctx: Any) -> bool:
        if action_id in {"hollow_overlay_preview", "preview"}:
            return self._preview_action(ctx, None)
        if action_id in {"hollow_overlay_apply", "apply_hollow"}:
            return self._apply_action(ctx, None)
        if action_id in {"hollow_overlay_cancel", "cancel_preview"}:
            return self.on_cancel(ctx)
        return False

    def on_scene_selection_changed(self, ctx: Any) -> None:
        self._sync_selection_report(ctx)
        if ctx.scene_selection.selected_indices():
            ctx.status.info("Hollow selection updated. Preview to stage the selected parts.")
        ctx.workflow.goto("select")

    def _panel(self, ctx: Any) -> Panel:
        setting_change = lambda _field, _value: self._on_setting_changed(ctx)
        return Panel(
            "Hollow",
            id="modifier.hollow",
            owner_tool=self.id,
            description="Create inner shells for selected closed meshes with presets, preflight checks and a non-destructive preview.",
            auto_preview=AutoPreview(
                action_id="preview",
                debounce_ms=350,
                include_fields=("hollow_preset", "thickness_mm"),
            ),
            sections=(
                Section(
                    "Selection",
                    fields=(
                        HelpText("hollow_help", "Select one or more closed parts. Open or non-manifold meshes are reported before Apply."),
                        ReadonlyField("selection_summary", "Selected", default="No mesh selected."),
                        ReadonlyField("preflight_check", "Check", default="No hollow target checked yet."),
                    ),
                ),
                Section(
                    "Quick hollow",
                    fields=(
                        ChoiceField("hollow_preset", "Preset", default="balanced", choices=hollow_preset_choices(), on_change=lambda _field, value: self._on_preset_change(ctx, value)),
                        ReadonlyField("preset_note", "Preset note", default=hollow_preset_note("balanced")),
                    ),
                ),
                Section(
                    "Shell options",
                    fields=(
                        FloatField(
                            "thickness_mm",
                            "Wall thickness",
                            default=2.0,
                            min_value=0.001,
                            max_value=100000.0,
                            step=0.5,
                            unit="mm",
                            tooltip="Distance used to offset the inner shell. Must fit inside the smallest selected part.",
                            on_change=setting_change,
                        ),
                    ),
                ),
                Section(
                    "Preview and apply",
                    fields=(
                        ButtonRow(
                            "hollow_actions",
                            "Actions",
                            buttons=(("preview", "Preview"), ("apply_hollow", "Apply"), ("cancel_preview", "Cancel")),
                            callbacks={
                                "preview": lambda event: self._preview_action(ctx, event),
                                "apply_hollow": lambda event: self._apply_action(ctx, event),
                                "cancel_preview": lambda _event: self.on_cancel(ctx),
                            },
                        ),
                        ReadonlyField("hollow_report", "Report", default="Ready. Preview hollow to stage selected parts."),
                    ),
                ),
            ),
        )

    def _operation_hollow(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        settings = hollow_settings_from_values(params)
        check = validate_hollow_targets(ctx, settings)
        if not check.ok:
            return OperationResult.failure(check.message, report=check.message)

        base_meshes = list(ctx.document.meshes(include_preview=False))
        chosen = tuple(int(i) for i in check.target_indices)
        before = sum(triangle_count(base_meshes[i]) for i in chosen)
        backend_result = hollow_selected_meshes([copy.deepcopy(mesh) for mesh in base_meshes], list(chosen), thickness=settings.thickness_mm)
        if not backend_result.ok:
            message = "\n".join(getattr(backend_result, "errors", ()) or ()) or "Hollow failed."
            return OperationResult.failure(message, report=message)
        meshes = tuple(backend_result.meshes)
        after = sum(triangle_count(meshes[i]) for i in chosen if 0 <= i < len(meshes))
        report = _format_hollow_report(selected_count=len(chosen), before=before, after=after)
        return OperationResult.success(
            meshes,
            report=report,
            warnings=getattr(backend_result, "warnings", ()),
            metadata={
                "changed_indices": tuple(chosen),
                "selected_indices": tuple(chosen),
                "before_triangles": before,
                "after_triangles": after,
                "thickness_mm": settings.thickness_mm,
                "settings_summary": settings.summary,
                "preset_id": settings.preset_id,
            },
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = dict(event.values if event is not None else ctx.inspector.values())
        settings = hollow_settings_from_values(values)
        check = validate_hollow_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if not check.ok:
            ctx.status.error(check.message)
            self._set_report(ctx, check.message, ok=False)
            self._sync_feedback(ctx, status=check.message)
            return False

        result = ctx.operations.hollow(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Hollow operation finished."), ok=result.ok)
        self._sync_selection_report(ctx, update_report=False)
        if not result.ok or not result.meshes:
            message = "; ".join(result.errors) or "Hollow failed."
            ctx.status.error(message)
            self._sync_feedback(ctx, status=message)
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Hollow preview")
        session.show_meshes(result.meshes)
        selected = tuple(int(i) for i in result.metadata.get("changed_indices", ()) if isinstance(i, int) or str(i).isdigit())
        if selected:
            ctx.scene_selection.select_indices(selected, active_index=selected[-1])
        ctx.workflow.goto("preview")
        ctx.status.info("Hollow preview ready. Use Apply to keep it or Cancel to discard it.")
        self._sync_feedback(ctx, status="Preview ready. Apply to keep it.")
        return True

    def _apply_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if not self._preview_action(ctx, event):
            return False
        return self.on_apply(ctx)

    def _on_preset_change(self, ctx: Any, value: Any) -> None:
        preset_id = str(value or CUSTOM_PRESET_ID)
        for field_id, field_value in hollow_preset_values(preset_id).items():
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        try:
            ctx.inspector.set_display_value("preset_note", hollow_preset_note(preset_id))
        except Exception:
            pass
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Preset loaded." if preset_id != CUSTOM_PRESET_ID else "Custom hollow settings.")

    def _on_setting_changed(self, ctx: Any) -> None:
        try:
            if ctx.inspector.value("hollow_preset", CUSTOM_PRESET_ID) != CUSTOM_PRESET_ID:
                ctx.inspector.update_value("hollow_preset", CUSTOM_PRESET_ID, notify=False)
                ctx.inspector.set_display_value("preset_note", hollow_preset_note(CUSTOM_PRESET_ID))
        except Exception:
            pass
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Hollow settings edited.")

    def _sync_selection_report(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        indices = tuple(ctx.scene_selection.selected_indices())
        summary = selected_indices_text(indices) if indices else "No mesh selected."
        ctx.inspector.set_display_value("selection_summary", summary)
        settings = hollow_settings_from_values(ctx.inspector.values())
        check = validate_hollow_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if default is not None and update_report:
            ctx.inspector.set_display_value("hollow_report", default)
        elif update_report:
            ctx.inspector.set_display_value(
                "hollow_report",
                _format_hollow_report(selected_count=len(check.target_indices), before=check.before_triangles),
            )
        self._sync_feedback(ctx, status=check.message)

    def _sync_preflight(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("preflight_check", text)
        if ok:
            ctx.inspector.clear_error("preflight_check")
        else:
            ctx.inspector.set_error("preflight_check", text)

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("hollow_report", text)
        if ok:
            ctx.inspector.clear_error("hollow_report")
        else:
            ctx.inspector.set_error("hollow_report", text)

    def _sync_feedback(self, ctx: Any, *, status: str) -> None:
        try:
            settings = hollow_settings_from_values(ctx.inspector.values())
            selected = tuple(ctx.scene_selection.selected_indices())
            ctx.overlay.show_window(
                build_hollow_feedback_window(
                    owner_tool=self.id,
                    settings=settings,
                    selected_indices=selected,
                    status=status,
                )
            )
        except Exception:
            pass


class HollowTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Hollow CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=HollowCreatorTool())

    def preview_hollow(self, context: Any) -> OperationResult:
        ctx = self.tool_context(context)
        return ctx.operations.hollow(inputs=(), params=ctx.inspector.values(), preview=False, owner_tool=TOOL_MOD_HOLLOW)


__all__ = ["HollowCreatorTool", "HollowTool"]

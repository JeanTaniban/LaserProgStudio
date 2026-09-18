# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.geometry_ops.simplify import simplify_selected_meshes
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tool_api.inspector import (
    AutoPreview,
    BoolField,
    ButtonRow,
    ChoiceField,
    HelpText,
    InspectorActionEvent,
    Panel,
    ReadonlyField,
    Section,
    SliderField,
)

from .base import ToolSpec
from .ids import TOOL_MOD_SIMPLIFY
from .mesh_simplify import (
    CUSTOM_PRESET_ID,
    SIMPLIFY_FEEDBACK_WINDOW_ID,
    build_simplify_feedback_window,
    selected_indices_text,
    simplify_preset_choices,
    simplify_preset_note,
    simplify_preset_values,
    simplify_settings_from_values,
    triangle_count,
    validate_simplify_targets,
)


def _format_simplify_report(*, selected_count: int, before: int, after: int | None = None, ok: bool = True, message: str = "") -> str:
    if message:
        return str(message)
    if after is None:
        return f"Selected: {int(selected_count)}\nTriangles before: {int(before)}"
    reduction = ((before - after) / before * 100.0) if before else 0.0
    prefix = "Simplify preview ready." if ok else "Simplify failed."
    return f"{prefix}\nSelected: {int(selected_count)}\nTriangles: {int(before)} → {int(after)}\nActual reduction: {reduction:.1f} %"


class SimplifyCreatorTool(CreatorTool):
    """Product-ready simplify modifier built on the Creator API."""

    id = TOOL_MOD_SIMPLIFY
    label = "Simplify"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects("select", "Select meshes", help="Select one or more meshes to simplify."),
                ctx.workflow.step("tune", "Tune simplify", help="Choose a reduction preset or adjust simplification options."),
                ctx.workflow.step("preview", "Preview simplify", help="Stage simplified meshes before applying them.", optional=True),
            ),
        )
        ctx.operations.register("simplify", self._operation_simplify, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_selection_report(ctx, default="Choose a simplify preset, then Preview.")
        ctx.status.info("Simplify ready. Select parts, preview, then Apply.")

    def on_close(self, ctx: Any) -> None:
        ctx.overlay.hide_window(SIMPLIFY_FEEDBACK_WINDOW_ID)
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.cancel())
        message = "Simplify preview cancelled." if changed else "No active simplify preview."
        self._set_report(ctx, message, ok=True)
        self._sync_feedback(ctx, status=message)
        return changed

    def on_apply(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.apply(label="Simplify applied", operation_type="modifier_simplify"))
        message = "Simplify applied." if changed else "Preview first, then apply."
        self._set_report(ctx, message, ok=changed)
        self._sync_feedback(ctx, status=message)
        return changed

    def on_event(self, event: Any, ctx: Any) -> bool:
        action_id = str(getattr(event, "action_id", "") or getattr(event, "id", ""))
        return self._handle_action_id(action_id, ctx)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        self._handle_action_id(str(button_id), ctx)

    def _handle_action_id(self, action_id: str, ctx: Any) -> bool:
        if action_id in {"simplify_overlay_preview", "preview"}:
            return self._preview_action(ctx, None)
        if action_id in {"simplify_overlay_apply", "apply_simplify"}:
            return self._apply_action(ctx, None)
        if action_id in {"simplify_overlay_cancel", "cancel_preview"}:
            return self.on_cancel(ctx)
        return False

    def on_scene_selection_changed(self, ctx: Any) -> None:
        self._sync_selection_report(ctx)
        if ctx.scene_selection.selected_indices():
            ctx.status.info("Simplify selection updated. Preview to stage the selected parts.")
        ctx.workflow.goto("select")

    def _panel(self, ctx: Any) -> Panel:
        setting_change = lambda _field, _value: self._on_setting_changed(ctx)
        return Panel(
            "Simplify",
            id="modifier.simplify",
            owner_tool=self.id,
            description="Reduce mesh density with presets, preflight checks and a non-destructive preview.",
            auto_preview=AutoPreview(
                action_id="preview",
                debounce_ms=350,
                include_fields=("simplify_preset", "reduction_percent", "preserve_topology"),
            ),
            sections=(
                Section(
                    "Selection",
                    fields=(
                        HelpText("simplify_help", "Select one or more real parts. Preview stages a simplified scene; Apply commits it."),
                        ReadonlyField("selection_summary", "Selected", default="No mesh selected."),
                        ReadonlyField("preflight_check", "Check", default="No simplify target checked yet."),
                    ),
                ),
                Section(
                    "Quick simplify",
                    fields=(
                        ChoiceField("simplify_preset", "Preset", default="balanced", choices=simplify_preset_choices(), on_change=lambda _field, value: self._on_preset_change(ctx, value)),
                        ReadonlyField("preset_note", "Preset note", default=simplify_preset_note("balanced")),
                    ),
                ),
                Section(
                    "Simplify options",
                    fields=(
                        SliderField(
                            "reduction_percent",
                            "Reduction",
                            default=50.0,
                            min_value=0.0,
                            max_value=95.0,
                            step=1.0,
                            unit="%",
                            tooltip="Approximate percentage of faces to remove.",
                            on_change=setting_change,
                        ),
                        ReadonlyField("reduction_label", "Reduction", default="Reduction: 50 %"),
                        BoolField(
                            "preserve_topology",
                            "Preserve topology",
                            default=True,
                            tooltip="Keep boundaries and refuse risky open meshes. Disable for stronger viewport reductions.",
                            on_change=setting_change,
                        ),
                    ),
                ),
                Section(
                    "Preview and apply",
                    fields=(
                        ButtonRow(
                            "simplify_actions",
                            "Actions",
                            buttons=(("preview", "Preview"), ("apply_simplify", "Apply"), ("cancel_preview", "Cancel")),
                            callbacks={
                                "preview": lambda event: self._preview_action(ctx, event),
                                "apply_simplify": lambda event: self._apply_action(ctx, event),
                                "cancel_preview": lambda _event: self.on_cancel(ctx),
                            },
                        ),
                        ReadonlyField("simplify_report", "Report", default="Ready. Preview simplify to stage selected parts."),
                    ),
                ),
            ),
        )

    def _operation_simplify(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        settings = simplify_settings_from_values(params)
        check = validate_simplify_targets(ctx, settings)
        if not check.ok:
            return OperationResult.failure(check.message, report=check.message)

        base_meshes = list(ctx.document.meshes(include_preview=False))
        valid = tuple(int(i) for i in check.target_indices)
        before = sum(triangle_count(base_meshes[i]) for i in valid)
        result = simplify_selected_meshes(
            [copy.deepcopy(mesh) for mesh in base_meshes],
            list(valid),
            reduction=settings.reduction_ratio,
            preserve_topology=settings.preserve_topology,
        )
        if not result.ok:
            message = "\n".join(result.errors) if getattr(result, "errors", ()) else "Simplify failed."
            return OperationResult.failure(message, report=message, warnings=getattr(result, "warnings", ()))
        meshes = tuple(result.meshes)
        after = sum(triangle_count(meshes[i]) for i in valid if 0 <= i < len(meshes))
        report = _format_simplify_report(selected_count=len(valid), before=before, after=after)
        return OperationResult.success(
            meshes,
            report=report,
            warnings=getattr(result, "warnings", ()),
            metadata={
                "changed_indices": tuple(valid),
                "selected_indices": tuple(valid),
                "before_triangles": before,
                "after_triangles": after,
                "reduction_percent": round(settings.reduction_percent, 3),
                "settings_summary": settings.summary,
                "preset_id": settings.preset_id,
            },
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = dict(event.values if event is not None else ctx.inspector.values())
        settings = simplify_settings_from_values(values)
        check = validate_simplify_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if not check.ok:
            ctx.status.error(check.message)
            self._set_report(ctx, check.message, ok=False)
            self._sync_feedback(ctx, status=check.message)
            return False

        result = ctx.operations.simplify(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Simplify operation finished."), ok=result.ok)
        self._sync_selection_report(ctx, update_report=False)
        if not result.ok or not result.meshes:
            message = "; ".join(result.errors) or "Simplify failed."
            ctx.status.error(message)
            self._sync_feedback(ctx, status=message)
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Simplify preview")
        session.show_meshes(result.meshes)
        selected = tuple(int(i) for i in result.metadata.get("changed_indices", ()) if isinstance(i, int) or str(i).isdigit())
        if selected:
            ctx.scene_selection.select_indices(selected, active_index=selected[-1])
        ctx.workflow.goto("preview")
        ctx.status.info("Simplify preview ready. Use Apply to keep it or Cancel to discard it.")
        self._sync_feedback(ctx, status="Preview ready. Apply to keep it.")
        return True

    def _apply_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if not self._preview_action(ctx, event):
            return False
        return self.on_apply(ctx)

    def _on_preset_change(self, ctx: Any, value: Any) -> None:
        preset_id = str(value or CUSTOM_PRESET_ID)
        for field_id, field_value in simplify_preset_values(preset_id).items():
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        try:
            ctx.inspector.set_display_value("preset_note", simplify_preset_note(preset_id))
        except Exception:
            pass
        self._sync_strength_label(ctx)
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Preset loaded." if preset_id != CUSTOM_PRESET_ID else "Custom simplify settings.")

    def _on_setting_changed(self, ctx: Any) -> None:
        try:
            if ctx.inspector.value("simplify_preset", CUSTOM_PRESET_ID) != CUSTOM_PRESET_ID:
                ctx.inspector.update_value("simplify_preset", CUSTOM_PRESET_ID, notify=False)
                ctx.inspector.set_display_value("preset_note", simplify_preset_note(CUSTOM_PRESET_ID))
        except Exception:
            pass
        self._sync_strength_label(ctx)
        self._sync_selection_report(ctx, update_report=False)
        self._sync_feedback(ctx, status="Simplify settings edited.")

    def _sync_strength_label(self, ctx: Any) -> None:
        value = ctx.inspector.value("reduction_percent", 50.0)
        try:
            value_text = f"{float(value):.0f}"
        except Exception:
            value_text = "50"
        ctx.inspector.set_display_value("reduction_label", f"Reduction: {value_text} %")

    def _sync_selection_report(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        indices = tuple(ctx.scene_selection.selected_indices())
        summary = selected_indices_text(indices) if indices else "No mesh selected."
        ctx.inspector.set_display_value("selection_summary", summary)
        self._sync_strength_label(ctx)
        settings = simplify_settings_from_values(ctx.inspector.values())
        check = validate_simplify_targets(ctx, settings)
        self._sync_preflight(ctx, check.message, ok=check.ok)
        if default is not None and update_report:
            ctx.inspector.set_display_value("simplify_report", default)
        elif update_report:
            ctx.inspector.set_display_value(
                "simplify_report",
                _format_simplify_report(selected_count=len(check.target_indices), before=check.before_triangles),
            )
        self._sync_feedback(ctx, status=check.message)

    def _sync_preflight(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("preflight_check", text)
        if ok:
            ctx.inspector.clear_error("preflight_check")
        else:
            ctx.inspector.set_error("preflight_check", text)

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("simplify_report", text)
        if ok:
            ctx.inspector.clear_error("simplify_report")
        else:
            ctx.inspector.set_error("simplify_report", text)

    def _sync_feedback(self, ctx: Any, *, status: str) -> None:
        try:
            settings = simplify_settings_from_values(ctx.inspector.values())
            selected = tuple(ctx.scene_selection.selected_indices())
            ctx.overlay.show_window(
                build_simplify_feedback_window(
                    owner_tool=self.id,
                    settings=settings,
                    selected_indices=selected,
                    status=status,
                )
            )
        except Exception:
            pass


class SimplifyTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Simplify CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=SimplifyCreatorTool())

    def preview_simplify(self, context: Any) -> OperationResult:
        ctx = self.tool_context(context)
        return ctx.operations.simplify(inputs=(), params=ctx.inspector.values(), preview=False, owner_tool=TOOL_MOD_SIMPLIFY)


__all__ = ["SimplifyCreatorTool", "SimplifyTool"]

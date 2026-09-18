# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import replace
from typing import Any

from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool
from laserprog_studio.tool_api.inspector import (
    AutoPreview,
    ButtonRow,
    ChoiceField,
    ColorField,
    FloatField,
    HelpText,
    InspectorActionEvent,
    Panel,
    ReadonlyField,
    Section,
    TextField,
)

from .base import ToolSpec
from .ids import TOOL_MATERIAL
from .material_painter import (
    material_from_values,
    material_preset_choices,
    material_preset_note,
    material_preset_values,
    material_settings_from_values,
    safe_hex_color,
    validate_material_apply,
)
from .material_painter.feedback import build_material_feedback_window, selected_indices_text


class MaterialCreatorTool(CreatorTool):
    """API-first Material Painter with presets, preflight and viewport feedback."""

    id = TOOL_MATERIAL
    label = "Materials"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_objects(
                    "select_targets",
                    "Select parts",
                    help="Select one or more scene parts, or use Target = All parts.",
                    optional=True,
                ),
                ctx.workflow.step("tune_material", "Tune material", help="Choose a preset or edit color, opacity and surface response."),
                ctx.workflow.step("preview_apply", "Preview and apply", help="Preview the material before committing it."),
            ),
        )
        ctx.modes.register(
            self.id,
            (
                ctx.modes.define("paint", "Paint", help="Click a part or preview the selected parts."),
                ctx.modes.define("all", "All parts", help="Apply the current material to every part."),
            ),
            active="paint",
        )
        ctx.operations.register("material_assign", self._operation_material, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._on_preset_change(ctx, str(ctx.inspector.value("preset_id", "custom")))
        self._sync_selection(ctx, default="Choose a material, then Preview or Apply.")
        ctx.status.info("Material Painter ready. Use presets, preview, then apply.")

    def on_close(self, ctx: Any) -> None:
        ctx.overlay.hide_window("material.painter.feedback")
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.cancel())
        self._set_report(ctx, "Preview cancelled." if changed else "No active material preview.", ok=True)
        self._sync_feedback(ctx, status="Preview cancelled." if changed else "Ready.")
        return changed

    def on_apply(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.apply(label="Material applied", operation_type="material"))
        self._set_report(ctx, "Material applied." if changed else "No active material preview to apply.", ok=changed)
        self._sync_feedback(ctx, status="Material applied." if changed else "Preview first, then apply.")
        return changed

    def on_event(self, event: Any, ctx: Any) -> bool:
        action_id = str(getattr(event, "action_id", "") or getattr(event, "id", ""))
        return self._handle_action_id(action_id, ctx)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        self._handle_action_id(str(button_id), ctx)

    def _handle_action_id(self, action_id: str, ctx: Any) -> bool:
        if action_id in {"material_overlay_preview", "preview"}:
            return self._preview_action(ctx, None)
        if action_id in {"material_overlay_apply", "apply_material"}:
            return self._apply_action(ctx, None)
        if action_id in {"material_overlay_cancel", "cancel_preview"}:
            return self.on_cancel(ctx)
        return False

    def on_scene_selection_changed(self, ctx: Any) -> None:
        self._sync_selection(ctx)

    def _panel(self, ctx: Any) -> Panel:
        material_change = lambda _field, _value: self._on_material_value_changed(ctx)
        return Panel(
            "Material Painter",
            id="material.painter",
            owner_tool=self.id,
            description="Assign presentation-ready visual materials through the Creator API.",
            auto_preview=AutoPreview(
                action_id="preview",
                debounce_ms=220,
                include_fields=("preset_id", "material_name", "material_color", "opacity", "metallic", "roughness", "target_scope"),
            ),
            sections=(
                Section(
                    "Quick start",
                    fields=(
                        HelpText("material_help", "Pick a preset, adjust the look, preview the target, then apply."),
                        ChoiceField("preset_id", "Preset", default="custom", choices=material_preset_choices(), on_change=lambda _field, value: self._on_preset_change(ctx, value)),
                        ReadonlyField("preset_note", "Preset note", default=material_preset_note("custom")),
                    ),
                ),
                Section(
                    "Material",
                    fields=(
                        TextField("material_name", "Name", default="Material", on_change=material_change),
                        ColorField("material_color", "Color", default="#336699", on_change=material_change),
                        FloatField("opacity", "Opacity", default=1.0, min_value=0.05, max_value=1.0, step=0.05, on_change=material_change),
                        FloatField("metallic", "Metallic", default=0.0, min_value=0.0, max_value=1.0, step=0.05, on_change=material_change),
                        FloatField("roughness", "Roughness", default=0.55, min_value=0.0, max_value=1.0, step=0.05, on_change=material_change),
                    ),
                ),
                Section(
                    "Target and apply",
                    fields=(
                        replace(
                            ChoiceField(
                                "target_scope",
                                "Target",
                                default="selected",
                                choices=(("selected", "Selected parts"), ("all", "All parts")),
                                on_change=lambda _field, value: self._on_target_changed(ctx, value),
                            ),
                            metadata={"persist": False},
                        ),
                        ReadonlyField("selection_summary", "Selected", default="No mesh selected."),
                        ReadonlyField("apply_check", "Check", default="No target checked yet."),
                        ButtonRow(
                            "material_actions",
                            "Actions",
                            buttons=(("preview", "Preview"), ("apply_material", "Apply"), ("cancel_preview", "Cancel")),
                            callbacks={
                                "preview": lambda event: self._preview_action(ctx, event),
                                "apply_material": lambda event: self._apply_action(ctx, event),
                                "cancel_preview": lambda event: self.on_cancel(ctx),
                            },
                        ),
                        ReadonlyField("material_report", "Report", default="Ready."),
                    ),
                ),
            ),
        )

    def _operation_material(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        base = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        settings = material_settings_from_values(params)
        check = validate_material_apply(ctx, settings)
        if not check.ok:
            return OperationResult.failure(check.message, metadata={"target_scope": settings.target_scope})
        material = settings.material
        for index in check.target_indices:
            base[index].material = copy.deepcopy(material)
            try:
                base[index].color = material.base_color
            except Exception:
                pass
        target_label = "all parts" if settings.target_scope == "all" else "selected parts"
        report = (
            "Material preview ready.\n"
            f"Material: {settings.summary}\n"
            f"Target: {target_label}\n"
            f"Parts: {', '.join(f'{i:02d}' for i in check.target_indices)}"
        )
        return OperationResult.success(
            tuple(base),
            report=report,
            metadata={
                "changed_indices": check.target_indices,
                "material_color": material.base_color,
                "material_name": material.name,
                "target_scope": settings.target_scope,
                "summary": settings.summary,
            },
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = dict(event.values if event is not None else ctx.inspector.values())
        settings = material_settings_from_values(values)
        check = validate_material_apply(ctx, settings)
        self._sync_apply_check(ctx, check.message, ok=check.ok)
        if not check.ok:
            ctx.status.error(check.message)
            self._set_report(ctx, check.message, ok=False)
            self._sync_feedback(ctx, status=check.message)
            return False
        result = ctx.operations.run("material_assign", inputs=(), params=values)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Material operation finished."), ok=result.ok)
        if not result.ok or not result.meshes:
            message = "; ".join(result.errors) or "Material preview failed."
            ctx.status.error(message)
            self._sync_feedback(ctx, status=message)
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Material preview")
        session.show_meshes(result.meshes)
        changed = tuple(int(i) for i in result.metadata.get("changed_indices", ()))
        if changed:
            ctx.scene_selection.select_indices(changed, active_index=changed[-1])
        if settings.target_scope == "all":
            ctx.modes.set(self.id, "all")
        else:
            ctx.modes.set(self.id, "paint")
        self._sync_selection(ctx, update_report=False)
        self._sync_feedback(ctx, status="Preview ready. Apply to keep it.")
        ctx.status.info("Material preview ready. Use Apply to keep it or Cancel to discard it.")
        return True

    def _apply_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        if not self._preview_action(ctx, event):
            return False
        return self.on_apply(ctx)

    def apply_to_index(self, ctx: Any, index: int) -> bool:
        ctx.scene_selection.select_indices((int(index),), active_index=int(index))
        ctx.inspector.update_value("target_scope", "selected", notify=False)
        return self._preview_action(ctx, None)

    def _on_preset_change(self, ctx: Any, value: Any) -> None:
        preset_id = str(value or "custom")
        for field_id, field_value in material_preset_values(preset_id).items():
            try:
                ctx.inspector.update_value(field_id, field_value, notify=False)
            except Exception:
                pass
        try:
            ctx.inspector.set_display_value("preset_note", material_preset_note(preset_id))
        except Exception:
            pass
        self._sync_selection(ctx, update_report=False)
        self._sync_feedback(ctx, status="Preset loaded." if preset_id != "custom" else "Custom material values.")

    def _on_material_value_changed(self, ctx: Any) -> None:
        try:
            if ctx.inspector.value("preset_id", "custom") != "custom":
                ctx.inspector.update_value("preset_id", "custom", notify=False)
                ctx.inspector.set_display_value("preset_note", material_preset_note("custom"))
        except Exception:
            pass
        self._sync_selection(ctx, update_report=False)
        self._sync_feedback(ctx, status="Material edited.")

    def _on_target_changed(self, ctx: Any, value: Any) -> None:
        mode = "all" if str(value) == "all" else "paint"
        try:
            ctx.modes.set(self.id, mode)
        except Exception:
            pass
        self._sync_selection(ctx, update_report=False)
        self._sync_feedback(ctx, status="Target changed.")

    def _sync_selection(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        selected = tuple(ctx.scene_selection.selected_indices())
        summary = selected_indices_text(selected)
        ctx.inspector.set_display_value("selection_summary", summary)
        settings = material_settings_from_values(ctx.inspector.values())
        check = validate_material_apply(ctx, settings)
        self._sync_apply_check(ctx, check.message, ok=check.ok)
        if update_report:
            ctx.inspector.set_display_value("material_report", default or f"Selected: {summary}")
        self._sync_feedback(ctx, status=check.message)

    def _sync_apply_check(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("apply_check", text)
        if ok:
            ctx.inspector.clear_error("apply_check")
        else:
            ctx.inspector.set_error("apply_check", text)

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("material_report", text)
        if ok:
            ctx.inspector.clear_error("material_report")
        else:
            ctx.inspector.set_error("material_report", text)

    def _sync_feedback(self, ctx: Any, *, status: str) -> None:
        try:
            settings = material_settings_from_values(ctx.inspector.values())
            selected = tuple(ctx.scene_selection.selected_indices())
            ctx.overlay.show_window(
                build_material_feedback_window(
                    owner_tool=self.id,
                    settings=settings,
                    selected_indices=selected,
                    status=status,
                )
            )
        except Exception:
            pass


class MaterialTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=MaterialCreatorTool())

    def apply_index(self, context: Any, index: int) -> bool:
        return bool(self.creator.apply_to_index(self.tool_context(context), int(index)))


__all__ = ["MaterialCreatorTool", "MaterialTool", "material_from_values", "safe_hex_color"]

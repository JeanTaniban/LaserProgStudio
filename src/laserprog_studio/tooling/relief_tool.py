# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.geometry_ops.text_relief import ReliefAnchor, add_text_relief_preview
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import ButtonRow, ChoiceField, FloatField, FontField, HelpText, InspectorActionEvent, IntField, Panel, ReadonlyField, Section, TextField, Vector3Field
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_MOD_RELIEF
from .preview_staleness import cancel_tool_preview_if_active


def _target_index(ctx: Any, override: int | str | None = None) -> int | None:
    try:
        if override not in (None, "", -1, "-1"):
            return int(override)
    except Exception:
        pass
    try:
        stored = ctx.inspector.value("target_index", -1)
        if stored not in (None, "", -1, "-1"):
            return int(stored)
    except Exception:
        pass
    active = ctx.scene_selection.active_index()
    if active is not None:
        return int(active)
    selected = tuple(ctx.scene_selection.selected_indices())
    return int(selected[-1]) if selected else None


def _anchor_from_values(values: dict[str, Any], target: int) -> ReliefAnchor | None:
    raw_has_anchor = values.get("has_anchor", False)
    if isinstance(raw_has_anchor, str):
        has_anchor = raw_has_anchor.strip().lower() in {"1", "true", "yes", "on"}
    else:
        try:
            has_anchor = bool(raw_has_anchor)
        except Exception:
            has_anchor = False
    if not has_anchor:
        return None
    try:
        point = tuple(float(v) for v in values.get("anchor_point", (0.0, 0.0, 0.0)))
        normal = tuple(float(v) for v in values.get("anchor_normal", (0.0, 0.0, 1.0)))
        if len(point) != 3 or len(normal) != 3:
            return None
        return ReliefAnchor(int(target), point, normal)  # type: ignore[arg-type]
    except Exception:
        return None


class ReliefCreatorTool(CreatorTool):
    """Text relief modifier implemented with Creator API only."""

    id = TOOL_MOD_RELIEF
    label = "Relief"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_object("select", "Select target"),
                ctx.workflow.step("anchor", "Pick face", help="Click a face to define the relief plane."),
                ctx.workflow.step("preview", "Preview relief", optional=True),
            ),
        )
        ctx.operations.register("relief_text", self._operation_relief, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_selection(ctx, default="Select a target part, then click a face.")
        ctx.status.info("Relief ready. Select a part, click a face, then preview.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.cancel())

    def on_apply(self, ctx: Any) -> bool:
        return bool(ctx.preview_session.apply(label="Relief applied", operation_type="modifier_relief"))

    def on_scene_selection_changed(self, ctx: Any) -> None:
        target = _target_index(ctx)
        active = ctx.scene_selection.active_index()
        if active is not None and target is not None and int(active) != int(target):
            try:
                ctx.inspector.update_values({"target_index": int(active), "has_anchor": "false"}, notify=False)
            except Exception:
                pass
        self._sync_selection(ctx)
        ctx.workflow.goto("select")

    def _panel(self, ctx: Any) -> Panel:
        changed = lambda _field, _value: self._on_values_changed(ctx)
        return Panel(
            "Relief",
            id="modifier.relief",
            owner_tool=self.id,
            description="Create raised/subtractive text bodies from Creator API operations.",
            sections=(
                Section(
                    "Target",
                    fields=(
                        HelpText("relief_help", "Select one mesh, click a face, then preview the text relief."),
                        ReadonlyField("selection_summary", "Target", default="No mesh selected."),
                    ),
                ),
                Section(
                    "Text",
                    fields=(
                        TextField("text", "Text", default="Text", on_change=changed),
                        FontField("font_family", "Font", default="VTK VectorText", on_change=changed),
                        FloatField("size_mm", "Size", default=12.0, min_value=0.1, max_value=10000.0, step=1.0, unit="mm", on_change=changed),
                        FloatField("depth_mm", "Depth", default=1.5, min_value=0.01, max_value=10000.0, step=0.25, unit="mm", on_change=changed),
                        FloatField("rotation_deg", "Rotation", default=0.0, min_value=-360.0, max_value=360.0, step=5.0, unit="°", on_change=changed),
                        ChoiceField("mode", "Mode", default="relief", choices=(("relief", "Raised"), ("subtract", "Subtract")), on_change=changed),
                        ChoiceField("align", "Alignment", default="center", choices=(("center", "Center"), ("left", "Left"), ("right", "Right")), on_change=changed),
                        IntField("target_index", "Target index", default=-1, min_value=-1, max_value=10_000_000, visible=False),
                        Vector3Field("anchor_point", "Anchor point", default=(0.0, 0.0, 0.0), visible=False),
                        Vector3Field("anchor_normal", "Anchor normal", default=(0.0, 0.0, 1.0), visible=False),
                        ChoiceField("has_anchor", "Has anchor", default="false", choices=(("false", "No"), ("true", "Yes")), visible=False),
                    ),
                ),
                Section(
                    "Preview",
                    fields=(
                        ButtonRow("relief_actions", "Actions", buttons=(("preview", "Preview relief"),), callbacks={"preview": lambda event: self._preview_action(ctx, event)}),
                        ReadonlyField("relief_report", "Report", default="Select a target, then click a face."),
                    ),
                ),
            ),
        )

    def _operation_relief(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        target = _target_index(ctx, params.get("target_index"))
        if target is None:
            return OperationResult.failure("Select a target part.")
        base = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        if not (0 <= int(target) < len(base)):
            return OperationResult.failure("The relief target is not a valid scene object.")
        anchor = _anchor_from_values(params, int(target))
        if anchor is None:
            return OperationResult.failure(f"Target: {int(target):02d}\nPick a face before previewing relief.")
        result = add_text_relief_preview(
            base,
            anchor,
            text=str(params.get("text", "Text") or "Text"),
            size_mm=max(0.1, float(params.get("size_mm", 12.0))),
            depth_mm=max(0.01, float(params.get("depth_mm", 1.5))),
            rotation_deg=float(params.get("rotation_deg", 0.0)),
            mode=str(params.get("mode", "relief") or "relief"),
            align=str(params.get("align", "center") or "center"),
            font_family=str(params.get("font_family", "") or ""),
        )
        if not result.ok:
            return OperationResult.failure("; ".join(str(e) for e in result.errors) or "Relief generation failed.")
        text = str(params.get("text", "Text") or "Text")
        report = f"Relief ready: '{text}'\nTarget: {int(target):02d}\nPreview object added: {max(0, len(result.meshes) - len(base))}"
        return OperationResult.success(
            tuple(result.meshes),
            report=report,
            warnings=result.warnings,
            metadata={
                "preview_indices": tuple(range(len(base), len(result.meshes))),
                "changed_indices": (int(target),),
                "target_index": int(target),
            },
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = event.values if event is not None else ctx.inspector.values()
        result = ctx.operations.relief_text(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Relief operation finished."), ok=result.ok)
        if not result.ok or not result.meshes:
            ctx.status.error("; ".join(result.errors) or "Relief failed.")
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label="Relief preview")
        session.show_meshes(result.meshes)
        target = result.metadata.get("target_index")
        try:
            target_i = int(target)
        except Exception:
            target_i = -1
        if 0 <= target_i < len(ctx.document.meshes(include_preview=False)):
            ctx.scene_selection.select_indices((target_i,), active_index=target_i)
        ctx.workflow.goto("preview")
        ctx.status.info("Relief preview ready. Use Apply to keep it or Cancel to discard it.")
        return True

    def _on_values_changed(self, ctx: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Relief preview discarded because text settings changed.")
        self._sync_selection(ctx, default="Text settings changed. Preview again before applying.")

    def set_anchor_from_pick(self, ctx: Any, mesh_index: int, point: Any, normal: Any) -> bool:
        if ctx.inspector.panel is None:
            return False
        ctx.scene_selection.select_indices((int(mesh_index),))
        ctx.inspector.set_display_value("selection_summary", f"{int(mesh_index):02d}")
        ctx.inspector.update_values(
            {
                "target_index": int(mesh_index),
                "anchor_point": tuple(float(v) for v in point),
                "anchor_normal": tuple(float(v) for v in normal),
                "has_anchor": "true",
            },
            notify=False,
        )
        self._sync_selection(ctx, default=f"Anchor set on part {int(mesh_index):02d}. Updating preview…")
        ctx.workflow.goto("anchor")
        return self._preview_action(ctx)

    def _sync_selection(self, ctx: Any, *, default: str | None = None) -> None:
        target = _target_index(ctx)
        summary = f"{target:02d}" if target is not None else "No mesh selected."
        ctx.inspector.set_display_value("selection_summary", summary)
        if target is not None:
            try:
                ctx.inspector.update_value("target_index", int(target), notify=False)
            except Exception:
                pass
        if default is not None:
            ctx.inspector.set_display_value("relief_report", default)
        elif target is not None:
            has_anchor = str(ctx.inspector.value("has_anchor", "false")).lower() in {"1", "true", "yes", "on"}
            ctx.inspector.set_display_value("relief_report", f"Target: {target:02d}. {'Preview can be refreshed.' if has_anchor else 'Pick a face.'}")

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("relief_report", text)
        if ok:
            ctx.inspector.clear_error("relief_report")
        else:
            ctx.inspector.set_error("relief_report", text)


class ReliefTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=ReliefCreatorTool())

    def set_anchor_from_pick(self, context: Any, mesh_index: int, point: Any, normal: Any) -> bool:
        return bool(self.creator.set_anchor_from_pick(self.tool_context(context), int(mesh_index), point, normal))


__all__ = ["ReliefCreatorTool", "ReliefTool"]

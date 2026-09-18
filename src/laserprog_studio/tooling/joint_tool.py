# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any

from laserprog_studio.fabrication.joint_builder import apply_tab_slot_simple
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import BoolField, ButtonRow, FloatField, HelpText, InspectorActionEvent, IntField, Panel, ReadonlyField, Section
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_JOINT
from .preview_staleness import cancel_tool_preview_if_active


def _selection_pair(ctx: Any) -> tuple[int, int] | None:
    selected = tuple(int(i) for i in ctx.scene_selection.selected_indices())
    if len(selected) != 2:
        return None
    return selected[0], selected[1]


class JointCreatorTool(CreatorTool):
    """Tab/slot joint builder implemented through Creator API operations."""

    id = TOOL_JOINT
    label = "Joint builder"

    def __init__(self) -> None:
        self._staged_joint_count = 0
        self._updating_preview_selection = False

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        self._staged_joint_count = 0
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_object("pick_a", "Pick part A"),
                ctx.workflow.require_scene_object("pick_b", "Pick part B"),
                ctx.workflow.step("preview", "Preview joint", help="Stage the tab/slot joint before applying it.", optional=True),
            ),
        )
        ctx.operations.register("joint_build", self._operation_joint, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_selection(ctx, default="Pick exactly two parts: A then B.")
        ctx.status.info("Joint builder ready. Select exactly two parts, then preview.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.cancel())
        self._staged_joint_count = 0
        return changed

    def on_apply(self, ctx: Any) -> bool:
        changed = bool(ctx.preview_session.apply(label="Joint batch applied", operation_type="joint_builder"))
        if changed:
            self._staged_joint_count = 0
        return changed

    def on_scene_selection_changed(self, ctx: Any) -> None:
        # Joint builder intentionally keeps the current preview when selection
        # changes: users can stage several joints in sequence, then Apply the
        # whole batch once.  The next preview operation starts from the current
        # preview meshes instead of the committed document.
        self._sync_selection(ctx)
        pair = _selection_pair(ctx)
        ctx.workflow.goto("preview" if pair else "pick_a")

    def _panel(self, ctx: Any) -> Panel:
        setting_change = lambda _field, _value: self._on_setting_changed(ctx)
        return Panel(
            "Joint builder",
            id="joint.builder",
            owner_tool=self.id,
            description="Create a tab/slot joint on a selected pair without window UI hooks.",
            sections=(
                Section(
                    "Selection",
                    fields=(
                        HelpText("joint_help", "Select exactly two meshes. The first selected object is A, the second is B."),
                        ReadonlyField("joint_selection", "A/B", default="A/B: —"),
                    ),
                ),
                Section(
                    "Joint options",
                    fields=(
                        FloatField("touch_tolerance_mm", "Contact tolerance", default=0.20, min_value=0.001, max_value=100.0, step=0.05, unit="mm", on_change=setting_change),
                        FloatField("clearance_mm", "Clearance", default=0.15, min_value=-100.0, max_value=100.0, step=0.05, unit="mm", on_change=setting_change),
                        FloatField("joint_size_mm", "Joint size", default=10.0, min_value=0.1, max_value=1000.0, step=1.0, unit="mm", on_change=setting_change),
                        IntField("joint_count", "Joint count", default=1, min_value=1, max_value=100, step=1, on_change=setting_change),
                        FloatField("joint_edge_margin_mm", "Edge margin", default=2.0, min_value=0.0, max_value=1000.0, step=0.5, unit="mm", on_change=setting_change),
                        BoolField("single_depth_probe", "Fast depth", default=True, on_change=setting_change),
                    ),
                ),
                Section(
                    "Preview",
                    fields=(
                        ButtonRow("joint_actions", "Actions", buttons=(("preview", "Add joint to preview"),), callbacks={"preview": lambda event: self._preview_action(ctx, event)}),
                        ReadonlyField("joint_report", "Report", default="Pick exactly two parts."),
                    ),
                ),
            ),
        )

    def _operation_joint(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        ctx.document.ensure()
        pair = _selection_pair(ctx)
        if pair is None:
            return OperationResult.failure("Select exactly two parts: A then B.")
        a, b = pair
        base_meshes = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=True)]
        if not (0 <= a < len(base_meshes) and 0 <= b < len(base_meshes)):
            return OperationResult.failure("Invalid joint selection.")

        touch_tolerance = max(0.001, float(params.get("touch_tolerance_mm", 0.20)))
        clearance = float(params.get("clearance_mm", 0.15))
        joint_size = max(0.1, float(params.get("joint_size_mm", 10.0)))
        joint_count = max(1, int(params.get("joint_count", 1)))
        edge_margin = max(0.0, float(params.get("joint_edge_margin_mm", 2.0)))
        single_depth_probe = bool(params.get("single_depth_probe", True))

        mesh_a, mesh_b = apply_tab_slot_simple(
            base_meshes[a],
            base_meshes[b],
            touch_tolerance=touch_tolerance,
            clearance=clearance,
            joint_size=joint_size,
            joint_count=joint_count,
            joint_edge_margin=edge_margin,
            single_depth_probe=single_depth_probe,
            debug=None,
        )
        base_meshes[a] = mesh_a
        base_meshes[b] = mesh_b
        report = f"Joint preview ready.\nA/B: {a:02d} / {b:02d}\nCount: {joint_count}\nSize: {joint_size:g} mm\nClearance: {clearance:g} mm"
        return OperationResult.success(
            tuple(base_meshes),
            report=report,
            metadata={"changed_indices": (a, b), "selected_indices": (a, b), "joint_count": joint_count, "joint_size_mm": joint_size},
        )

    def _preview_action(self, ctx: Any, event: InspectorActionEvent | None = None) -> bool:
        values = event.values if event is not None else ctx.inspector.values()
        result = ctx.operations.joint_build(inputs=(), params=values, preview=False, owner_tool=self.id)
        self._set_report(ctx, result.report or ("; ".join(result.errors) if result.errors else "Joint operation finished."), ok=result.ok)
        self._sync_selection(ctx, update_report=False)
        if not result.ok or not result.meshes:
            ctx.status.error("; ".join(result.errors) or "Joint generation failed.")
            return False
        session = getattr(ctx.preview_session, "current", None)
        if session is None or not bool(getattr(session, "active", False)) or getattr(session, "owner_tool", "") != self.id:
            session = ctx.preview_session.start(owner_tool=self.id, label="Joint batch preview")
        session.show_meshes(result.meshes)
        self._staged_joint_count += 1
        selected = tuple(int(i) for i in result.metadata.get("changed_indices", ()))
        if selected:
            self._updating_preview_selection = True
            try:
                ctx.scene_selection.select_indices(selected)
            finally:
                self._updating_preview_selection = False
        self._set_report(
            ctx,
            (result.report or "Joint preview ready.") + f"\nStaged joints: {self._staged_joint_count}\nApply will validate the whole preview batch.",
            ok=True,
        )
        ctx.workflow.goto("preview")
        ctx.status.info(f"Joint added to preview batch ({self._staged_joint_count}). Use Apply once when all joints are staged.")
        return True

    def _on_setting_changed(self, ctx: Any) -> None:
        if bool(getattr(getattr(ctx.preview_session, "current", None), "active", False)):
            self._sync_selection(ctx, default="Joint settings changed. Existing preview batch kept; click Add joint to preview for the next joint.")
        else:
            self._sync_selection(ctx, default="Joint settings changed. Preview before applying.")

    def _sync_selection(self, ctx: Any, *, default: str | None = None, update_report: bool = True) -> None:
        indices = tuple(ctx.scene_selection.selected_indices())
        label = " / ".join(f"{int(i):02d}" for i in indices[:2]) if indices else "—"
        ctx.inspector.set_display_value("joint_selection", f"A/B: {label}")
        if update_report:
            base = default or ("Ready to add another joint to preview." if len(indices) == 2 else "Select exactly two parts.")
            if self._staged_joint_count > 0:
                base = f"{base}\nStaged joints: {self._staged_joint_count}"
            ctx.inspector.set_display_value("joint_report", base)

    def _set_report(self, ctx: Any, text: str, *, ok: bool) -> None:
        ctx.inspector.set_display_value("joint_report", text)
        if ok:
            ctx.inspector.clear_error("joint_report")
        else:
            ctx.inspector.set_error("joint_report", text)


class JointTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=JointCreatorTool())


__all__ = ["JointCreatorTool", "JointTool"]

# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from typing import Any, Iterable

from laserprog_studio.engraving.roles import (
    FILL_ROLE,
    IGNORE_ROLE,
    OUTLINE_ROLE,
    apply_engraving_role,
    engraving_role_color,
    role_from_color_hint_or_ignore,
)
from laserprog_studio.tool_api.core import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_api.application import OperationResult
from laserprog_studio.tool_api.inspector import ButtonRow, ChoiceField, HelpText, InspectorActionEvent, Panel, ReadonlyField, Section, Title
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_ENGRAVING
from .preview_staleness import cancel_tool_preview_if_active


_ROLE_LABELS = {
    OUTLINE_ROLE: "Outline contour",
    FILL_ROLE: "Fill engraving",
    IGNORE_ROLE: "Ignore / preview only",
}


def engraving_role_choices(ctx: Any | None = None) -> tuple[tuple[str, str], ...]:
    """Return stable role choices for the Creator inspector."""

    roles = ()
    try:
        roles = tuple(ctx.engraving.roles()) if ctx is not None else ()
    except Exception:
        roles = ()
    if roles:
        return tuple((role.id, _ROLE_LABELS.get(role.id, role.label)) for role in roles)
    return (
        (OUTLINE_ROLE, _ROLE_LABELS[OUTLINE_ROLE]),
        (FILL_ROLE, _ROLE_LABELS[FILL_ROLE]),
        (IGNORE_ROLE, _ROLE_LABELS[IGNORE_ROLE]),
    )


def format_engraving_report(*, role: str, indices: Iterable[int], count: int) -> str:
    selected = tuple(int(i) for i in indices)
    label = _ROLE_LABELS.get(str(role), str(role).title())
    target = "none" if not selected else ", ".join(f"{i:02d}" for i in selected)
    return f"Role: {label}\nColor: {engraving_role_color(role)}\nTarget: {target}\nAffected parts: {int(count)}"


class EngravingRolesCreatorTool(CreatorTool):
    """Assign laser export roles through Creator API only.

    This replaces the historical hand-written Qt panel.  It stages role changes as preview meshes so the global Apply/Cancel
    workflow remains identical to other migrated Creator tools.
    """

    id = TOOL_ENGRAVING
    label = "Engraving roles"

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.document.ensure()
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("choose", "Choose role", help="Pick the laser export role to assign."),
                ctx.workflow.require_scene_objects("target", "Select target", help="Select or click parts to stage role changes.", optional=True),
                ctx.workflow.step("preview", "Preview", help="Apply or cancel the staged role changes.", optional=True),
            ),
        )
        ctx.operations.register("engraving_assign", self._operation_assign, replace=True)
        ctx.inspector.set_panel(self._panel(ctx))
        self._sync_report(ctx, message="Choose a role, then click a part or use the buttons.")
        ctx.status.info("Engraving roles ready. Click a part or assign the current selection.")

    def on_close(self, ctx: Any) -> None:
        ctx.inspector.clear()

    def on_cancel(self, ctx: Any) -> bool:
        ctx.preview_session.cancel()
        ctx.inspector.clear()
        return True

    def on_apply(self, ctx: Any) -> bool:
        return ctx.preview_session.apply(label="Engraving roles applied", operation_type="engraving_roles")

    def on_event(self, event: ToolEvent, ctx: Any) -> bool:
        if event.type != ToolEventType.MOUSE_RELEASE or event.button != MouseButton.LEFT:
            return False
        target = getattr(event, "raw", None)
        index = None
        if isinstance(target, dict):
            index = target.get("index")
        elif isinstance(target, (tuple, list)) and len(target) >= 2 and target[0] == "mesh":
            index = target[1]
        if index is None:
            return False
        return self.assign_index(ctx, int(index))

    def assign_index(self, ctx: Any, index: int, role: str | None = None) -> bool:
        role_id = self._role_value(ctx, role)
        return self._stage_role(ctx, role_id, (int(index),), label=f"Engraving role part {int(index):02d}")

    def assign_selected(self, ctx: Any, role: str | None = None) -> bool:
        role_id = self._role_value(ctx, role)
        indices = tuple(ctx.scene_selection.selected_indices())
        if not indices:
            ctx.status.error("Select one or more parts before assigning an engraving role.")
            self._sync_report(ctx, message="No selected part.")
            return False
        return self._stage_role(ctx, role_id, indices, label="Engraving role selected parts")

    def assign_all(self, ctx: Any, role: str | None = None) -> bool:
        role_id = self._role_value(ctx, role)
        if not ctx.document.ensure() or not ctx.document.available:
            message = "Engraving role preview needs an active document before staging role changes."
            ctx.status.error(message)
            self._sync_report(ctx, message=message)
            return False
        indices = range(len(ctx.document.meshes(include_preview=False)))
        return self._stage_role(ctx, role_id, indices, label="Engraving role all parts")

    def _panel(self, ctx: Any) -> Panel:
        return Panel(
            "Engraving roles",
            id="engraving.roles",
            owner_tool=self.id,
            description="Assign laser export roles through Creator API controller state.",
            sections=(
                Section(
                    "Role",
                    fields=(
                        HelpText("engraving_help", "Green/outline exports as vector contours. Red/fill exports as filled engraving. Ignore remains visible but is skipped by laser export."),
                        ChoiceField(
                            "role",
                            "Role",
                            default=OUTLINE_ROLE,
                            choices=engraving_role_choices(ctx),
                            on_change=lambda _field, _value: self._on_role_changed(ctx),
                        ),
                        ReadonlyField("role_color", "Color", default=engraving_role_color(OUTLINE_ROLE)),
                    ),
                ),
                Section(
                    "Selection",
                    fields=(
                        ReadonlyField("selection_summary", "Selected", default="No selected part."),
                        ReadonlyField("engraving_report", "Preview report", default="No preview staged."),
                    ),
                ),
                Section(
                    "Actions",
                    fields=(
                        Title("engraving_actions_title", "Stage role changes"),
                        ButtonRow(
                            "engraving_actions",
                            "Actions",
                            buttons=(
                                ("assign_selected", "Preview selected"),
                                ("assign_all", "Preview all"),
                                ("outline_all", "Set all outline"),
                                ("ignore_selected", "Ignore selected"),
                            ),
                            callbacks={
                                "assign_selected": lambda event: self._assign_selected_action(ctx, event),
                                "assign_all": lambda event: self._assign_all_action(ctx, event),
                                "outline_all": lambda event: self._assign_all_action(ctx, event, role=OUTLINE_ROLE),
                                "ignore_selected": lambda event: self._assign_selected_action(ctx, event, role=IGNORE_ROLE),
                            },
                        ),
                    ),
                ),
            ),
        )

    def _operation_assign(self, _inputs: tuple[Any, ...], params: dict[str, Any], ctx: Any) -> OperationResult:
        role = self._normalize_role(str(params.get("role") or OUTLINE_ROLE))
        indices = tuple(int(i) for i in params.get("indices", ()))
        meshes = [copy.deepcopy(mesh) for mesh in ctx.document.meshes(include_preview=False)]
        if not meshes:
            return OperationResult.failure("No part is loaded.")
        valid = tuple(index for index in indices if 0 <= int(index) < len(meshes))
        if not valid:
            return OperationResult.failure("No valid target part for engraving role assignment.")
        role_spec = ctx.engraving.role(role)
        for index in valid:
            apply_engraving_role(meshes[int(index)], role, layer=role_spec.layer, enabled=True)
        report = format_engraving_report(role=role, indices=valid, count=len(valid))
        return OperationResult.success(
            tuple(meshes),
            report=report,
            metadata={"role": role, "indices": tuple(int(i) for i in valid), "color": engraving_role_color(role)},
        )

    def _stage_role(self, ctx: Any, role: str, indices: Iterable[int], *, label: str) -> bool:
        if not ctx.document.ensure() or not ctx.document.available:
            message = "Engraving role preview needs an active document before staging role changes."
            ctx.status.error(message)
            self._sync_report(ctx, message=message)
            return False
        cleaned = tuple(dict.fromkeys(int(i) for i in indices))
        result = ctx.operations.run("engraving_assign", inputs=(), params={"role": role, "indices": cleaned})
        if not result.ok or not result.meshes:
            message = "; ".join(result.errors) or "Engraving role preview failed."
            ctx.status.error(message)
            self._sync_report(ctx, message=message)
            return False
        session = ctx.preview_session.start(owner_tool=self.id, label=label)
        session.show_meshes(result.meshes)
        ctx.scene_selection.select_indices(result.metadata.get("indices", cleaned))
        ctx.workflow.goto("preview")
        ctx.inspector.set_display_value("engraving_report", result.report)
        ctx.inspector.set_display_value("role_color", result.metadata.get("color", engraving_role_color(role)))
        ctx.inspector.clear_error("engraving_report")
        ctx.status.info(result.report.replace("\n", " | "))
        return True

    def _assign_selected_action(self, ctx: Any, event: InspectorActionEvent | None = None, role: str | None = None) -> bool:
        selected_role = role or self._role_value(ctx, (event.values or {}).get("role") if event else None)
        return self.assign_selected(ctx, selected_role)

    def _assign_all_action(self, ctx: Any, event: InspectorActionEvent | None = None, role: str | None = None) -> bool:
        selected_role = role or self._role_value(ctx, (event.values or {}).get("role") if event else None)
        return self.assign_all(ctx, selected_role)

    def _on_role_changed(self, ctx: Any) -> None:
        cancel_tool_preview_if_active(ctx, self.id, status="Engraving preview discarded because the role changed.")
        self._sync_report(ctx, message="Role changed. Preview again before applying.")

    def _sync_report(self, ctx: Any, message: str | None = None) -> None:
        role = self._role_value(ctx)
        selected = tuple(ctx.scene_selection.selected_indices())
        ctx.inspector.set_display_value("role_color", engraving_role_color(role))
        ctx.inspector.set_display_value("selection_summary", self._selection_summary(ctx))
        if message is not None:
            ctx.inspector.set_display_value("engraving_report", message)

    def _selection_summary(self, ctx: Any) -> str:
        indices = tuple(ctx.scene_selection.selected_indices())
        if not indices:
            return "No selected part. Click a mesh or select from the scene list."
        meshes = tuple(ctx.document.meshes(include_preview=True))
        parts: list[str] = []
        for index in indices:
            if 0 <= int(index) < len(meshes):
                mesh = meshes[int(index)]
                role = role_from_color_hint_or_ignore(getattr(mesh, "color", None))
                parts.append(f"{int(index):02d}:{role}")
            else:
                parts.append(f"{int(index):02d}:invalid")
        return ", ".join(parts)

    def _role_value(self, ctx: Any, role: str | None = None) -> str:
        return self._normalize_role(role or ctx.inspector.value("role", OUTLINE_ROLE))

    @staticmethod
    def _normalize_role(role: str | None) -> str:
        key = str(role or OUTLINE_ROLE).strip().lower()
        return key if key in {OUTLINE_ROLE, FILL_ROLE, IGNORE_ROLE} else IGNORE_ROLE


class EngravingRolesTool(CreatorStudioToolAdapter):
    """Runtime adapter for the built-in Engraving Roles CreatorTool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=EngravingRolesCreatorTool())

    def assign_index(self, context: Any, index: int, role: str | None = None) -> bool:
        return self.creator.assign_index(self.tool_context(context), int(index), role)

    def assign_selected(self, context: Any, role: str | None = None) -> bool:
        return self.creator.assign_selected(self.tool_context(context), role)

    def assign_all(self, context: Any, role: str | None = None) -> bool:
        return self.creator.assign_all(self.tool_context(context), role)


__all__ = ["EngravingRolesCreatorTool", "EngravingRolesTool", "engraving_role_choices", "format_engraving_report"]

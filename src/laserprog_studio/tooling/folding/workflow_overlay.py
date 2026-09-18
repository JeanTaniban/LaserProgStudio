# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .models import FoldingPhase, FoldingSession
from .state_machine import FoldingWorkflowMachine

FOLDING_WORKFLOW_WINDOW_ID = "folding.workflow"
FOLDING_ACTION_PREFIX = "folding.workflow.action."


class FoldingWorkflowOverlay:
    """Small, phase-aware viewport card. Detailed values stay in the inspector."""

    def __init__(self, owner_tool: str, session: FoldingSession) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session

    @staticmethod
    def _button(action: str, label: str, icon: str, *, style: str = "ghost", enabled: bool = True) -> visual.ToolButtonSpec:
        return visual.ToolButtonSpec(
            id=f"{FOLDING_ACTION_PREFIX}{action}",
            label=label,
            icon=icon,
            style=style,  # type: ignore[arg-type]
            enabled=bool(enabled),
        )

    @staticmethod
    def action_from_button(button_id: str | None) -> str | None:
        raw = str(button_id or "")
        if not raw.startswith(FOLDING_ACTION_PREFIX):
            return None
        return raw[len(FOLDING_ACTION_PREFIX):]

    def sync(self, ctx: Any, *, can_apply: bool = False) -> None:
        spec = FoldingWorkflowMachine.spec_for(self.session.phase)
        fields = [
            visual.OverlayFieldSpec("folding.workflow.step", "Step", f"Step {spec.step} of 5 · {spec.title}", kind="info"),
            visual.OverlayFieldSpec("folding.workflow.instruction", "", spec.instruction, kind="info"),
        ]
        status = str(self.session.status_message or "").strip()
        if status and status != spec.instruction:
            fields.append(visual.OverlayFieldSpec("folding.workflow.status", "", status, kind="info"))

        buttons: list[visual.ToolButtonSpec] = []
        if self.session.phase is not FoldingPhase.SELECT_MESH:
            buttons.append(self._button("back", "Back", "tool.reset", style="secondary"))
        if self.session.phase is FoldingPhase.ADJUST_CURVE:
            buttons.extend(
                (
                    self._button("reset_shape", "Reset shape", "tool.reset", style="secondary"),
                    self._button("invert", "Reverse", "tool.rotate", style="secondary"),
                    self._button("apply", "Apply", "tool.apply", style="primary", enabled=can_apply),
                )
            )
        buttons.append(self._button("cancel", "Cancel", "tool.close", style="danger"))

        ctx.overlay.show_window(
            visual.OverlayWindowSpec(
                id=FOLDING_WORKFLOW_WINDOW_ID,
                title="Folding",
                owner_tool=self.owner_tool,
                fields=fields,
                buttons=buttons,
                anchor="viewport_top_left",
                overlay_kind="inspector",
                width_px=330,
                movable=True,
                persistent=True,
                close_on_click_outside=False,
            )
        )
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import sync_creator_overlay_windows

                sync_creator_overlay_windows(owner, ctx)
            except Exception:
                pass

    def hide(self, ctx: Any) -> None:
        try:
            ctx.overlay.hide_window(FOLDING_WORKFLOW_WINDOW_ID)
        except Exception:
            pass
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import sync_creator_overlay_windows

                sync_creator_overlay_windows(owner, ctx)
            except Exception:
                pass


__all__ = ["FOLDING_ACTION_PREFIX", "FOLDING_WORKFLOW_WINDOW_ID", "FoldingWorkflowOverlay"]

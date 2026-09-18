# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .models import MechanicalMode
from .session import MechanicalSession

WORKFLOW_WINDOW_ID = "mechanical.motion.workflow"
WORKFLOW_ACTION_PREFIX = "mechanical.motion.workflow.action."


class MechanicalWorkflowOverlay:
    """Contextual instructions and explicit confirmation for multi-step MEC actions."""

    _VISIBLE_MODES = {
        MechanicalMode.PICK_PLANE,
        MechanicalMode.PICK_RACK_PINION,
        MechanicalMode.PLACE_RACK_START,
        MechanicalMode.PLACE_RACK_END,
        MechanicalMode.PICK_DRIVER_TARGET,
        MechanicalMode.PLACE_DRIVER_CENTER,
        MechanicalMode.PICK_ATTACHMENT_SOURCE,
        MechanicalMode.PICK_ATTACHMENTS,
    }

    def __init__(self, owner_tool: str, session: MechanicalSession) -> None:
        self.owner_tool = str(owner_tool)
        self.session = session

    def sync(self, ctx: Any) -> None:
        state = self.session.state
        mode = state.mode
        if mode not in self._VISIBLE_MODES:
            try:
                ctx.overlay.hide_window(WORKFLOW_WINDOW_ID)
            except Exception:
                pass
            return

        title = "Mechanical workflow"
        fields: list[visual.OverlayFieldSpec] = []
        buttons: list[visual.ToolButtonSpec] = []

        if mode is MechanicalMode.PICK_PLANE:
            title = "Start or reopen MEC"
            fields.append(
                visual.OverlayFieldSpec(
                    "mechanical.motion.workflow.start",
                    "Next step",
                    "Click a planar face for a new assembly, or select an existing MEC mesh to Edit / New assembly / Cancel. Orbit stays active.",
                    kind="info",
                )
            )
        elif mode is MechanicalMode.PICK_RACK_PINION:
            title = "1 · Choose rack pinion"
            fields.append(
                visual.OverlayFieldSpec(
                    "mechanical.motion.workflow.rack_pinion",
                    "Pinion",
                    "Click the generated gear mesh that will convert rotation into linear rack travel.",
                    kind="info",
                )
            )
            buttons.append(self._button("cancel_step", "Cancel rack", "tool.close", "secondary"))
        elif mode is MechanicalMode.PLACE_RACK_START:
            title = "2 · Place rack start"
            fields.append(
                visual.OverlayFieldSpec(
                    "mechanical.motion.workflow.rack_start",
                    "Next step",
                    "Click the first endpoint. The final pitch line will be snapped tangent to the selected pinion.",
                    kind="info",
                )
            )
            buttons.append(self._button("cancel_step", "Cancel rack", "tool.close", "secondary"))
        elif mode is MechanicalMode.PLACE_RACK_END:
            title = "3 · Define rack direction"
            fields.append(
                visual.OverlayFieldSpec(
                    "mechanical.motion.workflow.rack_end",
                    "Next step",
                    "Click the second endpoint to define rack length and travel direction.",
                    kind="info",
                )
            )
            buttons.append(self._button("cancel_step", "Replace first point", "tool.reset", "secondary"))
        elif mode is MechanicalMode.PICK_DRIVER_TARGET:
            title = "Choose the driver"
            fields.append(
                visual.OverlayFieldSpec(
                    "mechanical.motion.workflow.driver",
                    "Target",
                    "Click a generated gear mesh to assign it immediately. A normal scene part requires one additional click for its rotation centre.",
                    kind="info",
                )
            )
            buttons.append(self._button("cancel_step", "Cancel", "tool.close", "secondary"))
        elif mode is MechanicalMode.PLACE_DRIVER_CENTER:
            title = "Place driver centre"
            target = str(state.pending_driver_mesh_id or "No scene part selected")
            fields.extend(
                (
                    visual.OverlayFieldSpec("mechanical.motion.workflow.driver_target", "Scene part", target, kind="info"),
                    visual.OverlayFieldSpec(
                        "mechanical.motion.workflow.driver_center",
                        "Next step",
                        "Click the rotation centre on the construction plane.",
                        kind="info",
                    ),
                )
            )
            buttons.append(self._button("cancel_step", "Change target", "tool.reset", "secondary"))
        elif mode is MechanicalMode.PICK_ATTACHMENT_SOURCE:
            title = "1 · Choose motion source"
            fields.append(
                visual.OverlayFieldSpec(
                    "mechanical.motion.workflow.attachment_source_help",
                    "Source",
                    "Click a gear mesh, a chain gear/shaft, a rack, or a rotary-driver marker.",
                    kind="info",
                )
            )
            buttons.append(self._button("cancel_step", "Cancel attach", "tool.close", "secondary"))
        elif mode is MechanicalMode.PICK_ATTACHMENTS:
            title = "2 · Choose driven parts"
            source = self._source_label()
            target_count = len(state.pending_attachment_mesh_ids)
            fields.extend(
                (
                    visual.OverlayFieldSpec("mechanical.motion.workflow.attachment_source", "Motion source", source, kind="info"),
                    visual.OverlayFieldSpec(
                        "mechanical.motion.workflow.attachment_targets",
                        "Selected scene parts",
                        f"{target_count} part(s)",
                        kind="info",
                    ),
                    visual.OverlayFieldSpec(
                        "mechanical.motion.workflow.attachment_help",
                        "Next step",
                        "Select one or more normal scene meshes, then press Attach selected parts.",
                        kind="info",
                    ),
                )
            )
            buttons.extend(
                (
                    visual.ToolButtonSpec(
                        f"{WORKFLOW_ACTION_PREFIX}confirm_attachment",
                        "Attach selected parts",
                        icon="tool.attach",
                        style="primary",
                        enabled=target_count > 0,
                    ),
                    self._button("change_attachment_source", "Change source", "tool.reset", "secondary"),
                    self._button("cancel_step", "Cancel", "tool.close", "ghost"),
                )
            )

        ctx.overlay.show_window(
            visual.OverlayWindowSpec(
                id=WORKFLOW_WINDOW_ID,
                title=title,
                owner_tool=self.owner_tool,
                fields=fields,
                buttons=buttons,
                anchor="viewport_bottom_center",
                overlay_kind="inspector",
                width_px=380,
                movable=True,
                persistent=True,
                close_on_click_outside=False,
            )
        )

    def _source_label(self) -> str:
        source_id = str(self.session.state.pending_attachment_source_id or "")
        assembly = self.session.assembly
        source = assembly.gears.get(source_id) or assembly.chains.get(source_id) or assembly.racks.get(source_id) or assembly.drivers.get(source_id)
        return str(getattr(source, "name", "") or source_id or "No source selected")

    @staticmethod
    def _button(action: str, label: str, icon: str, style: str) -> visual.ToolButtonSpec:
        return visual.ToolButtonSpec(
            f"{WORKFLOW_ACTION_PREFIX}{action}",
            label,
            icon=icon,
            style=style,  # type: ignore[arg-type]
        )

    @staticmethod
    def action_from_button(button_id: str) -> str | None:
        raw = str(button_id or "")
        return raw[len(WORKFLOW_ACTION_PREFIX):] if raw.startswith(WORKFLOW_ACTION_PREFIX) else None


__all__ = ["MechanicalWorkflowOverlay", "WORKFLOW_ACTION_PREFIX", "WORKFLOW_WINDOW_ID"]

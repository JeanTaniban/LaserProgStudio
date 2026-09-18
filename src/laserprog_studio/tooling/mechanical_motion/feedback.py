# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api import visual

from .models import MechanicalMode

MECHANICAL_TOOLBAR_ID = "mechanical.motion.toolbar"
MECHANICAL_MODE_GROUP = "mechanical.motion.mode"
MECHANICAL_MODE_PREFIX = "mechanical.motion.mode."
MECHANICAL_ACTION_PREFIX = "mechanical.motion.action."


def mode_from_button(button_id: str | None) -> MechanicalMode | None:
    raw = str(button_id or "")
    if not raw.startswith(MECHANICAL_MODE_PREFIX):
        return None
    try:
        return MechanicalMode(raw[len(MECHANICAL_MODE_PREFIX):])
    except Exception:
        return None


def action_from_button(button_id: str | None) -> str | None:
    raw = str(button_id or "")
    return raw[len(MECHANICAL_ACTION_PREFIX):] if raw.startswith(MECHANICAL_ACTION_PREFIX) else None


def _mode(mode: MechanicalMode, label: str, icon: str, display: str, shortcut: str, tooltip: str, width: int) -> visual.OverlayModeSpec:
    return visual.OverlayModeSpec(
        id=f"{MECHANICAL_MODE_PREFIX}{mode.value}",
        label=label,
        icon=icon,
        display_label=display,
        shortcut=shortcut,
        tooltip=tooltip,
        slot_width_px=width,
    )


def _action(action: str, label: str, icon: str, display: str, tooltip: str, width: int, *, style: str = "ghost") -> visual.OverlayActionSpec:
    return visual.OverlayActionSpec(
        id=f"{MECHANICAL_ACTION_PREFIX}{action}",
        label=label,
        icon=icon,
        display_label=display,
        tooltip=tooltip,
        slot_width_px=width,
        style=style,  # type: ignore[arg-type]
    )


def build_mechanical_toolbar(*, active_mode: MechanicalMode, status: str, element_count: int) -> visual.OverlayWindowSpec:
    create = visual.OverlayToolbarSectionSpec(
        id="create",
        label="Create",
        modes=(
            _mode(MechanicalMode.PICK_PLANE, "Select construction plane", "sketch.face", "Plane", "P", "Click a planar model face to constrain every mechanical placement while keeping orbit available.", 96),
            _mode(MechanicalMode.PLACE_GEAR, "Place gear", "sketch.circle", "Gear", "G", "Click a gear centre.", 92),
            _mode(MechanicalMode.PLACE_CHAIN_START, "Place gear chain", "sketch.polyline", "Chain", "C", "Click the start and end axes, then edit the curve.", 98),
            _mode(MechanicalMode.PLACE_RACK_START, "Rack and pinion", "sketch.line", "Rack", "R", "Select a pinion, then draw rack direction and length.", 96),
        ),
    )
    edit = visual.OverlayToolbarSectionSpec(
        id="edit",
        label="Edit",
        modes=(
            _mode(MechanicalMode.SELECT, "Select", "sketch.modify", "Select", "S", "Select and edit mechanical markers.", 96),
            _mode(MechanicalMode.EDIT_CURVE, "Edit curve", "sketch.arc", "Curve", "E", "Drag the selected chain handles.", 96),
        ),
    )
    motion = visual.OverlayToolbarSectionSpec(
        id="motion",
        label="Motion",
        modes=(
            _mode(MechanicalMode.PICK_DRIVER_TARGET, "Rotary driver", "tool.rotate", "Driver", "D", "Select a target and place its rotation centre.", 100),
            _mode(MechanicalMode.PICK_ATTACHMENT_SOURCE, "Attach driven parts", "tool.attach", "Attach", "A", "Choose a motion source, select scene parts, then explicitly confirm the attachment.", 100),
            _mode(MechanicalMode.TEST, "Test motion", "tool.preview", "Test", "T", "Animate or scrub the mechanism.", 90),
        ),
    )
    actions = visual.OverlayToolbarSectionSpec(
        id="actions",
        label="Actions",
        actions=(
            _action("delete_selected", "Delete selected", "sketch.delete", "Delete", "Delete the selected mechanical element.", 96, style="danger"),
            _action("refresh_preview", "Refresh preview", "tool.preview", "Refresh", "Rebuild the selected gear-chain or rack geometry.", 100),
        ),
    )
    return visual.build_command_deck_window(
        window_id=MECHANICAL_TOOLBAR_ID,
        owner_tool="mechanical_motion",
        group_id=MECHANICAL_MODE_GROUP,
        sections=(create, edit, motion, actions),
        active_mode_id=f"{MECHANICAL_MODE_PREFIX}{active_mode.value}",
        badge_id="mechanical.motion.badge",
        badge_label="Assembly",
        badge_value=f"{element_count} element(s)",
        status_id="mechanical.motion.command_status",
        status_label="Status",
        status_value=str(status),
        title="Mechanical Motion",
        anchor="viewport_top_left",
        width_px=0,
        movable=True,
        persistent=True,
    )


def sync_mechanical_toolbar(ctx: Any, *, active_mode: MechanicalMode, status: str, element_count: int) -> None:
    try:
        ctx.overlay.set_group_active(MECHANICAL_MODE_GROUP, f"{MECHANICAL_MODE_PREFIX}{active_mode.value}")
        ctx.overlay.show_window(build_mechanical_toolbar(active_mode=active_mode, status=status, element_count=element_count))
    except Exception:
        return
    owner = getattr(ctx, "owner", None)
    if owner is None:
        return
    try:
        from laserprog_studio.application.creator_viewport_ui import render_creator_viewport_ui

        render_creator_viewport_ui(owner, ctx, "mechanical_motion", render=True, sync_overlays=True)
    except Exception:
        pass


__all__ = [
    "MECHANICAL_ACTION_PREFIX",
    "MECHANICAL_MODE_GROUP",
    "MECHANICAL_MODE_PREFIX",
    "MECHANICAL_TOOLBAR_ID",
    "action_from_button",
    "build_mechanical_toolbar",
    "mode_from_button",
    "sync_mechanical_toolbar",
]

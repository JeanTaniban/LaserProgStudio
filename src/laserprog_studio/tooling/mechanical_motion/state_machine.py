# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import MechanicalMode, MechanicalSessionState, Point3, point3


class MechanicalIntent(str, Enum):
    PICK_PLANE = "pick_plane"
    SELECT = "select"
    START_GEAR = "start_gear"
    START_CHAIN = "start_chain"
    START_RACK = "start_rack"
    EDIT_CURVE = "edit_curve"
    START_DRIVER = "start_driver"
    START_ATTACHMENTS = "start_attachments"
    CHANGE_ATTACHMENT_SOURCE = "change_attachment_source"
    CONFIRM_ATTACHMENTS = "confirm_attachments"
    START_TEST = "start_test"
    STOP_TEST = "stop_test"
    CANCEL_STEP = "cancel_step"
    RESET = "reset"


@dataclass(frozen=True, slots=True)
class TransitionResult:
    previous: MechanicalMode
    current: MechanicalMode
    changed: bool
    message: str


class MechanicalWorkflowMachine:
    """Explicit user interaction state machine for the mechanical tool."""

    def __init__(self, state: MechanicalSessionState) -> None:
        self.state = state

    def dispatch(self, intent: MechanicalIntent | str, payload: Any | None = None) -> TransitionResult:
        try:
            resolved = intent if isinstance(intent, MechanicalIntent) else MechanicalIntent(str(intent))
        except Exception:
            return TransitionResult(self.state.mode, self.state.mode, False, f"Unknown mechanical intent: {intent}")
        previous = self.state.mode
        message = ""
        needs_plane = resolved in {
            MechanicalIntent.SELECT,
            MechanicalIntent.START_GEAR,
            MechanicalIntent.START_CHAIN,
            MechanicalIntent.START_RACK,
            MechanicalIntent.EDIT_CURVE,
            MechanicalIntent.START_DRIVER,
            MechanicalIntent.START_ATTACHMENTS,
            MechanicalIntent.START_TEST,
        }
        if needs_plane and self.state.assembly.work_plane is None:
            self.state.mode = MechanicalMode.PICK_PLANE
            message = "Select a planar face before creating or testing mechanical parts."
        elif resolved is MechanicalIntent.PICK_PLANE:
            self.state.mode = MechanicalMode.PICK_PLANE
            self.state.pending_chain_start = None
            self.state.pending_rack_pinion_gear_id = None
            self.state.pending_rack_start = None
            self.state.pending_driver_mesh_id = None
            self.state.pending_attachment_source_id = None
            self.state.pending_attachment_mesh_ids = ()
            self.state.test_playing = False
            message = "Click a planar face to start a new assembly, or select an existing MEC assembly to edit it. Orbit remains available."
        elif resolved is MechanicalIntent.SELECT:
            self.state.mode = MechanicalMode.SELECT
            self.state.pending_chain_start = None
            self.state.pending_rack_pinion_gear_id = None
            self.state.pending_rack_start = None
            self.state.pending_driver_mesh_id = None
            message = "Select a mechanical marker to edit it."
        elif resolved is MechanicalIntent.START_GEAR:
            self.state.mode = MechanicalMode.PLACE_GEAR
            self.state.pending_chain_start = None
            message = "Click the desired gear centre."
        elif resolved is MechanicalIntent.START_CHAIN:
            self.state.mode = MechanicalMode.PLACE_CHAIN_START
            self.state.pending_chain_start = None
            message = "Click the chain start shaft."
        elif resolved is MechanicalIntent.START_RACK:
            pinion_id = str(payload or "")
            self.state.pending_rack_start = None
            if pinion_id:
                self.state.pending_rack_pinion_gear_id = pinion_id
                self.state.mode = MechanicalMode.PLACE_RACK_START
                message = "Pinion selected. Click the first rack endpoint; the pitch line will snap tangent to the gear."
            else:
                self.state.pending_rack_pinion_gear_id = None
                self.state.mode = MechanicalMode.PICK_RACK_PINION
                message = "Select the gear mesh that will drive the rack."
        elif resolved is MechanicalIntent.EDIT_CURVE:
            self.state.mode = MechanicalMode.EDIT_CURVE
            message = "Drag the two curve handles."
        elif resolved is MechanicalIntent.START_DRIVER:
            self.state.mode = MechanicalMode.PICK_DRIVER_TARGET
            self.state.pending_driver_mesh_id = None
            message = "Click a generated gear mesh to make it the driver, or select a scene part and then place its rotation centre."
        elif resolved is MechanicalIntent.START_ATTACHMENTS:
            source_id = str(payload or "")
            if source_id:
                self.state.pending_attachment_source_id = source_id
                self.state.pending_attachment_mesh_ids = ()
                self.state.mode = MechanicalMode.PICK_ATTACHMENTS
                message = "Motion source selected. Select the scene parts to move, then confirm Attach."
            else:
                self.state.pending_attachment_source_id = None
                self.state.pending_attachment_mesh_ids = ()
                self.state.mode = MechanicalMode.PICK_ATTACHMENT_SOURCE
                message = "Select a gear, rack, gear-chain output, or driver that will move the attached parts."
        elif resolved is MechanicalIntent.CHANGE_ATTACHMENT_SOURCE:
            self.state.pending_attachment_source_id = None
            self.state.pending_attachment_mesh_ids = ()
            self.state.mode = MechanicalMode.PICK_ATTACHMENT_SOURCE
            message = "Select a new motion source for the attachment."
        elif resolved is MechanicalIntent.CONFIRM_ATTACHMENTS:
            self.state.pending_attachment_source_id = None
            self.state.pending_attachment_mesh_ids = ()
            self.state.mode = MechanicalMode.SELECT
            message = "Driven parts attached."
        elif resolved is MechanicalIntent.START_TEST:
            self.state.mode = MechanicalMode.TEST
            self.state.test_playing = False
            message = "Test mode active. Set the driver RPM, press Play, or drag its rotation handle."
        elif resolved is MechanicalIntent.STOP_TEST:
            self.state.test_playing = False
            self.state.mode = MechanicalMode.SELECT
            message = "Test mode stopped."
        elif resolved is MechanicalIntent.CANCEL_STEP:
            if self.state.mode is MechanicalMode.PLACE_CHAIN_END:
                self.state.mode = MechanicalMode.PLACE_CHAIN_START
                self.state.pending_chain_start = None
                message = "Chain endpoint cancelled. Click a new start shaft."
            elif self.state.mode is MechanicalMode.PLACE_RACK_END:
                self.state.mode = MechanicalMode.PLACE_RACK_START
                self.state.pending_rack_start = None
                message = "Rack endpoint cancelled. Click a new first endpoint."
            elif self.state.mode in {MechanicalMode.PLACE_RACK_START, MechanicalMode.PICK_RACK_PINION}:
                self.state.mode = MechanicalMode.SELECT
                self.state.pending_rack_pinion_gear_id = None
                self.state.pending_rack_start = None
                message = "Rack creation cancelled."
            elif self.state.mode is MechanicalMode.PLACE_DRIVER_CENTER:
                self.state.mode = MechanicalMode.PICK_DRIVER_TARGET
                self.state.pending_driver_mesh_id = None
                message = "Driver centre cancelled. Select a target again."
            elif self.state.mode is MechanicalMode.PICK_ATTACHMENTS:
                self.state.mode = MechanicalMode.PICK_ATTACHMENT_SOURCE
                self.state.pending_attachment_source_id = None
                self.state.pending_attachment_mesh_ids = ()
                message = "Attachment targets cancelled. Select the motion source again."
            elif self.state.mode is MechanicalMode.PICK_ATTACHMENT_SOURCE:
                self.state.mode = MechanicalMode.SELECT
                self.state.pending_attachment_source_id = None
                self.state.pending_attachment_mesh_ids = ()
                message = "Attachment creation cancelled."
            else:
                self.state.mode = MechanicalMode.SELECT if self.state.assembly.work_plane is not None else MechanicalMode.PICK_PLANE
                self.state.pending_chain_start = None
                self.state.pending_rack_pinion_gear_id = None
                self.state.pending_rack_start = None
                self.state.pending_driver_mesh_id = None
                self.state.pending_attachment_source_id = None
                self.state.pending_attachment_mesh_ids = ()
                self.state.test_playing = False
                message = "Current mechanical action cancelled."
        elif resolved is MechanicalIntent.RESET:
            self.state.mode = MechanicalMode.PICK_PLANE
            self.state.assembly.work_plane = None
            self.state.pending_chain_start = None
            self.state.pending_rack_pinion_gear_id = None
            self.state.pending_rack_start = None
            self.state.pending_driver_mesh_id = None
            self.state.pending_attachment_source_id = None
            self.state.pending_attachment_mesh_ids = ()
            self.state.test_angle_deg = 0.0
            self.state.driver_angles_deg.clear()
            self.state.test_playing = False
            message = "Mechanical workflow reset."
        self.state.last_status = message
        return TransitionResult(previous, self.state.mode, previous != self.state.mode, message)

    def accept_chain_start(self, position: Point3) -> TransitionResult:
        previous = self.state.mode
        if previous is not MechanicalMode.PLACE_CHAIN_START:
            return TransitionResult(previous, previous, False, "Chain start is not expected in the current state.")
        self.state.pending_chain_start = point3(position)
        self.state.mode = MechanicalMode.PLACE_CHAIN_END
        self.state.last_status = "Start shaft placed. Click the chain end shaft."
        return TransitionResult(previous, self.state.mode, True, self.state.last_status)

    def accept_rack_pinion(self, gear_id: str | None) -> TransitionResult:
        previous = self.state.mode
        if previous is not MechanicalMode.PICK_RACK_PINION:
            return TransitionResult(previous, previous, False, "Rack pinion is not expected in the current state.")
        value = str(gear_id or "")
        if not value or value not in self.state.assembly.gears:
            return TransitionResult(previous, previous, False, "Select a valid generated gear mesh as the rack pinion.")
        self.state.pending_rack_pinion_gear_id = value
        self.state.pending_rack_start = None
        self.state.mode = MechanicalMode.PLACE_RACK_START
        self.state.last_status = "Pinion selected. Click the first rack endpoint."
        return TransitionResult(previous, self.state.mode, True, self.state.last_status)

    def accept_rack_start(self, position: Point3) -> TransitionResult:
        previous = self.state.mode
        if previous is not MechanicalMode.PLACE_RACK_START:
            return TransitionResult(previous, previous, False, "Rack start is not expected in the current state.")
        if not self.state.pending_rack_pinion_gear_id:
            self.state.mode = MechanicalMode.PICK_RACK_PINION
            return TransitionResult(previous, self.state.mode, True, "Select the rack pinion first.")
        self.state.pending_rack_start = point3(position)
        self.state.mode = MechanicalMode.PLACE_RACK_END
        self.state.last_status = "First endpoint placed. Click the second endpoint to define rack length and direction."
        return TransitionResult(previous, self.state.mode, True, self.state.last_status)

    def accept_driver_target(self, mesh_id: str | None) -> TransitionResult:
        previous = self.state.mode
        if previous is not MechanicalMode.PICK_DRIVER_TARGET:
            return TransitionResult(previous, previous, False, "Driver target is not expected in the current state.")
        self.state.pending_driver_mesh_id = str(mesh_id) if mesh_id else None
        self.state.mode = MechanicalMode.PLACE_DRIVER_CENTER
        self.state.last_status = "Target selected. Click its rotation centre."
        return TransitionResult(previous, self.state.mode, True, self.state.last_status)

    def accept_attachment_source(self, element_id: str | None) -> TransitionResult:
        previous = self.state.mode
        if previous is not MechanicalMode.PICK_ATTACHMENT_SOURCE:
            return TransitionResult(previous, previous, False, "Attachment source is not expected in the current state.")
        source_id = str(element_id or "")
        if not source_id:
            return TransitionResult(previous, previous, False, "Select a valid gear, chain, rack, or driver as the motion source.")
        self.state.pending_attachment_source_id = source_id
        self.state.pending_attachment_mesh_ids = ()
        self.state.mode = MechanicalMode.PICK_ATTACHMENTS
        self.state.last_status = "Motion source selected. Select one or more scene parts, then confirm Attach."
        return TransitionResult(previous, self.state.mode, True, self.state.last_status)

    def update_attachment_targets(self, mesh_ids: Any) -> TransitionResult:
        previous = self.state.mode
        if previous is not MechanicalMode.PICK_ATTACHMENTS:
            return TransitionResult(previous, previous, False, "Attachment targets are not expected in the current state.")
        values = tuple(dict.fromkeys(str(value) for value in (mesh_ids or ()) if str(value)))
        self.state.pending_attachment_mesh_ids = values
        if values:
            message = f"{len(values)} scene part(s) selected. Confirm Attach to bind them to the motion source."
        else:
            message = "Select one or more normal scene parts, then confirm Attach."
        self.state.last_status = message
        return TransitionResult(previous, previous, False, message)


__all__ = ["MechanicalIntent", "MechanicalWorkflowMachine", "TransitionResult"]

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass

from .models import FoldingPhase, FoldingSession


@dataclass(frozen=True, slots=True)
class FoldingPhaseSpec:
    phase: FoldingPhase
    step: int
    title: str
    instruction: str
    help_text: str


_PHASE_SPECS = {
    FoldingPhase.SELECT_MESH: FoldingPhaseSpec(
        FoldingPhase.SELECT_MESH,
        1,
        "Select the mesh",
        "Select one or more meshes, then start Folding or click a highlighted mesh.",
        "All selected meshes share the fold but stay separate after Apply.",
    ),
    FoldingPhase.SELECT_FACE: FoldingPhaseSpec(
        FoldingPhase.SELECT_FACE,
        2,
        "Select the drawing face",
        "Click the face that contains the hinge zone.",
        "The selected face defines the fold direction and surface normal.",
    ),
    FoldingPhase.PLACE_START: FoldingPhaseSpec(
        FoldingPhase.PLACE_START,
        3,
        "Place the fixed-side limit",
        "Click the first boundary of the flexible hinge band. Smart Snap is active.",
        "This side is fixed by default. The API cursor shows the active snap type.",
    ),
    FoldingPhase.PLACE_END: FoldingPhaseSpec(
        FoldingPhase.PLACE_END,
        4,
        "Place the moving-side limit",
        "Click the second boundary. Hold Shift to constrain the axis to 45° increments.",
        "Smart Snap remains active. The material between both points bends; the rest moves as a rigid part.",
    ),
    FoldingPhase.ADJUST_CURVE: FoldingPhaseSpec(
        FoldingPhase.ADJUST_CURVE,
        5,
        "Adjust the folding curve",
        "Drag the purple handles to shape the bend, then set the terminal angle.",
        "The neutral line keeps its length; the outer regions remain rigid. The 3D mesh updates after a short pause.",
    ),
}


@dataclass(frozen=True, slots=True)
class FoldingTransition:
    accepted: bool
    phase: FoldingPhase
    message: str


class FoldingWorkflowMachine:
    """Guarded UX state machine for the Folding creator tool.

    The machine owns phase transitions only. Picking, rendering and document
    preview remain in the tool/controller so the state model stays headless and
    testable.
    """

    def __init__(self, session: FoldingSession) -> None:
        self.session = session

    @property
    def phase_spec(self) -> FoldingPhaseSpec:
        return _PHASE_SPECS[self.session.phase]

    @staticmethod
    def spec_for(phase: FoldingPhase) -> FoldingPhaseSpec:
        return _PHASE_SPECS[phase]

    def _reject(self, message: str) -> FoldingTransition:
        return FoldingTransition(False, self.session.phase, message)

    def select_mesh(self) -> FoldingTransition:
        if not self.session.target_rows() and (self.session.source_mesh is None or self.session.target_object_id is None):
            return self._reject("No valid mesh group was selected.")
        if self.session.editing_existing and self.session.curve.complete and self.session.plane is not None:
            self.session.phase = FoldingPhase.ADJUST_CURVE
            return FoldingTransition(True, self.session.phase, "Existing folding group loaded. Adjust it or Apply without changing it.")
        self.session.phase = FoldingPhase.SELECT_FACE
        return FoldingTransition(True, self.session.phase, "Mesh group selected. Choose the face that contains the hinge.")

    def select_face(self) -> FoldingTransition:
        if self.session.phase is not FoldingPhase.SELECT_FACE:
            return self._reject("The workflow is not waiting for a face.")
        if self.session.plane is None:
            return self._reject("The selected face does not define a valid plane.")
        self.session.phase = FoldingPhase.PLACE_START
        return FoldingTransition(True, self.session.phase, "Face selected. Place the first boundary of the flexible band.")

    def place_start(self) -> FoldingTransition:
        if self.session.phase is not FoldingPhase.PLACE_START:
            return self._reject("The workflow is not waiting for the start point.")
        if self.session.curve.start is None:
            return self._reject("Place a valid start point on the selected face plane.")
        self.session.phase = FoldingPhase.PLACE_END
        return FoldingTransition(True, self.session.phase, "First boundary placed. Place the second boundary.")

    def place_end(self) -> FoldingTransition:
        if self.session.phase is not FoldingPhase.PLACE_END:
            return self._reject("The workflow is not waiting for the end point.")
        if not self.session.curve.complete:
            return self._reject("Place a valid end point on the selected face plane.")
        self.session.phase = FoldingPhase.ADJUST_CURVE
        self.session.dirty = True
        return FoldingTransition(True, self.session.phase, "Hinge ready. Shape the curve with the purple handles; the mesh preview updates after a short pause.")

    def back(self) -> FoldingTransition:
        phase = self.session.phase
        if phase is FoldingPhase.SELECT_FACE:
            self.session.reset(keep_applied_state=True)
            return FoldingTransition(True, self.session.phase, "Mesh selection cleared. Choose another mesh.")
        if phase is FoldingPhase.PLACE_START:
            self.session.plane = None
            self.session.plane_origin = None
            self.session.selected_face_index = None
            self.session.selected_face_vertices = ()
            self.session.phase = FoldingPhase.SELECT_FACE
            return FoldingTransition(True, self.session.phase, "Face selection cleared. Choose another face.")
        if phase is FoldingPhase.PLACE_END:
            self.session.curve.start = None
            self.session.hover_point = None
            self.session.phase = FoldingPhase.PLACE_START
            return FoldingTransition(True, self.session.phase, "Start point cleared. Place it again.")
        if phase is FoldingPhase.ADJUST_CURVE:
            self.session.curve.end = None
            self.session.curve.control_1_offset_mm = 0.0
            self.session.curve.control_2_offset_mm = 0.0
            self.session.hover_point = None
            self.session.phase = FoldingPhase.PLACE_END
            self.session.dirty = False
            return FoldingTransition(True, self.session.phase, "Curve cleared. Place the moving-side limit again.")
        return self._reject("Already at the first step.")


__all__ = ["FoldingPhaseSpec", "FoldingTransition", "FoldingWorkflowMachine"]

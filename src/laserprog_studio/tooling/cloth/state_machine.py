"""Headless UX state machines for Cloth.

The workflow phase, drawing mode and click draft are intentionally separated.
That prevents the final Creator tool from becoming one event-handler monolith.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from laserprog_studio.tool_api.tracing import TraceDraftMachine, TraceMode, normalize_trace_mode

from .flattening import ClothFlatteningResult, flatten_cloth_document
from .groups import create_textile_group
from .models import (
    ClothDocument,
    ClothEditMode,
    ClothFoldKind,
    ClothSession,
    ClothWorkflowPhase,
)
from .output import ClothApplyPlan, build_cloth_apply_plan
from .validation import ClothValidationReport, validate_cloth_document


class ClothTransitionError(RuntimeError):
    pass


class ClothFoldDraftPhase(str, Enum):
    IDLE = "idle"
    SELECT_EDGE = "select_edge"
    SELECT_SECOND_PANEL = "select_second_panel"
    ADJUST = "adjust"
    READY = "ready"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ClothFoldDraft:
    phase: ClothFoldDraftPhase = ClothFoldDraftPhase.IDLE
    curve_id: str | None = None
    patch_a_id: str | None = None
    patch_b_id: str | None = None
    angle_degrees: float = 0.0
    kind: ClothFoldKind = ClothFoldKind.NEUTRAL


class ClothFoldDraftMachine:
    def __init__(self, draft: ClothFoldDraft | None = None) -> None:
        self.draft = draft or ClothFoldDraft()

    def begin(self) -> ClothFoldDraft:
        self.draft = ClothFoldDraft(phase=ClothFoldDraftPhase.SELECT_EDGE)
        return self.draft

    def select_edge(self, curve_id: str, patch_a_id: str) -> ClothFoldDraft:
        if self.draft.phase is not ClothFoldDraftPhase.SELECT_EDGE:
            raise ClothTransitionError("Fold edge can only be selected at the beginning of a fold draft.")
        self.draft.curve_id = str(curve_id)
        self.draft.patch_a_id = str(patch_a_id)
        self.draft.phase = ClothFoldDraftPhase.SELECT_SECOND_PANEL
        return self.draft

    def select_second_panel(self, patch_b_id: str) -> ClothFoldDraft:
        if self.draft.phase is not ClothFoldDraftPhase.SELECT_SECOND_PANEL:
            raise ClothTransitionError("Second fold panel is not expected in the current state.")
        if str(patch_b_id) == self.draft.patch_a_id:
            raise ClothTransitionError("A fold needs two distinct panels.")
        self.draft.patch_b_id = str(patch_b_id)
        self.draft.phase = ClothFoldDraftPhase.ADJUST
        return self.draft

    def adjust(self, *, angle_degrees: float, kind: ClothFoldKind | None = None) -> ClothFoldDraft:
        if self.draft.phase not in {ClothFoldDraftPhase.ADJUST, ClothFoldDraftPhase.READY}:
            raise ClothTransitionError("Fold angle cannot be adjusted before both panels are selected.")
        angle = float(angle_degrees)
        if not -180.0 <= angle <= 180.0:
            raise ValueError("Fold angle must stay between -180 and 180 degrees.")
        self.draft.angle_degrees = angle
        if kind is not None:
            self.draft.kind = kind
        self.draft.phase = ClothFoldDraftPhase.READY
        return self.draft

    def cancel(self) -> ClothFoldDraft:
        self.draft.phase = ClothFoldDraftPhase.CANCELLED
        return self.draft


class ClothWorkflowMachine:
    """Top-level Cloth session coordinator used by the future Creator adapter."""

    def __init__(self, session: ClothSession | None = None) -> None:
        self.session = session or ClothSession()
        self.trace = TraceDraftMachine(self.session.trace_draft)
        self.fold = ClothFoldDraftMachine()
        self.last_validation: ClothValidationReport | None = None
        self.last_flattening: ClothFlatteningResult | None = None
        self.last_apply_plan: ClothApplyPlan | None = None

    def start_new(self) -> ClothSession:
        if self.session.phase not in {ClothWorkflowPhase.OPENING, ClothWorkflowPhase.CANCELLED, ClothWorkflowPhase.APPLIED}:
            raise ClothTransitionError("A new Cloth document can only start from the opening state.")
        self.session = ClothSession(
            document=ClothDocument(),
            phase=ClothWorkflowPhase.EDITING,
            edit_mode=ClothEditMode.POLYLINE,
            status="Polyline ready. Place points directly in 3D.",
        )
        self.trace = TraceDraftMachine(self.session.trace_draft)
        self.fold = ClothFoldDraftMachine()
        return self.session

    def edit_existing(self, document: ClothDocument, *, source_mesh_id: str | None = None) -> ClothSession:
        if self.session.phase is not ClothWorkflowPhase.OPENING:
            raise ClothTransitionError("Existing Cloth geometry can only be opened from the opening state.")
        clone = document.clone()
        self.session = ClothSession(
            document=clone,
            original_document=clone.clone(),
            phase=ClothWorkflowPhase.EDITING,
            editing_existing=True,
            source_mesh_id=source_mesh_id,
            status="Existing Cloth surface loaded. Select a drawing or fold mode.",
        )
        self.trace = TraceDraftMachine(self.session.trace_draft)
        self.fold = ClothFoldDraftMachine()
        return self.session

    def set_edit_mode(self, mode: str | ClothEditMode | TraceMode) -> ClothSession:
        self._require_phase(ClothWorkflowPhase.EDITING)
        raw = mode.value if isinstance(mode, (ClothEditMode, TraceMode)) else str(mode)
        allowed = {item.value for item in ClothEditMode}
        normalized = normalize_trace_mode(raw, default=raw, allowed=allowed)
        if normalized not in allowed:
            normalized = raw if raw in allowed else ClothEditMode.MODIFY.value
        self.session.edit_mode = ClothEditMode(normalized)
        self.trace.cancel()
        self.trace.reset()
        self.session.trace_draft = self.trace.draft
        self.session.status = f"Cloth mode: {self.session.edit_mode.value}."
        return self.session

    def begin_trace(self, mode: str | TraceMode | None = None) -> ClothSession:
        self._require_phase(ClothWorkflowPhase.EDITING)
        selected = mode or self.session.edit_mode.value
        normalized = normalize_trace_mode(selected)
        if normalized not in {TraceMode.POINT.value, TraceMode.LINE.value, TraceMode.POLYLINE.value, TraceMode.ARC.value}:
            raise ClothTransitionError(f"Mode {selected!r} is not a point-placement trace mode.")
        self.trace.begin(normalized)
        self.session.trace_draft = self.trace.draft
        self.session.status = f"Place points for {normalized}."
        return self.session

    def add_trace_point(self, point_id: str, *, finish: bool = False, closed: bool = False) -> ClothSession:
        self._require_phase(ClothWorkflowPhase.EDITING)
        update = self.trace.add_point(point_id, finish=finish, closed=closed)
        if not update.accepted:
            raise ClothTransitionError(update.reason or "Trace point was rejected.")
        self.session.trace_draft = update.draft
        if update.committed:
            self._materialize_committed_trace()
        return self.session

    def finish_trace(self, *, closed: bool = False) -> ClothSession:
        self._require_phase(ClothWorkflowPhase.EDITING)
        update = self.trace.finish(closed=closed)
        if not update.committed:
            raise ClothTransitionError(update.reason or "Trace is incomplete.")
        self.session.trace_draft = update.draft
        self._materialize_committed_trace()
        return self.session

    def _materialize_committed_trace(self) -> None:
        draft = self.trace.draft
        document = self.session.document
        if draft.mode == TraceMode.LINE.value:
            document.add_line(draft.point_ids[0], draft.point_ids[1])
        elif draft.mode == TraceMode.ARC.value:
            document.add_arc(draft.point_ids[0], draft.point_ids[1], draft.point_ids[2])
        elif draft.mode == TraceMode.POLYLINE.value:
            curve = document.add_polyline(draft.point_ids, closed=draft.closed)
            if draft.closed:
                patch = document.add_patch((curve.id,), name=f"Panel {len(document.patches) + 1}")
                create_textile_group(document, (patch.id,), origin="draw")
        elif draft.mode != TraceMode.POINT.value:
            raise ClothTransitionError(f"Unsupported committed trace mode: {draft.mode}")
        self.session.dirty = True
        self.session.status = f"{draft.mode.capitalize()} committed."
        self.trace.reset()
        self.session.trace_draft = self.trace.draft

    def create_patch(self, curve_ids, *, name: str = "Panel"):
        self._require_phase(ClothWorkflowPhase.EDITING)
        patch = self.session.document.add_patch(tuple(curve_ids), name=name)
        create_textile_group(self.session.document, (patch.id,), origin="draw")
        self.session.dirty = True
        self.session.status = f"Panel {patch.name} created."
        return patch

    def begin_fold(self) -> ClothFoldDraft:
        self._require_phase(ClothWorkflowPhase.EDITING)
        self.session.edit_mode = ClothEditMode.FOLD
        return self.fold.begin()

    def commit_fold(self):
        self._require_phase(ClothWorkflowPhase.EDITING)
        draft = self.fold.draft
        if draft.phase is not ClothFoldDraftPhase.READY or not all((draft.curve_id, draft.patch_a_id, draft.patch_b_id)):
            raise ClothTransitionError("Fold draft is not complete.")
        fold = self.session.document.add_fold(
            draft.curve_id,
            draft.patch_a_id,
            draft.patch_b_id,
            angle_degrees=draft.angle_degrees,
            kind=draft.kind,
        )
        self.session.dirty = True
        self.session.status = f"Fold {fold.id} created."
        self.fold = ClothFoldDraftMachine()
        return fold

    def request_flat_preview(self) -> ClothSession:
        self._require_phase(ClothWorkflowPhase.EDITING, ClothWorkflowPhase.VALIDATION_BLOCKED)
        self.last_validation = validate_cloth_document(self.session.document)
        if not self.last_validation.can_apply:
            self.session.phase = ClothWorkflowPhase.VALIDATION_BLOCKED
            self.session.status = self.last_validation.errors[0].message
            return self.session
        self.last_flattening = flatten_cloth_document(self.session.document)
        if not self.last_flattening.success:
            self.session.phase = ClothWorkflowPhase.VALIDATION_BLOCKED
            error = next((issue.message for issue in self.last_flattening.issues if issue.error), "Flattening failed.")
            self.session.status = error
            return self.session
        self.session.phase = ClothWorkflowPhase.FLAT_PREVIEW
        self.session.status = "Flat pattern preview is ready."
        return self.session

    def return_to_editing(self) -> ClothSession:
        self._require_phase(ClothWorkflowPhase.FLAT_PREVIEW, ClothWorkflowPhase.VALIDATION_BLOCKED, ClothWorkflowPhase.APPLY_READY)
        self.session.phase = ClothWorkflowPhase.EDITING
        self.session.status = "Continue editing the Cloth surface."
        return self.session

    def prepare_apply(self, *, name: str = "Cloth") -> ClothApplyPlan:
        if self.session.phase is ClothWorkflowPhase.EDITING:
            self.request_flat_preview()
        self._require_phase(ClothWorkflowPhase.FLAT_PREVIEW, ClothWorkflowPhase.APPLY_READY)
        plan = build_cloth_apply_plan(self.session.document, name=name)
        self.last_apply_plan = plan
        if not plan.ready:
            self.session.phase = ClothWorkflowPhase.VALIDATION_BLOCKED
            self.session.status = plan.issues[0] if plan.issues else "Cloth output is not ready."
            return plan
        self.session.phase = ClothWorkflowPhase.APPLY_READY
        self.session.status = "Apply will create the 3D surface and a flat-pattern scene."
        return plan

    def mark_applied(self) -> ClothSession:
        self._require_phase(ClothWorkflowPhase.APPLY_READY)
        self.session.phase = ClothWorkflowPhase.APPLIED
        self.session.dirty = False
        self.session.status = "Cloth applied."
        return self.session

    def cancel(self) -> ClothSession:
        if self.session.phase in {ClothWorkflowPhase.APPLIED, ClothWorkflowPhase.CANCELLED}:
            return self.session
        if self.session.editing_existing and self.session.original_document is not None:
            self.session.document = self.session.original_document.clone()
        self.session.phase = ClothWorkflowPhase.CANCELLED
        self.session.dirty = False
        self.session.status = "Cloth changes cancelled."
        return self.session

    def invariant_issues(self) -> tuple[str, ...]:
        issues: list[str] = []
        if self.session.phase is ClothWorkflowPhase.OPENING and self.session.dirty:
            issues.append("opening_session_is_dirty")
        if self.session.phase in {ClothWorkflowPhase.FLAT_PREVIEW, ClothWorkflowPhase.APPLY_READY} and self.last_flattening is None:
            issues.append("flat_phase_without_flattening")
        if self.session.phase is ClothWorkflowPhase.APPLY_READY and (self.last_apply_plan is None or not self.last_apply_plan.ready):
            issues.append("apply_ready_without_output_plan")
        if self.session.trace_draft.status.value == "active" and self.session.phase is not ClothWorkflowPhase.EDITING:
            issues.append("trace_active_outside_editing")
        return tuple(issues)

    def describe(self) -> dict[str, object]:
        return {
            "phase": self.session.phase.value,
            "edit_mode": self.session.edit_mode.value,
            "trace_mode": self.session.trace_draft.mode,
            "trace_points": len(self.session.trace_draft.point_ids),
            "points": len(self.session.document.points),
            "curves": len(self.session.document.curves),
            "patches": len(self.session.document.patches),
            "folds": len(self.session.document.folds),
            "seams": len(self.session.document.seams),
            "dirty": self.session.dirty,
            "can_apply": self.last_apply_plan.ready if self.last_apply_plan is not None else False,
            "status": self.session.status,
        }

    def _require_phase(self, *allowed: ClothWorkflowPhase) -> None:
        if self.session.phase not in allowed:
            expected = ", ".join(item.value for item in allowed)
            raise ClothTransitionError(f"Cloth phase {self.session.phase.value!r} does not allow this action; expected {expected}.")


__all__ = [
    "ClothFoldDraft",
    "ClothFoldDraftMachine",
    "ClothFoldDraftPhase",
    "ClothTransitionError",
    "ClothWorkflowMachine",
]

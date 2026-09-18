"""Small headless placement machine shared by 2D and 3D tracing tools."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .modes import TraceMode, normalize_trace_mode


class TraceDraftStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    READY = "ready"
    COMMITTED = "committed"
    CANCELLED = "cancelled"


_FIXED_POINT_COUNTS: dict[str, int] = {
    TraceMode.POINT.value: 1,
    TraceMode.LINE.value: 2,
    TraceMode.RECTANGLE.value: 2,
    TraceMode.CIRCLE.value: 2,
    TraceMode.ARC.value: 3,
}


@dataclass(frozen=True, slots=True)
class TraceDraft:
    mode: str = TraceMode.MODIFY.value
    point_ids: tuple[str, ...] = ()
    status: TraceDraftStatus = TraceDraftStatus.IDLE
    closed: bool = False

    @property
    def required_points(self) -> int | None:
        return _FIXED_POINT_COUNTS.get(self.mode)

    @property
    def can_finish(self) -> bool:
        if self.mode == TraceMode.POLYLINE.value:
            return len(self.point_ids) >= 2
        required = self.required_points
        return required is not None and len(self.point_ids) >= required


@dataclass(frozen=True, slots=True)
class TraceDraftUpdate:
    draft: TraceDraft
    accepted: bool
    ready_to_commit: bool = False
    committed: bool = False
    reason: str = ""


class TraceDraftMachine:
    """Deterministic click-sequence state for point/line/arc/polyline tools.

    The machine stores only point identifiers.  Coordinate picking, snapping,
    rendering and document mutation remain responsibilities of the owning tool.
    This separation lets Plan Tracer 2D and Cloth share interaction semantics
    without sharing their very different geometry documents.
    """

    def __init__(self, draft: TraceDraft | None = None) -> None:
        self._draft = draft or TraceDraft()

    @property
    def draft(self) -> TraceDraft:
        return self._draft

    def begin(self, mode: str | TraceMode) -> TraceDraft:
        normalized = normalize_trace_mode(mode)
        if normalized == TraceMode.MODIFY.value:
            self._draft = TraceDraft(mode=normalized, status=TraceDraftStatus.IDLE)
        else:
            self._draft = TraceDraft(mode=normalized, status=TraceDraftStatus.ACTIVE)
        return self._draft

    def add_point(self, point_id: str, *, finish: bool = False, closed: bool = False) -> TraceDraftUpdate:
        draft = self._draft
        if draft.status not in {TraceDraftStatus.ACTIVE, TraceDraftStatus.READY}:
            return TraceDraftUpdate(draft, False, reason="draft_not_active")
        point = str(point_id).strip()
        if not point:
            return TraceDraftUpdate(draft, False, reason="empty_point_id")

        if draft.mode == TraceMode.POLYLINE.value:
            points = (*draft.point_ids, point)
            can_finish = len(points) >= 2
            status = TraceDraftStatus.READY if can_finish else TraceDraftStatus.ACTIVE
            self._draft = replace(draft, point_ids=points, status=status, closed=bool(closed))
            if finish:
                return self.commit()
            return TraceDraftUpdate(self._draft, True, ready_to_commit=can_finish)

        required = draft.required_points
        if required is None:
            return TraceDraftUpdate(draft, False, reason="unsupported_mode")
        if len(draft.point_ids) >= required:
            return TraceDraftUpdate(draft, False, ready_to_commit=True, reason="point_count_complete")
        points = (*draft.point_ids, point)
        ready = len(points) >= required
        self._draft = replace(draft, point_ids=points, status=TraceDraftStatus.READY if ready else TraceDraftStatus.ACTIVE)
        return TraceDraftUpdate(self._draft, True, ready_to_commit=ready)

    def finish(self, *, closed: bool | None = None) -> TraceDraftUpdate:
        if closed is not None:
            self._draft = replace(self._draft, closed=bool(closed))
        return self.commit()

    def commit(self) -> TraceDraftUpdate:
        draft = self._draft
        if not draft.can_finish:
            return TraceDraftUpdate(draft, False, reason="insufficient_points")
        self._draft = replace(draft, status=TraceDraftStatus.COMMITTED)
        return TraceDraftUpdate(self._draft, True, ready_to_commit=True, committed=True)

    def cancel(self) -> TraceDraft:
        self._draft = replace(self._draft, status=TraceDraftStatus.CANCELLED)
        return self._draft

    def reset(self) -> TraceDraft:
        self._draft = TraceDraft()
        return self._draft


__all__ = ["TraceDraft", "TraceDraftMachine", "TraceDraftStatus", "TraceDraftUpdate"]

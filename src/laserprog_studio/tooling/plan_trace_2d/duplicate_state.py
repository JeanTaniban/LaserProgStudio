# -*- coding: utf-8 -*-
"""Explicit user-state machine for Plan Tracer Duplicate.

Duplicate is a Modify extension, not an isolated drawing tool.  This module
keeps its interaction policy declarative so viewport event routing, overlay
enablement and Escape/Back behaviour cannot silently diverge.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DuplicateStage(str, Enum):
    LIBRARY = "library"
    CAPTURE = "capture"
    PIVOT = "pivot"
    PIVOT_READY = "pivot_ready"
    PLACE = "place"
    EDGE = "edge"
    FACE = "face"

    @classmethod
    def coerce(cls, value: "DuplicateStage | str") -> "DuplicateStage":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except Exception as exc:
            raise ValueError(f"Unknown Duplicate stage: {value!r}") from exc


_ALLOWED_TRANSITIONS: dict[DuplicateStage, frozenset[DuplicateStage]] = {
    DuplicateStage.LIBRARY: frozenset({
        DuplicateStage.CAPTURE,
        DuplicateStage.PLACE,
        DuplicateStage.EDGE,
        DuplicateStage.FACE,
    }),
    DuplicateStage.CAPTURE: frozenset({DuplicateStage.LIBRARY, DuplicateStage.PIVOT}),
    DuplicateStage.PIVOT: frozenset({DuplicateStage.LIBRARY, DuplicateStage.PIVOT_READY}),
    DuplicateStage.PIVOT_READY: frozenset({DuplicateStage.LIBRARY, DuplicateStage.PIVOT}),
    DuplicateStage.PLACE: frozenset({DuplicateStage.LIBRARY}),
    DuplicateStage.EDGE: frozenset({DuplicateStage.LIBRARY}),
    DuplicateStage.FACE: frozenset({DuplicateStage.LIBRARY}),
}


@dataclass(slots=True)
class DuplicateWorkflow:
    """Small, testable state machine shared by input and overlay code."""

    _stage: DuplicateStage = DuplicateStage.LIBRARY
    revision: int = 0
    reason: str = "initial"

    @property
    def stage(self) -> DuplicateStage:
        return self._stage

    def force(self, value: DuplicateStage | str, *, reason: str = "compatibility") -> DuplicateStage:
        """Set a stage without transition validation.

        Kept for legacy tests and project migration. Production UI actions use
        :meth:`transition`, which validates the user journey.
        """

        target = DuplicateStage.coerce(value)
        if target != self._stage:
            self._stage = target
            self.revision += 1
        self.reason = str(reason)
        return target

    def transition(self, value: DuplicateStage | str, *, reason: str) -> DuplicateStage:
        target = DuplicateStage.coerce(value)
        if target == self._stage:
            self.reason = str(reason)
            return target
        if target not in _ALLOWED_TRANSITIONS[self._stage]:
            raise ValueError(f"Invalid Duplicate transition: {self._stage.value} -> {target.value} ({reason})")
        self._stage = target
        self.revision += 1
        self.reason = str(reason)
        return target

    @property
    def uses_modify_selection(self) -> bool:
        """Stages that inherit normal Modify select/hover/drag behaviour."""

        return self._stage in {DuplicateStage.LIBRARY, DuplicateStage.CAPTURE}

    @property
    def uses_filtered_selection(self) -> bool:
        return self._stage in {DuplicateStage.EDGE, DuplicateStage.FACE}

    @property
    def uses_selection_box(self) -> bool:
        return self.uses_modify_selection or self.uses_filtered_selection

    @property
    def uses_pointer_preview(self) -> bool:
        return self._stage in {DuplicateStage.PIVOT, DuplicateStage.PLACE}

    @property
    def selection_kind(self) -> str:
        if self._stage in {DuplicateStage.LIBRARY, DuplicateStage.CAPTURE}:
            return "all"
        if self._stage is DuplicateStage.EDGE:
            return "curve"
        if self._stage is DuplicateStage.FACE:
            return "face"
        return "none"

    @property
    def back_target(self) -> DuplicateStage | None:
        if self._stage is DuplicateStage.LIBRARY:
            return None
        return DuplicateStage.LIBRARY


__all__ = ["DuplicateStage", "DuplicateWorkflow"]

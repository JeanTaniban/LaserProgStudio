# -*- coding: utf-8 -*-
"""Explicit user-state machine for Plan Tracer Mirror."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MirrorStage(str, Enum):
    AXIS_START = "axis_start"
    AXIS_END = "axis_end"
    PREVIEW = "preview"


@dataclass(slots=True)
class MirrorWorkflow:
    stage: MirrorStage = MirrorStage.AXIS_START

    def begin_axis(self) -> None:
        self.stage = MirrorStage.AXIS_END

    def preview_ready(self) -> None:
        if self.stage is not MirrorStage.AXIS_END:
            raise RuntimeError("Mirror preview requires an axis start")
        self.stage = MirrorStage.PREVIEW

    def restart(self) -> None:
        self.stage = MirrorStage.AXIS_START


__all__ = ["MirrorStage", "MirrorWorkflow"]

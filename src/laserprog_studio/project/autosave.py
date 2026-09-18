# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AutosavePolicy:
    """Timing policy for future project recovery saves.

    Soft autosave waits for an idle window. Forced autosave guarantees progress
    for very active users but still waits until critical operations end.
    """

    soft_interval_s: float = 120.0
    idle_required_s: float = 10.0
    forced_interval_s: float = 300.0

    def due_kind(
        self,
        *,
        dirty: bool,
        now_s: float,
        last_autosave_s: float | None,
        last_activity_s: float | None,
        critical_operation_active: bool = False,
        save_in_progress: bool = False,
    ) -> str | None:
        if not dirty or critical_operation_active or save_in_progress:
            return None
        if last_autosave_s is None:
            last_autosave_s = now_s
        if last_activity_s is None:
            last_activity_s = now_s
        since_save = max(0.0, float(now_s) - float(last_autosave_s))
        idle_for = max(0.0, float(now_s) - float(last_activity_s))
        if since_save >= float(self.forced_interval_s):
            return "forced"
        if since_save >= float(self.soft_interval_s) and idle_for >= float(self.idle_required_s):
            return "soft"
        return None

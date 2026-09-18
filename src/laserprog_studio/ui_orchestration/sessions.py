# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .models import UILayoutSnapshot


class UISessionService:
    """In-memory UI session snapshots used by tutorials and temporary guidance."""

    def __init__(self, layouts: Any) -> None:
        self.layouts = layouts
        self._snapshots: dict[str, UILayoutSnapshot] = {}

    def capture(self, session_id: str) -> UILayoutSnapshot:
        snapshot = self.layouts.capture()
        self._snapshots[str(session_id)] = snapshot
        return snapshot

    def restore(self, session_id: str, *, forget: bool = True) -> bool:
        snapshot = self._snapshots.get(str(session_id))
        if snapshot is None:
            return False
        ok = bool(self.layouts.restore(snapshot))
        if ok and forget:
            self._snapshots.pop(str(session_id), None)
        return ok

    def discard(self, session_id: str) -> None:
        self._snapshots.pop(str(session_id), None)

    def has_snapshot(self, session_id: str) -> bool:
        return str(session_id) in self._snapshots

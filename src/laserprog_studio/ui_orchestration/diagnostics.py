# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..bootstrap import compute_paths
from ..services.debug_mode import should_record_diagnostics


class UIOrchestrationDiagnostics:
    def __init__(self, owner: Any = None, path: Path | None = None) -> None:
        self.owner = owner
        self.path = path or (compute_paths().diagnostics_dir / "ui_orchestration_debug.jsonl")

    @property
    def enabled(self) -> bool:
        return bool(should_record_diagnostics(self.owner))

    def record(self, event: str, **payload: Any) -> None:
        if not self.enabled:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            row = {"ts": time.time(), "event": str(event), **payload}
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

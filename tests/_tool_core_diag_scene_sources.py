# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

_TOOL_CORE_DIAG_SCENE_RUNTIME_FILES = (
    "src/laserprog_studio/application/tool_core_diag_scene.py",
    "src/laserprog_studio/application/_tool_core_diag_scene_state.py",
    "src/laserprog_studio/application/_tool_core_diag_scene_painter.py",
)


def read_tool_core_diag_scene_runtime_source() -> str:
    """Return the full Tool Core scene runtime source used by source-guard tests."""

    return "\n".join(Path(path).read_text(encoding="utf-8") for path in _TOOL_CORE_DIAG_SCENE_RUNTIME_FILES)

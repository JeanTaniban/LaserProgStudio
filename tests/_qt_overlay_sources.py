# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

_QT_OVERLAY_RUNTIME_FILES = (
    "src/laserprog_studio/tool_core/overlay/qt_adapter.py",
    "src/laserprog_studio/tool_core/overlay/qt_widgets.py",
    "src/laserprog_studio/tool_core/overlay/qt_layout.py",
    "src/laserprog_studio/tool_core/overlay/qt_style.py",
)


def read_qt_overlay_runtime_source() -> str:
    """Return the complete Qt overlay runtime source used by source-guard tests."""

    return "\n".join(Path(path).read_text(encoding="utf-8") for path in _QT_OVERLAY_RUNTIME_FILES)

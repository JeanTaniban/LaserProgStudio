# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_pass227_qt_overlay_adapter_is_split_by_runtime_responsibility() -> None:
    adapter = Path("src/laserprog_studio/tool_core/overlay/qt_adapter.py")
    widgets = Path("src/laserprog_studio/tool_core/overlay/qt_widgets.py")
    layout = Path("src/laserprog_studio/tool_core/overlay/qt_layout.py")
    style = Path("src/laserprog_studio/tool_core/overlay/qt_style.py")

    assert adapter.exists()
    assert widgets.exists()
    assert layout.exists()
    assert style.exists()
    assert len(adapter.read_text(encoding="utf-8").splitlines()) < 800

    adapter_source = adapter.read_text(encoding="utf-8")
    assert "build_tool_core_overlay_frame" in adapter_source
    assert "rebuild_overlay_widget" in adapter_source
    assert "paint_overlay_frame" in adapter_source


def test_pass227_qt_overlay_source_guards_cover_split_modules() -> None:
    helper = _read("tests/_qt_overlay_sources.py")
    assert "qt_adapter.py" in helper
    assert "qt_widgets.py" in helper
    assert "qt_layout.py" in helper
    assert "qt_style.py" in helper

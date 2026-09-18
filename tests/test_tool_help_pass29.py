# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tooling.help_docs import get_tool_help_document, iter_tool_help_documents, render_tool_help_markdown
from laserprog_studio.tooling.ids import TOOL_NONE
from laserprog_studio.tooling.registry import iter_tool_specs

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


def test_every_builtin_tool_has_user_help() -> None:
    missing = [spec.id for spec in iter_tool_specs() if spec.id != TOOL_NONE and get_tool_help_document(spec.id) is None]
    assert missing == []


def test_help_documents_are_concise_markdown_with_required_sections() -> None:
    docs = iter_tool_help_documents()
    assert len(docs) >= 14
    for doc in docs:
        markdown = doc.as_markdown()
        assert markdown.startswith("# ")
        assert "## When to use it" in markdown
        assert "## Parameters" in markdown
        assert "## Workflow" in markdown
        assert len(markdown) < 2600


def test_render_unknown_help_has_safe_fallback() -> None:
    markdown = render_tool_help_markdown("unknown_extension_tool")
    assert "No dedicated documentation" in markdown


def test_tool_help_controller_uses_lazy_qt_imports() -> None:
    source = (STUDIO / "application" / "tool_help_controller.py").read_text(encoding="utf-8")
    header = source.split("def _qt_widgets", 1)[0]
    assert "PySide6" not in header
    assert "QDialog" not in header
    assert "QTextBrowser" not in header


def test_tool_panel_contains_global_help_button() -> None:
    source = (STUDIO / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    assert "btn_tool_help" in source
    assert "open_active_tool_help" in source
    assert "ToolHelpButton" in source


def test_runtime_composes_tool_help_controller() -> None:
    source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "ToolHelpController.create" in source

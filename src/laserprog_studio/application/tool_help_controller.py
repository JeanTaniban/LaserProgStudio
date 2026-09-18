# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..app_context import AppContext
from ..tooling.help_docs import get_tool_help_document, render_tool_help_markdown
from .owner_delegating_controller import OwnerDelegatingController


def _qt_widgets() -> tuple[Any, Any, Any, Any, Any]:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

    return Qt, QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout


class ToolHelpController(OwnerDelegatingController):
    """Open concise user documentation for the currently active tool.

    The documentation lives in ``tooling.help_docs`` so panels, registry entries
    and future plugin-style tools are not forced to carry long UI strings.
    """

    @classmethod
    def create(cls, context: AppContext) -> "ToolHelpController":
        return cls(context)

    def active_tool_id(self) -> str | None:
        tool_id = getattr(self.owner, "active_tool", None)
        if tool_id in {None, getattr(self.owner, "TOOL_NONE", "none")}:
            return None
        return str(tool_id)

    def update_button_state(self) -> None:
        button = getattr(self.owner, "btn_tool_help", None)
        if button is None:
            return
        tool_id = self.active_tool_id()
        doc = get_tool_help_document(tool_id)
        enabled = doc is not None
        active = tool_id is not None
        try:
            button.setEnabled(bool(active and enabled))
            button.setVisible(bool(active))
            button.setToolTip("Open documentation for the active tool." if enabled else "No documentation is available for this tool.")
        except Exception:
            pass

    def open_active_tool_help(self) -> None:
        tool_id = self.active_tool_id()
        self.open_tool_help(tool_id)

    def open_tool_help(self, tool_id: str | None) -> None:
        Qt, QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout = _qt_widgets()
        doc = get_tool_help_document(tool_id)
        title = doc.title if doc is not None else "Tool help"
        markdown = render_tool_help_markdown(tool_id)

        dialog = QDialog(self.owner)
        dialog.setWindowTitle(f"Help - {title}")
        dialog.setModal(False)
        dialog.resize(680, 620)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        browser = QTextBrowser(dialog)
        browser.setOpenExternalLinks(False)
        browser.setReadOnly(True)
        try:
            browser.setMarkdown(markdown)
        except Exception:
            browser.setPlainText(markdown)
        layout.addWidget(browser, 1)

        try:
            close_button = QDialogButtonBox.StandardButton.Close
        except AttributeError:
            close_button = QDialogButtonBox.Close
        buttons = QDialogButtonBox(close_button, parent=dialog)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons, 0, Qt.AlignRight)
        # Keep a Python reference for non-modal dialogs. Without this, the
        # wrapper may be garbage-collected even though the Qt parent exists.
        self._last_dialog = dialog
        dialog.show()
        try:
            dialog.raise_()
            dialog.activateWindow()
        except Exception:
            pass

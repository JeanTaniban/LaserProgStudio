from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_tool_panel_stack_wraps_pages_at_top() -> None:
    factory = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    panels = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    widgets = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_widgets.py").read_text(encoding="utf-8")

    assert "top_aligned_tool_page(widget)" in factory
    assert "stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)" in factory
    assert "tool_layout.addWidget(self.tool_panel_stack, 0, Qt.AlignTop)" in panels
    assert "def pin_compact_tool_panel" in widgets
    assert "label.setSizePolicy(policy.horizontalPolicy(), QSizePolicy.Fixed)" in widgets
    assert "layout.addStretch(1)" in widgets

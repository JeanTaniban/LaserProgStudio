from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_core.overlay import OverlayManager, OverlayWindowSpec, ToolButtonSpec
from laserprog_studio.tool_core.overlay.qt_adapter import QtOverlayAdapter


def test_overlay_button_spec_exposes_semantic_styles_and_auto_resolution() -> None:
    assert ToolButtonSpec("a", "A").style == "auto"
    assert ToolButtonSpec("a", "A", checkable=True).style == "auto"
    assert QtOverlayAdapter._resolve_button_style(ToolButtonSpec("mode.a", "A", checkable=True, group="mode")) == "mode"
    assert QtOverlayAdapter._resolve_button_style(ToolButtonSpec("snap", "Snap", checkable=True)) == "toggle"
    assert QtOverlayAdapter._resolve_button_style(ToolButtonSpec("delete", "Delete")) == "danger"
    assert QtOverlayAdapter._resolve_button_style(ToolButtonSpec("save", "Save", style="primary")) == "primary"


def test_overlay_toolbar_kind_is_compact_and_preserves_exclusive_state() -> None:
    overlay = OverlayManager()
    overlay.show_window(
        OverlayWindowSpec(
            id="test.toolbar",
            title="",
            owner_tool="test",
            overlay_kind="toolbar",
            width_px=320,
            fields=[],
            buttons=[
                ToolButtonSpec("test.modify", "Modify", checkable=True, checked=True, group="test.mode", style="mode"),
                ToolButtonSpec("test.line", "Line", checkable=True, group="test.mode", style="mode"),
                ToolButtonSpec("test.snap", "Snap", checkable=True, style="toggle"),
                ToolButtonSpec("test.reset", "Reset", style="ghost"),
            ],
        )
    )

    assert overlay.window("test.toolbar").overlay_kind == "toolbar"  # type: ignore[union-attr]
    assert QtOverlayAdapter._minimum_height_for_spec(overlay.window("test.toolbar")) <= 56  # type: ignore[arg-type]
    assert overlay.toggle_button("test.line") is True
    assert overlay.button("test.modify").checked is False  # type: ignore[union-attr]
    assert overlay.button("test.line").checked is True  # type: ignore[union-attr]
    assert overlay.window("test.toolbar").buttons[1].checked is True  # type: ignore[union-attr]


def test_overlay_qt_adapter_declares_dynamic_style_properties() -> None:
    source = read_qt_overlay_runtime_source()
    docs = Path("docs/tool_creator/06_overlay_preview_gizmos.md").read_text(encoding="utf-8")

    assert "overlayButtonStyle" in source
    assert "overlay_kind=\"toolbar\"" in docs
    for style in ("primary", "secondary", "ghost", "toggle", "mode", "danger", "icon"):
        assert f'overlayButtonStyle=\\"{style}\\"' in source
        assert style in docs

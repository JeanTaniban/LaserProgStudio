# -*- coding: utf-8 -*-
from __future__ import annotations
from _qt_overlay_sources import read_qt_overlay_runtime_source

from pathlib import Path

from laserprog_studio.tool_api import AutoPreview, AutoPreviewConfig
from laserprog_studio.tool_api import inspector
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tool_core.overlay import OverlayWindowSpec


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_pass182_autopreview_config_is_public_normalized_and_field_scoped() -> None:
    config = inspector.auto_preview(action_id=" preview ", debounce_ms=-20, include_fields=("width",), exclude_fields=("height",))

    assert isinstance(config, AutoPreviewConfig)
    assert isinstance(AutoPreview(action_id="preview"), AutoPreviewConfig)
    assert config.action_id == "preview"
    assert config.debounce_ms == 0
    assert config.accepts_field("width") is True
    assert config.accepts_field("height") is False
    assert config.accepts_field("depth") is False


def test_pass182_panel_describes_autopreview_policy_for_runtime_and_docs() -> None:
    ctx = ToolContext()
    panel = inspector.panel(
        "Auto preview panel",
        id="example.autopreview",
        owner_tool="example.autopreview",
        auto_preview=inspector.auto_preview(action_id="preview", debounce_ms=275, exclude_fields=("report",)),
        sections=(
            inspector.section("Values", (inspector.float_field("width", "Width", default=10.0),)),
            inspector.section("Actions", (inspector.button_row("actions", "Actions", buttons=(("preview", "Preview"),)),)),
            inspector.section("Report", (inspector.readonly_field("report", "Report", default="Idle"),)),
        ),
    )

    ctx.inspector.set_panel(panel)
    description = ctx.inspector.describe()

    assert description["auto_preview"] == {
        "enabled": True,
        "action_id": "preview",
        "debounce_ms": 275,
        "include_fields": (),
        "exclude_fields": ("report",),
    }


def test_pass182_cleanup_tool_closes_and_syncs_tool_owned_overlays(monkeypatch) -> None:
    ctx = ToolContext()
    calls: list[tuple[object, object]] = []

    class Owner:
        pass

    owner = Owner()
    ctx.owner = owner
    ctx.overlay.show_window(
        OverlayWindowSpec(
            id="example.overlay",
            title="Overlay",
            owner_tool="example.tool",
            persistent=True,
            visible=True,
        )
    )

    import laserprog_studio.tool_core.overlay.qt_adapter as qt_adapter

    def fake_sync(sync_owner: object, manager: object) -> int:
        calls.append((sync_owner, manager))
        return 0

    monkeypatch.setattr(qt_adapter, "sync_qt_overlay_windows", fake_sync)
    monkeypatch.setattr("laserprog_studio.tool_core.overlay.sync_qt_overlay_windows", fake_sync)

    ctx.cleanup_tool("example.tool", include_persistent_overlays=True)

    assert ctx.overlay.window("example.overlay") is not None
    assert ctx.overlay.window("example.overlay").visible is False
    assert calls == [(owner, ctx.overlay)]


def test_pass182_overlay_adapter_has_drag_zorder_and_fixed_hit_geometry_guards() -> None:
    source = read_qt_overlay_runtime_source()

    assert "any_dragging" in source
    assert "dragging_widget.raise_()" in source
    assert "not dragging and not any_dragging" in source
    assert "widget.setMaximumHeight(height)" in source
    assert "qt-move fast-path" in source
    assert "parent.update(old_geometry)" not in source


def test_pass182_docs_explain_autopreview_and_overlay_lifecycle() -> None:
    inspector_doc = _read("docs/tool_creator/05_inspector_panel.md")
    overlay_doc = _read("docs/tool_creator/06_overlay_preview_gizmos.md")
    direction_doc = _read("docs/tool_creator/00_creator_ui_direction.md")
    checklist = _read("docs/tool_creator/09_creator_api_checklist.md")

    assert "Native AutoPreview" in inspector_doc
    assert "debounce_ms" in inspector_doc
    assert "ctx.inspector.trigger(action_id)" in inspector_doc
    assert "tool-owned overlays" in overlay_doc.lower()
    assert "Draggable overlays are kept non-overlapping" in overlay_doc
    assert "AutoPreview is a panel policy" in direction_doc
    assert "Native AutoPreview checklist" in checklist

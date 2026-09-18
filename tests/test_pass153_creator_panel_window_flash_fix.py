# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.inspector import FloatField, Panel, ReadonlyField, Section
from laserprog_studio.tool_core.inspector.specs import InspectorManager

ROOT = Path(__file__).resolve().parents[1]


def test_pass153_live_declarative_panel_never_detaches_visible_child_to_top_level() -> None:
    source = (ROOT / "src/laserprog_studio/ui/declarative_tool_panel_host.py").read_text(encoding="utf-8")

    assert "setParent(None)" not in source
    assert "_dispose_child" in source
    assert "self._child.hide()" in source


def test_pass153_inspector_distinguishes_layout_and_value_revisions() -> None:
    manager = InspectorManager()
    panel = Panel(
        "Demo",
        id="demo",
        sections=(
            Section(
                "Main",
                fields=(
                    FloatField("width", "Width", default=10.0),
                    ReadonlyField("report", "Report", default="initial"),
                ),
            ),
        ),
    )

    manager.set_panel(panel)
    layout_before = manager.layout_revision
    value_before = manager.value_revision

    manager.update_value("width", 12.0)

    assert manager.layout_revision == layout_before
    assert manager.value_revision > value_before

    value_before = manager.value_revision
    manager.set_display_value("report", "updated")

    assert manager.layout_revision == layout_before
    assert manager.value_revision > value_before

    state_before = manager.state_revision
    manager.set_visible("width", False)

    assert manager.layout_revision == layout_before
    assert manager.state_revision > state_before


def test_pass153_live_panel_syncs_values_in_place_instead_of_rebuilding_on_value_change() -> None:
    source = (ROOT / "src/laserprog_studio/ui/declarative_tool_panel_host.py").read_text(encoding="utf-8")
    adapter_source = (ROOT / "src/laserprog_studio/ui/inspector_panel_adapter.py").read_text(encoding="utf-8")

    assert "layout_revision" in source
    assert "value_revision" in source
    assert "state_revision" in source
    assert "sync_widget_values" in source
    assert "InspectorPanelQtAdapter.sync_widget_values" in source
    assert "inspector_field_id" in adapter_source
    assert "_editor_has_user_focus" in adapter_source

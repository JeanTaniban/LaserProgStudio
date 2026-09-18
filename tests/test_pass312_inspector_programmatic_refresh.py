# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.tool_core.inspector import FloatField, Panel, ReadonlyField, Section
from laserprog_studio.tool_core.inspector.specs import InspectorManager

ROOT = Path(__file__).resolve().parents[1]


def _manager() -> InspectorManager:
    manager = InspectorManager()
    manager.set_panel(
        Panel(
            "Demo",
            id="demo.panel",
            owner_tool="demo",
            sections=(
                Section(
                    "Main",
                    fields=(
                        FloatField("width", "Width", default=10.0),
                        ReadonlyField("selected_length", "Selected length", default="—"),
                    ),
                ),
            ),
        )
    )
    return manager


def test_programmatic_readonly_value_notifies_presentation_observer() -> None:
    manager = _manager()
    observed: list[tuple[int, str]] = []

    def _observe() -> None:
        observed.append((manager.value_revision, manager.value("selected_length")))

    token = manager.subscribe_changes(_observe)
    manager.set_display_value("selected_length", "42.0 mm · contiguous")

    assert observed == [(manager.value_revision, "42.0 mm · contiguous")]

    manager.unsubscribe_changes(token)
    manager.set_display_value("selected_length", "84.0 mm · contiguous")
    assert len(observed) == 1


def test_unchanged_display_value_does_not_schedule_redundant_refresh() -> None:
    manager = _manager()
    calls: list[int] = []

    def _observe() -> None:
        calls.append(manager.value_revision)

    manager.subscribe_changes(_observe)
    manager.set_display_value("selected_length", "42.0 mm")
    manager.set_display_value("selected_length", "42.0 mm")

    assert len(calls) == 1


def test_presentation_observer_is_independent_from_business_on_change() -> None:
    business_calls: list[tuple[str, float]] = []
    manager = InspectorManager()
    manager.set_panel(
        Panel(
            "Demo",
            id="demo.panel",
            sections=(
                Section(
                    "Main",
                    fields=(
                        FloatField(
                            "width",
                            "Width",
                            default=10.0,
                            on_change=lambda field_id, value: business_calls.append((field_id, value)),
                        ),
                        ReadonlyField("report", "Report", default="initial"),
                    ),
                ),
            ),
        )
    )
    presentation_calls: list[int] = []

    def _observe() -> None:
        presentation_calls.append(manager.value_revision)

    manager.subscribe_changes(_observe)
    manager.set_display_value("report", "computed")

    assert presentation_calls
    assert business_calls == []


def test_live_panel_subscribes_to_manager_and_coalesces_qt_refreshes() -> None:
    source = (ROOT / "src/laserprog_studio/ui/declarative_tool_panel_host.py").read_text(encoding="utf-8")

    assert "subscribe_changes" in source
    assert "unsubscribe_changes" in source
    assert "_refresh_queued" in source
    assert "QTimer.singleShot(0, self._consume_manager_refresh)" in source
    assert "if self.isVisible():" in source

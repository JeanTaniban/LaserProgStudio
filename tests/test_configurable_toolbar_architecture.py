from __future__ import annotations

import pytest

from laserprog_studio.ui.toolbar_catalog import (
    TOOLBAR_MAX_ITEMS,
    ToolbarItemSpec,
    default_toolbar_item_ids,
    get_toolbar_item_spec,
    iter_toolbar_button_attrs,
    iter_toolbar_item_specs,
    register_toolbar_item,
    reset_toolbar_item_registry,
    sanitized_toolbar_item_ids,
    search_toolbar_item_specs,
    unregister_toolbar_item,
    validate_toolbar_item_registry,
)


def teardown_function(_fn):
    reset_toolbar_item_registry()


def test_toolbar_registry_validates_builtin_specs():
    specs = iter_toolbar_item_specs()
    assert specs
    assert len(default_toolbar_item_ids()) <= TOOLBAR_MAX_ITEMS
    validate_toolbar_item_registry(specs)
    assert "btn_tool_texture_projection" in iter_toolbar_button_attrs()
    assert get_toolbar_item_spec("tool:texture_projection").code == "TEX"


def test_toolbar_sanitizer_drops_duplicates_unknowns_and_limits():
    raw = ["unknown", "tool:primitive", "tool:primitive", "modifier:repair", "boolean:union"]
    assert sanitized_toolbar_item_ids(raw, max_items=2) == ["tool:primitive", "modifier:repair"]


def test_toolbar_registry_supports_future_extensions():
    spec = ToolbarItemSpec(
        "tool:future_probe",
        "FUT",
        "Future tool",
        "Probe extension registration.",
        "tool",
        "tool",
        999,
        tool_id="future_probe",
        button_attr="btn_tool_future_probe",
        default_visible=False,
    )
    register_toolbar_item(spec)
    assert get_toolbar_item_spec("tool:future_probe") == spec
    assert "tool:future_probe" not in default_toolbar_item_ids()
    assert search_toolbar_item_specs("probe extension") == (spec,)
    assert "btn_tool_future_probe" in iter_toolbar_button_attrs()
    unregister_toolbar_item("tool:future_probe")
    assert get_toolbar_item_spec("tool:future_probe") is None


def test_toolbar_registry_rejects_invalid_or_duplicate_items():
    with pytest.raises(ValueError):
        register_toolbar_item(
            ToolbarItemSpec("tool:primitive", "PRI2", "Duplicate", "Duplicate id.", "tool", "tool", 1, tool_id="dup")
        )
    with pytest.raises(ValueError):
        ToolbarItemSpec("tool:bad", "B", "Bad", "Missing tool id.", "tool", "tool", 1).validate()


def test_v70_default_toolbar_order_and_retired_entries():
    assert default_toolbar_item_ids() == [
        "tool:box",
        "tool:plan_trace",
        "tool:joint",
        "tool:texture_projection",
        "tool:layflat",
        "tool:engraving",
        "modifier:split",
        "boolean:subtract",
        "boolean:union",
        "boolean:separate",
    ]
    assert get_toolbar_item_spec("tool:gizmo_catalog") is None
    assert get_toolbar_item_spec("tool:core_diagnostic") is None

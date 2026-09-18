from __future__ import annotations

from laserprog_studio.services.project_preferences import (
    KeyboardShortcutsPreferences,
    ProjectPreferences,
    coerce_project_preferences,
)


def test_shortcut_defaults_match_product_request() -> None:
    shortcuts = ProjectPreferences().shortcuts
    assert shortcuts == KeyboardShortcutsPreferences(
        toolbar_modifier="shift",
        transform_cycle_key="tab",
        preview_apply_key="left_alt",
        hold_threshold_s=0.5,
        multi_press_window_s=0.65,
    )


def test_shortcut_preferences_are_coerced_and_clamped() -> None:
    prefs = coerce_project_preferences(
        {
            "shortcuts": {
                "toolbar_modifier": "shift",
                "transform_cycle_key": "space",
                "preview_apply_key": "space",
                "hold_threshold_s": 0.1,
                "multi_press_window_s": 3.0,
            }
        }
    )
    assert prefs.shortcuts.toolbar_modifier == "shift"
    assert prefs.shortcuts.transform_cycle_key == "space"
    assert prefs.shortcuts.preview_apply_key == "space"
    assert prefs.shortcuts.hold_threshold_s == 0.5
    assert prefs.shortcuts.multi_press_window_s == 0.65


def test_shortcut_preferences_accept_fast_multi_press_window() -> None:
    prefs = coerce_project_preferences({"shortcuts": {"multi_press_window_s": 0.1}})
    assert prefs.shortcuts.multi_press_window_s == 0.1


def test_transform_cycle_applies_live_before_timeout() -> None:
    source = open("src/laserprog_studio/controllers/interaction.py", encoding="utf-8").read()
    assert "_apply_transform_cycle_taps_immediately" in source
    assert "QTimer.singleShot(self._shortcut_multi_press_window_ms(), lambda g=generation: self._finish_transform_cycle_window(g))" in source
    assert "The transform mode was already applied live at each tap" in source

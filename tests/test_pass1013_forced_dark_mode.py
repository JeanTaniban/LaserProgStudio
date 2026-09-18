from __future__ import annotations

import json
from pathlib import Path


def test_dark_mode_and_native_dialogs_are_enabled_by_default_in_shipped_settings():
    payload = json.loads(Path("settings/studio_appearance.json").read_text(encoding="utf-8"))
    assert payload["force_dark_mode"] is True
    assert payload["use_native_dialogs"] is True


def test_app_applies_dark_theme_before_window_creation():
    text = Path("src/laserprog_studio/app.py").read_text(encoding="utf-8")
    assert "configure_dark_mode_before_application" in text
    assert "apply_forced_dark_theme(app)" in text
    assert text.index("apply_forced_dark_theme(app)") < text.index("window = LaserProgStudioV18()")


def test_dark_theme_covers_standard_dialogs_and_palette():
    text = Path("src/laserprog_studio/ui/dark_theme.py").read_text(encoding="utf-8")
    assert "QFileDialog" in text
    assert "QColorDialog" in text
    assert "QMessageBox" in text
    assert "AA_DontUseNativeDialogs" in text
    assert "setColorScheme" in text
    assert "setPalette" in text
    assert "ApplicationPaletteChange" in text


def test_appearance_preferences_have_safe_environment_overrides():
    text = Path("src/laserprog_studio/services/appearance_preferences.py").read_text(encoding="utf-8")
    assert '"LPS_FORCE_DARK_MODE"' in text
    assert '"LPS_USE_NATIVE_DIALOGS"' in text
    assert "force_dark_mode: bool = True" in text
    assert "use_native_dialogs: bool = True" in text
    assert "save_appearance_preferences" in text

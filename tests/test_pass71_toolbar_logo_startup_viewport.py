from __future__ import annotations

from pathlib import Path

from PIL import Image

from laserprog_studio.ui.toolbar_catalog import TOOLBAR_MAX_ITEMS, default_toolbar_item_ids, sanitized_toolbar_item_ids


ROOT = Path(__file__).resolve().parents[1]


def test_toolbar_is_limited_to_18_visible_items() -> None:
    assert TOOLBAR_MAX_ITEMS == 18
    assert len(default_toolbar_item_ids()) <= 18
    raw = default_toolbar_item_ids(max_items=99) + ["boolean:union", "boolean:separate"]
    assert len(sanitized_toolbar_item_ids(raw, max_items=TOOLBAR_MAX_ITEMS)) == 18


def test_logo_png_uses_real_transparency_not_a_baked_white_background() -> None:
    logo_path = ROOT / "src" / "laserprog_studio" / "assets" / "logo.png"
    image = Image.open(logo_path).convert("RGBA")
    alpha_min, alpha_max = image.getchannel("A").getextrema()
    assert alpha_min == 0
    assert alpha_max == 255


def test_app_starts_main_window_maximized() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "app.py").read_text(encoding="utf-8")
    assert "window.showMaximized()" in source


def test_viewport_mouse_state_recovers_from_lost_releases() -> None:
    interaction = (ROOT / "src" / "laserprog_studio" / "controllers" / "interaction.py").read_text(encoding="utf-8")
    recovery = (ROOT / "src" / "laserprog_studio" / "controllers" / "interaction_pointer_recovery.py").read_text(encoding="utf-8")
    assert "InteractionPointerRecoveryLayer" in interaction
    assert "def _release_vtk_mouse_buttons" in recovery
    assert "RightButtonReleaseEvent" in recovery
    assert "buttons == Qt.NoButton" in interaction
    assert "_reset_viewport_pointer_state(release_vtk=True)" in interaction

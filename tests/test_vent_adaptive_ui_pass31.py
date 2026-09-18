from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_pass31_vent_panel_uses_creator_api_adaptive_fields() -> None:
    panel_source = _source("src/laserprog_studio/tooling/vent_generator/panel.py")
    settings_source = _source("src/laserprog_studio/tooling/vent_generator/settings.py")
    tool_source = _source("src/laserprog_studio/tooling/vent_generator_tool.py")
    for field_id in (
        "section_area",
        "rect_width",
        "rect_height",
        "flare_factor",
        "fill_area",
        "curve_radius",
        "curve_strength",
    ):
        assert field_id in panel_source
    assert "AutoPreview" in panel_source
    assert "VentGeneratorSettings" in settings_source
    assert "update_field_state" in tool_source


def test_pass31_vent_settings_are_applied_without_qt_widgets() -> None:
    settings_source = _source("src/laserprog_studio/tooling/vent_generator/settings.py")
    controller_source = _source("src/laserprog_studio/application/planar_tool_payload.py")
    assert "def apply_settings_to_payload" in settings_source
    assert "VentGeneratorSettings.from_values" in controller_source
    assert "apply_settings_to_payload(payload" in controller_source

from pathlib import Path


def test_vent_tool_uses_declarative_panel_instead_of_bespoke_qt_panel():
    assert not Path("src/laserprog_studio/ui/vent_tool_panel.py").exists()
    text = Path("src/laserprog_studio/tooling/vent_generator/panel.py").read_text(encoding="utf-8")
    assert "owner = self.owner" not in text
    assert "build_vent_generator_panel" in text


def test_pass32_documentation_exists():
    assert Path("docs/archive/passes/vent_geometry_rework_pass32.md").exists()

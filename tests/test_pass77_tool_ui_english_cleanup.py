from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _string_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def test_tool_panels_keep_instructions_short_and_english() -> None:
    panel_paths = [
        ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py",
        ROOT / "src" / "laserprog_studio" / "tooling" / "vent_generator" / "panel.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in panel_paths)
    forbidden = [
        "Sélectionne",
        "Clique",
        "Ouvre",
        "Matériaux",
        "Simplifier",
        "Creux",
        "Traceur",
        "Générateur",
        "Workflow conseillé",
        "Shortcuts: Delete",
    ]
    for token in forbidden:
        assert token not in text

    visible_literals: list[str] = []
    for path in panel_paths:
        visible_literals.extend(_string_literals(path))
    long_visible = [s for s in visible_literals if len(s) > 90 and "Builds the right-inspector" not in s]
    assert long_visible == []


def test_key_tools_have_concise_default_statuses() -> None:
    factory = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    vent = (ROOT / "src" / "laserprog_studio" / "tooling" / "vent_generator" / "panel.py").read_text(encoding="utf-8")
    assert 'QLabel("Pick two parts: A then B.")' in factory
    assert 'QLabel("A/B: — · Preview: no")' in factory
    assert 'QLabel("Select a target, then click a face.")' in factory
    assert "Draw a locked-plan vent route" in vent

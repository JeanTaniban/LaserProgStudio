from __future__ import annotations

import ast
from pathlib import Path

from _path_setup import ROOT  # noqa: F401

SRC = ROOT / "src" / "laserprog_studio"


def _class_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def test_layout_controller_uses_owned_layout_state() -> None:
    source = (SRC / "application" / "layout_controller.py").read_text(encoding="utf-8")
    state_source = (SRC / "state" / "ui_layout_state.py").read_text(encoding="utf-8")
    assert "context.layout.inspector" in source
    assert "class InspectorLayoutState" in state_source
    assert "_restore_light_ui_after_tool" not in source
    assert "_restore_splitter_after_tool_close" not in source
    assert "sync_to_legacy_attributes" not in source


def test_application_controller_base_has_product_name() -> None:
    source = (SRC / "application" / "action_controller.py").read_text(encoding="utf-8")
    assert "class WindowController" in source
    assert "LegacyWindowController" not in source
    assert not (SRC / "application" / "legacy_bridge.py").exists()
    assert (SRC / "application" / "owner_delegating_controller.py").exists()


def test_ui_and_engraving_layers_no_longer_count_as_mixins() -> None:
    expected_layers = {
        SRC / "ui" / "panels.py": "UIPanelsLayer",
        SRC / "ui" / "configurable_toolbar.py": "UIConfigurableToolbarLayer",
        SRC / "ui" / "light_transform_overlay.py": "UILightTransformOverlayLayer",
        SRC / "engraving" / "laser_3mf_app_ui.py": "Laser3MFAppUILayer",
    }
    for path, class_name in expected_layers.items():
        names = _class_names(path)
        assert class_name in names
        assert not any(name.endswith("Mixin") for name in names)


def test_mixin_debt_does_not_regrow() -> None:
    mixin_classes = []
    for path in SRC.rglob("*.py"):
        mixin_classes.extend(
            (path.relative_to(ROOT).as_posix(), name)
            for name in _class_names(path)
            if name.endswith("Mixin")
        )
    assert len(mixin_classes) == 0

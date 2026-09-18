from __future__ import annotations

import ast
from pathlib import Path

from _path_setup import ROOT  # noqa: F401

SRC = ROOT / "src" / "laserprog_studio"


def _class_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]


def test_controller_stack_uses_layers_not_mixins() -> None:
    controller_classes = []
    for path in (SRC / "controllers").glob("*.py"):
        controller_classes.extend((path.name, name) for name in _class_names(path))
    assert controller_classes
    assert not [(path, name) for path, name in controller_classes if name.endswith("Mixin")]

    controllers_init = (SRC / "controllers" / "__init__.py").read_text(encoding="utf-8")
    assert "class StudioControllers" in controllers_init
    assert "class StudioControllersMixin" not in controllers_init
    for required in ("InteractionLayer", "MaterialToolLayer", "CameraNavigationLayer", "ClipboardActionsLayer"):
        assert required in controllers_init


def test_window_bridges_target_studio_controllers_layer() -> None:
    source = (SRC / "window.py").read_text(encoding="utf-8")
    assert "from .controllers import StudioControllers" in source
    assert "StudioControllers.eventFilter" in source
    assert "StudioControllersMixin" not in source


def test_modifier_registry_uses_tool_hosted_runtime_entries() -> None:
    modifier_source = (SRC / "modifiers" / "modifier.py").read_text(encoding="utf-8")
    registry_source = (SRC / "modifiers" / "registry.py").read_text(encoding="utf-8")
    assert "class ToolHostedModifier" in modifier_source
    assert "LegacyModifierAdapter" not in modifier_source
    assert "LegacyModifierAdapter" not in registry_source
    assert "ToolHostedModifier(spec)" in registry_source

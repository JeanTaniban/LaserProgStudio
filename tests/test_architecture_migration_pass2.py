from __future__ import annotations

import ast
from pathlib import Path

from _path_setup import ROOT  # noqa: F401

STUDIO = ROOT / "src" / "laserprog_studio"


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"Missing class {class_name} in {path}")


def test_configurable_toolbar_controller_owns_toolbar_workflow() -> None:
    source = (STUDIO / "application" / "toolbar_controller.py").read_text(encoding="utf-8")
    methods = _class_methods(STUDIO / "application" / "toolbar_controller.py", "ConfigurableToolbarController")
    assert {"setup", "set_remove_mode", "apply_remove_mode_visuals", "rebuild", "activate_item", "add_item", "remove_item", "open_palette"}.issubset(methods)
    assert "WindowController" in source
    assert "TOOLBAR_REMOVABLE_ITEM_STYLE" in source
    assert "sanitized_toolbar_item_ids" in source
    assert "search_toolbar_item_specs" in source


def test_configurable_toolbar_mixin_is_only_a_facade() -> None:
    path = STUDIO / "ui" / "configurable_toolbar.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "UIConfigurableToolbarLayer")
    assert {"_toolbar_controller", "_setup_configurable_toolbar", "add_toolbar_item", "remove_toolbar_item", "open_toolbar_palette"}.issubset(methods)
    assert len(source.splitlines()) < 90
    assert "QToolButton" not in source
    assert "QMessageBox" not in source
    assert "TOOLBAR_REMOVABLE_ITEM_STYLE" not in source
    assert "ConfigurableToolbarController" in source


def test_runtime_state_composes_toolbar_controller() -> None:
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "from .application.toolbar_controller import ConfigurableToolbarController" in runtime_source
    assert "self.toolbar_controller = ConfigurableToolbarController.create(self.app_context)" in runtime_source


def test_architecture_docs_record_pass2() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_2.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "ConfigurableToolbarController" in text
    assert "compatibility facade" in text
    assert "toolbar" in (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8").lower()

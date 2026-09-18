from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.app_context import AppContext
from laserprog_studio.application.boolean_controller import BooleanController
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState

STUDIO = ROOT / "src" / "laserprog_studio"


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"Missing class {class_name} in {path}")


def _fake_context() -> AppContext:
    owner = SimpleNamespace(
        TOOL_NONE="none",
        active_tool="none",
        selection_state=SelectionState(),
        transform_state=TransformState(),
        tool_state=ToolState(active_tool="none"),
        preview_state=PreviewState(),
        ui_layout_state=UiLayoutState(),
        render_state=RenderState(),
        clipboard_state=ClipboardState(),
        mesh_store=None,
        scene_renderer=None,
    )
    owner.ui_log = lambda _message: None
    return AppContext.from_window(owner)


def test_boolean_controller_is_composed_from_app_context() -> None:
    context = _fake_context()
    controller = BooleanController.create(context)
    assert controller.context is context
    assert controller.owner is context.owner


def test_boolean_controller_owns_boolean_workflows() -> None:
    path = STUDIO / "application" / "boolean_controller.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "BooleanController")
    expected = {
        "active_boolean_cutter_index",
        "blocked_message",
        "touching_mesh_indices",
        "subtract_touching",
        "union_selected",
        "separate_selected",
    }
    assert expected.issubset(methods)
    assert "boolean_difference" in source
    assert "boolean_union" in source
    assert "split_disconnected_mesh" in source
    assert "mesh_bounds" in source


def test_boolean_actions_mixin_is_facade_only() -> None:
    facade = STUDIO / "controllers" / "boolean_actions.py"
    source = facade.read_text(encoding="utf-8")
    methods = _class_methods(facade, "BooleanActionsLayer")
    assert len(source.splitlines()) < 90
    assert "BooleanController" in source
    assert {
        "_active_boolean_cutter_index",
        "_boolean_blocked_message",
        "_touching_mesh_indices",
        "boolean_subtract_touching",
        "boolean_union_selected",
        "boolean_separate_selected",
    }.issubset(methods)
    assert "from .._window_deps import *" not in source
    assert "boolean_difference(" not in source
    assert "boolean_union(" not in source
    assert "split_disconnected_mesh(" not in source


def test_boolean_controller_keeps_qt_import_lazy() -> None:
    source = (STUDIO / "application" / "boolean_controller.py").read_text(encoding="utf-8")
    assert "from .._window_deps import *" not in source
    assert "def _qmessagebox" in source
    assert "from PySide6.QtWidgets import QMessageBox" in source


def test_runtime_state_composes_boolean_controller() -> None:
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "from .application.boolean_controller import BooleanController" in runtime_source
    assert "self.boolean_controller = BooleanController.create(self.app_context)" in runtime_source


def test_architecture_docs_record_pass7() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_7.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "BooleanController" in text
    assert "Compatibility facade" in text
    architecture_text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "BooleanController" in architecture_text

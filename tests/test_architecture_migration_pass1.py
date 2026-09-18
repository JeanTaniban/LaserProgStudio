from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.app_context import AppContext
from laserprog_studio.application import ClipboardController, HistoryController, SceneEditController, StudioActionController
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState

STUDIO = ROOT / "src" / "laserprog_studio"


def _class_methods(path: Path, class_name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return [item.name for item in node.body if isinstance(item, ast.FunctionDef)]
    raise AssertionError(f"Missing class {class_name} in {path}")


def _fake_context() -> AppContext:
    owner = SimpleNamespace(
        selection_state=SelectionState(),
        transform_state=TransformState(),
        tool_state=ToolState(),
        preview_state=PreviewState(),
        ui_layout_state=UiLayoutState(),
        render_state=RenderState(),
        clipboard_state=ClipboardState(),
        mesh_store=None,
        scene_renderer=None,
    )
    owner.ui_log = lambda _message: None
    return AppContext.from_window(owner)


def test_studio_action_controller_is_composed_from_app_context() -> None:
    context = _fake_context()
    controller = StudioActionController.create(context)
    assert controller.context is context
    assert isinstance(controller.history, HistoryController)
    assert isinstance(controller.clipboard, ClipboardController)
    assert isinstance(controller.scene_edit, SceneEditController)
    assert controller.history.context is context
    assert controller.clipboard.context is context
    assert controller.scene_edit.context is context


def test_legacy_action_mixins_are_lightweight_facades() -> None:
    expected = {
        "history_actions.py": ("HistoryActionsLayer", {"undo_scene", "redo_scene", "_capture_drag_undo_snapshot", "_commit_drag_undo_snapshot"}),
        "clipboard_actions.py": ("ClipboardActionsLayer", {"copy_selected", "paste_selection", "duplicate_selected", "_clipboard_blocked_message"}),
        "scene_edit_actions.py": ("SceneEditActionsLayer", {"delete_selected", "new_scene"}),
    }
    for filename, (class_name, required_methods) in expected.items():
        path = STUDIO / "controllers" / filename
        methods = set(_class_methods(path, class_name))
        assert required_methods.issubset(methods)
        source = path.read_text(encoding="utf-8")
        assert "application" in source
        assert "copy.deepcopy" not in source
        assert "mesh_store.undo" not in source
        assert "mesh_store.redo" not in source
        assert "set_meshes(" not in source


def test_architecture_docs_exist_for_external_contributors() -> None:
    architecture = ROOT / "docs" / "architecture.md"
    migration = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_1.md"
    assert architecture.exists()
    assert migration.exists()
    architecture_text = architecture.read_text(encoding="utf-8")
    assert "composition over inheritance" in architecture_text.lower()
    assert "no new mixins" in architecture_text.lower()
    assert "AppContext" in architecture_text
    assert "StudioActionController" in migration.read_text(encoding="utf-8")

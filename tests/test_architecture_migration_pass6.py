from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.app_context import AppContext
from laserprog_studio.application.tool_lifecycle_controller import ToolLifecycleController
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


def test_tool_lifecycle_controller_is_composed_from_app_context() -> None:
    context = _fake_context()
    controller = ToolLifecycleController.create(context)
    assert controller.context is context
    assert controller.owner is context.owner


def test_tool_lifecycle_controller_owns_tool_workflow() -> None:
    path = STUDIO / "application" / "tool_lifecycle_controller.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "ToolLifecycleController")
    expected = {
        "_sync_tool_buttons",
        "_sync_modifier_buttons",
        "confirm_preview_before_tool_change",
        "_invoke_tool_hook",
        "_close_previous_tool_resources",
        "open_tool",
        "close_active_tool",
        "apply_preview_and_close_tool",
        "discard_preview_and_close_tool",
    }
    assert expected.issubset(methods)
    assert "get_studio_tool" in source
    assert "get_tool_spec" in source
    assert "iter_studio_tools" in source
    assert "tool.on_open(self.context)" in source
    assert "tool.on_close(self.context" in source
    assert "_schedule_light_transform_overlay_sync" in source


def test_tool_lifecycle_mixin_is_facade_only() -> None:
    facade = STUDIO / "controllers" / "tool_lifecycle.py"
    source = facade.read_text(encoding="utf-8")
    methods = _class_methods(facade, "ToolLifecycleLayer")
    assert len(source.splitlines()) < 90
    assert "ToolLifecycleController" in source
    assert "return self._tool_lifecycle().confirm_preview_before_tool_change(context)" in source
    assert "QMessageBox" not in source
    assert "get_studio_tool(tool_id)" not in source
    assert "discard_preview_only" not in methods


def test_tool_lifecycle_controller_keeps_qt_import_lazy() -> None:
    source = (STUDIO / "application" / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
    assert "from .._window_deps import *" not in source
    assert "def _qmessagebox" in source
    assert "from PySide6.QtWidgets import QMessageBox" in source


def test_runtime_state_composes_tool_lifecycle_controller() -> None:
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "from .application.tool_lifecycle_controller import ToolLifecycleController" in runtime_source
    assert "self.tool_lifecycle_controller = ToolLifecycleController.create(self.app_context)" in runtime_source


def test_architecture_docs_record_pass6() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_6.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "ToolLifecycleController" in text
    assert "Compatibility facade" in text
    architecture_text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "ToolLifecycleController" in architecture_text

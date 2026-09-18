from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.app_context import AppContext
from laserprog_studio.application.layout_controller import InspectorRestoreSnapshot, LayoutController
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


def test_layout_controller_is_composed_from_app_context() -> None:
    context = _fake_context()
    controller = LayoutController.create(context)
    assert controller.context is context
    assert isinstance(controller.snapshot, InspectorRestoreSnapshot)
    controller.snapshot.restore_light_ui = True
    controller.snapshot.light_ui_sizes = [0, 900, 0]
    controller.snapshot.full_splitter_sizes = [220, 900, 260]
    controller.snapshot.user_dragged_during_tool = True
    controller.snapshot.reset()
    assert controller.snapshot.restore_light_ui is False
    assert controller.snapshot.light_ui_sizes is None
    assert controller.snapshot.full_splitter_sizes is None
    assert controller.snapshot.user_dragged_during_tool is False


def test_layout_controller_owns_inspector_workflow() -> None:
    path = STUDIO / "application" / "layout_controller.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "LayoutController")
    assert {"remember_before_tool_open", "restore_after_tool_close", "ensure_inspector_open", "note_user_splitter_drag"}.issubset(methods)
    assert "InspectorRestoreSnapshot" in source
    assert "context.layout.inspector" in source
    assert "_restore_light_ui_after_tool" not in source
    assert "_preferred_side_widths" in source
    assert "_restore_compact_transform_ui" in source
    assert "_set_main_splitter_sizes_coalesced" in source


def test_layout_restore_mixin_is_only_a_facade() -> None:
    path = STUDIO / "controllers" / "layout_restore.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "LayoutRestoreLayer")
    assert {"_layout_controller", "_remember_inspector_mode_before_tool_open", "_restore_inspector_mode_after_tool_close", "_ensure_inspector_open"}.issubset(methods)
    assert len(source.splitlines()) < 60
    assert "LayoutController" in source
    assert "QSplitter" not in source
    assert "preferred_full_sizes" not in source
    assert "main_splitter.sizes" not in source


def test_runtime_state_composes_layout_controller() -> None:
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "from .application.layout_controller import LayoutController" in runtime_source
    assert "self.layout_controller = LayoutController.create(self.app_context)" in runtime_source


def test_architecture_docs_record_pass3() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_3.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "LayoutController" in text
    assert "compatibility facade" in text
    assert "Light UI" in text
    architecture_text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "LayoutController" in architecture_text

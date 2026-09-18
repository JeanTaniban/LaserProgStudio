from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.app_context import AppContext
from laserprog_studio.application.preview_controller import PreviewController
from laserprog_studio.application.tool_preview_controller import ToolPreviewController
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


def test_preview_controllers_are_composed_from_app_context() -> None:
    context = _fake_context()
    preview = PreviewController.create(context)
    tool_preview = ToolPreviewController.create(context)
    assert preview.context is context
    assert tool_preview.context is context
    assert tool_preview.fabrication.context is context
    assert tool_preview.modifiers.context is context
    assert not hasattr(tool_preview, "acoustic")


def test_preview_controller_owns_session_lifecycle() -> None:
    path = STUDIO / "application" / "preview_controller.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "PreviewController")
    assert {"ensure_model_store", "has_preview", "update_state", "set_meshes", "set_result", "commit_to_model", "discard_only"}.issubset(methods)
    assert "OperationResult" in source
    assert "[PREVIEW][ERROR]" in source
    assert "_schedule_light_transform_overlay_sync" in source
    assert "WindowController" in source


def test_tool_preview_controllers_split_fabrication_and_modifiers() -> None:
    router = STUDIO / "application" / "tool_preview_controller.py"
    fabrication = STUDIO / "application" / "fabrication_preview_controller.py"
    modifiers = STUDIO / "application" / "modifier_preview_controller.py"
    router_source = router.read_text(encoding="utf-8")
    fabrication_source = fabrication.read_text(encoding="utf-8")
    modifier_source = modifiers.read_text(encoding="utf-8")
    assert "FabricationPreviewController" in router_source
    assert "ModifierPreviewController" in router_source
    assert "generate_box_preview" not in fabrication_source
    assert "update_box_report" not in fabrication_source
    assert "generate_joint_preview" in fabrication_source
    assert "generate_simplify_modifier_preview" not in modifier_source
    assert (STUDIO / "tooling" / "simplify_tool.py").exists()
    assert "generate_hollow_modifier_preview" not in modifier_source
    assert (STUDIO / "tooling" / "hollow_tool.py").exists()
    assert "from .._window_deps import *" not in fabrication_source
    assert "from .._window_deps import *" not in modifier_source
    assert "def _qmessagebox" in fabrication_source
    assert "def _qtimer" in modifier_source
    assert len(fabrication_source.splitlines()) < 260
    assert len(modifier_source.splitlines()) < 700


def test_preview_mixins_are_facades_only() -> None:
    preview_mixin = STUDIO / "controllers" / "preview_controller.py"
    tool_previews = STUDIO / "controllers" / "tool_previews.py"
    preview_source = preview_mixin.read_text(encoding="utf-8")
    tool_source = tool_previews.read_text(encoding="utf-8")
    assert len(preview_source.splitlines()) < 55
    assert len(tool_source.splitlines()) < 220
    assert "PreviewController.create" in preview_source
    assert "ToolPreviewController.create" in tool_source
    assert "QMessageBox.warning" not in tool_source
    assert "QTimer.singleShot" not in tool_source


def test_runtime_state_composes_preview_controllers() -> None:
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "from .application.preview_controller import PreviewController" in runtime_source
    assert "from .application.tool_preview_controller import ToolPreviewController" in runtime_source
    assert "self.preview_controller = PreviewController.create(self.app_context)" in runtime_source
    assert "self.tool_preview_controller = ToolPreviewController.create(self.app_context)" in runtime_source


def test_architecture_docs_record_pass5() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_5.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "PreviewController" in text
    assert "ToolPreviewController" in text
    assert "compatibility adapter" in text
    architecture_text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "PreviewController" in architecture_text
    assert "ToolPreviewController" in architecture_text

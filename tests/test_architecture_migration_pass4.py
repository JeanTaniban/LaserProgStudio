from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.app_context import AppContext
from laserprog_studio.application.export_controller import ExportController
from laserprog_studio.application.render_output_controller import RenderOutputController
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


def test_export_and_render_output_controllers_are_composed_from_app_context() -> None:
    context = _fake_context()
    export = ExportController.create(context)
    render_output = RenderOutputController.create(context)
    assert export.context is context
    assert render_output.context is context


def test_export_controller_owns_export_and_engraving_workflows() -> None:
    path = STUDIO / "application" / "export_controller.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "ExportController")
    assert {
        "export_3mf_dialog",
        "open_engrave_workspace",
        "render_engrave_current",
        "save_engrave_all",
        "save_engrave_falcon_svg",
        "save_engrave_dimensions_json",
        "open_3mf_dialog",
    }.issubset(methods)
    assert "WindowController" in source
    assert "class _ExportOperations" in source
    assert "_LazyQtSymbol" in source
    assert "PySide6" in source
    assert len(source.splitlines()) < 650


def test_render_output_controller_owns_render_camera_workflow() -> None:
    path = STUDIO / "application" / "render_output_controller.py"
    source = path.read_text(encoding="utf-8")
    methods = _class_methods(path, "RenderOutputController")
    assert {
        "_editor_camera_pose_snapshot",
        "_render_camera_indices",
        "_make_render_camera_mesh_from_pose",
        "_render_camera_pose_from_scene",
        "capture_render_camera_from_editor",
        "open_render_preview_window",
    }.issubset(methods)
    assert "WindowController" in source
    assert "class _RenderOutputOperations" in source
    assert "RenderPreviewDialog requires the Qt runtime" in source
    assert len(source.splitlines()) < 500


def test_export_and_render_mixins_are_only_facades() -> None:
    exporting = STUDIO / "controllers" / "exporting.py"
    render = STUDIO / "controllers" / "render_output.py"
    exporting_source = exporting.read_text(encoding="utf-8")
    render_source = render.read_text(encoding="utf-8")
    assert len(exporting_source.splitlines()) < 90
    assert len(render_source.splitlines()) < 75
    assert "ExportController" in exporting_source
    assert "RenderOutputController" in render_source
    assert "QFileDialog" not in exporting_source
    assert "RenderPreviewDialog" not in render_source
    assert "write_3mf_container" not in exporting_source
    assert "WorkMesh" not in render_source


def test_runtime_state_composes_export_controllers() -> None:
    runtime_source = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    assert "from .application.export_controller import ExportController" in runtime_source
    assert "from .application.render_output_controller import RenderOutputController" in runtime_source
    assert "self.export_controller = ExportController.create(self.app_context)" in runtime_source
    assert "self.render_output_controller = RenderOutputController.create(self.app_context)" in runtime_source


def test_architecture_docs_record_pass4() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_4.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "ExportController" in text
    assert "RenderOutputController" in text
    assert "compatibility facade" in text
    architecture_text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "ExportController" in architecture_text
    assert "RenderOutputController" in architecture_text

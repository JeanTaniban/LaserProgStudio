# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import unittest
from pathlib import Path

import _path_setup  # noqa: F401
from laserprog_studio.app_context import AppContext
from laserprog_studio.geometry_ops import OperationResult
from laserprog_studio.parameters import ParameterPanelFactory, ParameterSpec
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState
from laserprog_studio.tooling.base import ToolSpec

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"
CONTROLLERS = STUDIO / "controllers"


def class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"missing class {class_name} in {path}")


class Pass14ExtensionContractsTest(unittest.TestCase):
    def test_app_context_forwards_dynamic_mesh_store_and_state_objects(self) -> None:
        class DummyWindow:
            def __init__(self) -> None:
                self.mesh_store = "first"
                self.selection_state = SelectionState()
                self.transform_state = TransformState()
                self.tool_state = ToolState()
                self.preview_state = PreviewState()
                self.ui_layout_state = UiLayoutState()
                self.render_state = RenderState()
                self.clipboard_state = ClipboardState()
                self.scene_renderer = "renderer"
                self.messages: list[str] = []

            def ui_log(self, message: str) -> None:
                self.messages.append(message)

        window = DummyWindow()
        context = AppContext.from_window(window)
        self.assertIs(context.selection, window.selection_state)
        self.assertEqual(context.mesh_store, "first")
        self.assertEqual(context.renderer, "renderer")
        window.mesh_store = "second"
        self.assertEqual(context.mesh_store, "second")
        context.ui_log("hello")
        self.assertEqual(window.messages, ["hello"])

    def test_tool_spec_can_own_parameter_contracts(self) -> None:
        params = (
            ParameterSpec("segments", "Segments", "int", 64, min_value=3, max_value=256),
            ParameterSpec("mode", "Mode", "choice", "solid", choices=(("solid", "Solid"), ("wire", "Wire"))),
        )
        spec = ToolSpec("demo", "Demo", "tool", panel_index=0, parameters=params)
        self.assertEqual(spec.default_parameters(), {"segments": 64, "mode": "solid"})
        self.assertEqual(spec.validate_parameters({"segments": 1, "mode": "bad"}), {"segments": 3, "mode": "solid"})

    def test_parameter_panel_factory_is_lazy_qt_import(self) -> None:
        # Importing the factory must work in headless CI without PySide6. PySide
        # is imported only when create_panel() is called by the desktop app.
        self.assertTrue(hasattr(ParameterPanelFactory, "create_panel"))

    def test_preview_controller_owns_preview_lifecycle_helpers(self) -> None:
        preview_methods = class_methods(CONTROLLERS / "preview_controller.py", "PreviewControllerLayer")
        for method in ("has_preview", "set_preview_meshes", "commit_preview_to_model", "discard_preview_only"):
            self.assertIn(method, preview_methods)
        scene_methods = class_methods(CONTROLLERS / "scene.py", "SceneStateLayer")
        self.assertNotIn("has_preview", scene_methods)
        self.assertNotIn("set_preview_meshes", scene_methods)
        lifecycle_methods = class_methods(CONTROLLERS / "tool_lifecycle.py", "ToolLifecycleLayer")
        lifecycle_controller_methods = class_methods(ROOT / "src" / "laserprog_studio" / "application" / "tool_lifecycle_controller.py", "ToolLifecycleController")
        self.assertNotIn("discard_preview_only", lifecycle_methods)
        self.assertIn("apply_preview_and_close_tool", lifecycle_methods)
        self.assertIn("apply_preview_and_close_tool", lifecycle_controller_methods)

    def test_studio_controllers_composes_preview_before_scene(self) -> None:
        source = (CONTROLLERS / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("PreviewControllerLayer", source)
        self.assertLess(source.index("PreviewControllerLayer"), source.index("SceneStateLayer"))

    def test_operation_result_is_standard_geometry_contract(self) -> None:
        ok = OperationResult.success(["mesh"], warnings=["minor"])
        self.assertTrue(ok.ok)
        self.assertEqual(ok.meshes, ["mesh"])
        self.assertEqual(ok.warnings, ("minor",))
        fail = OperationResult.failure("bad mesh")
        self.assertFalse(fail.ok)
        self.assertEqual(fail.errors, ("bad mesh",))

    def test_preview_controller_accepts_operation_result_contract(self) -> None:
        methods = class_methods(CONTROLLERS / "preview_controller.py", "PreviewControllerLayer")
        self.assertIn("set_preview_result", methods)
        source = (CONTROLLERS / "preview_controller.py").read_text(encoding="utf-8")
        self.assertIn("OperationResult", source)
        self.assertIn("[PREVIEW][ERROR]", source)


if __name__ == "__main__":
    unittest.main()

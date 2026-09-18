# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import importlib.util
import unittest
from pathlib import Path

import _path_setup  # noqa: F401
from laserprog_studio.rendering.scene_renderer import SceneRenderer
from laserprog_studio.state import ClipboardState, RenderState, SelectionState, ToolState, TransformState

ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS = ROOT / "src" / "laserprog_studio" / "controllers"
_state_bridge_spec = importlib.util.spec_from_file_location("state_bridge_for_test", CONTROLLERS / "state_bridge.py")
_state_bridge_module = importlib.util.module_from_spec(_state_bridge_spec)
assert _state_bridge_spec is not None and _state_bridge_spec.loader is not None
_state_bridge_spec.loader.exec_module(_state_bridge_module)
StateBridge = _state_bridge_module.StateBridge


def class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"missing class {class_name} in {path}")


class Pass15StateAndLifecycleSplitTest(unittest.TestCase):
    def test_state_bridge_keeps_window_names_synced_with_state_objects(self) -> None:
        class Dummy(StateBridge):
            def __init__(self) -> None:
                self.selection_state = SelectionState()
                self.transform_state = TransformState()
                self.tool_state = ToolState()
                self.render_state = RenderState()
                self.clipboard_state = ClipboardState()

        obj = Dummy()
        obj.selected_indices = ["1", 2]
        obj.active_index = "2"
        obj.active_tool = "primitive"
        obj.transform_mode = "translate"
        obj.actors_by_index = {1: "actor"}
        obj.polydata_by_index = {1: "poly"}
        obj.floor_grid_actor = "grid"
        obj._copy_buffer_meshes = ["mesh"]

        self.assertEqual(obj.selection_state.selected_indices, [1, 2])
        self.assertEqual(obj.selection_state.active_index, 2)
        self.assertEqual(obj.tool_state.active_tool, "primitive")
        self.assertEqual(obj.transform_state.mode, "translate")
        self.assertEqual(obj.render_state.actors_by_index, {1: "actor"})
        self.assertEqual(obj.render_state.polydata_by_index, {1: "poly"})
        self.assertEqual(obj.render_state.floor_grid_actor, "grid")
        self.assertEqual(obj.clipboard_state.meshes, ["mesh"])

    def test_scene_renderer_facade_syncs_display_mode_without_qt(self) -> None:
        class DummyOwner:
            def __init__(self) -> None:
                self.render_state = RenderState()
                self.show_edges = True
                self.render_calls = 0

                class DummyPlotter:
                    def __init__(inner_self, outer) -> None:
                        inner_self.outer = outer

                    def render(inner_self) -> None:
                        inner_self.outer.render_calls += 1

                self.plotter = DummyPlotter(self)

        owner = DummyOwner()
        renderer = SceneRenderer(owner)
        self.assertEqual(renderer.set_display_mode("solid"), "solid")
        self.assertEqual(owner.render_state.display_mode, "solid")
        self.assertFalse(owner.show_edges)
        renderer.render()
        self.assertEqual(owner.render_calls, 1)

    def test_tool_lifecycle_is_split_from_layout_and_selection_policy(self) -> None:
        lifecycle = class_methods(CONTROLLERS / "tool_lifecycle.py", "ToolLifecycleLayer")
        policy = class_methods(CONTROLLERS / "tool_selection_policy.py", "ToolSelectionPolicyLayer")
        layout = class_methods(CONTROLLERS / "layout_restore.py", "LayoutRestoreLayer")
        self.assertNotIn("_apply_tool_selection_policy", lifecycle)
        self.assertIn("_apply_tool_selection_policy", policy)
        self.assertIn("_tool_meets_selection_policy", policy)
        self.assertNotIn("_ensure_inspector_open", lifecycle)
        self.assertIn("_ensure_inspector_open", layout)
        self.assertIn("_restore_inspector_mode_after_tool_close", layout)

    def test_studio_controllers_composes_state_policy_layout_before_tool_lifecycle(self) -> None:
        source = (CONTROLLERS / "__init__.py").read_text(encoding="utf-8")
        for name in ("StateBridge", "ToolSelectionPolicyLayer", "LayoutRestoreLayer", "ToolLifecycleLayer"):
            self.assertIn(name, source)
        self.assertLess(source.index("StateBridge"), source.index("InteractionLayer"))
        self.assertLess(source.index("ToolSelectionPolicyLayer"), source.index("ToolLifecycleLayer"))
        self.assertLess(source.index("LayoutRestoreLayer"), source.index("ToolLifecycleLayer"))


if __name__ == "__main__":
    unittest.main()

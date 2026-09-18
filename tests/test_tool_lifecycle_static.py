# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS = ROOT / "src" / "laserprog_studio" / "controllers"
APPLICATION = ROOT / "src" / "laserprog_studio" / "application"


def class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"missing class {class_name} in {path}")


class ToolLifecycleStaticTest(unittest.TestCase):
    def test_scene_no_longer_owns_tool_lifecycle(self) -> None:
        scene_methods = class_methods(CONTROLLERS / "scene.py", "SceneStateLayer")
        for method in ("open_tool", "close_active_tool", "apply_preview_and_close_tool", "update_preview_state"):
            self.assertNotIn(method, scene_methods)
        lifecycle_methods = class_methods(CONTROLLERS / "tool_lifecycle.py", "ToolLifecycleLayer")
        for method in ("open_tool", "close_active_tool", "apply_preview_and_close_tool"):
            self.assertIn(method, lifecycle_methods)
        preview_methods = class_methods(CONTROLLERS / "preview_controller.py", "PreviewControllerLayer")
        self.assertIn("update_preview_state", preview_methods)
        self.assertNotIn("update_preview_state", lifecycle_methods)
        policy_methods = class_methods(CONTROLLERS / "tool_selection_policy.py", "ToolSelectionPolicyLayer")
        self.assertIn("_apply_tool_selection_policy", policy_methods)
        layout_methods = class_methods(CONTROLLERS / "layout_restore.py", "LayoutRestoreLayer")
        self.assertIn("_ensure_inspector_open", layout_methods)

    def test_tool_lifecycle_uses_registry_not_hardcoded_display_mapping(self) -> None:
        text = (APPLICATION / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
        self.assertIn("get_tool_spec", text)
        self.assertIn("iter_studio_tools", text)
        self.assertIn("tool_label", text)
        self.assertIn("_tool_meets_selection_policy", text)
        self.assertNotIn('self.TOOL_PRIMITIVE: "Primitives"', text)


if __name__ == "__main__":
    unittest.main()

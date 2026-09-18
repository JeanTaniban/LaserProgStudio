# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTROLLERS = ROOT / "src" / "laserprog_studio" / "controllers"


def class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"missing class {class_name} in {path}")


class ActionControllerSplitStaticTest(unittest.TestCase):
    def test_boolean_clipboard_history_wrapper_stays_thin(self) -> None:
        legacy = CONTROLLERS / "booleans_clipboard_history.py"
        text = legacy.read_text(encoding="utf-8")
        self.assertLessEqual(len(text.splitlines()), 45)
        for forbidden in (
            "def boolean_subtract_touching",
            "def copy_selected",
            "def duplicate_selected",
            "def undo_scene",
            "def delete_selected",
        ):
            self.assertNotIn(forbidden, text)

    def test_focused_action_mixins_own_their_responsibilities(self) -> None:
        self.assertTrue(
            {"boolean_subtract_touching", "boolean_union_selected", "boolean_separate_selected"}
            <= class_methods(CONTROLLERS / "boolean_actions.py", "BooleanActionsLayer")
        )
        self.assertTrue(
            {"copy_selected", "paste_selection", "duplicate_selected", "_camera_duplicate_delta"}
            <= class_methods(CONTROLLERS / "clipboard_actions.py", "ClipboardActionsLayer")
        )
        self.assertTrue(
            {"delete_selected", "new_scene"}
            <= class_methods(CONTROLLERS / "scene_edit_actions.py", "SceneEditActionsLayer")
        )
        self.assertTrue(
            {"undo_scene", "redo_scene", "_capture_drag_undo_snapshot", "_commit_drag_undo_snapshot"}
            <= class_methods(CONTROLLERS / "history_actions.py", "HistoryActionsLayer")
        )

    def test_studio_controllers_uses_focused_mixins_directly(self) -> None:
        text = (CONTROLLERS / "__init__.py").read_text(encoding="utf-8")
        for mixin in ("BooleanActionsLayer", "ClipboardActionsLayer", "SceneEditActionsLayer", "HistoryActionsLayer"):
            self.assertIn(mixin, text)
        self.assertNotIn("BooleanClipboardHistoryLayer,", text)


if __name__ == "__main__":
    unittest.main()

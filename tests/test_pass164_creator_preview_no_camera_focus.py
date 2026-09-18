# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PREVIEW_METHOD_NAMES = {"_stage_preview", "_preview_action"}
MIGRATED_TOOL_FILES = (
    "primitive_tool.py",
    "box_tool.py",
    "acoustic_diffuser_tool.py",
    "cavity_volume_tool.py",
    "engraving_roles_tool.py",
    "repair_tool.py",
    "simplify_tool.py",
    "hollow_tool.py",
    "layflat_tool.py",
    "joint_tool.py",
    "material_tool.py",
    "texture_projection_creator_tool.py",
    "relief_tool.py",
    "extrude_down_tool.py",
    "split_tool.py",
)


def _attribute_chain(node: ast.AST) -> str:
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))


def test_creator_preview_methods_do_not_move_camera() -> None:
    """Preview must stage meshes without recentering/zooming the user camera."""

    tooling_dir = ROOT / "src" / "laserprog_studio" / "tooling"
    violations: list[str] = []
    for file_name in MIGRATED_TOOL_FILES:
        path = tooling_dir / file_name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or node.name not in PREVIEW_METHOD_NAMES:
                continue
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                chain = _attribute_chain(call.func)
                if chain.startswith("ctx.view.focus_"):
                    violations.append(f"{path.relative_to(ROOT)}:{node.name} calls {chain}")
    assert not violations, "Creator preview actions must not move the camera:\n" + "\n".join(violations)


def test_migrated_tool_sources_have_no_direct_camera_focus_calls() -> None:
    tooling_dir = ROOT / "src" / "laserprog_studio" / "tooling"
    for file_name in MIGRATED_TOOL_FILES:
        source = (tooling_dir / file_name).read_text(encoding="utf-8")
        assert "ctx.view.focus_" not in source

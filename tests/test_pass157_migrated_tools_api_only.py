from __future__ import annotations

import ast
from pathlib import Path

from _path_setup import ROOT  # noqa: F401
from laserprog_studio.tooling.ids import TOOL_ACOUSTIC_DIFFUSER, TOOL_BOX, TOOL_PRIMITIVE
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec

SRC = ROOT / "src" / "laserprog_studio"


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"Missing class {class_name} in {path}")


def test_pass157_migrated_tools_use_only_declarative_creator_panels() -> None:
    for tool_id in (TOOL_PRIMITIVE, TOOL_BOX, TOOL_ACOUSTIC_DIFFUSER):
        spec = get_tool_panel_spec(tool_id)
        assert spec is not None
        assert spec.builder == "panel_declarative_creator_tool"

    factory_methods = _class_methods(SRC / "ui" / "tool_panel_factory.py", "ToolPanelFactory")
    assert "panel_declarative_creator_tool" in factory_methods
    assert not {"panel_primitive_tool", "panel_box_tool", "panel_acoustic_diffuser_tool"} & factory_methods

    facade_methods = _class_methods(SRC / "ui" / "tool_panels.py", "UIToolPanelsLayer")
    assert not {"_panel_primitive_tool", "_panel_box_tool", "_panel_acoustic_diffuser_tool"} & facade_methods


def test_pass157_migrated_preview_bridges_are_removed() -> None:
    tool_preview_methods = _class_methods(SRC / "controllers" / "tool_previews.py", "ToolPreviewLayer")
    assert not {
        "generate_box_preview",
        "update_box_report",
        "_current_acoustic_diffuser_settings",
        "update_acoustic_diffuser_report",
        "generate_acoustic_diffuser_preview",
    } & tool_preview_methods

    router_source = (SRC / "application" / "tool_preview_controller.py").read_text(encoding="utf-8")
    assert "AcousticDiffuserController" not in router_source
    assert "generate_box_preview" not in router_source
    assert "generate_acoustic_diffuser_preview" not in router_source
    assert not (SRC / "application" / "acoustic_diffuser_controller.py").exists()


def test_pass157_primitive_window_bridges_are_removed() -> None:
    export_methods = _class_methods(SRC / "application" / "export_controller.py", "ExportController")
    exporting_methods = _class_methods(SRC / "controllers" / "exporting.py", "ExportingLayer")
    assert not {"_make_primitive_mesh", "add_primitive_to_scene"} & export_methods
    assert not {"_make_primitive_mesh", "add_primitive_to_scene"} & exporting_methods


def test_pass157_creator_tool_sources_stay_owner_isolated() -> None:
    for rel in (
        "tooling/primitive_tool.py",
        "tooling/box_tool.py",
        "tooling/acoustic_diffuser_tool.py",
    ):
        source = (SRC / rel).read_text(encoding="utf-8")
        assert "ctx.owner" not in source
        assert "getattr(ctx, \"owner\"" not in source
        assert "owner." not in source

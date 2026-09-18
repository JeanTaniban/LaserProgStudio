from __future__ import annotations

import ast
from pathlib import Path

from _path_setup import ROOT  # noqa: F401
from laserprog_studio.tooling.ids import TOOL_MOD_REPAIR, TOOL_TEXTURE_PROJECTION
from laserprog_studio.tooling.registry import iter_tool_specs
from laserprog_studio.ui.tool_panel_catalog import TOOL_PANEL_SPECS, get_tool_panel_spec, iter_tool_panel_specs

STUDIO = ROOT / "src" / "laserprog_studio"


def _class_methods(path: Path, class_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
    raise AssertionError(f"Missing class {class_name} in {path}")


def test_tool_panel_catalog_matches_builtin_panel_indices() -> None:
    panel_by_key = {spec.key: spec.panel_index for spec in iter_tool_panel_specs()}
    assert panel_by_key["none"] == 0
    for tool in iter_tool_specs():
        assert panel_by_key[tool.id] == tool.panel_index
    assert get_tool_panel_spec(TOOL_TEXTURE_PROJECTION) is not None
    assert get_tool_panel_spec(TOOL_MOD_REPAIR) is not None
    assert tuple(iter_tool_panel_specs()) == TOOL_PANEL_SPECS


def test_tool_panel_factory_owns_panel_builders() -> None:
    factory = STUDIO / "ui" / "tool_panel_factory.py"
    source = factory.read_text(encoding="utf-8")
    methods = _class_methods(factory, "ToolPanelFactory")
    expected = {
        "build_stack",
        "build_panel",
        "panel_no_tool",
        "panel_declarative_creator_tool",
        "panel_joint_tool",
        "panel_texture_projection_tool",
        "panel_split_modifier",
    }
    assert expected.issubset(methods)
    assert "for spec in iter_tool_panel_specs()" in source
    assert "owner.tool_panel_widgets_by_key" in source
    assert "A/B: — · Preview: no" in source
    assert "owner.joint_clearance = owner._spin(-100, 100, 0.15, 0.05)" in source
    assert "def panel_material_tool" not in source
    assert "def panel_primitive_tool" not in source
    assert "def panel_box_tool" not in source
    assert "def panel_acoustic_diffuser_tool" not in source
    assert "def panel_repair_modifier" not in source


def test_tool_panels_mixin_is_factory_shell() -> None:
    facade = STUDIO / "ui" / "tool_panels.py"
    source = facade.read_text(encoding="utf-8")
    methods = _class_methods(facade, "UIToolPanelsLayer")
    assert len(source.splitlines()) < 380
    assert "ToolPanelFactory" in source
    assert "self.tool_panel_stack = self._tool_panel_factory().build_stack()" in source
    assert "def _panel_texture_projection_tool" in source
    assert "Texture repeat" not in source
    assert "Legacy algorithm: lay-flat orientation" not in source
    assert {
        "_make_right_panel",
        "_tool_panel_factory",
        "_panel_joint_tool",
        "_spin",
    }.issubset(methods)


def test_architecture_docs_record_pass8() -> None:
    doc = ROOT / "docs" / "archive" / "architecture_migrations" / "architecture_migration_pass_8.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    assert "ToolPanelFactory" in text
    assert "ToolPanelSpec" in text
    architecture_text = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    assert "ToolPanelFactory" in architecture_text

from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401

from laserprog_studio.domain.work_model import WorkMesh, build_3mf_model_xml
from laserprog_studio.domain import MeshMaterial
from laserprog_studio.rendering.materials import actor_style_for_mesh
from laserprog_studio.services.ui_preferences import load_ui_layout_preferences, save_ui_layout_preferences
from laserprog_studio.state import UiLayoutState
from laserprog_studio.tooling.ids import TOOL_MATERIAL, TOOL_MOD_EXTRUDE_DOWN, TOOL_MOD_HOLLOW, TOOL_MOD_RELIEF, TOOL_MOD_SIMPLIFY
from laserprog_studio.tooling.registry import get_tool_spec, iter_tool_specs

ROOT = Path(__file__).resolve().parents[1]


def test_material_tool_is_registered_and_has_ui_panel() -> None:
    spec = get_tool_spec(TOOL_MATERIAL)
    assert spec is not None
    assert spec.label == "Materials"
    assert spec.panel_index == 6
    assert spec.button_attr == "btn_tool_material"
    layout = (ROOT / "src" / "laserprog_studio" / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    panels = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    factory = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec

    panel = get_tool_panel_spec(TOOL_MATERIAL)
    assert "self.btn_tool_material" in layout
    assert panel is not None
    assert panel.builder == "panel_declarative_creator_tool"
    assert "def _panel_material_tool" not in panels
    assert "def panel_material_tool" not in factory


def test_all_new_modifiers_are_in_registry_driven_tools_menu() -> None:
    modifier_ids = {spec.id for spec in iter_tool_specs(category="modifier")}
    assert {TOOL_MOD_SIMPLIFY, TOOL_MOD_RELIEF, TOOL_MOD_EXTRUDE_DOWN, TOOL_MOD_HOLLOW}.issubset(modifier_ids)
    menus = (ROOT / "src" / "laserprog_studio" / "ui" / "actions_menus.py").read_text(encoding="utf-8")
    assert "iter_tool_specs(category=\"modifier\")" in menus
    assert "Modifier: {spec.label}" in menus


def test_material_mode_uses_neutral_default_not_engraving_color() -> None:
    mesh = WorkMesh("cut-role", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], color="#E53935")
    material = actor_style_for_mesh(mesh, "material")
    assert material.color == (0xB8 / 255.0, 0xB8 / 255.0, 0xB8 / 255.0)
    mesh.material = MeshMaterial(base_color="#336699")
    material = actor_style_for_mesh(mesh, "material")
    assert material.color == (0x33 / 255.0, 0x66 / 255.0, 0x99 / 255.0)


def test_ui_layout_preferences_roundtrip(tmp_path: Path) -> None:
    state = UiLayoutState()
    state.update_from_splitter_sizes([320, 900, 360], threshold=12)
    path = tmp_path / "layout.json"
    save_ui_layout_preferences(state, path)
    payload = load_ui_layout_preferences(path)
    restored = UiLayoutState()
    restored.apply_preferences(payload)
    assert restored.last_left_width == 320
    assert restored.last_right_width == 360
    assert restored.preferred_full_sizes()[0] == 320


def test_3mf_export_uses_visual_material_color_when_available() -> None:
    mesh = WorkMesh("part", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)], color="#E53935")
    mesh.material = MeshMaterial(base_color="#336699")
    xml = build_3mf_model_xml([mesh], application_name="test")
    assert 'displaycolor="#336699"' in xml

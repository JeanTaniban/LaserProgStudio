from __future__ import annotations

from pathlib import Path

from _light_transform_source import read_light_transform_source

import _path_setup  # noqa: F401
from laserprog_studio.tooling.ids import TOOL_JOINT
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec

ROOT = Path(__file__).resolve().parents[1]


def test_joint_opens_without_existing_selection_in_real_context() -> None:
    tool = get_studio_tool(TOOL_JOINT)
    spec = get_tool_spec(TOOL_JOINT)
    assert tool is not None
    assert spec is not None
    assert spec.selection_policy == "multi"
    assert spec.allow_multi_selection is True
    assert spec.open_without_initial_selection is True
    # Existing static contract checks None as a pure registry validation context.
    # Real tool opening passes the AppContext and must allow zero initial picks.
    assert tool.can_open(object(), selected_count=0)


def test_joint_panel_status_is_compact() -> None:
    text = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panel_factory.py").read_text(encoding="utf-8")
    assert "A/B: — · Preview: no" in text
    assert "setMaximumHeight(20)" in text
    assert "Select two parts: A then B" not in text
    assert "Selection A/B:" not in (ROOT / "src" / "laserprog_studio" / "controllers" / "tool_previews.py").read_text(encoding="utf-8")


def test_material_render_controls_are_in_left_view_panel() -> None:
    layout = (ROOT / "src" / "laserprog_studio" / "ui" / "layout_panels.py").read_text(encoding="utf-8")
    material_tool = (ROOT / "src" / "laserprog_studio" / "controllers" / "material_tool.py").read_text(encoding="utf-8")
    assert "self.material_render_box = QGroupBox(\"Material render\")" in layout
    assert "self.material_render_light_intensity" in layout
    assert "self.material_render_shadows" in layout
    assert "self.material_render_floor" not in layout
    assert "Render floor" not in layout
    assert "def _sync_material_scene_rendering" in material_tool
    assert "SetInterpolationToPBR" in material_tool
    assert "vtk_shadow_maps" in material_tool
    assert "enable_vtk_shadows" in material_tool


def test_material_selection_keeps_material_color() -> None:
    scene = (ROOT / "src" / "laserprog_studio" / "controllers" / "scene.py").read_text(encoding="utf-8")
    assert 'elif str(mode) == "material": pass' in scene
    assert "keep material color" in scene


def test_inspector_open_uses_remembered_width_not_tiny_column() -> None:
    layout_controller = (ROOT / "src" / "laserprog_studio" / "application" / "layout_controller.py").read_text(encoding="utf-8")
    layout_restore = (ROOT / "src" / "laserprog_studio" / "controllers" / "layout_restore.py").read_text(encoding="utf-8")
    light = read_light_transform_source(ROOT)
    panels = (ROOT / "src" / "laserprog_studio" / "ui" / "tool_panels.py").read_text(encoding="utf-8")
    assert "LayoutController" in layout_restore
    assert "plan_open_inspector" in layout_controller
    assert "kept user splitter" in layout_controller
    assert "open inspector" in layout_controller
    assert "right.setMinimumWidth(0 if right_collapsible else right_min)" in light
    assert "outer.setMinimumWidth(200)" in panels

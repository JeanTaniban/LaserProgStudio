# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.planar_tools import (
    PlanarPolygonDraft,
    VentPathDraft,
    make_extruded_polygon_mesh,
    make_locked_plane,
    make_vent_path_mesh,
)
from laserprog_studio.tooling.ids import TOOL_PLAN_TRACE, TOOL_VENT_GENERATOR
from laserprog_studio.tooling.registry import get_tool_spec
from laserprog_studio.ui.toolbar_catalog import get_toolbar_item_spec

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


def test_pass20_planar_tools_are_registered_and_toolbar_visible() -> None:
    plan = get_tool_spec(TOOL_PLAN_TRACE)
    vent = get_tool_spec(TOOL_VENT_GENERATOR)
    assert plan is not None
    assert vent is not None
    assert plan.open_hook is None
    assert vent.open_hook is None
    assert plan.panel_index == 30
    assert vent.panel_index == 31
    assert get_toolbar_item_spec("tool:plan_trace") is not None
    assert get_toolbar_item_spec("tool:vent_generator") is not None
    assert get_toolbar_item_spec("tool:plan_trace").default_visible is True  # type: ignore[union-attr]
    assert get_toolbar_item_spec("tool:vent_generator").default_visible is False  # type: ignore[union-attr]


def test_pass20_plan_trace_mesh_generation_contract() -> None:
    draft = PlanarPolygonDraft(make_locked_plane("top"), extrusion_depth=5.0)
    for point in ((0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)):
        draft.add_point_plane(point)
    assert draft.close_polygon() is True
    mesh = make_extruded_polygon_mesh(draft)
    assert len(mesh.vertices) == 8
    assert len(mesh.triangles) == 12
    assert max(z for _x, _y, z in mesh.vertices) == 5.0


def test_pass20_vent_mesh_generation_contract() -> None:
    draft = VentPathDraft(make_locked_plane("front"))
    for point in ((0.0, 0.0), (30.0, 0.0), (60.0, 20.0)):
        draft.add_waypoint_plane(point)
    mesh = make_vent_path_mesh(draft)
    assert len(mesh.vertices) > 80
    assert len(mesh.triangles) > 80
    assert draft.estimated_centerline_length() > 50.0


def test_pass20_interaction_and_apply_are_wired_to_planar_controller() -> None:
    interaction = (STUDIO / "controllers" / "interaction.py").read_text(encoding="utf-8")
    lifecycle = (STUDIO / "application" / "tool_lifecycle_controller.py").read_text(encoding="utf-8")
    transform = (STUDIO / "controllers" / "transform_inspector.py").read_text(encoding="utf-8")
    controller = (STUDIO / "application" / "planar_tool_controller.py").read_text(encoding="utf-8")
    app_context = (STUDIO / "app_context.py").read_text(encoding="utf-8")
    assert "handle_pointer_press" in interaction
    assert "handle_pointer_move" in interaction
    assert "handle_pointer_release" in interaction
    assert "handle_pointer_double_click" in interaction
    assert "ensure_preview_before_apply" in lifecycle
    assert "update_selected_from_transform_fields" in transform
    assert "make_extruded_polygon_mesh" in controller
    assert "make_vent_path_mesh" in controller
    assert "planar_tool_controller" in app_context
    assert "handle_lifecycle_hook" in app_context

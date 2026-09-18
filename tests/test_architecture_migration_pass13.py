# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from laserprog_studio.planar_tools import (
    FixedPlanarView,
    PlanarEditMode,
    PlanarPolygonDraft,
    VentPathDraft,
    VentSectionKind,
    VentSectionSpec,
    make_locked_plane,
    nearest_locked_view_from_forward,
    plane_from_first_hit,
    plane_to_world,
    world_to_plane,
)
from laserprog_studio.tooling import PLANAR_TOOL_BLUEPRINTS, TOOL_PLAN_TRACE, TOOL_VENT_GENERATOR
from laserprog_studio.tooling.registry import get_tool_spec

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "src" / "laserprog_studio"


def test_pass13_texture_services_no_longer_import_private_helpers_from_facade() -> None:
    for rel in (
        "application/texture_gizmo_target_service.py",
        "application/texture_gizmo_live_update_service.py",
    ):
        source = (STUDIO / rel).read_text(encoding="utf-8")
        assert "from laserprog_studio.geometry_ops.texture_projection import _" not in source
    assert "texture_projection_vector import _dot, _sub, _uv_from_plane_coords" in (STUDIO / "application/texture_gizmo_live_update_service.py").read_text(encoding="utf-8")
    assert "texture_projection_decal import _is_texture_decal" in (STUDIO / "application/texture_gizmo_target_service.py").read_text(encoding="utf-8")


def test_pass13_locked_plane_orientation_and_depth_contract() -> None:
    assert nearest_locked_view_from_forward((0.0, 0.0, -5.0)) is FixedPlanarView.TOP
    assert nearest_locked_view_from_forward((0.0, 0.0, 5.0)) is FixedPlanarView.BOTTOM
    assert nearest_locked_view_from_forward((0.0, 2.0, 0.0)) is FixedPlanarView.FRONT

    plane = plane_from_first_hit(FixedPlanarView.TOP, (12.0, 3.0, 7.5))
    assert plane.depth == 7.5
    assert world_to_plane(plane, (2.0, 4.0, 999.0)) == (2.0, 4.0)
    assert plane_to_world(plane, 2.0, 4.0) == (2.0, 4.0, 7.5)


def test_pass13_plan_tracer_model_clears_selection_on_mode_change_and_reset() -> None:
    draft = PlanarPolygonDraft(make_locked_plane(FixedPlanarView.TOP, depth=0.0), extrusion_depth=4.0)
    draft.add_point_plane((0.0, 0.0))
    draft.add_point_plane((10.0, 0.0))
    draft.add_point_plane((10.0, 10.0))
    assert draft.selected_index == 2
    draft.set_mode(PlanarEditMode.MOD)
    assert draft.selected_index is None
    assert draft.select_nearest_plane((9.5, 10.1)) == 2
    draft.update_selected_plane((8.0, 9.0))
    draft.set_mode(PlanarEditMode.ADD)
    assert draft.selected_index is None
    assert draft.close_polygon()
    assert draft.is_ready_for_extrusion()
    assert draft.polygon_area() > 0.0
    draft.set_mode(PlanarEditMode.RST)
    assert draft.mode is PlanarEditMode.ADD
    assert draft.points == []
    assert draft.selected_index is None


def test_pass13_vent_path_contract_estimates_curve_and_section_dimensions() -> None:
    vent = VentPathDraft(
        make_locked_plane("front", depth=-2.0),
        section=VentSectionSpec(kind=VentSectionKind.RECTANGLE, area=144.0),
        wall_thickness=3.0,
    )
    vent.add_waypoint_plane((0.0, 0.0))
    vent.add_waypoint_plane((20.0, 0.0))
    vent.add_waypoint_plane((20.0, 10.0))
    assert vent.is_ready_for_mesh()
    assert vent.section_dimensions() == (12.0, 12.0)
    assert vent.estimated_centerline_length(samples_per_segment=8) > 25.0
    vent.set_mode("MOD")
    assert vent.selected_index is None
    assert vent.select_nearest_plane((20.0, 9.5)) == 2
    vent.set_mode("SUPP")
    assert vent.selected_index is None


def test_pass13_planar_tool_blueprints_match_registered_tools() -> None:
    ids = {bp.tool.id for bp in PLANAR_TOOL_BLUEPRINTS}
    assert ids == {TOOL_PLAN_TRACE, TOOL_VENT_GENERATOR}
    for blueprint in PLANAR_TOOL_BLUEPRINTS:
        assert blueprint.toolbar_item.tool_id == blueprint.tool.id
        assert blueprint.expected_panel_builder.startswith(("panel_", "creator_api_"))
        registered = get_tool_spec(blueprint.tool.id)
        assert registered is not None
        assert registered.panel_index == blueprint.tool.panel_index
        assert registered.open_hook == blueprint.tool.open_hook


def test_pass13_runtime_composes_planar_controller_and_state() -> None:
    runtime = (STUDIO / "runtime_state.py").read_text(encoding="utf-8")
    app_context = (STUDIO / "app_context.py").read_text(encoding="utf-8")
    assert "PlanarToolState" in runtime
    assert "PlanarToolController.create(self.app_context)" in runtime
    assert "def planar" in app_context
    assert (STUDIO / "application" / "planar_tool_controller.py").exists()
    assert (STUDIO / "state" / "planar_tool_state.py").exists()

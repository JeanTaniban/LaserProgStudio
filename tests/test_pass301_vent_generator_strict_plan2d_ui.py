from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import VentPathDraft, make_locked_plane
from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.ui_motifs import API_UI_VISIBLE_METADATA_KEY
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR
from laserprog_studio.tooling.vent_generator.feedback import sync_vent_route_visuals


def test_pass301_vent_route_uses_only_plan2d_actor_motifs() -> None:
    payload = VentPathDraft(make_locked_plane("top"))
    payload.add_waypoint_plane((0.0, 0.0))
    payload.add_waypoint_plane((80.0, 0.0))
    payload.add_waypoint_plane((100.0, 45.0))
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    owner.planar_tool_state.payload = payload
    ctx = ToolContext(owner=owner)

    sync_vent_route_visuals(ctx, payload, state=owner.planar_tool_state, render=False, full=True)

    actors = {actor.id: actor for actor in ctx.selection.actors(owner_tool=TOOL_VENT_GENERATOR)}
    assert "vent.generator.route.waypoint.00" in actors
    assert "vent.generator.route.waypoint.01" in actors
    assert "vent.generator.route.segment.00" in actors
    assert "vent.generator.route.segment.01" in actors

    for actor in actors.values():
        assert actor.metadata["motif_family"] == "plan_trace_2d"
        assert actor.metadata[API_UI_VISIBLE_METADATA_KEY] is True

    # Compatibility ids may exist for older tests, but they are now hidden
    # Projected Drawing primitives and must not create selection actors.
    projected = {item.id: item for item in ctx.projected_drawing.for_tool(TOOL_VENT_GENERATOR).items()}
    assert "vent.generator.preview.centerline" in projected
    for item_id, item in projected.items():
        if item_id.startswith("vent.generator.preview.waypoint.") or item_id.startswith("vent.generator.preview.label."):
            assert item.visible is False
            assert ctx.selection.actor(item_id) is None


def test_pass301_no_vent_specific_pyvistafallback_route_ui_left() -> None:
    source = Path("src/laserprog_studio/application/planar_preview_service.py").read_text(encoding="utf-8")
    assert "vent_generator_route_" not in source
    assert "_flat_point_actor" not in source
    assert "Vent editable route UI is strictly owned by the public Plan2D" in source


def test_pass301_vent_feedback_has_no_direct_legacy_viewport_api() -> None:
    source = Path("src/laserprog_studio/tooling/vent_generator/feedback.py").read_text(encoding="utf-8")
    assert "ctx.preview" not in source
    assert "ctx.gizmos" not in source
    assert "ctx.actor_registry" not in source
    assert "ctx.projected_drawing" in source

from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import PlanarEditMode, VentPathDraft, make_locked_plane
from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.ids import TOOL_VENT_GENERATOR
from laserprog_studio.tooling.vent_generator.feedback import sync_vent_route_visuals
from laserprog_studio.tooling.vent_generator.panel import build_vent_generator_panel
from laserprog_studio.tooling.vent_generator.acoustics import estimate_vent_acoustics
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _payload() -> VentPathDraft:
    payload = VentPathDraft(make_locked_plane("top"))
    payload.add_waypoint_plane((0.0, 0.0))
    payload.add_waypoint_plane((80.0, 0.0))
    payload.add_waypoint_plane((120.0, 40.0))
    return payload


def test_pass304_vent_add_preview_syncs_only_pending_cursor_and_link() -> None:
    payload = _payload()
    state = PlanarToolState()
    state.payload = payload
    state.pending_plane_point = (140.0, 65.0)
    owner = SimpleNamespace(planar_tool_state=state)
    ctx = ToolContext(owner=owner)

    sync_vent_route_visuals(ctx, payload, state=state, render=False, full=True)
    before_actor_ids = {actor.id for actor in ctx.selection.actors(owner_tool=TOOL_VENT_GENERATOR)}

    sync_vent_route_visuals(ctx, payload, state=state, render=False, full=False, position_only=True)

    snapshot = ctx.profiler.snapshot()
    assert snapshot["vent.visual.fast_path.pending_only"] == 1
    assert snapshot["vent.visual.last_waypoints_synced"] == 0
    assert snapshot["vent.visual.last_segments_synced"] == 0
    assert snapshot["vent.visual.last_changed_actor_ids"] == 1
    assert snapshot["vent.visual.last_extra_preview_ids"] == 1
    assert {actor.id for actor in ctx.selection.actors(owner_tool=TOOL_VENT_GENERATOR)} == before_actor_ids | {"vent.generator.route.pending"}


def test_pass304_vent_mod_preview_syncs_only_selected_waypoint_and_adjacent_segments() -> None:
    payload = _payload()
    payload.mode = PlanarEditMode.MOD
    payload.selected_index = 1
    state = PlanarToolState()
    state.payload = payload
    owner = SimpleNamespace(planar_tool_state=state)
    ctx = ToolContext(owner=owner)

    sync_vent_route_visuals(ctx, payload, state=state, render=False, full=True)
    sync_vent_route_visuals(ctx, payload, state=state, render=False, full=False, position_only=True)

    snapshot = ctx.profiler.snapshot()
    assert snapshot["vent.visual.fast_path.selected_only"] == 1
    assert snapshot["vent.visual.last_waypoints_synced"] == 1
    assert snapshot["vent.visual.last_segments_synced"] == 2
    assert snapshot["vent.visual.last_changed_actor_ids"] == 3


def test_pass304_vent_export_timings_action_writes_diagnostics(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    ctx.profiler.increment("vent.event.mouse_move")
    with ctx.profiler.measure("vent.pointer.resolve"):
        pass

    tool.on_overlay_button_clicked("vent.generator.action.export_timings", ctx)

    assert (tmp_path / "diagnostics" / "vent_generator_timings.md").exists()
    assert (tmp_path / "diagnostics" / "vent_generator_timings.json").exists()
    assert (tmp_path / "diagnostics" / "vent_generator_timings.csv").exists()
    assert "Vent Generator diagnostic report" in (tmp_path / "diagnostics" / "vent_generator_timings.md").read_text(encoding="utf-8")


def test_pass304_vent_panel_action_row_declares_compact_columns() -> None:
    panel = build_vent_generator_panel(
        on_mode_changed=lambda _field, _value: None,
        on_values_changed=lambda _field, _value: None,
        on_preset_changed=lambda _field, _value: None,
        on_action=lambda _event: None,
    )
    action_field = next(field for field in panel.fields() if field.id == "vent_actions")
    assert action_field.metadata.get("columns") == 2


def test_pass304_vent_acoustic_estimate_and_readouts() -> None:
    payload = VentPathDraft(make_locked_plane("top"))
    payload.section.kind = "rectangle"
    payload.section.width = 120.0
    payload.section.height = 35.0
    payload.section.area = 120.0 * 35.0
    payload.add_waypoint_plane((0.0, 0.0))
    payload.add_waypoint_plane((200.0, 0.0))
    payload.add_waypoint_plane((200.0, 100.0))

    estimate = estimate_vent_acoustics(payload, enclosure_volume_l=45.0)
    assert estimate is not None
    assert estimate.physical_length_mm > 250.0
    assert estimate.inner_height_mm == 35.0
    assert estimate.tuning_hz is not None
    assert estimate.tuning_hz > 0.0

    state = PlanarToolState()
    state.payload = payload
    owner = SimpleNamespace(planar_tool_state=state)
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    state.payload = payload
    ctx.inspector.update_value("rect_width", 120.0, notify=False)
    ctx.inspector.update_value("rect_height", 35.0, notify=False)
    ctx.inspector.update_value("enclosure_volume_l", 45.0, notify=False)
    tool._on_values_changed(ctx)

    assert "mm" in str(ctx.inspector.value("vent_length_measure"))
    assert ctx.inspector.value("vent_height_measure") == "35.0 mm"
    assert "cm²" in str(ctx.inspector.value("vent_area_measure"))
    assert "Hz" in str(ctx.inspector.value("vent_tuning_measure"))

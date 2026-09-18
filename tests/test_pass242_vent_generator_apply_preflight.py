from __future__ import annotations

from types import SimpleNamespace

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import VentSectionKind, VentPathDraft
from laserprog_studio.state import PlanarToolState
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.vent_generator import VentGeneratorSettings, preflight_vent_apply_mesh, validate_vent_apply_payload
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _ctx_and_tool() -> tuple[ToolContext, VentGeneratorCreatorTool]:
    owner = SimpleNamespace(planar_tool_state=PlanarToolState())
    ctx = ToolContext(owner=owner)
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)
    return ctx, tool


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(float(x), float(y), 0.0), button=MouseButton.LEFT)


def test_pass242_vent_settings_parse_boolean_strings_for_packaged_ui_hosts() -> None:
    assert VentGeneratorSettings.from_values({"fill_area": "false"}).fill_area is False
    assert VentGeneratorSettings.from_values({"fill_area": "true"}).fill_area is True


def test_pass242_round_profile_clears_rectangular_only_fill_option() -> None:
    ctx, _tool = _ctx_and_tool()
    ctx.inspector.update_value("fill_area", True)
    ctx.inspector.update_value("section_kind", VentSectionKind.ROUND.value)

    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)
    assert ctx.inspector.value("fill_area") is False
    assert payload.fill_area is False
    assert ctx.inspector.field_state("fill_area").visible is False
    assert payload.section.kind is VentSectionKind.ROUND


def test_pass242_apply_reports_route_errors_before_generating_mesh() -> None:
    ctx, tool = _ctx_and_tool()
    ok = tool.on_apply(ctx)

    assert ok is False
    assert "add at least 2 waypoints" in ctx.inspector.value("apply_check")
    assert ctx.inspector.field_state("route_summary").error
    assert ctx.status.latest(level="warning") is not None


def test_pass242_apply_preflight_builds_requested_mesh_variant() -> None:
    ctx, tool = _ctx_and_tool()
    ctx.inspector.update_value("fill_area", True)
    ctx.inspector.update_value("flare_side", "both")
    ctx.inspector.update_value("flare_factor", 1.6)

    assert tool.on_event(_release(0, 0), ctx) is True
    assert tool.on_event(_release(72, 0), ctx) is True
    payload = ctx.owner.planar_tool_state.payload
    assert isinstance(payload, VentPathDraft)

    structural = validate_vent_apply_payload(payload)
    assert structural.ok is True
    assert structural.mesh_kind == "rectangular fill block"

    preflight = preflight_vent_apply_mesh(payload)
    assert preflight.ok is True
    assert preflight.mesh_vertices > 0
    assert preflight.mesh_triangles > 0

    assert tool.on_apply(ctx) is True
    assert "rectangular fill block" in ctx.inspector.value("apply_check")
    assert "vertices" in ctx.inspector.value("apply_check")
    assert ctx.inspector.field_state("apply_check").error is None

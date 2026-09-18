from __future__ import annotations

from collections import Counter

from _path_setup import ROOT  # noqa: F401

from laserprog_studio.planar_tools import VentPathDraft, VentSectionKind, make_locked_plane, make_vent_path_mesh
from laserprog_studio.tool_api.core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.vent_generator_tool import VentGeneratorCreatorTool


def _bad_edge_count(mesh) -> int:
    counts: Counter[tuple[int, int]] = Counter()
    for tri in mesh.triangles:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            counts[tuple(sorted((int(a), int(b))))] += 1
    return sum(1 for count in counts.values() if count != 2)


def _rect_draft(points: list[tuple[float, float]]) -> VentPathDraft:
    draft = VentPathDraft(make_locked_plane("top"))
    draft.section.kind = VentSectionKind.RECTANGLE
    draft.section.width = 20.0
    draft.section.height = 8.0
    draft.section.area = 160.0
    draft.wall_thickness = 2.0
    draft.waypoints = list(points)
    return draft


def _release(x: float, y: float) -> ToolEvent:
    return ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(float(x), float(y), 0.0), button=MouseButton.LEFT)


def test_pass259_curved_rectangular_wall_mesh_has_no_degenerate_or_non_manifold_edges() -> None:
    draft = _rect_draft([(0.0, 0.0), (60.0, 0.0)])
    draft.update_curve_handle_plane(0, (30.0, 20.0))

    mesh = make_vent_path_mesh(draft)

    assert len(mesh.vertices) > 0
    assert len(mesh.triangles) > 0
    assert _bad_edge_count(mesh) == 0


def test_pass259_compact_rectangular_u_turn_is_valid_and_reconstructs_closed_mesh() -> None:
    draft = _rect_draft([(0.0, 0.0), (80.0, 0.0), (80.0, 22.0), (0.0, 22.0)])

    assert draft.clearance_policy().min_centerline_spacing == 22.0
    assert draft.validation_result().ok is True

    mesh = make_vent_path_mesh(draft)

    assert len(mesh.vertices) > 0
    assert len(mesh.triangles) > 0
    assert _bad_edge_count(mesh) == 0


def test_pass259_inspector_makes_wall_only_default_and_compact_pitch_explicit() -> None:
    ctx = ToolContext()
    tool = VentGeneratorCreatorTool()
    tool.open(ctx)

    assert "Wall-only rectangular duct" in ctx.inspector.value("build_mode_summary")
    assert "Compact pitch" in ctx.inspector.value("compact_route_guide")
    assert "13.0 mm" in ctx.inspector.value("compact_route_guide")

    assert tool.on_event(_release(0.0, 0.0), ctx) is True
    assert tool.on_event(_release(80.0, 0.0), ctx) is True
    assert tool.on_apply(ctx) is True
    assert "rectangular wall-only duct" in ctx.inspector.value("apply_check")

    ctx.inspector.update_value("fill_area", True)

    assert "Solid fill block" in ctx.inspector.value("build_mode_summary")
    assert tool.on_apply(ctx) is True
    assert "rectangular fill block" in ctx.inspector.value("apply_check")

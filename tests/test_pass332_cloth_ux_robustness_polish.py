# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import pytest

from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.fold_ops import set_fold_angle
from laserprog_studio.tooling.cloth.interaction import ClothInteractionState
from laserprog_studio.tooling.cloth.models import ClothDocument, ClothFoldKind, ClothSession, ClothWorkflowPhase
from laserprog_studio.tooling.cloth.rendering import ClothRenderer
from laserprog_studio.tooling.cloth.serialization import CLOTH_SOURCE_KEY, cloth_output_kind, restore_cloth_source
from laserprog_studio.tooling.cloth.validation import ClothValidationCache, validate_cloth_document
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool
from laserprog_studio.tooling.ids import TOOL_CLOTH


def _context() -> ToolContext:
    ctx = ToolContext()
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    return ctx


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float) -> bool:
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT)
    assert tool.on_event(press, ctx) is False
    return bool(tool.on_event(release, ctx))


def _square_document() -> ClothDocument:
    doc = ClothDocument()
    points = [
        doc.add_point((0.0, 0.0, 0.0), point_id="p0"),
        doc.add_point((20.0, 0.0, 0.0), point_id="p1"),
        doc.add_point((20.0, 10.0, 0.0), point_id="p2"),
        doc.add_point((0.0, 10.0, 0.0), point_id="p3"),
    ]
    curves = [
        doc.add_line(points[0].id, points[1].id, curve_id="c0"),
        doc.add_line(points[1].id, points[2].id, curve_id="c1"),
        doc.add_line(points[2].id, points[3].id, curve_id="c2"),
        doc.add_line(points[3].id, points[0].id, curve_id="c3"),
    ]
    doc.add_patch(tuple(curve.id for curve in curves), patch_id="panel0", name="Panel 1")
    return doc


def _two_coplanar_panels() -> ClothDocument:
    doc = ClothDocument()
    for point_id, position in {
        "p0": (0.0, 0.0, 0.0),
        "p1": (10.0, 0.0, 0.0),
        "p2": (10.0, 10.0, 0.0),
        "p3": (0.0, 10.0, 0.0),
        "p4": (20.0, 0.0, 0.0),
        "p5": (20.0, 10.0, 0.0),
    }.items():
        doc.add_point(position, point_id=point_id)
    c0 = doc.add_line("p0", "p1", curve_id="c0")
    shared = doc.add_line("p1", "p2", curve_id="shared")
    c2 = doc.add_line("p2", "p3", curve_id="c2")
    c3 = doc.add_line("p3", "p0", curve_id="c3")
    c4 = doc.add_line("p1", "p4", curve_id="c4")
    c5 = doc.add_line("p4", "p5", curve_id="c5")
    c6 = doc.add_line("p5", "p2", curve_id="c6")
    a = doc.add_patch((c0.id, shared.id, c2.id, c3.id), patch_id="a", name="A")
    b = doc.add_patch((c4.id, c5.id, c6.id, shared.id), patch_id="b", name="B")
    doc.add_fold(shared.id, a.id, b.id, fold_id="fold", angle_degrees=45.0, kind=ClothFoldKind.VALLEY)
    return doc


def test_overlay_is_a_plan_tracer_style_toolbox_and_context_actions_follow_the_draft() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)

    opening = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert opening is not None
    buttons = {button.id: button for button in opening.buttons}
    assert buttons[f"{CLOTH_ACTION_PREFIX}draw_create_from_mesh"].checked
    assert f"{CLOTH_ACTION_PREFIX}draw_join_textile_faces" in buttons
    assert f"{CLOTH_ACTION_PREFIX}draw_polyline" in buttons
    assert f"{CLOTH_ACTION_PREFIX}close_polyline" not in buttons
    assert not any("plane" in button_id for button_id in buttons)

    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}draw_polyline", ctx)

    assert _click(tool, ctx, 0.0, 0.0)
    first = {button.id: button for button in ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID).buttons}
    assert not first[f"{CLOTH_ACTION_PREFIX}finish_open"].enabled
    assert not first[f"{CLOTH_ACTION_PREFIX}close_polyline"].enabled

    assert _click(tool, ctx, 20.0, 0.0)
    second = {button.id: button for button in ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID).buttons}
    assert second[f"{CLOTH_ACTION_PREFIX}finish_open"].enabled
    assert not second[f"{CLOTH_ACTION_PREFIX}close_polyline"].enabled

    assert _click(tool, ctx, 20.0, 10.0)
    third = {button.id: button for button in ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID).buttons}
    assert third[f"{CLOTH_ACTION_PREFIX}close_polyline"].enabled


def test_legacy_plane_actions_enter_free_3d_drawing_without_exposing_a_plane_stage() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}pick_plane", ctx)
    assert tool.interaction.stage.value == "draw"
    assert tool.session.phase is ClothWorkflowPhase.EDITING
    assert tool.session.edit_mode.value == "polyline"


def test_surface_preview_mesh_is_reused_while_only_hover_state_changes(monkeypatch) -> None:
    from laserprog_studio.tooling.cloth import rendering

    doc = _square_document()
    session = ClothSession(document=doc, phase=ClothWorkflowPhase.EDITING)
    interaction = ClothInteractionState()
    drawing = ClothDrawingController(doc)
    renderer = ClothRenderer(TOOL_CLOTH, session, interaction, drawing)
    ctx = _context()

    original = rendering.build_cloth_surface_mesh
    calls = 0

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(rendering, "build_cloth_surface_mesh", counted)
    renderer.sync(ctx)
    interaction.hovered_curve_id = "c0"
    renderer.sync(ctx)
    interaction.hovered_curve_id = "c1"
    renderer.sync(ctx)
    assert calls == 1

    doc.move_point("p0", (-1.0, 0.0, 0.0))
    renderer.sync(ctx)
    assert calls == 2


def test_validation_cache_is_revision_keyed_and_noop_point_moves_do_not_invalidate_it() -> None:
    doc = _square_document()
    cache = ClothValidationCache()
    first = cache.get(doc)
    revision = doc.revision
    assert doc.move_point("p0", doc.points["p0"].position)
    assert doc.revision == revision
    assert cache.get(doc) is first
    doc.move_point("p0", (-1.0, 0.0, 0.0))
    assert cache.get(doc) is not first


def test_v1_holes_are_apply_blocking_instead_of_silently_filled() -> None:
    doc = _square_document()
    for point_id, position in {
        "h0": (5.0, 3.0, 0.0),
        "h1": (15.0, 3.0, 0.0),
        "h2": (15.0, 7.0, 0.0),
        "h3": (5.0, 7.0, 0.0),
    }.items():
        doc.add_point(position, point_id=point_id)
    hole = (
        doc.add_line("h0", "h1", curve_id="h_c0").id,
        doc.add_line("h1", "h2", curve_id="h_c1").id,
        doc.add_line("h2", "h3", curve_id="h_c2").id,
        doc.add_line("h3", "h0", curve_id="h_c3").id,
    )
    doc.patches["panel0"].hole_curve_loops = (hole,)
    doc.revision += 1
    report = validate_cloth_document(doc)
    assert not report.can_apply
    assert "cloth.patch.holes_unsupported" in {issue.code for issue in report.errors}


def test_self_intersecting_panel_is_reported_before_triangulation() -> None:
    doc = ClothDocument()
    for point_id, position in {
        "p0": (0.0, 0.0, 0.0),
        "p1": (10.0, 10.0, 0.0),
        "p2": (0.0, 10.0, 0.0),
        "p3": (10.0, 0.0, 0.0),
    }.items():
        doc.add_point(position, point_id=point_id)
    curves = (
        doc.add_line("p0", "p1", curve_id="c0").id,
        doc.add_line("p1", "p2", curve_id="c1").id,
        doc.add_line("p2", "p3", curve_id="c2").id,
        doc.add_line("p3", "p0", curve_id="c3").id,
    )
    doc.add_patch(curves, patch_id="bow", name="Crossed panel")
    report = validate_cloth_document(doc)
    assert not report.can_apply
    assert "cloth.patch.self_intersection" in {issue.code for issue in report.errors}


def test_closed_fold_cycle_uses_a_virtual_flat_pattern_cut() -> None:
    doc = ClothDocument()
    for point_id, position in {
        "p0": (0.0, 0.0, 0.0),
        "p1": (10.0, 0.0, 0.0),
        "p2": (5.0, 8.0, 0.0),
        "p3": (5.0, -8.0, 0.0),
    }.items():
        doc.add_point(position, point_id=point_id)
    e01 = doc.add_line("p0", "p1", curve_id="e01")
    e12 = doc.add_line("p1", "p2", curve_id="e12")
    e20 = doc.add_line("p2", "p0", curve_id="e20")
    e23 = doc.add_line("p2", "p3", curve_id="e23")
    e31 = doc.add_line("p3", "p1", curve_id="e31")
    e30 = doc.add_line("p3", "p0", curve_id="e30")
    a = doc.add_patch((e01.id, e12.id, e20.id), patch_id="a", name="A")
    b = doc.add_patch((e12.id, e23.id, e31.id), patch_id="b", name="B")
    c = doc.add_patch((e01.id, e31.id, e30.id), patch_id="c", name="C")
    doc.add_fold(e12.id, a.id, b.id, fold_id="fab")
    doc.add_fold(e31.id, b.id, c.id, fold_id="fbc")
    doc.add_fold(e01.id, c.id, a.id, fold_id="fca")
    report = validate_cloth_document(doc)
    assert report.can_apply
    assert "cloth.fold.cycle_virtual_cut" in {issue.code for issue in report.warnings}


def test_degenerate_circular_arc_is_rejected_with_a_specific_message() -> None:
    doc = ClothDocument()
    doc.add_point((0.0, 0.0, 0.0), point_id="a")
    doc.add_point((10.0, 0.0, 0.0), point_id="b")
    doc.add_point((5.0, 0.0, 0.0), point_id="control")
    doc.add_arc("a", "b", "control", curve_id="arc")
    report = validate_cloth_document(doc)
    assert "cloth.arc.degenerate" in {issue.code for issue in report.errors}


def test_corrupted_cloth_metadata_is_ignored_safely_during_hover_detection() -> None:
    mesh = SimpleNamespace(metadata={CLOTH_SOURCE_KEY: {"output_kind": "folded", "document": {"schema_version": 999}}})
    assert cloth_output_kind(mesh) is None
    assert restore_cloth_source(mesh) is None
    assert cloth_output_kind(None) is None
    assert restore_cloth_source(None) is None


def test_fold_metadata_changes_touch_the_document_even_when_geometry_already_matches() -> None:
    doc = _two_coplanar_panels()
    before = doc.revision
    changed = set_fold_angle(doc, "fold", 0.0)
    assert changed == ()
    assert doc.folds["fold"].angle_degrees == pytest.approx(0.0)
    assert doc.folds["fold"].kind is ClothFoldKind.NEUTRAL
    assert doc.revision == before + 1

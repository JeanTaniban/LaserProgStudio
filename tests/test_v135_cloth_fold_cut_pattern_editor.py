from __future__ import annotations

import pytest

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.flattening import flatten_cloth_document
from laserprog_studio.tooling.cloth.models import (
    ClothCurveKind,
    ClothDocument,
    ClothEditMode,
    ClothFoldKind,
    ClothSession,
    ClothWorkflowPhase,
)
from laserprog_studio.tooling.cloth.pattern_edges import (
    ClothPatternEdgeError,
    analyze_pattern,
    apply_cycle_cuts,
    apply_pattern_edge,
    pattern_edge_state,
    pattern_spacing_mm,
    set_pattern_spacing,
)
from laserprog_studio.tooling.cloth.pattern_overlay import CLOTH_PATTERN_ACTION_PREFIX, CLOTH_PATTERN_WINDOW_ID
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _context() -> ToolContext:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    return ctx


def _two_panels(*, with_fold: bool = True) -> ClothDocument:
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
    for curve_id, first, second in (
        ("c0", "p0", "p1"),
        ("shared", "p1", "p2"),
        ("c2", "p2", "p3"),
        ("c3", "p3", "p0"),
        ("c4", "p1", "p4"),
        ("c5", "p4", "p5"),
        ("c6", "p5", "p2"),
    ):
        doc.add_line(first, second, curve_id=curve_id)
    doc.add_patch(("c0", "shared", "c2", "c3"), patch_id="a", name="A")
    doc.add_patch(("c4", "c5", "c6", "shared"), patch_id="b", name="B")
    if with_fold:
        doc.add_fold("shared", "a", "b", fold_id="fold", kind=ClothFoldKind.NEUTRAL)
    return doc


def _triangle_cycle() -> ClothDocument:
    doc = ClothDocument()
    for point_id, position in {
        "p0": (0.0, 0.0, 0.0),
        "p1": (10.0, 0.0, 0.0),
        "p2": (5.0, 8.0, 0.0),
        "p3": (5.0, -8.0, 0.0),
    }.items():
        doc.add_point(position, point_id=point_id)
    for curve_id, a, b in (
        ("e01", "p0", "p1"),
        ("e12", "p1", "p2"),
        ("e20", "p2", "p0"),
        ("e23", "p2", "p3"),
        ("e31", "p3", "p1"),
        ("e30", "p3", "p0"),
    ):
        doc.add_line(a, b, curve_id=curve_id)
    doc.add_patch(("e01", "e12", "e20"), patch_id="a")
    doc.add_patch(("e12", "e23", "e31"), patch_id="b")
    doc.add_patch(("e01", "e31", "e30"), patch_id="c")
    doc.add_fold("e12", "a", "b", fold_id="fab")
    doc.add_fold("e31", "b", "c", fold_id="fbc")
    doc.add_fold("e01", "c", "a", fold_id="fca")
    return doc


def test_pattern_overlay_is_visible_before_selection_and_apply_is_disabled() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    session = ClothSession(document=_two_panels(), phase=ClothWorkflowPhase.EDITING, edit_mode=ClothEditMode.MODIFY)
    tool._bind_session(session)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_fold", ctx)

    window = ctx.overlay.window(CLOTH_PATTERN_WINDOW_ID)
    assert window is not None
    buttons = {button.id: button for button in window.buttons}
    assert f"{CLOTH_PATTERN_ACTION_PREFIX}operation_fold" in buttons
    assert f"{CLOTH_PATTERN_ACTION_PREFIX}operation_cut" in buttons
    assert not buttons[f"{CLOTH_PATTERN_ACTION_PREFIX}apply_edge"].enabled
    assert buttons[f"{CLOTH_PATTERN_ACTION_PREFIX}done"].enabled


def test_selecting_an_edge_is_non_destructive_until_apply_edge() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    document = _two_panels(with_fold=True)
    original_revision = document.revision
    tool._bind_session(ClothSession(document=document, phase=ClothWorkflowPhase.EDITING, edit_mode=ClothEditMode.FOLD))
    tool._interaction.enter_fold()

    assert tool._select_fold(ctx, (10.0, 5.0))
    assert document.revision == original_revision
    assert tool.interaction.selected_pattern_curve_id == "shared"
    tool.on_overlay_button_clicked(f"{CLOTH_PATTERN_ACTION_PREFIX}operation_cut", ctx)
    assert not document.folds  # live preview
    tool.on_overlay_button_clicked(f"{CLOTH_PATTERN_ACTION_PREFIX}clear_edge", ctx)
    assert "fold" in document.folds  # cancelled preview restored exactly
    assert tool._select_fold(ctx, (10.0, 5.0))
    tool.on_overlay_button_clicked(f"{CLOTH_PATTERN_ACTION_PREFIX}operation_cut", ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_PATTERN_ACTION_PREFIX}apply_edge", ctx)
    assert not document.folds
    assert document.curves["shared"].metadata["cloth_user_cut"] is True
    assert tool.interaction.selected_pattern_curve_id is None


def test_fold_validation_rotates_only_after_commit_and_stores_radius() -> None:
    document = _two_panels(with_fold=False)
    before = document.points["p4"].position
    result = apply_pattern_edge(document, "shared", "fold", angle_degrees=90.0, radius_mm=3.5)
    assert result.changed
    fold = next(iter(document.folds.values()))
    assert fold.angle_degrees == pytest.approx(90.0)
    assert fold.radius_mm == pytest.approx(3.5)
    assert document.points["p4"].position != before
    assert pattern_edge_state(document, "shared").operation == "fold"


def test_cut_separates_flat_pattern_components_without_breaking_3d_points() -> None:
    document = _two_panels(with_fold=True)
    positions = {point_id: point.position for point_id, point in document.points.items()}
    apply_pattern_edge(document, "shared", "cut")
    assert {point_id: point.position for point_id, point in document.points.items()} == positions
    analysis = analyze_pattern(document)
    assert analysis.fold_count == 0
    assert analysis.cut_count == 1
    assert analysis.component_count == 2
    flat = flatten_cloth_document(document)
    assert flat.success
    assert len({placement.component_index for placement in flat.placements.values()}) == 2


def test_cycle_fix_converts_only_cycle_closing_folds_into_cuts() -> None:
    document = _triangle_cycle()
    analysis = analyze_pattern(document)
    assert len(analysis.cycle_fold_ids) == 1
    cut_curves = apply_cycle_cuts(document)
    assert len(cut_curves) == 1
    assert analyze_pattern(document).unfoldable
    assert len(document.folds) == 2
    assert document.curves[cut_curves[0]].metadata["cloth_user_cut"] is True


def test_new_fold_is_rejected_when_it_would_close_a_pattern_cycle() -> None:
    document = _triangle_cycle()
    apply_cycle_cuts(document)
    cut_curve = next(curve.id for curve in document.curves.values() if curve.metadata.get("cloth_user_cut"))
    with pytest.raises(ClothPatternEdgeError, match="cycle"):
        apply_pattern_edge(document, cut_curve, "fold", angle_degrees=45.0)


def test_pattern_spacing_is_persisted_and_used_by_flattening() -> None:
    document = _two_panels(with_fold=True)
    apply_pattern_edge(document, "shared", "cut")
    assert set_pattern_spacing(document, 55.0)
    assert pattern_spacing_mm(document) == pytest.approx(55.0)
    result = flatten_cloth_document(document)
    assert result.success
    from laserprog_studio.tooling.cloth.topology import sample_patch_boundary
    first_x = [result.placements["a"].map_world(point)[0] for point in sample_patch_boundary(document, "a")]
    second_x = [result.placements["b"].map_world(point)[0] for point in sample_patch_boundary(document, "b")]
    assert min(second_x) - max(first_x) >= 55.0 - 1.0e-9


def test_curved_shared_edge_can_be_cut_but_not_folded() -> None:
    document = _two_panels(with_fold=False)
    document.curves["shared"].kind = ClothCurveKind.ARC
    document.curves["shared"].point_ids = ("p1", "p2", "p0")
    state = pattern_edge_state(document, "shared")
    assert not state.can_fold
    apply_pattern_edge(document, "shared", "cut")
    with pytest.raises(ClothPatternEdgeError, match="straight"):
        apply_pattern_edge(document, "shared", "fold")


def test_apply_edge_without_changing_controls_creates_the_default_fold() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    document = _two_panels(with_fold=False)
    tool._bind_session(ClothSession(document=document, phase=ClothWorkflowPhase.EDITING, edit_mode=ClothEditMode.FOLD))
    tool._interaction.enter_fold()
    assert tool._select_fold(ctx, (10.0, 5.0))
    assert not document.folds
    tool.on_overlay_button_clicked(f"{CLOTH_PATTERN_ACTION_PREFIX}apply_edge", ctx)
    assert len(document.folds) == 1


def test_switching_tool_restores_an_unvalidated_fold_preview() -> None:
    ctx = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    document = _two_panels(with_fold=True)
    original_positions = {key: point.position for key, point in document.points.items()}
    tool._bind_session(ClothSession(document=document, phase=ClothWorkflowPhase.EDITING, edit_mode=ClothEditMode.FOLD))
    tool._interaction.enter_fold()
    assert tool._select_fold(ctx, (10.0, 5.0))
    tool._on_value_changed(ctx, "cloth_fold_angle", 90.0)
    assert {key: point.position for key, point in document.points.items()} != original_positions
    assert tool.can_apply(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_modify", ctx)
    assert {key: point.position for key, point in document.points.items()} == original_positions
    assert tool._pattern_edge_snapshot is None

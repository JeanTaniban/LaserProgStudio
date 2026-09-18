from __future__ import annotations

import math

from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.join_faces import (
    ClothJoinProposal,
    _vertex_complete_boundary_strategy,
    analyze_textile_close_groups,
    commit_join_proposal,
)
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan
from laserprog_studio.tooling.cloth.workspace import ClothWorkspaceMachine
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _u_boundary() -> tuple[tuple[float, float, float], ...]:
    return tuple(
        (float(x), float(y), 0.0)
        for x, y in (
            (0, 100), (0, 20), (2, 10), (8, 2), (20, 0), (32, 2),
            (38, 10), (40, 20), (40, 100), (34, 100), (34, 22),
            (32, 14), (27, 8), (20, 6), (13, 8), (8, 14), (6, 22), (6, 100),
        )
    )


def _retessellated_transformed_u(*, angle_degrees: float = 18.0, scale: float = 1.08):
    source = _u_boundary()
    dense: list[tuple[float, float, float]] = []
    for index, point in enumerate(source):
        following = source[(index + 1) % len(source)]
        dense.append(point)
        if index % 3 == 0:
            dense.append(tuple((point[axis] + following[axis]) * 0.5 for axis in range(3)))
    angle = math.radians(angle_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return tuple(
        (
            cosine * (scale * x) + 3.0,
            scale * y - 4.0,
            -sine * (scale * x) + 25.0,
        )
        for x, y, _z in reversed(dense)
    )


def _action(sections, suffix: str):
    for section in sections:
        for action in section.actions:
            if str(action.id).endswith(suffix):
                return action
    raise AssertionError(f"Missing action {suffix}")


def test_close_apply_uses_real_proposals_even_when_workspace_counter_lags() -> None:
    tool = ClothCreatorTool()
    tool._workspace_machine.enter_close(proposals=0)
    tool.interaction.join_proposals = (
        ClothJoinProposal("preview", (), (), 1.0, 0.0, "Preview ready."),
    )

    apply_action = _action(tool._workflow_overlay._close_sections(), "apply_closure")

    assert apply_action.enabled


def test_workspace_reset_keeps_overlay_state_reference_alive() -> None:
    machine = ClothWorkspaceMachine()
    referenced_state = machine.state
    machine.enter_close(proposals=3, proposal_index=2)

    reset_state = machine.reset()

    assert reset_state is referenced_state
    assert referenced_state.close_proposal_count == 0
    assert referenced_state.overlay_mode.value == "main"


def test_main_apply_is_clickable_to_run_validation_when_faces_exist() -> None:
    tool = ClothCreatorTool()
    created = tool._drawing.create_surface_from_positions(
        ((0.0, 0.0, 0.0), (20.0, 0.0, 0.0), (20.0, 20.0, 0.0), (0.0, 20.0, 0.0))
    )
    assert created.committed

    apply_action = _action(
        tool._workflow_overlay._main_sections(can_apply=False, pending_count=0),
        "apply_output",
    )
    blocked_while_drawing = _action(
        tool._workflow_overlay._main_sections(can_apply=False, pending_count=1),
        "apply_output",
    )

    assert apply_action.enabled
    assert not blocked_while_drawing.enabled


def test_complete_vertex_closure_accepts_reversed_rotated_scaled_retessellation() -> None:
    first = _u_boundary()
    second = _retessellated_transformed_u()

    strategy = _vertex_complete_boundary_strategy("first", first, "second", second, 8, 72)

    assert strategy is not None
    pair = strategy.pairs[0]
    assert pair.strategy == "complete_boundary_vertex"
    assert pair.coverage_first == 1.0 and pair.coverage_second == 1.0
    assert pair.segment_count >= max(len(first), len(second))
    assert all(vertex in pair.first_rail for vertex in first)
    assert all(vertex in pair.second_rail for vertex in second)


def test_transformed_retessellated_u_keeps_diverse_safe_and_apply_ready_results() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_u_boundary())
    second = drawing.create_surface_from_positions(_retessellated_transformed_u())
    assert first.committed and second.committed

    proposals = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )

    assert proposals
    assert proposals[0].id == "close_complete_boundary"
    assert len(proposals) <= 20
    assert proposals[0].pairs[0].coverage == 1.0

    ready = []
    for proposal in proposals:
        candidate = document.clone()
        outcome = commit_join_proposal(candidate, proposal)
        if not outcome.committed:
            continue
        plan = build_cloth_apply_plan(candidate, name=proposal.id)
        if plan.ready and plan.flattening is not None and plan.flattening.success:
            ready.append(proposal.id)
    assert ready

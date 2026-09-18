from __future__ import annotations

from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.groups import create_textile_group
from laserprog_studio.tooling.cloth.join_faces import (
    _build_closure_cell_validator,
    analyze_textile_close_groups,
    commit_join_proposal,
)
from laserprog_studio.tooling.cloth.models import ClothDocument, ClothSession
from laserprog_studio.tooling.cloth.output import build_cloth_apply_plan
from laserprog_studio.tooling.cloth.rendering import ClothRenderer
from laserprog_studio.tooling.cloth.interaction import ClothInteractionState
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _u_panel(z: float = 0.0):
    return (
        (0.0, 100.0, z), (0.0, 20.0, z), (2.0, 10.0, z),
        (8.0, 2.0, z), (20.0, 0.0, z), (32.0, 2.0, z),
        (38.0, 10.0, z), (40.0, 20.0, z), (40.0, 100.0, z),
        (34.0, 100.0, z), (34.0, 22.0, z), (32.0, 14.0, z),
        (27.0, 8.0, z), (20.0, 6.0, z), (13.0, 8.0, z),
        (8.0, 14.0, z), (6.0, 22.0, z), (6.0, 100.0, z),
    )


def _square(drawing: ClothDrawingController, x0: float, x1: float) -> str:
    outcome = drawing.create_surface_from_positions(
        ((x0, 0.0, 0.0), (x1, 0.0, 0.0), (x1, 10.0, 0.0), (x0, 10.0, 0.0))
    )
    assert outcome.committed, outcome.message
    assert outcome.created_patch_id is not None
    return outcome.created_patch_id


def test_close_exposes_diverse_safe_endpoint_strategies_for_u_boundaries() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_u_panel(0.0))
    second = drawing.create_surface_from_positions(_u_panel(25.0))
    assert first.committed and second.committed

    groups = ((first.created_patch_id,), (second.created_patch_id,))
    proposals = analyze_textile_close_groups(document, groups)

    assert 5 <= len(proposals) <= 20
    assert proposals[0].id == "close_complete_boundary"
    assert any(proposal.id.startswith("close_endpoint_arc") for proposal in proposals[1:])
    assert len({proposal.id for proposal in proposals}) == len(proposals)
    assert any(
        sum(pair.coverage for pair in proposal.pairs) >= 0.75
        and proposal.id.startswith("close_endpoint_arc")
        for proposal in proposals
    )

    validator, _metadata = _build_closure_cell_validator(document, groups)
    assert validator is not None
    for proposal in proposals:
        for pair in proposal.pairs:
            assert all(
                validator(
                    pair.first_patch_id,
                    pair.second_patch_id,
                    pair.first_rail[index],
                    pair.first_rail[index + 1],
                    pair.second_rail[index + 1],
                    pair.second_rail[index],
                )
                for index in range(pair.segment_count)
            )


def test_endpoint_parameter_sweep_does_not_emit_visual_density_duplicates() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_u_panel(0.0))
    second = drawing.create_surface_from_positions(_u_panel(25.0))
    proposals = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )

    endpoint_pairs = [proposal.pairs[0] for proposal in proposals if proposal.id.startswith("close_endpoint_arc")]
    endpoints = {
        (
            pair.first_rail[0], pair.first_rail[-1],
            pair.second_rail[0], pair.second_rail[-1],
        )
        for pair in endpoint_pairs
    }
    assert len(endpoints) == len(endpoint_pairs)




def test_at_least_one_non_primary_arc_is_apply_and_flatten_ready() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = drawing.create_surface_from_positions(_u_panel(0.0))
    second = drawing.create_surface_from_positions(_u_panel(25.0))
    proposals = analyze_textile_close_groups(
        document,
        ((first.created_patch_id,), (second.created_patch_id,)),
    )

    ready_ids: list[str] = []
    for proposal in proposals[1:]:
        candidate = document.clone()
        outcome = commit_join_proposal(candidate, proposal)
        if not outcome.committed:
            continue
        plan = build_cloth_apply_plan(candidate, name=proposal.id)
        if plan.ready and plan.flattening is not None and plan.flattening.success:
            ready_ids.append(proposal.id)
    assert ready_ids
    assert any(value.startswith("close_endpoint_arc") for value in ready_ids)


class _Registry:
    def __init__(self) -> None:
        self._items: dict[str, object] = {}

    def items(self):
        return tuple(self._items.values())

    def remove_many(self, ids, *, render=False):  # noqa: ARG002
        for value in ids:
            self._items.pop(str(value), None)

    def add_many(self, items, *, replace=True, render=False):  # noqa: ARG002
        for item in items:
            self._items[str(item.id)] = item


def test_main_hover_highlights_every_technical_patch_in_the_persistent_group() -> None:
    tool = ClothCreatorTool()
    first = _square(tool._drawing, 0.0, 10.0)
    second = _square(tool._drawing, 10.0, 20.0)
    create_textile_group(tool.session.document, (first, second), group_id="hover_group", origin="take_face")
    tool._interaction.enter_main()

    tool._set_hovered_textile_patch(second, logical_group=True)

    assert set(tool.interaction.hovered_patch_group_ids) == {first, second}
    registry = _Registry()
    assert tool._renderer._sync_static(registry)
    ids = {str(item.id) for item in registry.items()}
    assert f"cloth:surface:selection:{first}" in ids
    assert f"cloth:surface:selection:{second}" in ids


def test_draw_hover_remains_technical_face_only() -> None:
    session = ClothSession()
    drawing = ClothDrawingController(session.document)
    first = _square(drawing, 0.0, 10.0)
    second = _square(drawing, 10.0, 20.0)
    create_textile_group(session.document, (first, second), group_id="draw_group", origin="take_face")
    interaction = ClothInteractionState()
    interaction.enter_draw()
    interaction.hovered_patch_id = second
    interaction.hovered_patch_group_ids = (second,)
    renderer = ClothRenderer("cloth-test", session, interaction, drawing)
    registry = _Registry()

    assert renderer._sync_static(registry)
    ids = {str(item.id) for item in registry.items()}
    assert f"cloth:surface:selection:{second}" in ids
    assert f"cloth:surface:selection:{first}" not in ids

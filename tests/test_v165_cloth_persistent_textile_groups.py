from __future__ import annotations

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.groups import (
    explicit_textile_group_id,
    normalize_disconnected_textile_groups,
    textile_group_record,
)
from laserprog_studio.tooling.cloth.models import ClothDocument
from laserprog_studio.tooling.cloth.selection import (
    assign_logical_patch_group,
    delete_cloth_selection,
    logical_patch_group,
)
from laserprog_studio.tooling.cloth.serialization import cloth_document_from_dict, cloth_document_to_dict
from laserprog_studio.tooling.cloth.workspace import ClothDrawMode
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _square(drawing: ClothDrawingController, x0: float, x1: float, *, z: float = 0.0) -> str:
    outcome = drawing.create_surface_from_positions(
        ((x0, 0.0, z), (x1, 0.0, z), (x1, 10.0, z), (x0, 10.0, z))
    )
    assert outcome.committed, outcome.message
    assert outcome.created_patch_id is not None
    return outcome.created_patch_id


def test_main_click_selects_exactly_one_persistent_group_even_when_groups_touch() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = _square(tool._drawing, 0.0, 10.0)
    second = _square(tool._drawing, 10.0, 20.0)
    assign_logical_patch_group(tool.session.document, (first,), "group_a", origin="take_face")
    assign_logical_patch_group(tool.session.document, (second,), "group_b", origin="take_face")
    tool.geometry_trace.set_smart_tolerance(1.0)

    tool._frontmost_face_target = lambda _ctx, _pos: ("textile", first)
    tool._select_main(ctx, (5.0, 5.0), additive=False)

    assert tool.session.selected_patch_ids == (first,)
    assert tool._selected_textile_patch_groups() == (frozenset((first,)),)


def test_clicking_any_technical_patch_selects_the_complete_take_face_group_only() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = _square(tool._drawing, 0.0, 10.0)
    second = _square(tool._drawing, 10.0, 20.0)
    neighbour = _square(tool._drawing, 20.0, 30.0)
    assign_logical_patch_group(tool.session.document, (first, second), "take_curve", origin="take_face")
    assign_logical_patch_group(tool.session.document, (neighbour,), "other", origin="take_face")

    tool._frontmost_face_target = lambda _ctx, _pos: ("textile", second)
    tool._select_main(ctx, (15.0, 5.0), additive=False)

    assert set(tool.session.selected_patch_ids) == {first, second}
    assert neighbour not in tool.session.selected_patch_ids


def test_close_creates_one_independent_group_not_joined_to_its_input_groups() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = _square(tool._drawing, 0.0, 20.0, z=0.0)
    second = _square(tool._drawing, 0.0, 20.0, z=20.0)
    assign_logical_patch_group(tool.session.document, (first,), "input_a", origin="take_face")
    assign_logical_patch_group(tool.session.document, (second,), "input_b", origin="take_face")
    tool._set_selected_textile_groups(((first,), (second,)))
    before = set(tool.session.document.patches)

    tool._enter_close(ctx)
    assert tool.interaction.join_proposals
    tool._accept_close(ctx)

    created = set(tool.session.document.patches) - before
    assert created
    created_ids = {explicit_textile_group_id(tool.session.document, patch_id) for patch_id in created}
    assert len(created_ids) == 1
    created_group_id = next(iter(created_ids))
    assert created_group_id not in {"input_a", "input_b"}
    record = textile_group_record(tool.session.document, created_group_id)
    assert record is not None
    assert set(record["parent_group_ids"]) == {"input_a", "input_b"}
    assert set(tool.session.selected_patch_ids) == created

    seed = min(created)
    tool._frontmost_face_target = lambda _ctx, _pos: ("textile", seed)
    tool._select_main(ctx, (5.0, 5.0), additive=False)
    assert set(tool.session.selected_patch_ids) == created
    assert first not in tool.session.selected_patch_ids
    assert second not in tool.session.selected_patch_ids


def test_draw_modify_apply_separates_selected_technical_faces_from_their_group() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = _square(tool._drawing, 0.0, 10.0)
    second = _square(tool._drawing, 10.0, 20.0)
    assign_logical_patch_group(tool.session.document, (first, second), "combined", origin="take_face")

    tool._enter_draw(ctx, ClothDrawMode.MODIFY)
    tool.session.selected_patch_ids = (first,)
    tool._selected_textile_groups = [frozenset((first,))]
    tool._on_action(ctx, "apply_draw")

    first_group = explicit_textile_group_id(tool.session.document, first)
    second_group = explicit_textile_group_id(tool.session.document, second)
    assert first_group
    assert second_group
    assert first_group != second_group
    assert logical_patch_group(tool.session.document, first) == (first,)
    assert logical_patch_group(tool.session.document, second) == (second,)


def test_deleting_a_middle_draw_face_splits_remaining_islands_into_groups() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = _square(drawing, 0.0, 10.0)
    middle = _square(drawing, 10.0, 20.0)
    last = _square(drawing, 20.0, 30.0)
    assign_logical_patch_group(document, (first, middle, last), "strip", origin="take_face")

    result = delete_cloth_selection(document, patch_ids=(middle,))
    assert result.changed
    normalized = normalize_disconnected_textile_groups(document, group_ids=("strip",))

    assert normalized.split_group_count == 1
    assert explicit_textile_group_id(document, first) != explicit_textile_group_id(document, last)
    assert logical_patch_group(document, first) == (first,)
    assert logical_patch_group(document, last) == (last,)


def test_group_registry_and_identity_survive_cloth_serialization() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    first = _square(drawing, 0.0, 10.0)
    second = _square(drawing, 10.0, 20.0)
    assign_logical_patch_group(document, (first, second), "saved_group", origin="draw")

    restored = cloth_document_from_dict(cloth_document_to_dict(document))

    assert explicit_textile_group_id(restored, first) == "saved_group"
    assert set(logical_patch_group(restored, second)) == {first, second}
    record = textile_group_record(restored, "saved_group")
    assert record is not None
    assert set(record["patch_ids"]) == {first, second}

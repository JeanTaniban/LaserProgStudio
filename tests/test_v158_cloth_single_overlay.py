from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.models import ClothEditMode, ClothPatchFunction
from laserprog_studio.tooling.cloth.selection import assign_logical_patch_group
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth.workspace import (
    ClothDrawMode,
    ClothOverlayMode,
    ClothPropertySelectionMode,
)
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _square_mesh(name: str = "support", x: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name,
        [(x, 0, 0), (x + 20, 0, 0), (x + 20, 10, 0), (x, 10, 0)],
        [(0, 1, 2), (0, 2, 3)],
    )


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float, *, shift: bool = False, ctrl: bool = False) -> None:
    modifiers = set()
    if shift:
        modifiers.add("shift")
    if ctrl:
        modifiers.add("ctrl")
    frozen = frozenset(modifiers)
    tool.on_event(
        ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, 0), button=MouseButton.LEFT, modifiers=frozen),
        ctx,
    )
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, 0), button=MouseButton.LEFT, modifiers=frozen),
        ctx,
    )


def _button(window, label: str):
    return next(button for button in window.buttons if button.display_label == label)


def test_main_overlay_is_the_only_cloth_overlay_and_has_requested_commands() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert [button.display_label for button in window.buttons] == ["Take face", "Close", "Draw", "Properties", "Apply"]
    assert window.accent_color == "#38BDF8"
    assert _button(window, "Take face").enabled is False
    assert _button(window, "Close").enabled is False
    assert ctx.overlay.window("cloth.geometry_trace") is None
    assert ctx.overlay.window("cloth.pattern_edges") is None


def test_take_face_converts_temporary_mesh_group_to_persistent_textile() -> None:
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [_square_mesh()]))
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_object_at(self, _screen_pos, **_filters):
            return None

        def pick_face_at(self, _screen_pos, **_filters):
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": 0,
                "element_index": 0,
                "world_pos": (5.0, 5.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    _click(tool, ctx, 5, 5)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert _button(window, "Take face").enabled is True
    assert tool.geometry_trace.smart_session.selected_region_count == 1

    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}take_face", ctx)
    assert tool.geometry_trace.smart_session.selected_region_count == 0
    assert len(tool.session.document.patches) == 1
    assert len(tool.session.selected_patch_ids) == 1
    patch = next(iter(tool.session.document.patches.values()))
    assert patch.metadata.get("cloth_source_object_id") == obj.id
    assert patch.function is ClothPatchFunction.TEXTILE


def test_main_selection_combines_textile_groups_and_solitary_edges() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    face = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    edge = tool._drawing.create_line_from_positions((0, 20, 0), (10, 20, 0))
    assert face.committed and edge.committed

    _click(tool, ctx, 5, 5)
    _click(tool, ctx, 5, 20, shift=True)
    assert len(tool.session.selected_patch_ids) == 1
    assert len(tool.session.selected_curve_ids) == 1
    assert tool._workspace.textile_anchor_count == 2
    assert _button(ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID), "Close").enabled is True


def test_close_replaces_overlay_content_and_applies_edge_proposal() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = tool._drawing.create_line_from_positions((0, 0, 0), (20, 0, 0))
    second = tool._drawing.create_line_from_positions((0, 10, 0), (20, 10, 0))
    assert first.committed and second.committed

    _click(tool, ctx, 10, 0)
    _click(tool, ctx, 10, 10, shift=True)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}open_close", ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert tool._workspace.overlay_mode is ClothOverlayMode.CLOSE
    assert [button.display_label for button in window.buttons] == ["Apply", "Prev", "Next", "Reset"]
    assert window.accent_color == "#F59E0B"
    assert tool.interaction.join_proposals

    before = len(tool.session.document.patches)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}apply_close", ctx)
    assert len(tool.session.document.patches) > before
    assert tool._workspace.overlay_mode is ClothOverlayMode.MAIN


def test_draw_overlay_is_green_and_closed_polyline_creates_face_automatically() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    tool._enter_draw(ctx, ClothDrawMode.POLYLINE)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert window.accent_color == "#22C55E"
    assert {button.display_label for button in window.buttons} == {
        "Apply", "Modify", "Line", "Polyline", "Faces", "Edges", "Smart snap", "Axis guides", "Clear"
    }

    for x, y in ((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)):
        tool._draw_click(
            ctx,
            ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, 0), button=MouseButton.LEFT),
            double=False,
        )
    assert len(tool.session.document.patches) == 1
    assert len(tool.session.selected_patch_ids) == 1
    assert tool.session.edit_mode is ClothEditMode.POLYLINE


def test_properties_rejects_mesh_and_selects_textile_by_face_or_api_group() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    second = tool._drawing.create_surface_from_positions(((20, 0, 0), (30, 0, 0), (30, 10, 0), (20, 10, 0)))
    assert first.committed and second.committed
    assign_logical_patch_group(tool.session.document, (first.created_patch_id, second.created_patch_id), "pair")

    tool._enter_properties(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert window.accent_color == "#A855F7"
    assert _button(window, "Textile").enabled is False

    tool._workspace_machine.set_property_selection_mode(ClothPropertySelectionMode.FACE)
    _click(tool, ctx, 5, 5)
    assert tool.session.selected_patch_ids == (first.created_patch_id,)

    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}reset_properties", ctx)
    tool._workspace_machine.set_property_selection_mode(ClothPropertySelectionMode.GROUP)
    _click(tool, ctx, 5, 5)
    assert set(tool.session.selected_patch_ids) == {first.created_patch_id, second.created_patch_id}
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert _button(window, "Pattern").enabled is True
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}set_function_pattern", ctx)
    assert all(patch.function is ClothPatchFunction.PATTERN for patch in tool.session.document.patches.values())


def test_double_click_empty_clears_mixed_main_selection() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    face = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    assert face.committed
    _click(tool, ctx, 5, 5)
    assert tool.session.selected_patch_ids
    tool._double_click_main(ctx, (1000, 1000))
    assert not tool.session.selected_patch_ids
    assert not tool.session.selected_curve_ids
    assert tool.geometry_trace.smart_session.selected_region_count == 0


def test_draw_modify_selects_unique_face_and_delete_removes_it() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    outcome = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    assert outcome.committed
    tool._enter_draw(ctx, ClothDrawMode.MODIFY)
    tool._workspace_machine.set_draw_pick_mode(tool._workspace.draw_pick_mode.FACE)
    _click(tool, ctx, 5, 5)
    assert tool.session.selected_patch_ids == (outcome.created_patch_id,)
    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="delete"), ctx)
    assert not tool.session.document.patches


def test_renderer_shows_points_only_in_draw_and_preserves_role_colours() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    normal = tool._drawing.create_surface_from_positions(((0, 0, 0), (8, 0, 0), (8, 8, 0), (0, 8, 0)))
    pattern = tool._drawing.create_surface_from_positions(((12, 0, 0), (20, 0, 0), (20, 8, 0), (12, 8, 0)))
    anchor = tool._drawing.create_surface_from_positions(((24, 0, 0), (32, 0, 0), (32, 8, 0), (24, 8, 0)))
    tool.session.document.set_patch_properties((pattern.created_patch_id,), function=ClothPatchFunction.PATTERN)
    tool.session.document.set_patch_properties((anchor.created_patch_id,), function=ClothPatchFunction.JUNCTION)
    tool._enter_main(ctx)
    tool._renderer.sync(ctx)
    items = ctx.projected_drawing.for_tool(tool.id).items()
    ids = {item.id for item in items}
    assert not any(value.startswith("cloth:point:") for value in ids)
    assert f"cloth:surface:function:{pattern.created_patch_id}" in ids
    assert f"cloth:surface:function:{anchor.created_patch_id}" in ids

    tool._enter_draw(ctx, ClothDrawMode.MODIFY)
    tool._renderer.sync(ctx)
    ids = {item.id for item in ctx.projected_drawing.for_tool(tool.id).items()}
    assert any(value.startswith("cloth:point:") for value in ids)


def test_apply_generates_folded_output_and_linked_flat_preview() -> None:
    from types import SimpleNamespace
    from laserprog_studio.project import ProjectStore

    store = ProjectStore.new_empty(scene_name="Main")
    owner = SimpleNamespace(
        project_store=store,
        rebuild_scene=lambda **_kwargs: None,
        update_preview_state=lambda: None,
        _sync_history_buttons=lambda: None,
        sync_scene_tabs=lambda: None,
        update_project_title=lambda: None,
        update_inspector=lambda: None,
    )
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store.active_model_store)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    outcome = tool._drawing.create_surface_from_positions(((0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)))
    assert outcome.committed
    source_scene_id = store.active_scene_id
    assert tool._apply_and_continue(ctx)
    assert store.active_scene_id == source_scene_id
    folded = store.active_model_store.committed_meshes[0]
    linked_flat = folded.metadata.get("cloth_linked_flat_scene_id")
    assert linked_flat and linked_flat in set(store.scenes)
    assert tool._workspace.overlay_mode is ClothOverlayMode.MAIN


def test_persistent_textile_group_counts_as_one_close_anchor() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    second = tool._drawing.create_surface_from_positions(((10, 0, 0), (20, 0, 0), (20, 10, 0), (10, 10, 0)))
    assert first.committed and second.committed

    # Textile selection is based on a persistent authored group identity. The
    # surface API is only used before Take face, not to merge textile groups.
    assign_logical_patch_group(
        tool.session.document,
        (first.created_patch_id, second.created_patch_id),
        "persistent_pair",
        origin="take_face",
    )
    tool._set_selected_textile_groups(((first.created_patch_id,),))
    tool._sync_workspace_selection()
    assert set(tool.session.selected_patch_ids) == {first.created_patch_id, second.created_patch_id}
    assert tool._workspace.selected_textile_faces == 1
    assert tool._workspace.can_close is True


def test_close_uses_complete_boundary_of_multi_patch_logical_group() -> None:
    from laserprog_studio.tooling.cloth.join_faces import _patch_group_boundary, analyze_textile_close_groups
    from laserprog_studio.tooling.cloth.models import ClothDocument

    document = ClothDocument()
    positions = {
        "a": (0, 0, 0), "b": (10, 0, 0), "c": (20, 0, 0),
        "d": (0, 10, 0), "e": (10, 10, 0), "f": (20, 10, 0),
        "g": (0, 20, 0), "h": (20, 20, 0), "i": (20, 30, 0), "j": (0, 30, 0),
    }
    for point_id, position in positions.items():
        document.add_point(position, point_id=point_id)
    for curve_id, start, end in (
        ("ab", "a", "b"), ("be", "b", "e"), ("ed", "e", "d"), ("da", "d", "a"),
        ("bc", "b", "c"), ("cf", "c", "f"), ("fe", "f", "e"),
        ("gh", "g", "h"), ("hi", "h", "i"), ("ij", "i", "j"), ("jg", "j", "g"),
    ):
        document.add_line(start, end, curve_id=curve_id)
    left = document.add_patch(("ab", "be", "ed", "da"), patch_id="left")
    right = document.add_patch(("bc", "cf", "fe", "be"), patch_id="right")
    upper = document.add_patch(("gh", "hi", "ij", "jg"), patch_id="upper")

    proposals = analyze_textile_close_groups(document, ((left.id, right.id), (upper.id,)))
    assert proposals
    proposal = proposals[0]
    assert set(proposal.patch_ids) == {left.id, right.id, upper.id}
    assert proposal.pairs
    # The logical boundary spans the full 20 mm width and removes the shared
    # technical edge between the two member patches.
    group_boundary = _patch_group_boundary(document, (left.id, right.id))
    xs = [point[0] for point in group_boundary]
    assert min(xs) <= 1.0e-6
    assert max(xs) >= 20.0 - 1.0e-6

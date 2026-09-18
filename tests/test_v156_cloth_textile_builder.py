from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.drawing import ClothDrawingController
from laserprog_studio.tooling.cloth.join_faces import analyze_patch_join, commit_join_proposal
from laserprog_studio.tooling.cloth.models import ClothDocument, ClothPatchFunction
from laserprog_studio.tooling.cloth.serialization import cloth_document_from_dict, cloth_document_to_dict
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth.workspace import ClothDrawMode, ClothOverlayMode, ClothWorkspaceMachine, ClothWorkspacePhase
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _square_mesh() -> WorkMesh:
    return WorkMesh("support", [(0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)], [(0, 1, 2), (0, 2, 3)])


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float, *, shift: bool = False, ctrl: bool = False) -> None:
    modifiers = set()
    if shift:
        modifiers.add("shift")
    if ctrl:
        modifiers.add("ctrl")
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, 0), button=MouseButton.LEFT, modifiers=frozenset(modifiers))
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, 0), button=MouseButton.LEFT, modifiers=frozenset(modifiers))
    tool.on_event(press, ctx)
    assert tool.on_event(release, ctx)


def test_workspace_machine_has_clear_intent_states() -> None:
    machine = ClothWorkspaceMachine()
    machine.enter_main()
    assert machine.state.overlay_mode is ClothOverlayMode.MAIN
    assert machine.state.phase is ClothWorkspacePhase.SELECTING
    machine.update_selection(textile_faces=2)
    assert machine.state.can_close
    machine.enter_close(proposals=1)
    assert machine.state.phase is ClothWorkspacePhase.REVIEWING_CLOSE
    machine.enter_draw(ClothDrawMode.POLYLINE)
    assert machine.state.phase is ClothWorkspacePhase.DRAWING
    machine.enter_properties()
    assert machine.state.phase is ClothWorkspacePhase.EDITING_PROPERTIES


def test_overlay_exposes_only_new_primary_workflow() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    labels = [button.display_label for button in window.buttons]
    assert labels == ["Take face", "Close", "Draw", "Properties", "Apply"]
    assert window.accent_color == "#38BDF8"


def test_add_mesh_faces_creates_textile_from_one_smart_surface() -> None:
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
                "world_pos": (5.0, 2.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    _click(tool, ctx, 5.0, 2.0)
    assert tool.geometry_trace.smart_session.selected_region_count == 1
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}create_source_textile", ctx)
    assert len(tool.session.document.patches) == 1
    patch = next(iter(tool.session.document.patches.values()))
    assert patch.function is ClothPatchFunction.TEXTILE
    assert patch.layer_id == "layer1"


def test_join_assistant_builds_editable_ruled_panels() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    assert drawing.create_surface_from_positions(((0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0))).committed
    assert drawing.create_surface_from_positions(((0, 0, 10), (20, 0, 10), (20, 10, 10), (0, 10, 10))).committed
    anchors = tuple(document.patches)
    proposals = analyze_patch_join(document, anchors)
    assert proposals and proposals[0].confidence > 0.8
    before = len(document.patches)
    outcome = commit_join_proposal(document, proposals[0], drawing=drawing)
    assert outcome.committed
    assert len(document.patches) > before
    assert all(patch.metadata.get("cloth_creation_kind") == "join_faces" for patch in list(document.patches.values())[before:])


def test_patch_functions_layers_and_materials_round_trip() -> None:
    document = ClothDocument()
    drawing = ClothDrawingController(document)
    outcome = drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    patch_id = outcome.created_patch_id
    document.set_patch_properties((patch_id,), function=ClothPatchFunction.JUNCTION, layer_id="lining", material_name="Cotton")
    payload = cloth_document_to_dict(document)
    restored = cloth_document_from_dict(payload)
    assert restored.patches[patch_id].function is ClothPatchFunction.JUNCTION
    assert restored.patches[patch_id].layer_id == "lining"
    assert restored.patches[patch_id].material_name == "Cotton"
    assert "lining" in restored.layers


def test_join_faces_ui_selects_multiple_panels_and_accepts_preview() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    drawing = tool._drawing
    assert drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0))).committed
    assert drawing.create_surface_from_positions(((30, 0, 0), (40, 0, 0), (40, 10, 0), (30, 10, 0))).committed
    _click(tool, ctx, 5, 5)
    _click(tool, ctx, 35, 5, shift=True)
    assert len(tool.session.selected_patch_ids) == 2
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}open_close", ctx)
    assert tool.interaction.join_proposals
    before_ids = set(tool.session.document.patches)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}apply_close", ctx)
    created_ids = tuple(patch_id for patch_id in tool.session.document.patches if patch_id not in before_ids)
    assert created_ids
    assert len(created_ids) > 1  # A full closure is a ruled strip, not one local quad.
    group_ids = {tool.session.document.patches[patch_id].metadata.get("cloth_logical_group_id") for patch_id in created_ids}
    assert len(group_ids) == 1
    assert None not in group_ids
    assert not tool.interaction.join_proposals


def test_textile_properties_buttons_change_function_and_inspector_changes_layer_material() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    outcome = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    patch_id = outcome.created_patch_id
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}workspace_properties", ctx)
    _click(tool, ctx, 5, 5)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}set_function_pattern", ctx)
    tool._on_value_changed(ctx, "cloth_patch_layer", "decoration")
    tool._on_value_changed(ctx, "cloth_patch_material", "Felt")
    patch = tool.session.document.patches[patch_id]
    assert patch.function is ClothPatchFunction.PATTERN
    assert patch.layer_id == "decoration"
    assert patch.material_name == "Felt"
    assert "decoration" in tool.session.document.layers


def test_schema_v1_cloth_remains_detectable_and_restorable() -> None:
    from laserprog_studio.domain.work_model import WorkMesh
    from laserprog_studio.tooling.cloth.serialization import CLOTH_SOURCE_KEY, cloth_output_kind, restore_cloth_source

    mesh = WorkMesh("legacy", [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])
    mesh.metadata[CLOTH_SOURCE_KEY] = {
        "schema_version": 1,
        "output_kind": "folded",
        "document": {
            "schema_version": 1,
            "revision": 0,
            "next_id": 8,
            "metadata": {},
            "points": [
                {"id": "p1", "position": [0, 0, 0], "metadata": {}},
                {"id": "p2", "position": [1, 0, 0], "metadata": {}},
                {"id": "p3", "position": [0, 1, 0], "metadata": {}},
            ],
            "curves": [
                {"id": "c1", "kind": "line", "point_ids": ["p1", "p2"], "role": "boundary", "closed": False, "metadata": {}},
                {"id": "c2", "kind": "line", "point_ids": ["p2", "p3"], "role": "boundary", "closed": False, "metadata": {}},
                {"id": "c3", "kind": "line", "point_ids": ["p3", "p1"], "role": "boundary", "closed": False, "metadata": {}},
            ],
            "patches": [{"id": "panel1", "outer_curve_ids": ["c1", "c2", "c3"], "name": "Legacy", "metadata": {}}],
            "folds": [],
            "seams": [],
        },
    }
    assert cloth_output_kind(mesh) == "folded"
    restored = restore_cloth_source(mesh)
    assert restored is not None
    document, output_kind = restored
    assert output_kind == "folded"
    assert document.patches["panel1"].layer_id == "layer1"
    assert document.patches["panel1"].function is ClothPatchFunction.TEXTILE


def test_selected_panel_name_and_layer_thickness_are_editable() -> None:
    ctx = ToolContext()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    outcome = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    patch_id = outcome.created_patch_id
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}workspace_properties", ctx)
    _click(tool, ctx, 5, 5)
    tool._on_value_changed(ctx, "cloth_patch_name", "Outer panel")
    tool._on_value_changed(ctx, "cloth_layer_thickness", 1.4)
    patch = tool.session.document.patches[patch_id]
    assert patch.name == "Outer panel"
    assert tool.session.document.layers[patch.layer_id].thickness_mm == 1.4

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Superseded by the v158 single-overlay Cloth UX contract.")

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.interaction import ClothUxStage
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth.workspace import ClothDrawTool, ClothWorkspacePhase, ClothWorkspaceMachine
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _square(name: str, x: float) -> WorkMesh:
    return WorkMesh(
        name,
        [(x, 0, 0), (x + 10, 0, 0), (x + 10, 10, 0), (x, 10, 0)],
        [(0, 1, 2), (0, 2, 3)],
    )


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float, *, shift: bool = False) -> None:
    modifiers = frozenset({"shift"} if shift else ())
    tool.on_event(ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), button=MouseButton.LEFT, modifiers=modifiers), ctx)
    assert tool.on_event(ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), button=MouseButton.LEFT, modifiers=modifiers), ctx)


def test_public_workspace_names_describe_domain_transition() -> None:
    machine = ClothWorkspaceMachine()
    assert machine.state.draw_tool is ClothDrawTool.CREATE_FROM_MESH
    assert machine.state.phase is ClothWorkspacePhase.SELECTING_MESH_SURFACES
    machine.update_source_selection(regions=2, meshes=2)
    assert machine.state.phase is ClothWorkspacePhase.MESH_SURFACES_READY
    assert "copy them into Cloth" in machine.state.message
    machine.mark_textile_created(patches=2, origin="mesh")
    assert machine.state.phase is ClothWorkspacePhase.TEXTILE_CREATED
    assert machine.state.can_use_created_textile


def test_overlay_uses_unambiguous_cloth_labels() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    labels = {button.display_label for button in window.buttons}
    assert "Create from mesh" in labels
    assert "Join textile faces" in labels
    assert "Add mesh faces" not in labels
    assert "Join faces" not in labels


def test_created_mesh_faces_remain_selected_and_flow_into_join() -> None:
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [_square("left", 0), _square("right", 30)]))
    objects = ctx.document.objects()

    class Scene:
        def pick_object_at(self, _screen_pos, **_filters):
            return None

        def pick_face_at(self, screen_pos, **_filters):
            index = 0 if screen_pos[0] < 20 else 1
            obj = objects[index]
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": index,
                "element_index": 0,
                "world_pos": (5.0 if index == 0 else 35.0, 5.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

    ctx.scene = Scene()
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    tool = ClothCreatorTool()
    tool.open(ctx)
    _click(tool, ctx, 5, 5)
    _click(tool, ctx, 35, 5, shift=True)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}create_source_textile", ctx)

    created = tool.session.selected_patch_ids
    assert len(created) == 2
    assert all(patch_id in tool.session.document.patches for patch_id in created)
    assert tool._workspace.phase is ClothWorkspacePhase.TEXTILE_CREATED

    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}join_created_textile", ctx)
    assert tool.interaction.stage is ClothUxStage.SELECT_JOIN_FACES
    assert tool.session.selected_patch_ids == created
    assert tool.interaction.join_proposals


def test_create_more_returns_to_empty_temporary_mesh_selection() -> None:
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [_square("support", 0)]))
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
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}create_source_textile", ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}create_more_from_mesh", ctx)
    assert tool.geometry_trace.smart_session.selected_region_count == 0
    assert tool._workspace.selected_source_regions == 0
    assert tool._workspace.phase is ClothWorkspacePhase.SELECTING_MESH_SURFACES


def test_workflow_step_and_inspector_visibility_follow_active_domain() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    assert ctx.workflow.state.active_id == "opening"

    tool._start_new(ctx)
    tool._enter_draw_tool(ctx, ClothDrawTool.CREATE_FROM_MESH)
    assert ctx.workflow.state.active_id == "faces"
    assert ctx.inspector.field_state("cloth_surface_auto").visible is True
    assert ctx.inspector.field_state("cloth_patch_name").visible is False

    tool._enter_textile_properties(ctx)
    assert ctx.workflow.state.active_id == "properties"
    assert ctx.inspector.field_state("cloth_surface_auto").visible is False
    assert ctx.inspector.field_state("cloth_patch_name").visible is True

# -*- coding: utf-8 -*-
from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _square(name: str, x_offset: float = 0.0) -> WorkMesh:
    return WorkMesh(
        name,
        [
            (x_offset + 0.0, 0.0, 0.0),
            (x_offset + 20.0, 0.0, 0.0),
            (x_offset + 20.0, 10.0, 0.0),
            (x_offset + 0.0, 10.0, 0.0),
        ],
        [(0, 1, 2), (0, 2, 3)],
    )


def test_pointer_machine_uses_short_explicit_double_click_interval() -> None:
    machine = surface_selection.SurfaceSelectionPointerMachine(double_click_interval_ms=260.0)

    machine.press((10.0, 10.0))
    assert machine.release((10.0, 10.0), now_s=1.000) is surface_selection.SurfaceSelectionPointerAction.CLICK
    machine.press((11.0, 10.0))
    assert machine.release((11.0, 10.0), now_s=1.240) is surface_selection.SurfaceSelectionPointerAction.DOUBLE_CLICK

    machine.press((10.0, 10.0))
    assert machine.release((10.0, 10.0), now_s=2.000) is surface_selection.SurfaceSelectionPointerAction.CLICK
    machine.press((10.0, 10.0))
    assert machine.release((10.0, 10.0), now_s=2.310) is surface_selection.SurfaceSelectionPointerAction.CLICK


def test_session_policy_can_select_complete_regions_on_several_meshes() -> None:
    first = surface_selection.SurfaceMeshSnapshot.from_mesh(_square("A"), object_id="a")
    second = surface_selection.SurfaceMeshSnapshot.from_mesh(_square("B", 30.0), object_id="b")
    session = surface_selection.SurfaceSelectionSession(
        mesh_policy=surface_selection.SurfaceSelectionMeshPolicy.MULTIPLE_MESHES,
    )

    session.adopt(first, surface_selection.auto_surface_region(first, 0))
    session.add_region(second, surface_selection.auto_surface_region(second, 0))

    assert session.selected_mesh_count == 2
    assert session.selected_region_count == 2
    assert session.selection_mode == "multiple"
    assert session.selected_faces_by_object == {"a": (0, 1), "b": (0, 1)}


def test_single_mesh_policy_restarts_when_shift_selection_hits_another_mesh() -> None:
    first = surface_selection.SurfaceMeshSnapshot.from_mesh(_square("A"), object_id="a")
    second = surface_selection.SurfaceMeshSnapshot.from_mesh(_square("B", 30.0), object_id="b")
    session = surface_selection.SurfaceSelectionSession(
        mesh_policy=surface_selection.SurfaceSelectionMeshPolicy.SINGLE_MESH,
    )
    session.adopt(first, surface_selection.auto_surface_region(first, 0))
    session.add_region(second, surface_selection.auto_surface_region(second, 0))

    assert session.selected_mesh_count == 1
    assert session.selected_faces_by_object == {"b": (0, 1)}


def test_cloth_face_mode_uses_smart_regions_and_shift_adds_another_mesh() -> None:
    ctx = ToolContext()
    meshes = [_square("A"), _square("B", 30.0)]
    ctx.document.bind(SceneDocument.from_meshes("main", meshes))
    objects = ctx.document.objects()

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            object_index = 0 if float(screen_pos[0]) < 25.0 else 1
            obj = objects[object_index]
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": object_index,
                "element_index": 0,
                "world_pos": (5.0 if object_index == 0 else 35.0, 2.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_mesh_trace", ctx)

    first_press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(5.0, 2.0), button=MouseButton.LEFT)
    first_release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(5.0, 2.0), button=MouseButton.LEFT)
    assert tool.on_event(first_press, ctx) is False
    assert tool.on_event(first_release, ctx)
    assert len(tool.geometry_trace.selected_faces) == 2

    second_press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(35.0, 2.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"shift"}),
    )
    second_release = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(35.0, 2.0),
        button=MouseButton.LEFT,
        modifiers=frozenset({"shift"}),
    )
    assert tool.on_event(second_press, ctx) is False
    assert tool.on_event(second_release, ctx)

    assert tool.geometry_trace.smart_session.selected_mesh_count == 2
    assert len(tool.geometry_trace.selected_faces) == 4
    assert len({item.object_id for item in tool.geometry_trace.selected_faces}) == 2

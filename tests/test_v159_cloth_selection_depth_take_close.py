from __future__ import annotations

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project.scene_document import SceneDocument
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.cloth.interaction import ClothUxStage
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth.workspace import ClothOverlayMode
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool


def _square_mesh(z: float = 0.0) -> WorkMesh:
    return WorkMesh(
        "support",
        [(0, 0, z), (20, 0, z), (20, 10, z), (0, 10, z)],
        [(0, 1, 2), (0, 2, 3)],
    )


def _scene_for_object(obj, *, z: float = 0.0):
    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            x, y = screen_pos
            if not (0 <= x <= 20 and 0 <= y <= 10):
                return None
            return {
                "kind": "face",
                "object_id": obj.id,
                "object_index": 0,
                "element_index": 0,
                "world_pos": (float(x), float(y), float(z)),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    return Scene()


def test_single_click_empty_clears_mixed_selection() -> None:
    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    created = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    assert created.committed
    tool._select_main(ctx, (5, 5), additive=False)
    assert tool.session.selected_patch_ids

    tool._select_main(ctx, (1000, 1000), additive=True)
    assert not tool.session.selected_patch_ids
    assert not tool.session.selected_curve_ids
    assert tool.geometry_trace.smart_session.selected_region_count == 0


def test_frontmost_scene_mesh_wins_over_textile_behind() -> None:
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [_square_mesh(0.0)]))
    obj = ctx.document.objects()[0]
    ctx.scene = _scene_for_object(obj, z=0.0)
    ctx.viewport.screen_to_ray = lambda screen_pos: {
        "kind": "ray", "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 10.0),
        "metadata": {"direction": (0.0, 0.0, -1.0)},
    }
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    behind = tool._drawing.create_surface_from_positions(((0, 0, -1), (20, 0, -1), (20, 10, -1), (0, 10, -1)))
    assert behind.committed

    tool._select_main(ctx, (5, 5), additive=False)
    assert not tool.session.selected_patch_ids
    assert tool.geometry_trace.smart_session.selected_region_count == 1


def test_frontmost_textile_wins_over_mesh_behind_and_coplanar_textile_is_editable() -> None:
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [_square_mesh(0.0)]))
    obj = ctx.document.objects()[0]
    ctx.scene = _scene_for_object(obj, z=0.0)
    ctx.viewport.screen_to_ray = lambda screen_pos: {
        "kind": "ray", "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 10.0),
        "metadata": {"direction": (0.0, 0.0, -1.0)},
    }
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    front = tool._drawing.create_surface_from_positions(((0, 0, 0.5), (20, 0, 0.5), (20, 10, 0.5), (0, 10, 0.5)))
    assert front.committed

    tool._select_main(ctx, (5, 5), additive=False)
    assert tool.session.selected_patch_ids == (front.created_patch_id,)
    assert tool.geometry_trace.smart_session.selected_region_count == 0

    # A copied textile face can be exactly coincident with its source mesh. In
    # that tiny depth tie, the editable textile domain remains selectable.
    ctx2 = ToolContext()
    ctx2.document.bind(SceneDocument.from_meshes("main", [_square_mesh(0.0)]))
    obj2 = ctx2.document.objects()[0]
    ctx2.scene = _scene_for_object(obj2, z=0.0)
    ctx2.viewport.screen_to_ray = lambda screen_pos: {
        "kind": "ray", "world_pos": (float(screen_pos[0]), float(screen_pos[1]), 10.0),
        "metadata": {"direction": (0.0, 0.0, -1.0)},
    }
    tool2 = ClothCreatorTool()
    tool2.open(ctx2)
    tool2._start_new(ctx2)
    coplanar = tool2._drawing.create_surface_from_positions(((0, 0, 0), (20, 0, 0), (20, 10, 0), (0, 10, 0)))
    assert coplanar.committed
    tool2._select_main(ctx2, (5, 5), additive=False)
    assert coplanar.created_patch_id in tool2.session.selected_patch_ids


def test_take_face_keeps_disconnected_source_regions_as_separate_textile_groups() -> None:
    mesh = WorkMesh(
        "two islands",
        [
            (0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
            (30, 0, 0), (40, 0, 0), (40, 10, 0), (30, 10, 0),
        ],
        [(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)],
    )
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [mesh]))
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            x, y = screen_pos
            if 0 <= x <= 10 and 0 <= y <= 10:
                face = 0
            elif 30 <= x <= 40 and 0 <= y <= 10:
                face = 2
            else:
                return None
            return {
                "kind": "face", "object_id": obj.id, "object_index": 0,
                "element_index": face, "world_pos": (float(x), float(y), 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    tool._select_main(ctx, (5, 5), additive=False)
    tool._select_main(ctx, (35, 5), additive=True)
    assert tool.geometry_trace.smart_session.selected_region_count == 2

    tool._create_source_textile(ctx)
    groups = tool._selected_textile_patch_groups()
    assert len(groups) == 2
    assert len(tool.session.document.patches) == 2
    assert tool._workspace.selected_textile_faces == 2
    assert tool._workspace.can_close


def test_take_face_copies_curved_selection_strictly_without_outer_cap() -> None:
    mesh = WorkMesh(
        "bent",
        [(0, 0, 0), (10, 0, 0), (0, 10, 0), (10, 10, 2)],
        [(0, 1, 2), (1, 3, 2)],
    )
    ctx = ToolContext()
    ctx.document.bind(SceneDocument.from_meshes("main", [mesh]))
    obj = ctx.document.objects()[0]

    class Scene:
        def pick_face_at(self, screen_pos, **_filters):
            return {
                "kind": "face", "object_id": obj.id, "object_index": 0,
                "element_index": 0, "world_pos": (2.0, 2.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
            }

        def pick_object_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = Scene()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    tool.geometry_trace.set_smart_tolerance(1.0)
    tool._select_main(ctx, (2, 2), additive=False)
    assert len(tool.geometry_trace.selected_faces) == 2

    tool._create_source_textile(ctx)
    # The bent quad is not replaced by one planar polygon. Its two selected
    # source triangles remain two technical textile patches in one logical group.
    assert len(tool.session.document.patches) == 2
    assert len(tool._selected_textile_patch_groups()) == 1
    assert {
        tuple(patch.metadata.get("cloth_source_faces") or ())
        for patch in tool.session.document.patches.values()
    } == {(0,), (1,)}


def test_close_solver_failure_keeps_orange_overlay_and_reset_available(monkeypatch) -> None:
    import laserprog_studio.tooling.cloth_tool as cloth_tool_module

    ctx = ToolContext()
    tool = ClothCreatorTool()
    tool.open(ctx)
    tool._start_new(ctx)
    first = tool._drawing.create_surface_from_positions(((0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)))
    second = tool._drawing.create_surface_from_positions(((20, 0, 0), (30, 0, 0), (30, 10, 0), (20, 10, 0)))
    assert first.committed and second.committed
    tool._set_selected_textile_groups(((first.created_patch_id,), (second.created_patch_id,)))
    tool._sync_workspace_selection()

    def fail(*_args, **_kwargs):
        raise RuntimeError("diagnostic failure")

    monkeypatch.setattr(cloth_tool_module, "analyze_textile_close_groups", fail)
    tool._enter_close(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert window is not None
    assert window.accent_color == "#F59E0B"
    assert tool._workspace.overlay_mode is ClothOverlayMode.CLOSE
    assert tool.interaction.stage is ClothUxStage.CLOSE
    assert [button.display_label for button in window.buttons] == ["Apply", "Prev", "Next", "Reset"]

    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}reset_close", ctx)
    assert tool._workspace.overlay_mode is ClothOverlayMode.MAIN
    assert ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID) is not None

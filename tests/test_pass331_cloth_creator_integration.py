# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from laserprog_studio.project import ProjectStore
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.cloth.models import ClothWorkflowPhase
from laserprog_studio.tooling.cloth.serialization import restore_cloth_source
from laserprog_studio.tooling.cloth.workflow_overlay import CLOTH_ACTION_PREFIX, CLOTH_WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.cloth_tool import ClothCreatorTool
from laserprog_studio.tooling.ids import TOOL_CLOTH
from laserprog_studio.tooling.registry import get_studio_tool, get_tool_spec
from laserprog_studio.ui.toolbar_catalog import get_toolbar_item_spec
from laserprog_studio.ui.toolbar_icons import toolbar_icon_path
from laserprog_studio.ui.tool_panel_catalog import get_tool_panel_spec
from laserprog_studio.tooling.help_docs import get_tool_help_document


def _context(*, project: bool = False) -> tuple[ToolContext, ProjectStore | None]:
    if project:
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
    else:
        store = None
        ctx = ToolContext()
    ctx.viewport.screen_to_world_on_plane = lambda screen, _plane: (float(screen[0]), float(screen[1]), 0.0)
    ctx.viewport.world_to_screen = lambda point: (float(point[0]), float(point[1]))
    return ctx, store


def _click(tool: ClothCreatorTool, ctx: ToolContext, x: float, y: float) -> bool:
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(x, y), world_pos=(x, y, 0.0), button=MouseButton.LEFT)
    assert tool.on_event(press, ctx) is False
    return bool(tool.on_event(release, ctx))


def _draw_panel(tool: ClothCreatorTool, ctx: ToolContext) -> None:
    for x, y in ((0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0)):
        assert _click(tool, ctx, x, y)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}close_polyline", ctx)


def test_cloth_is_registered_as_a_real_creator_tool_with_a_light_icon() -> None:
    spec = get_tool_spec(TOOL_CLOTH)
    assert spec is not None and spec.panel_index == 34 and spec.open_without_initial_selection
    assert type(get_studio_tool(TOOL_CLOTH)).__name__ == "ClothTool"
    toolbar = get_toolbar_item_spec("tool:cloth")
    assert toolbar is not None and toolbar.tool_id == TOOL_CLOTH and toolbar.default_visible is False
    panel = get_tool_panel_spec(TOOL_CLOTH)
    assert panel is not None and panel.panel_index == 34 and panel.builder == "panel_declarative_creator_tool"
    help_doc = get_tool_help_document(TOOL_CLOTH)
    assert help_doc is not None and "flat pattern" in help_doc.as_markdown().lower()
    icon = Path(toolbar_icon_path("tool:cloth") or "")
    assert icon.exists() and icon.stat().st_size < 16_000


def test_cloth_opens_with_a_compact_free_3d_command_deck_and_inspector() -> None:
    ctx, _ = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    window = ctx.overlay.window(CLOTH_WORKFLOW_WINDOW_ID)
    assert window is not None and window.visible
    assert window.owner_tool == TOOL_CLOTH
    assert window.title == "Cloth · Textile Builder"
    button_ids = {button.id for button in window.buttons}
    assert {
        f"{CLOTH_ACTION_PREFIX}workspace_draw",
        f"{CLOTH_ACTION_PREFIX}workspace_properties",
        f"{CLOTH_ACTION_PREFIX}draw_create_from_mesh",
        f"{CLOTH_ACTION_PREFIX}draw_join_textile_faces",
        f"{CLOTH_ACTION_PREFIX}draw_polyline",
        f"{CLOTH_ACTION_PREFIX}cancel",
    }.issubset(button_ids)
    assert not any("plane" in button_id for button_id in button_ids)
    assert len(window.fields) == 2  # compact Mode + Status only
    assert ctx.inspector.panel is not None and ctx.inspector.panel.id == "cloth.tool"
    assert tuple(step.id for step in ctx.workflow.state.steps) == ("opening", "faces", "properties", "flat")


def test_world_plane_closed_polyline_creates_one_surface_panel_and_flat_preview() -> None:
    ctx, _ = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    _draw_panel(tool, ctx)
    assert tool.session.phase is ClothWorkflowPhase.EDITING
    assert len(tool.session.document.points) == 4
    assert len(tool.session.document.curves) == 4
    assert len(tool.session.document.patches) == 1
    assert tool.can_apply(ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}preview_flat", ctx)
    assert tool.session.phase is ClothWorkflowPhase.FLAT_PREVIEW
    assert tool.interaction.flat_preview_mesh is not None
    ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_CLOTH).items()}
    assert {"cloth:surface", "cloth:flat_preview"}.issubset(ids)


def test_real_pointer_drag_remains_camera_navigation_and_does_not_draw() -> None:
    ctx, _ = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    press = ToolEvent(ToolEventType.MOUSE_PRESS, screen_pos=(0.0, 0.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_press_passthrough(press, ctx)
    release = ToolEvent(ToolEventType.MOUSE_RELEASE, screen_pos=(30.0, 20.0), button=MouseButton.LEFT)
    assert tool.wants_pointer_release_passthrough(release, ctx)
    assert tool.on_event(release, ctx) is False
    assert not tool._drawing.pending_world_points
    assert not tool.session.document.points


def test_apply_creates_linked_folded_and_flat_surface_scenes_and_keeps_source_active() -> None:
    ctx, project = _context(project=True)
    assert project is not None
    tool = ClothCreatorTool()
    tool.open(ctx)
    _draw_panel(tool, ctx)
    source_scene_id = project.active_scene_id
    assert tool.apply(ctx)
    assert project.active_scene_id == source_scene_id
    assert len(project.scenes) == 2
    scenes = list(project.scenes.values())
    folded = scenes[0].model_store.committed_meshes[0]
    flat = scenes[1].model_store.committed_meshes[0]
    assert folded.metadata["cloth_output_kind"] == "folded"
    assert flat.metadata["cloth_output_kind"] == "flat"
    assert folded.metadata["cloth_linked_flat_scene_id"] == scenes[1].scene_id
    assert restore_cloth_source(folded) is not None
    assert restore_cloth_source(flat) is not None
    assert all(abs(float(vertex[2])) < 1.0e-9 for vertex in flat.vertices)


def test_escape_cancels_only_the_current_primitive_and_keeps_committed_panels() -> None:
    ctx, _ = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    _draw_panel(tool, ctx)
    assert _click(tool, ctx, 50.0, 0.0)
    assert tool._drawing.pending_world_points
    assert tool.on_event(ToolEvent(ToolEventType.KEY_PRESS, key="Escape"), ctx)
    assert not tool._drawing.pending_world_points
    assert len(tool.session.document.patches) == 1


def test_two_coplanar_panels_share_one_edge_then_fold_into_3d() -> None:
    ctx, _ = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    for x, y in ((0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (0.0, 30.0)):
        assert _click(tool, ctx, x, y)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}close_polyline", ctx)
    for x, y in ((30.0, 0.0), (60.0, 0.0), (60.0, 30.0), (30.0, 30.0)):
        assert _click(tool, ctx, x, y)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}close_polyline", ctx)

    assert len(tool.session.document.patches) == 2
    assert len(tool.session.document.points) == 6
    assert len(tool.session.document.folds) == 1

    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_fold", ctx)
    assert _click(tool, ctx, 30.0, 15.0)
    assert tool.interaction.selected_fold_id is not None
    tool._on_value_changed(ctx, "cloth_fold_angle", 90.0)
    moving_z = [point.position[2] for point in tool.session.document.points.values() if point.position[0] > 30.0]
    assert moving_z and all(abs(value) > 1.0 for value in moving_z)
    assert tool.can_apply(ctx)


def test_applied_cloth_has_yellow_reopen_hover_and_reuses_the_linked_flat_scene() -> None:
    ctx, project = _context(project=True)
    assert project is not None
    first = ClothCreatorTool()
    first.open(ctx)
    _draw_panel(first, ctx)
    assert first.apply(ctx)
    folded = project.active_model_store.committed_meshes[0]
    flat_scene_id = folded.metadata["cloth_linked_flat_scene_id"]

    class PickScene:
        def pick_object_at(self, _screen_pos, **_filters):
            return {"kind": "object", "object_id": folded.mesh_id, "object_index": 0}

        def pick_face_at(self, _screen_pos, **_filters):
            return None

    ctx.scene = PickScene()
    second = ClothCreatorTool()
    second.open(ctx)
    second.on_event(ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=(5.0, 5.0), button=MouseButton.NONE), ctx)
    ids = {item.id for item in ctx.projected_drawing.for_tool(TOOL_CLOTH).items()}
    assert "cloth:editable_hover:0" in ids
    assert _click(second, ctx, 5.0, 5.0)
    assert second.session.editing_existing
    assert second.interaction.source_flat_scene_id == flat_scene_id
    second.session.document.move_point(next(iter(second.session.document.points)), (-2.0, 0.0, 0.0))
    assert second.apply(ctx)
    assert len(project.scenes) == 2
    assert flat_scene_id in project.scenes


def test_modify_mode_drags_a_free_panel_vertex_without_rebuilding_the_tool() -> None:
    ctx, _ = _context()
    tool = ClothCreatorTool()
    tool.open(ctx)
    _draw_panel(tool, ctx)
    tool.on_overlay_button_clicked(f"{CLOTH_ACTION_PREFIX}mode_modify", ctx)
    tool._smart_snap = False

    point_id = next(
        point.id
        for point in tool.session.document.points.values()
        if point.position == (0.0, 0.0, 0.0)
    )
    press = ToolEvent(
        ToolEventType.MOUSE_PRESS,
        screen_pos=(0.0, 0.0),
        world_pos=(0.0, 0.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert tool.wants_pointer_press_passthrough(press, ctx) is False
    assert tool.on_event(press, ctx) is True
    move = ToolEvent(
        ToolEventType.MOUSE_MOVE,
        screen_pos=(-5.0, 5.0),
        world_pos=(-5.0, 5.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert tool.on_event(move, ctx) is True
    release = ToolEvent(
        ToolEventType.MOUSE_RELEASE,
        screen_pos=(-5.0, 5.0),
        world_pos=(-5.0, 5.0, 0.0),
        button=MouseButton.LEFT,
    )
    assert tool.on_event(release, ctx) is True
    assert tool.session.document.points[point_id].position == (-5.0, 5.0, 0.0)
    assert tool.session.dirty
    assert tool.can_apply(ctx)

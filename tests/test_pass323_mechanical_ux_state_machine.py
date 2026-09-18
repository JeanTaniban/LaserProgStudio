# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.mechanical_motion.chain_overlay import CHAIN_FIELD_PREFIX, CHAIN_WINDOW_ID
from laserprog_studio.tooling.mechanical_motion.models import MechanicalMode
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.serialization import assembly_from_mesh
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion.workflow_overlay import WORKFLOW_ACTION_PREFIX, WORKFLOW_WINDOW_ID
from laserprog_studio.tooling.mechanical_motion_tool import MechanicalMotionCreatorTool


def _applied_assembly_mesh() -> WorkMesh:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 2.0)))
    session.add_gear((25.0, 10.0, 2.0), teeth=30)
    return session.applied_meshes()[-1]


def _open_tool_with_store(meshes: list[WorkMesh], owner=None) -> tuple[MechanicalMotionCreatorTool, ToolContext, ModelStore]:
    store = ModelStore()
    store.set_meshes(meshes, push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    return tool, ctx, store


def _pick_plane(tool: MechanicalMotionCreatorTool, ctx: ToolContext) -> None:
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(0.0, 0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )


def test_cancel_on_preselected_old_mec_keeps_startup_phase_open() -> None:
    mesh = _applied_assembly_mesh()

    class Owner:
        def __init__(self) -> None:
            self.selected_indices = [0]
            self.active_index = 0
            self.close_calls = 0

        def ask_mechanical_edit_or_new(self, _mesh, _assembly):
            return "cancel"

        def close_active_tool(self, **_kwargs):
            self.close_calls += 1

    owner = Owner()
    store = ModelStore()
    store.set_meshes([mesh], push_undo=False)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    ctx.scene_selection.set_selected((0,))
    tool = MechanicalMotionCreatorTool()

    tool.open(ctx)

    assert owner.close_calls == 0
    assert tool._session.state.mode is MechanicalMode.PICK_PLANE
    assert not tool.assembly.gears
    assert ctx.overlay.window(WORKFLOW_WINDOW_ID) is not None


def test_existing_mec_click_raycast_opens_edit_before_plane_pick(monkeypatch) -> None:
    mesh = _applied_assembly_mesh()
    owner = SimpleNamespace(
        selected_indices=[],
        active_index=None,
        ask_mechanical_edit_or_new=lambda _mesh, _assembly: "edit",
    )
    tool, ctx, _store = _open_tool_with_store([mesh], owner=owner)

    from laserprog_studio.tool_api import plan2d

    monkeypatch.setattr(
        plan2d,
        "pick_plan_surface_anchor_by_raycast",
        lambda *_args, **_kwargs: SimpleNamespace(
            hit=True,
            object_index=0,
            object_id=mesh.mesh_id,
        ),
    )
    assert not tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_PRESS,
            screen_pos=(120.0, 80.0),
            button=MouseButton.LEFT,
        ),
        ctx,
    )
    assert tool.on_event(
        ToolEvent(
            ToolEventType.MOUSE_RELEASE,
            screen_pos=(120.0, 80.0),
            button=MouseButton.LEFT,
        ),
        ctx,
    )

    assert len(tool.assembly.gears) == 1
    assert tool._session.state.mode is MechanicalMode.SELECT


def test_existing_mec_can_be_selected_and_edited_during_startup_phase() -> None:
    mesh = _applied_assembly_mesh()
    original = assembly_from_mesh(mesh)
    assert original is not None
    owner = SimpleNamespace(
        selected_indices=[],
        active_index=None,
        ask_mechanical_edit_or_new=lambda _mesh, _assembly: "edit",
    )
    tool, ctx, _store = _open_tool_with_store([mesh], owner=owner)
    assert tool._session.state.mode is MechanicalMode.PICK_PLANE

    ctx.scene_selection.set_selected((0,))
    tool.on_scene_selection_changed(ctx)

    assert tool.assembly.id == original.id
    assert len(tool.assembly.gears) == 1
    assert tool._session.state.mode is MechanicalMode.SELECT


def test_clicking_generated_gear_mesh_assigns_driver_without_marker_indexing() -> None:
    tool, ctx, _store = _open_tool_with_store([])
    _pick_plane(tool, ctx)
    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PLACE_GEAR.value, notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(15.0, 5.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    gear_id = next(iter(tool.assembly.gears))

    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PICK_DRIVER_TARGET.value, notify=True)
    generated_index = next(
        obj.index
        for obj in ctx.document.objects()
        if str((getattr(obj.mesh, "metadata", {}) or {}).get("mechanical_gear_id") or "") == gear_id
    )
    ctx.scene_selection.set_selected((generated_index,))
    tool.on_scene_selection_changed(ctx)

    driver = tool.assembly.primary_driver()
    assert driver is not None
    assert driver.target_gear_id == gear_id
    assert tool._session.state.mode is MechanicalMode.SELECT


def test_attach_is_explicit_source_targets_confirm_workflow() -> None:
    part = WorkMesh(
        name="arm",
        vertices=[(60.0, 0.0, 0.0), (70.0, 0.0, 0.0), (60.0, 5.0, 0.0)],
        triangles=[(0, 1, 2)],
    )
    tool, ctx, _store = _open_tool_with_store([part])
    _pick_plane(tool, ctx)
    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PLACE_GEAR.value, notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(10.0, 10.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    source_gear_id = next(iter(tool.assembly.gears))

    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PICK_ATTACHMENT_SOURCE.value, notify=True)
    assert tool._session.state.mode is MechanicalMode.PICK_ATTACHMENTS
    assert tool._session.state.pending_attachment_source_id == source_gear_id
    assert not tool.assembly.attachments

    part_index = next(obj.index for obj in ctx.document.objects() if obj.id == part.mesh_id)
    ctx.scene_selection.set_selected((part_index,))
    tool.on_scene_selection_changed(ctx)
    assert tool._session.state.pending_attachment_mesh_ids == (part.mesh_id,)
    assert not tool.assembly.attachments
    workflow = ctx.overlay.window(WORKFLOW_WINDOW_ID)
    assert workflow is not None
    confirm = next(button for button in workflow.buttons if button.id.endswith("confirm_attachment"))
    assert confirm.enabled is True

    tool.on_overlay_button_clicked(f"{WORKFLOW_ACTION_PREFIX}confirm_attachment", ctx)

    attachment = next(iter(tool.assembly.attachments.values()))
    assert attachment.source_gear_id == source_gear_id
    assert attachment.target_mesh_ids == [part.mesh_id]
    assert tool._session.state.mode is MechanicalMode.SELECT


def test_attach_does_not_reuse_selection_from_before_attach_mode() -> None:
    part = WorkMesh(
        name="stale selection",
        vertices=[(40.0, 0.0, 0.0), (50.0, 0.0, 0.0), (40.0, 5.0, 0.0)],
        triangles=[(0, 1, 2)],
    )
    tool, ctx, _store = _open_tool_with_store([part])
    _pick_plane(tool, ctx)
    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PLACE_GEAR.value, notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(5.0, 5.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    part_index = next(obj.index for obj in ctx.document.objects() if obj.id == part.mesh_id)
    ctx.scene_selection.set_selected((part_index,))

    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PICK_ATTACHMENT_SOURCE.value, notify=True)
    assert tool._session.state.mode is MechanicalMode.PICK_ATTACHMENTS
    assert tool._session.state.pending_attachment_mesh_ids == ()

    assert not tool._commands.attach_scene_selection(ctx, sync=tool._sync_all)
    assert not tool.assembly.attachments


def test_selected_chain_opens_overlay_and_numeric_change_rebuilds() -> None:
    tool, ctx, _store = _open_tool_with_store([])
    _pick_plane(tool, ctx)
    chain = tool._session.add_chain((0.0, 0.0, 0.0), (170.0, 20.0, 0.0), intermediate_shaft_count=2)
    tool._machine.state.mode = MechanicalMode.SELECT
    tool._sync_all(ctx, "Chain selected.")

    window = ctx.overlay.window(CHAIN_WINDOW_ID)
    assert window is not None
    assert window.title == "Gear chain parameters"
    old_count = len(chain.shaft_ids)

    assert tool.on_overlay_field_changed(
        CHAIN_WINDOW_ID,
        f"{CHAIN_FIELD_PREFIX}intermediate_shafts",
        "4",
        ctx,
    )

    assert chain.intermediate_shaft_count == 4
    assert len(chain.shaft_ids) == 6
    assert len(chain.shaft_ids) != old_count


def test_apply_keeps_committed_assembly_selected_and_reopenable() -> None:
    tool, ctx, store = _open_tool_with_store([])
    _pick_plane(tool, ctx)
    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PLACE_GEAR.value, notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(20.0, 0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )

    assert tool.on_apply(ctx)
    assert ctx.scene_selection.selected_indices()
    assert assembly_from_mesh(store.committed_meshes[0]) is not None

    owner = SimpleNamespace(
        selected_indices=[],
        active_index=None,
        ask_mechanical_edit_or_new=lambda _mesh, _assembly: "edit",
    )
    ctx2 = ToolContext(owner=owner)
    ctx2.document.bind(store)
    reopened = MechanicalMotionCreatorTool()
    reopened.open(ctx2)
    assert reopened._session.state.mode is MechanicalMode.PICK_PLANE
    ctx2.scene_selection.set_selected((0,))
    reopened.on_scene_selection_changed(ctx2)
    assert len(reopened.assembly.gears) == 1

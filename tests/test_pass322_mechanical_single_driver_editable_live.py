# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.mechanical_motion.commands import MechanicalCommandService
from laserprog_studio.tooling.mechanical_motion.interactions import MechanicalInteractionService
from laserprog_studio.tooling.mechanical_motion.models import MechanicalMode
from laserprog_studio.tooling.mechanical_motion.parameters import MechanicalParameterService
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.rendering import MechanicalRenderer
from laserprog_studio.tooling.mechanical_motion.serialization import (
    MECHANICAL_DRAFT_KIND,
    MECHANICAL_SOURCE_KIND,
    assembly_from_mesh,
)
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion.state_machine import MechanicalWorkflowMachine
from laserprog_studio.tooling.mechanical_motion_tool import MechanicalMotionCreatorTool


def _session_with_plane() -> MechanicalSession:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    return session


def _add_gear_through_tool(tool: MechanicalMotionCreatorTool, ctx: ToolContext, point: tuple[float, float, float]) -> None:
    if tool._session.work_plane is None:
        assert tool.on_event(
            ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(0.0, 0.0, 0.0), button=MouseButton.LEFT),
            ctx,
        )
    ctx.inspector.update_value("mechanical_mode", "place_gear", notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=point, button=MouseButton.LEFT),
        ctx,
    )


def test_exact_clicked_chain_gear_becomes_the_driver_target() -> None:
    session = _session_with_plane()
    chain = session.add_chain((0.0, 0.0, 0.0), (180.0, 20.0, 0.0), intermediate_shaft_count=3)
    exact_gear_id = chain.gear_ids[-1]
    actor = SimpleNamespace(
        metadata={
            "mechanical_element_id": chain.id,
            "mechanical_gear_id": exact_gear_id,
            "mechanical_role": "gear_pitch",
        }
    )
    ctx = SimpleNamespace(
        selection=SimpleNamespace(actor=lambda _actor_id: actor),
        inspector=ToolContext().inspector,
    )
    parameters = MechanicalParameterService(session)
    interactions = MechanicalInteractionService(session, MechanicalWorkflowMachine(session.state), parameters)

    interactions.handle_native_result(
        ctx,
        SimpleNamespace(action="select", hit=SimpleNamespace(actor_id="clicked-gear")),
        sync=lambda *_args, **_kwargs: None,
    )

    assert session.assembly.selected_element_id == chain.id
    assert session.state.driver_candidate_gear_id == exact_gear_id
    assert parameters.input_gear_id_for_selection() == exact_gear_id
    driver = session.add_driver_for_gear(parameters.input_gear_id_for_selection())
    assert driver.target_gear_id == exact_gear_id
    assert driver.shaft_id == session.assembly.gears[exact_gear_id].shaft_id


def test_generated_and_draft_meshes_are_generic_editable_objects() -> None:
    session = _session_with_plane()
    session.add_gear((20.0, 30.0, 0.0))

    applied = session.applied_meshes()[-1]
    applied_metadata = applied.metadata
    assert applied_metadata["source_tool"] == "mechanical_motion"
    assert applied_metadata["editable_tool_id"] == "mechanical_motion"
    assert applied_metadata["editable_kind"] == MECHANICAL_SOURCE_KIND
    assert assembly_from_mesh(applied) is not None

    draft = session.draft_meshes()[-1]
    draft_metadata = draft.metadata
    assert draft_metadata["source_tool"] == "mechanical_motion"
    assert draft_metadata["editable_tool_id"] == "mechanical_motion"
    assert draft_metadata["editable_kind"] == MECHANICAL_DRAFT_KIND
    assert assembly_from_mesh(draft).draft is True


def test_cancel_draft_rebuilds_scene_and_selects_visible_placeholder() -> None:
    class Owner:
        def __init__(self) -> None:
            self.rebuild_calls = 0
            self.preview_state_calls = 0
            self.selected_indices: list[int] = []
            self.active_index = None

        def rebuild_scene(self, keep_camera: bool = False) -> None:
            assert keep_camera is True
            self.rebuild_calls += 1

        def update_preview_state(self) -> None:
            self.preview_state_calls += 1

    owner = Owner()
    store = ModelStore()
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    session = _session_with_plane()
    session.add_gear((15.0, 10.0, 0.0))
    parameters = MechanicalParameterService(session)
    commands = MechanicalCommandService(session, MechanicalWorkflowMachine(session.state), parameters)

    assert commands.save_draft(ctx)
    assert owner.rebuild_calls == 1
    assert owner.preview_state_calls == 1
    assert owner.selected_indices == [0]
    assert owner.active_index == 0
    assert len(store.committed_meshes) == 1
    assert store.committed_meshes[0].color == "#F44336"
    assert store.committed_meshes[0].metadata["editable_tool_id"] == "mechanical_motion"


def test_selection_only_change_does_not_turn_host_apply_into_draft() -> None:
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    _add_gear_through_tool(tool, ctx, (10.0, 0.0, 0.0))
    first_id = next(iter(tool.assembly.gears))
    _add_gear_through_tool(tool, ctx, (70.0, 0.0, 0.0))

    # The current preview contains the second selection. Selection is transient
    # and must not invalidate a successful generic host Apply.
    tool.assembly.selected_element_id = first_id
    assert ctx.document.commit_preview(label="Host Apply", operation_type="tool_apply")
    tool.on_close(ctx)

    assert len(store.committed_meshes) == 2
    assert all(mesh.color != "#F44336" for mesh in store.committed_meshes)
    restored = assembly_from_mesh(store.committed_meshes[0])
    assert restored is not None and restored.draft is False
    assert store.committed_meshes[0].metadata["editable_tool_id"] == "mechanical_motion"


def test_test_motion_fast_path_never_rebuilds_mesh_preview(monkeypatch) -> None:
    session = _session_with_plane()
    gear = session.add_gear((0.0, 0.0, 0.0))
    driver = session.add_driver_for_gear(gear.id)
    session.state.mode = MechanicalMode.TEST
    session.state.driver_angles_deg = {driver.id: 45.0}
    renderer = MechanicalRenderer("mechanical_motion", session)
    calls: list[str] = []

    monkeypatch.setattr(renderer._live_motion, "update", lambda *_args, **_kwargs: calls.append("matrix") or True)
    monkeypatch.setattr(renderer, "sync_test_handle", lambda *_args, **_kwargs: calls.append("handle"))
    monkeypatch.setattr(
        renderer,
        "sync_mesh_preview",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("full mesh rebuild during Test")),
    )

    assert renderer.sync_test_motion(SimpleNamespace(), render=True)
    assert calls == ["matrix", "handle"]


def test_animation_callback_updates_only_live_motion(monkeypatch) -> None:
    tool = MechanicalMotionCreatorTool()
    session = tool._session
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    gear = session.add_gear((0.0, 0.0, 0.0))
    driver = session.add_driver_for_gear(gear.id)
    ctx = ToolContext()
    tool._ctx = ctx
    calls: list[tuple[float, bool]] = []
    monkeypatch.setattr(
        tool._renderer,
        "sync_test_motion",
        lambda _ctx, *, render=True: calls.append((session.state.test_angle_deg, render)) or True,
    )

    tool._on_animation_angles({driver.id: 725.0})

    assert session.state.driver_angles_deg == {driver.id: 725.0}
    assert session.state.test_angle_deg == 5.0
    assert calls == [(5.0, True)]


def test_live_motion_caches_only_reachable_moving_actors(monkeypatch) -> None:
    import laserprog_studio.tooling.mechanical_motion.live_motion as live_module

    moving_part = WorkMesh(
        name="moving",
        vertices=[(20.0, 0.0, 0.0), (22.0, 0.0, 0.0), (20.0, 2.0, 0.0)],
        triangles=[(0, 1, 2)],
    )
    static_part = WorkMesh(
        name="static",
        vertices=[(100.0, 0.0, 0.0), (102.0, 0.0, 0.0), (100.0, 2.0, 0.0)],
        triangles=[(0, 1, 2)],
    )
    session = MechanicalSession()
    session.begin([moving_part, static_part])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    gear = session.add_gear((0.0, 0.0, 0.0))
    driver = session.add_driver_for_gear(gear.id)
    session.attach_meshes([moving_part.mesh_id], source_element_id=gear.id)
    preview = session.build_preview(use_test_state=False).meshes

    class Actor:
        def __init__(self, name: str) -> None:
            self.name = name
            self.matrix = f"baseline:{name}"
            self.set_calls: list[object] = []

        def GetUserMatrix(self):
            return self.matrix

        def SetUserMatrix(self, value) -> None:
            self.matrix = value
            self.set_calls.append(value)

    actors = {index: Actor(str(index)) for index in range(len(preview))}
    owner = SimpleNamespace(
        actors_by_index=actors,
        _scene_rebuild_generation=7,
        plotter=SimpleNamespace(render=lambda: None),
    )
    store = ModelStore()
    store.set_preview_meshes(preview)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    renderer = MechanicalRenderer("mechanical_motion", session)
    monkeypatch.setattr(live_module, "_vtk_matrix", lambda values: values)
    monkeypatch.setattr(live_module, "_compose", lambda delta, baseline: (delta, baseline))

    assert renderer.begin_live_motion(ctx)
    cached = renderer._live_motion._baselines
    generated_index = len(preview) - 1
    assert set(cached) == {0, generated_index}
    assert 1 not in cached

    session.state.driver_angles_deg = {driver.id: 90.0}
    assert renderer.sync_test_motion(ctx, render=False)
    assert actors[0].set_calls
    assert actors[generated_index].set_calls
    assert actors[1].set_calls == []

    renderer.end_live_motion(ctx)
    assert actors[0].matrix == "baseline:0"
    assert actors[generated_index].matrix == f"baseline:{generated_index}"


def test_applied_multi_shaft_mec_reopens_from_any_shaft_and_replaces_in_place() -> None:
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    tool._session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    chain = tool._session.add_chain(
        (0.0, 0.0, 0.0),
        (180.0, 25.0, 0.0),
        intermediate_shaft_count=3,
        total_reduction=6.0,
    )
    original_assembly_id = tool.assembly.id
    tool._session.add_driver_for_gear(chain.gear_ids[-1])
    tool._sync_all(ctx, "Ready")
    assert ctx.document.commit_preview(label="Host Apply", operation_type="tool_apply")
    tool.on_close(ctx)

    original_count = len(store.committed_meshes)
    assert original_count == len(chain.shaft_ids)
    selected_index = original_count // 2

    ctx2 = ToolContext()
    ctx2.document.bind(store)
    ctx2.scene_selection.set_selected((selected_index,), active_index=selected_index)
    reopened = MechanicalMotionCreatorTool()
    reopened.open(ctx2)
    assert reopened.assembly.id == original_assembly_id
    reopened_chain = next(iter(reopened.assembly.chains.values()))
    reopened_chain.total_reduction = 11.0
    reopened._session.rebuild_chain(reopened_chain.id)
    reopened._sync_all(ctx2, "Edited")
    assert ctx2.document.commit_preview(label="Host Apply edited MEC", operation_type="tool_apply")
    reopened.on_close(ctx2)

    assert len(store.committed_meshes) == original_count
    assert all(mesh.color != "#F44336" for mesh in store.committed_meshes)
    restored = [assembly_from_mesh(mesh) for mesh in store.committed_meshes]
    assert all(value is not None and value.id == original_assembly_id and value.draft is False for value in restored)
    assert all(next(iter(value.chains.values())).total_reduction == 11.0 for value in restored)

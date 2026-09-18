# -*- coding: utf-8 -*-
from __future__ import annotations

from math import hypot, isclose
from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore
from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.mechanical_motion.interactions import MechanicalInteractionService
from laserprog_studio.tooling.mechanical_motion.kinematics import solve_kinematics
from laserprog_studio.tooling.mechanical_motion.parameters import MechanicalParameterService
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.rendering import MechanicalRenderer
from laserprog_studio.tooling.mechanical_motion.serialization import deserialize_assembly, serialize_assembly
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion.smart_snap import (
    SMART_MESH_CONNECTION_KIND,
    find_gear_snap_candidate,
    smart_mesh_stages_for_gear,
)
from laserprog_studio.tooling.mechanical_motion.state_machine import MechanicalWorkflowMachine


def _session() -> MechanicalSession:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    return session


def _cyclic_fraction_error(value: float, target: float) -> float:
    return ((float(value) - float(target) + 0.5) % 1.0) - 0.5


def test_smart_snap_aligns_pitch_centres_and_preserves_target_phase() -> None:
    session = _session()
    target = session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    target.phase_deg = 17.0
    dragged = session.add_gear((80.0, 0.0, 0.0), teeth=30, module_mm=2.0)
    plane = session.require_work_plane()

    candidate = find_gear_snap_candidate(
        session.assembly,
        dragged.id,
        (53.0, 5.0, 0.0),
        plane,
    )

    assert candidate is not None
    target_support = plane.coordinates(target.center)
    dragged_support = plane.coordinates(candidate.center)
    distance = hypot(dragged_support[0] - target_support[0], dragged_support[1] - target_support[1])
    assert isclose(distance, target.pitch_radius_mm + dragged.pitch_radius_mm, abs_tol=1.0e-10)

    target_pitch = 360.0 / target.teeth
    dragged_pitch = 360.0 / dragged.teeth
    target_fraction = ((candidate.mesh_angle_deg - target.phase_deg) / target_pitch) % 1.0
    dragged_fraction = ((candidate.mesh_angle_deg + 180.0 - candidate.phase_deg) / dragged_pitch) % 1.0
    assert abs(_cyclic_fraction_error(target_fraction + dragged_fraction, 0.5)) < 1.0e-10


def test_snap_release_creates_a_bidirectional_motion_stage() -> None:
    session = _session()
    target = session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    dragged = session.add_gear((80.0, 0.0, 0.0), teeth=30, module_mm=2.0)
    driver = session.add_driver_for_gear(target.id, speed_rpm=60.0)

    candidate = session.preview_move_unique_gear(
        dragged.id,
        (52.0, 2.0, 0.0),
        unsnapped_phase_deg=dragged.phase_deg,
    )
    assert candidate is not None
    session.commit_unique_gear_drag(dragged.id, candidate)

    stages = smart_mesh_stages_for_gear(session.assembly, dragged.id)
    assert len(stages) == 1
    stage = stages[0]
    assert stage.connection_kind == SMART_MESH_CONNECTION_KIND
    assert stage.driver_gear_id == target.id
    assert stage.driven_gear_id == dragged.id
    assert isclose(stage.actual_reduction, 1.5, abs_tol=1.0e-12)

    state = solve_kinematics(session.assembly, {driver.id: 90.0})
    assert isclose(state.shaft_angles_deg[target.shaft_id], 90.0, abs_tol=1.0e-12)
    assert isclose(state.shaft_angles_deg[dragged.shaft_id], -60.0, abs_tol=1.0e-12)
    assert isclose(state.shaft_speeds_rpm[dragged.shaft_id], -40.0, abs_tol=1.0e-12)


def test_dragging_a_snapped_gear_away_detaches_the_old_motion_stage() -> None:
    session = _session()
    target = session.add_gear((0.0, 0.0, 0.0), teeth=24, module_mm=2.0)
    dragged = session.add_gear((90.0, 0.0, 0.0), teeth=24, module_mm=2.0)
    candidate = session.preview_move_unique_gear(
        dragged.id,
        (50.0, 0.0, 0.0),
        unsnapped_phase_deg=0.0,
    )
    assert candidate is not None
    session.commit_unique_gear_drag(dragged.id, candidate)
    assert smart_mesh_stages_for_gear(session.assembly, dragged.id)

    detached = session.preview_move_unique_gear(
        dragged.id,
        (180.0, 30.0, 0.0),
        unsnapped_phase_deg=dragged.phase_deg,
    )
    assert detached is None
    session.commit_unique_gear_drag(dragged.id, detached)

    assert smart_mesh_stages_for_gear(session.assembly, dragged.id) == ()
    assert target.id in session.assembly.gears


def test_incompatible_modules_do_not_snap() -> None:
    session = _session()
    session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    dragged = session.add_gear((80.0, 0.0, 0.0), teeth=20, module_mm=3.0)
    assert session.gear_snap_candidate(dragged.id, (50.0, 0.0, 0.0)) is None


def test_native_gear_drag_uses_only_the_fast_preview_until_release(monkeypatch) -> None:
    session = _session()
    session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    dragged = session.add_gear((80.0, 0.0, 0.0), teeth=30, module_mm=2.0)
    parameters = MechanicalParameterService(session)
    interactions = MechanicalInteractionService(session, MechanicalWorkflowMachine(session.state), parameters)
    actor = SimpleNamespace(
        points=[(52.0, 1.0, 12.0)],
        metadata={"mechanical_role": "gear_center", "mechanical_element_id": dragged.id},
    )
    ctx = SimpleNamespace(
        selection=SimpleNamespace(actor=lambda _actor_id: actor),
        inspector=ToolContext().inspector,
    )
    sync_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        session,
        "build_preview",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("mesh preview rebuilt during drag")),
    )

    interactions.handle_native_result(
        ctx,
        SimpleNamespace(action="drag", grabbed_ids=("gear-center",)),
        sync=lambda _ctx, status=None, **kwargs: sync_calls.append({"status": status, **kwargs}),
    )

    assert sync_calls[-1]["update_mesh_preview"] is False
    assert sync_calls[-1]["gear_drag_gear_id"] == dragged.id
    assert sync_calls[-1]["gear_snap_candidate"] is not None
    assert sync_calls[-1]["gear_drag_origin_center"] == (80.0, 0.0, 3.0)
    assert sync_calls[-1]["gear_drag_origin_phase_deg"] == 0.0


def test_actor_matrix_uses_the_real_pre_drag_baseline(monkeypatch) -> None:
    import laserprog_studio.tooling.mechanical_motion.drag_preview as drag_module

    session = _session()
    session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    dragged = session.add_gear((80.0, 0.0, 0.0), teeth=30, module_mm=2.0)
    original_center = dragged.center
    original_phase = dragged.phase_deg
    preview = session.build_preview(use_test_state=False).meshes
    dragged_index = next(
        index
        for index, mesh in enumerate(preview)
        if (mesh.metadata or {}).get("mechanical_gear_id") == dragged.id
    )

    class Actor:
        def __init__(self) -> None:
            self.matrix = "neutral"
            self.visible = True
            self.set_matrices: list[object] = []

        def GetUserMatrix(self):
            return self.matrix

        def SetUserMatrix(self, value) -> None:
            self.matrix = value
            self.set_matrices.append(value)

        def GetVisibility(self) -> bool:
            return self.visible

        def SetVisibility(self, visible: bool) -> None:
            self.visible = bool(visible)

    actor = Actor()
    owner = SimpleNamespace(
        actors_by_index={dragged_index: actor},
        _scene_rebuild_generation=4,
        plotter=SimpleNamespace(render=lambda: None),
    )
    store = ModelStore()
    store.set_preview_meshes(preview)
    ctx = ToolContext(owner=owner)
    ctx.document.bind(store)
    renderer = MechanicalRenderer("mechanical_motion", session)
    affine_values: list[tuple[tuple[float, ...], ...]] = []
    monkeypatch.setattr(drag_module, "_vtk_matrix", lambda values: affine_values.append(values) or "delta")
    monkeypatch.setattr(drag_module, "_compose", lambda delta, baseline: (delta, baseline))

    candidate = session.preview_move_unique_gear(
        dragged.id,
        (52.0, 1.0, 0.0),
        unsnapped_phase_deg=original_phase,
    )
    assert candidate is not None
    assert renderer.sync_gear_drag(
        ctx,
        dragged.id,
        candidate,
        origin_center=original_center,
        origin_phase_deg=original_phase,
        render=False,
    )

    assert affine_values
    assert actor.set_matrices[-1] == ("delta", "neutral")
    assert actor.visible is True
    assert any(abs(affine_values[-1][axis][3]) > 1.0e-6 for axis in range(3))


def test_renderer_drag_overlay_does_not_call_session_build_preview(monkeypatch) -> None:
    session = _session()
    session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    dragged = session.add_gear((80.0, 0.0, 0.0), teeth=30, module_mm=2.0)
    candidate = session.preview_move_unique_gear(
        dragged.id,
        (52.0, 1.0, 0.0),
        unsnapped_phase_deg=0.0,
    )
    assert candidate is not None
    renderer = MechanicalRenderer("mechanical_motion", session)
    ctx = ToolContext()

    monkeypatch.setattr(
        session,
        "build_preview",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("mesh generation in renderer drag path")),
    )

    assert renderer.sync_gear_drag(ctx, dragged.id, candidate, render=False)
    ids = {primitive.id for primitive in ctx.projected_drawing.for_tool("mechanical_motion").items()}
    assert f"mechanical:drag:{dragged.id}:outline" in ids
    assert "mechanical:drag:snap:contact" in ids


def test_smart_mesh_stage_and_visual_link_survive_serialization() -> None:
    session = _session()
    target = session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    dragged = session.add_gear((80.0, 0.0, 0.0), teeth=30, module_mm=2.0)
    candidate = session.preview_move_unique_gear(
        dragged.id,
        (52.0, 1.0, 0.0),
        unsnapped_phase_deg=0.0,
    )
    assert candidate is not None
    session.commit_unique_gear_drag(dragged.id, candidate)
    stage = smart_mesh_stages_for_gear(session.assembly, dragged.id)[0]

    restored = deserialize_assembly(serialize_assembly(session.assembly))
    assert restored is not None
    restored_stage = restored.stages[stage.id]
    assert restored_stage.connection_kind == SMART_MESH_CONNECTION_KIND
    assert restored_stage.owner_id == dragged.id

    restored_session = MechanicalSession()
    restored_session.state.assembly = restored
    renderer = MechanicalRenderer("mechanical_motion", restored_session)
    ctx = ToolContext()
    renderer.sync_projected_markers(ctx, render=False)
    ids = {primitive.id for primitive in ctx.projected_drawing.for_tool("mechanical_motion").items()}
    assert f"mechanical:smart_mesh:{stage.id}:centres" in ids
    assert f"mechanical:smart_mesh:{stage.id}:contact" in ids

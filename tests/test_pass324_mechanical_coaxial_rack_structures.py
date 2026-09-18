# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from math import isclose, pi

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tooling.mechanical_motion.kinematics import solve_kinematics
from laserprog_studio.tooling.mechanical_motion.models import (
    GearSpec,
    MechanicalAssembly,
    MechanicalMode,
    MechanicalSessionState,
    RotaryDriverSpec,
)
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.rack_geometry import rack_axis, rack_toward_pinion
from laserprog_studio.tooling.mechanical_motion.serialization import deserialize_assembly, serialize_assembly
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion.state_machine import MechanicalIntent, MechanicalWorkflowMachine


def _closed_edge_counts(mesh: WorkMesh) -> Counter[tuple[int, int]]:
    counts: Counter[tuple[int, int]] = Counter()
    for a, b, c in mesh.triangles:
        for u, v in ((a, b), (b, c), (c, a)):
            counts[tuple(sorted((u, v)))] += 1
    return counts


def _horizontal_session(meshes=()) -> MechanicalSession:
    session = MechanicalSession()
    session.begin(list(meshes))
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    return session


def test_touching_coaxial_gears_are_one_kinematic_shaft() -> None:
    plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
    lower = GearSpec(center=(0.0, 0.0, 3.0), thickness_mm=6.0, teeth=20, shaft_id="legacy-a").normalized()
    upper = GearSpec(center=(0.0, 0.0, 9.0), thickness_mm=6.0, teeth=42, shaft_id="legacy-b").normalized()
    assembly = MechanicalAssembly(work_plane=plane)
    assembly.gears = {lower.id: lower, upper.id: upper}
    driver = RotaryDriverSpec(
        target_gear_id=lower.id,
        shaft_id="legacy-a",
        center=plane.clamp(lower.center),
        speed_rpm=36.0,
    ).normalized()
    assembly.drivers[driver.id] = driver

    state = solve_kinematics(assembly, {driver.id: 137.0})

    assert lower.shaft_id == upper.shaft_id
    assert driver.shaft_id == lower.shaft_id
    assert isclose(state.shaft_angles_deg[lower.shaft_id], 137.0, abs_tol=1.0e-12)
    assert isclose(state.shaft_speeds_rpm[lower.shaft_id], 36.0, abs_tol=1.0e-12)
    assert isclose(
        state.gear_angles_deg[lower.id] - lower.phase_deg,
        state.gear_angles_deg[upper.id] - upper.phase_deg,
        abs_tol=1.0e-12,
    )
    assert any("coaxial shaft" in warning for warning in state.warnings)


def test_coaxial_repair_is_applied_when_legacy_assembly_is_opened() -> None:
    plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
    first = GearSpec(center=(15.0, -4.0, 2.5), thickness_mm=5.0, shaft_id="old-first").normalized()
    second = GearSpec(center=(15.0, -4.0, 7.5), thickness_mm=5.0, shaft_id="old-second").normalized()
    assembly = MechanicalAssembly(work_plane=plane)
    assembly.gears = {first.id: first, second.id: second}

    carrier = WorkMesh(name="legacy MEC", vertices=[(0.0, 0.0, 0.0)], triangles=[])
    from laserprog_studio.tooling.mechanical_motion.serialization import attach_source

    attach_source(carrier, assembly)
    session = MechanicalSession()
    session.begin([carrier], selected_meshes=[carrier])

    reopened = tuple(session.assembly.gears.values())
    assert len(reopened) == 2
    assert len({gear.shaft_id for gear in reopened}) == 1
    assert session.build_preview(test_angle_deg=45.0).generated_count == 1


def test_rack_snaps_to_pitch_tangent_and_converts_rotation_to_translation() -> None:
    session = _horizontal_session()
    gear = session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0, thickness_mm=6.0)
    rack = session.add_rack((-45.0, 35.0, 0.0), (55.0, 35.0, 0.0), pinion_gear_id=gear.id)
    driver = session.add_driver_for_gear(gear.id, speed_rpm=60.0)

    toward = rack_toward_pinion(rack, session.require_work_plane())
    midpoint = tuple((rack.start[i] + rack.end[i]) * 0.5 for i in range(3))
    center = session.require_work_plane().clamp(gear.center)
    assert isclose(midpoint[0], 5.0, abs_tol=1.0e-12)
    separation = abs(sum((center[i] - midpoint[i]) * toward[i] for i in range(3)))
    assert isclose(separation, gear.pitch_radius_mm, rel_tol=1.0e-12, abs_tol=1.0e-12)

    state = solve_kinematics(session.assembly, {driver.id: 90.0})
    assert isclose(abs(state.rack_displacements_mm[rack.id]), 0.5 * pi * gear.pitch_radius_mm, rel_tol=1.0e-12)
    assert isclose(abs(state.rack_speeds_mm_s[rack.id]), 2.0 * pi * gear.pitch_radius_mm, rel_tol=1.0e-12)


def test_rack_mesh_is_closed_and_roundtrips_with_assembly() -> None:
    session = _horizontal_session()
    gear = session.add_gear((0.0, 0.0, 0.0), teeth=24, module_mm=1.5)
    rack = session.add_rack((-60.0, 30.0, 0.0), (60.0, 30.0, 0.0), pinion_gear_id=gear.id)

    preview = session.build_preview(test_angle_deg=0.0)
    rack_mesh = next(mesh for mesh in preview.meshes if (mesh.metadata or {}).get("mechanical_rack_id") == rack.id)
    assert rack_mesh.vertices
    assert rack_mesh.triangles
    assert set(_closed_edge_counts(rack_mesh).values()) == {2}

    restored = deserialize_assembly(serialize_assembly(session.assembly))
    assert restored is not None
    assert restored.schema_version == 3
    assert restored.racks[rack.id].pinion_gear_id == gear.id
    assert isclose(restored.racks[rack.id].length_mm, rack.length_mm, rel_tol=1.0e-12)


def test_scene_part_attached_to_rack_translates_without_rotating() -> None:
    part = WorkMesh(
        name="slider",
        vertices=[(5.0, 50.0, 0.0), (15.0, 50.0, 0.0), (5.0, 55.0, 0.0)],
        triangles=[(0, 1, 2)],
    )
    session = _horizontal_session([part])
    gear = session.add_gear((0.0, 0.0, 0.0), teeth=20, module_mm=2.0)
    rack = session.add_rack((-50.0, 30.0, 0.0), (50.0, 30.0, 0.0), pinion_gear_id=gear.id)
    session.add_driver_for_gear(gear.id)
    attachment = session.attach_meshes([part.mesh_id], source_element_id=rack.id)
    assert attachment.source_element_id == rack.id

    preview = session.build_preview(test_angle_deg=90.0)
    moved = next(mesh for mesh in preview.meshes if mesh.mesh_id == part.mesh_id)
    axis = rack_axis(rack)
    delta = tuple(moved.vertices[0][i] - part.vertices[0][i] for i in range(3))
    expected = 0.5 * pi * gear.pitch_radius_mm
    assert isclose(abs(sum(delta[i] * axis[i] for i in range(3))), expected, rel_tol=1.0e-12)
    assert isclose(sum(delta[i] * delta[i] for i in range(3)), expected * expected, rel_tol=1.0e-12)
    original_edge = tuple(part.vertices[1][i] - part.vertices[0][i] for i in range(3))
    moved_edge = tuple(moved.vertices[1][i] - moved.vertices[0][i] for i in range(3))
    assert moved_edge == original_edge


def test_rack_creation_has_explicit_pinion_start_end_states() -> None:
    state = MechanicalSessionState()
    state.assembly.work_plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
    gear = GearSpec(center=(0.0, 0.0, 3.0)).normalized()
    state.assembly.gears[gear.id] = gear
    machine = MechanicalWorkflowMachine(state)

    result = machine.dispatch(MechanicalIntent.START_RACK)
    assert result.current is MechanicalMode.PICK_RACK_PINION
    result = machine.accept_rack_pinion(gear.id)
    assert result.current is MechanicalMode.PLACE_RACK_START
    result = machine.accept_rack_start((-30.0, 20.0, 0.0))
    assert result.current is MechanicalMode.PLACE_RACK_END


def test_chain_topology_change_migrates_and_resnaps_connected_rack() -> None:
    session = _horizontal_session()
    chain = session.add_chain((0.0, 0.0, 0.0), (180.0, 0.0, 0.0), intermediate_shaft_count=2)
    old_output = chain.gear_ids[-1]
    rack = session.add_rack((100.0, 60.0, 0.0), (220.0, 60.0, 0.0), pinion_gear_id=old_output)

    chain.intermediate_shaft_count = 4
    session.rebuild_chain(chain.id)

    assert rack.pinion_gear_id == chain.gear_ids[-1]
    assert rack.pinion_gear_id in session.assembly.gears
    pinion = session.assembly.gears[rack.pinion_gear_id]
    midpoint = tuple((rack.start[i] + rack.end[i]) * 0.5 for i in range(3))
    toward = rack_toward_pinion(rack, session.require_work_plane())
    center = session.require_work_plane().clamp(pinion.center)
    separation = abs(sum((center[i] - midpoint[i]) * toward[i] for i in range(3)))
    assert isclose(separation, pinion.pitch_radius_mm, rel_tol=1.0e-12, abs_tol=1.0e-12)


def test_rack_can_be_created_from_the_real_tool_mode_and_two_clicks() -> None:
    from laserprog_studio.domain.work_model import ModelStore
    from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
    from laserprog_studio.tooling.mechanical_motion_tool import MechanicalMotionCreatorTool

    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(0.0, 0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PLACE_GEAR.value, notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(0.0, 0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    pinion_id = next(iter(tool.assembly.gears))

    ctx.inspector.update_value("mechanical_mode", MechanicalMode.PLACE_RACK_START.value, notify=True)
    assert tool._session.state.mode is MechanicalMode.PLACE_RACK_START
    assert tool._session.state.pending_rack_pinion_gear_id == pinion_id
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(-50.0, 30.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    assert tool._session.state.mode is MechanicalMode.PLACE_RACK_END
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(50.0, 30.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )

    rack = next(iter(tool.assembly.racks.values()))
    assert rack.pinion_gear_id == pinion_id
    assert tool._session.state.mode is MechanicalMode.SELECT

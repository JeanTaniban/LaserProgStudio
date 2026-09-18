# -*- coding: utf-8 -*-
from __future__ import annotations

from math import isclose, sqrt
from unittest.mock import patch

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.tooling.mechanical_motion.animation import MechanicalAnimationController
from laserprog_studio.tooling.mechanical_motion.gear_solver import solve_chain
from laserprog_studio.tooling.mechanical_motion.kinematics import solve_kinematics
from laserprog_studio.tooling.mechanical_motion.models import GearChainSpec, MechanicalAssembly, RotaryDriverSpec
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.serialization import attach_source
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession


def _axial_overlap_mm(left, right, plane: MechanicalWorkPlane) -> float:
    left_center = sum(float(left.center[index]) * float(plane.normal[index]) for index in range(3))
    right_center = sum(float(right.center[index]) * float(plane.normal[index]) for index in range(3))
    return min(
        left_center + 0.5 * float(left.thickness_mm),
        right_center + 0.5 * float(right.thickness_mm),
    ) - max(
        left_center - 0.5 * float(left.thickness_mm),
        right_center - 0.5 * float(right.thickness_mm),
    )


def _pitch_contacts(result, plane: MechanicalWorkPlane) -> set[frozenset[str]]:
    contacts: set[frozenset[str]] = set()
    gears = tuple(result.gears)
    for index, left in enumerate(gears):
        for right in gears[index + 1 :]:
            if str(left.shaft_id) == str(right.shaft_id):
                continue
            lu, lv = plane.coordinates(left.center)
            ru, rv = plane.coordinates(right.center)
            planar_distance = sqrt((lu - ru) ** 2 + (lv - rv) ** 2)
            tangent = isclose(
                planar_distance,
                left.pitch_radius_mm + right.pitch_radius_mm,
                rel_tol=1.0e-9,
                abs_tol=1.0e-8,
            )
            if tangent and _axial_overlap_mm(left, right, plane) > 1.0e-6:
                contacts.add(frozenset((left.id, right.id)))
    return contacts


def test_chain_uses_three_layers_and_has_exactly_one_contact_per_stage() -> None:
    plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
    chain = GearChainSpec(
        start=(0.0, 0.0, 0.0),
        end=(180.0, 0.0, 0.0),
        intermediate_shaft_count=3,
        total_reduction=8.0,
        thickness_mm=6.0,
        axial_clearance_mm=1.0,
    )
    result = solve_chain(chain, plane=plane)

    assert [stage.axial_layer for stage in result.stages] == [0, 1, 2, 0]
    intended = {
        frozenset((stage.driver_gear_id, stage.driven_gear_id))
        for stage in result.stages
    }
    assert _pitch_contacts(result, plane) == intended

    first_intermediate_lower = result.gears[1]
    first_intermediate_upper = result.gears[2]
    axial_distance = abs(
        sum(
            (float(first_intermediate_upper.center[index]) - float(first_intermediate_lower.center[index]))
            * float(plane.normal[index])
            for index in range(3)
        )
    )
    assert isclose(axial_distance, chain.thickness_mm + chain.axial_clearance_mm, abs_tol=1.0e-12)


def test_compound_intermediate_shafts_receive_a_rigid_hub() -> None:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    chain = session.add_chain(
        (0.0, 0.0, 0.0),
        (180.0, 0.0, 0.0),
        intermediate_shaft_count=3,
        total_reduction=8.0,
        axial_clearance_mm=1.0,
    )

    preview = session.build_preview(use_test_state=False)
    intermediate_shaft_ids = set(chain.shaft_ids[1:-1])
    compound_meshes = {
        str((mesh.metadata or {}).get("mechanical_shaft_id")): mesh
        for mesh in preview.meshes
        if bool((mesh.metadata or {}).get("mechanical_compound"))
    }

    assert set(compound_meshes) == intermediate_shaft_ids
    assert all(bool((mesh.metadata or {}).get("mechanical_compound_hub")) for mesh in compound_meshes.values())
    assert all(len((mesh.metadata or {}).get("mechanical_gear_ids") or ()) == 2 for mesh in compound_meshes.values())


def test_opening_an_old_two_layer_chain_migrates_without_changing_ids() -> None:
    plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
    chain = GearChainSpec(
        start=(0.0, 0.0, 0.0),
        end=(180.0, 0.0, 0.0),
        intermediate_shaft_count=2,
        total_reduction=8.0,
        thickness_mm=6.0,
        axial_clearance_mm=1.0,
    )
    solved = solve_chain(chain, plane=plane)
    assembly = MechanicalAssembly(work_plane=plane)
    assembly.chains[chain.id] = chain
    assembly.gears = {gear.id: gear for gear in solved.gears}
    assembly.stages = {stage.id: stage for stage in solved.stages}
    stable_gear_ids = tuple(chain.gear_ids)
    stable_stage_ids = tuple(chain.stage_ids)
    stable_shaft_ids = tuple(chain.shaft_ids)

    # Recreate the v105 two-layer/no-clearance placement.
    for index, stage in enumerate(solved.stages):
        old_layer = index % 2
        stage.axial_layer = old_layer
        assembly.gears[stage.driver_gear_id].center = plane.gear_center(
            chain.shafts[index], chain.thickness_mm, layer=old_layer
        )
        assembly.gears[stage.driven_gear_id].center = plane.gear_center(
            chain.shafts[index + 1], chain.thickness_mm, layer=old_layer
        )

    carrier = WorkMesh(name="old mechanical chain", vertices=[(0.0, 0.0, 0.0)], triangles=[])
    attach_source(carrier, assembly)
    reopened = MechanicalSession()
    reopened.begin([carrier], selected_meshes=[carrier])
    migrated = reopened.assembly.chains[chain.id]

    assert tuple(migrated.gear_ids) == stable_gear_ids
    assert tuple(migrated.stage_ids) == stable_stage_ids
    assert tuple(migrated.shaft_ids) == stable_shaft_ids
    assert [reopened.assembly.stages[stage_id].axial_layer for stage_id in migrated.stage_ids] == [0, 1, 2]
    lower = reopened.assembly.gears[migrated.gear_ids[1]]
    upper = reopened.assembly.gears[migrated.gear_ids[2]]
    assert isclose(abs(upper.center[2] - lower.center[2]), 7.0, abs_tol=1.0e-12)


def test_animation_keeps_accumulated_driver_angle_for_reduced_stages() -> None:
    emitted: list[dict[str, float]] = []
    controller = MechanicalAnimationController(emitted.append)
    controller._angles = {"driver": 350.0}
    controller._speeds_rpm = {"driver": 60.0}
    controller._last_tick = 0.75

    with patch(
        "laserprog_studio.tooling.mechanical_motion.animation.time.perf_counter",
        return_value=1.0,
    ):
        controller._tick()

    assert emitted
    assert isclose(emitted[-1]["driver"], 440.0, abs_tol=1.0e-12)

    plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
    chain = GearChainSpec(
        start=(0.0, 0.0, 0.0),
        end=(160.0, 0.0, 0.0),
        intermediate_shaft_count=2,
        total_reduction=8.0,
    )
    solved = solve_chain(chain, plane=plane)
    assembly = MechanicalAssembly(work_plane=plane)
    assembly.chains[chain.id] = chain
    assembly.gears = {gear.id: gear for gear in solved.gears}
    assembly.stages = {stage.id: stage for stage in solved.stages}
    input_gear = solved.gears[0]
    driver = RotaryDriverSpec(
        id="driver",
        target_gear_id=input_gear.id,
        shaft_id=input_gear.shaft_id,
        center=plane.clamp(input_gear.center),
        speed_rpm=60.0,
    )
    assembly.drivers[driver.id] = driver

    before = solve_kinematics(assembly, {driver.id: 350.0})
    after = solve_kinematics(assembly, emitted[-1])
    output_shaft = chain.shaft_ids[-1]
    expected_delta = (440.0 - 350.0) * ((-1.0) ** chain.stage_count) / chain.actual_reduction
    assert isclose(
        after.shaft_angles_deg[output_shaft] - before.shaft_angles_deg[output_shaft],
        expected_delta,
        rel_tol=1.0e-9,
        abs_tol=1.0e-9,
    )

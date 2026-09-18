# -*- coding: utf-8 -*-
from __future__ import annotations

from math import isclose

from laserprog_studio.tool_core import ToolContext
from laserprog_studio.tooling.mechanical_motion.kinematics import solve_kinematics
from laserprog_studio.tooling.mechanical_motion.models import MechanicalMode
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.serialization import deserialize_assembly, serialize_assembly
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion.test_overlay import MechanicalTestOverlay, TEST_FIELD_PREFIX, TEST_WINDOW_ID


def _side_plane() -> MechanicalWorkPlane:
    return MechanicalWorkPlane(
        view="front",
        normal=(1.0, 0.0, 0.0),
        u_axis=(0.0, 1.0, 0.0),
        v_axis=(0.0, 0.0, 1.0),
        depth=10.0,
        anchor_world=(10.0, 2.0, 3.0),
        support_object_id="support",
        support_object_index=4,
    ).normalized()


def test_arbitrary_work_plane_constrains_points_and_orients_gear_mesh() -> None:
    session = MechanicalSession()
    session.begin([])
    plane = session.set_work_plane(_side_plane())
    gear = session.add_gear((100.0, 5.0, 7.0), thickness_mm=6.0, teeth=20)

    assert gear.center == (13.0, 5.0, 7.0)
    preview = session.build_preview(use_test_state=False)
    assert preview.generated_count == 1
    mesh = preview.meshes[-1]
    xs = [point[0] for point in mesh.vertices]
    assert isclose(min(xs), 10.0, abs_tol=1e-8)
    assert isclose(max(xs), 16.0, abs_tol=1e-8)
    assert plane.clamp((500.0, 8.0, 9.0)) == (10.0, 8.0, 9.0)


def test_work_plane_roundtrips_with_support_identity() -> None:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(_side_plane())
    restored = deserialize_assembly(serialize_assembly(session.assembly))
    assert restored is not None
    plane = restored.work_plane
    assert isinstance(plane, MechanicalWorkPlane)
    assert plane.normal == (1.0, 0.0, 0.0)
    assert plane.support_object_id == "support"
    assert plane.support_object_index == 4


def test_compound_chain_builds_one_hub_connected_mesh_per_shaft() -> None:
    session = MechanicalSession()
    session.begin([])
    plane = session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    chain = session.add_chain((0.0, 0.0, 0.0), (190.0, 30.0, 0.0), intermediate_shaft_count=3, total_reduction=9.0)

    for shaft_id in chain.shaft_ids[1:-1]:
        gears = sorted(
            (gear for gear in session.assembly.gears.values() if gear.shaft_id == shaft_id),
            key=lambda gear: gear.center[2],
        )
        assert len(gears) == 2
        lower_top = gears[0].center[2] + 0.5 * gears[0].thickness_mm
        upper_bottom = gears[1].center[2] - 0.5 * gears[1].thickness_mm
        assert upper_bottom - lower_top >= chain.axial_clearance_mm - 1.0e-9

    preview = session.build_preview(use_test_state=False)
    generated = [mesh for mesh in preview.meshes if (getattr(mesh, "metadata", {}) or {}).get("mechanical_generated")]
    assert len(generated) == len(chain.shaft_ids)
    compound = [mesh for mesh in generated if (getattr(mesh, "metadata", {}) or {}).get("mechanical_compound")]
    assert len(compound) == len(chain.shaft_ids) - 2
    assert all(len(mesh.metadata.get("mechanical_gear_ids", ())) == 2 for mesh in compound)
    assert all(bool(mesh.metadata.get("mechanical_compound_hub")) for mesh in compound)
    assert plane.normal == (0.0, 0.0, 1.0)


def test_assigning_a_new_driver_replaces_the_previous_one() -> None:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    first = session.add_gear((0.0, 0.0, 0.0))
    second = session.add_gear((80.0, 0.0, 0.0))
    driver_a = session.add_driver_for_gear(first.id, direction=-1)
    driver_b = session.add_driver_for_gear(second.id, direction=1)

    assert tuple(session.assembly.drivers) == (driver_b.id,)
    assert driver_a.id not in session.state.driver_angles_deg
    state = solve_kinematics(session.assembly, {driver_b.id: 22.5})
    assert first.shaft_id not in state.shaft_angles_deg
    assert state.shaft_angles_deg[second.shaft_id] == 22.5
    assert state.shaft_speeds_rpm[second.shaft_id] > 0.0


def test_test_overlay_exposes_only_the_current_driver_rpm() -> None:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    first = session.add_gear((0.0, 0.0, 0.0))
    second = session.add_gear((80.0, 0.0, 0.0))
    old_driver = session.add_driver_for_gear(first.id, speed_rpm=12.0)
    driver = session.add_driver_for_gear(second.id, speed_rpm=25.0, direction=-1)
    session.state.mode = MechanicalMode.TEST

    ctx = ToolContext()
    overlay = MechanicalTestOverlay("mechanical_motion", session)
    overlay.sync(ctx)
    window = ctx.overlay.window(TEST_WINDOW_ID)
    assert window is not None and window.visible
    rpm_fields = [field for field in window.fields if field.id.startswith(TEST_FIELD_PREFIX)]
    assert {field.id for field in rpm_fields} == {f"{TEST_FIELD_PREFIX}{driver.id}"}
    assert overlay.field_changed(f"{TEST_FIELD_PREFIX}{old_driver.id}", "10") is None
    assert overlay.field_changed(f"{TEST_FIELD_PREFIX}{driver.id}", "-42.5") == (driver.id, -42.5)
    assert driver.direction == -1
    assert driver.speed_rpm == 42.5

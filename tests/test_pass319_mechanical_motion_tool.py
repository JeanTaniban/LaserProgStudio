# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import Counter
from math import isclose, prod

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.ids import TOOL_MECHANICAL_MOTION
from laserprog_studio.tooling.mechanical_motion.gear_solver import distributed_stage_reductions, solve_chain
from laserprog_studio.tooling.mechanical_motion.geometry import build_gear_mesh
from laserprog_studio.tooling.mechanical_motion.kinematics import solve_kinematics
from laserprog_studio.tooling.mechanical_motion.models import GearChainSpec, GearSpec, MechanicalAssembly
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.serialization import assembly_from_mesh, attach_source, serialize_assembly, deserialize_assembly
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion_tool import MechanicalMotionCreatorTool, MechanicalMotionTool
from laserprog_studio.tooling.registry import get_studio_tool


def _set_horizontal_plane(session: MechanicalSession, point=(0.0, 0.0, 0.0)) -> None:
    session.set_work_plane(MechanicalWorkPlane.horizontal_at(point))


def _pick_horizontal_plane(tool: MechanicalMotionCreatorTool, ctx: ToolContext, point=(0.0, 0.0, 0.0)) -> None:
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=point, button=MouseButton.LEFT),
        ctx,
    )


def _closed_edge_counts(mesh: WorkMesh) -> Counter[tuple[int, int]]:
    counts: Counter[tuple[int, int]] = Counter()
    for a, b, c in mesh.triangles:
        for u, v in ((a, b), (b, c), (c, a)):
            counts[tuple(sorted((u, v)))] += 1
    return counts


def test_mechanical_tool_is_registered_as_creator_runtime() -> None:
    runtime = get_studio_tool(TOOL_MECHANICAL_MOTION)
    assert isinstance(runtime, MechanicalMotionTool)
    assert isinstance(runtime.creator, MechanicalMotionCreatorTool)
    assert runtime.spec.panel_index == 32


def test_ratio_distribution_preserves_total_and_moves_reduction() -> None:
    early = distributed_stage_reductions(10.0, 4, -1.0)
    even = distributed_stage_reductions(10.0, 4, 0.0)
    late = distributed_stage_reductions(10.0, 4, 1.0)
    assert isclose(prod(early), 10.0, rel_tol=1e-12)
    assert isclose(prod(even), 10.0, rel_tol=1e-12)
    assert isclose(prod(late), 10.0, rel_tol=1e-12)
    assert early[0] > early[-1]
    assert late[0] < late[-1]
    assert all(isclose(value, even[0], rel_tol=1e-12) for value in even)


def test_curve_chain_builds_compound_tangent_stages() -> None:
    chain = GearChainSpec(
        start=(0.0, 0.0, 0.0),
        end=(180.0, 30.0, 0.0),
        control_1=(45.0, 80.0, 0.0),
        control_2=(130.0, -40.0, 0.0),
        intermediate_shaft_count=3,
        total_reduction=10.0,
        ratio_distribution=0.4,
    )
    result = solve_chain(chain)
    assert result.chain.shafts[0] == chain.start
    assert result.chain.shafts[-1] == chain.end
    assert len(result.chain.shafts) == 5
    assert len(result.stages) == 4
    assert len(result.gears) == 8
    gears = {gear.id: gear for gear in result.gears}
    for stage in result.stages:
        driver = gears[stage.driver_gear_id]
        driven = gears[stage.driven_gear_id]
        assert isclose(driver.pitch_radius_mm + driven.pitch_radius_mm, stage.center_distance_mm, rel_tol=1e-9, abs_tol=1e-8)
    assert isclose(result.chain.actual_reduction, prod(stage.actual_reduction for stage in result.stages), rel_tol=1e-12)


def test_generated_gear_mesh_is_closed_and_serialization_roundtrips() -> None:
    gear = GearSpec(center=(12.0, -3.0, 4.0), teeth=28, module_mm=1.5, thickness_mm=5.0, bore_diameter_mm=6.0)
    mesh = build_gear_mesh(gear)
    assert mesh.vertices
    assert mesh.triangles
    assert set(_closed_edge_counts(mesh).values()) == {2}

    assembly = MechanicalAssembly()
    gear.shaft_id = gear.id
    assembly.gears[gear.id] = gear
    assembly.selected_element_id = gear.id
    restored = deserialize_assembly(serialize_assembly(assembly))
    assert restored is not None
    assert restored.id == assembly.id
    assert restored.gears[gear.id].teeth == 28
    attach_source(mesh, assembly)
    assert assembly_from_mesh(mesh).id == assembly.id


def test_compound_kinematics_reaches_requested_output_shaft() -> None:
    session = MechanicalSession()
    session.begin([])
    _set_horizontal_plane(session)
    chain = session.add_chain((0.0, 0.0, 0.0), (160.0, 0.0, 0.0), intermediate_shaft_count=2, total_reduction=8.0)
    input_gear = chain.gear_ids[0]
    session.add_driver_for_gear(input_gear, speed_rpm=60.0)
    state = solve_kinematics(session.assembly, 80.0)
    output_shaft = chain.shaft_ids[-1]
    expected = 80.0 * ((-1.0) ** chain.stage_count) / chain.actual_reduction
    assert isclose(state.shaft_angles_deg[output_shaft], expected, rel_tol=1e-9)


def test_attachment_preview_is_rebuilt_from_immutable_baseline() -> None:
    part = WorkMesh(name="arm", vertices=[(10.0, 0.0, 0.0), (12.0, 0.0, 0.0), (10.0, 2.0, 0.0)], triangles=[(0, 1, 2)])
    session = MechanicalSession()
    session.begin([part])
    _set_horizontal_plane(session)
    gear = session.add_gear((0.0, 0.0, 0.0))
    session.add_driver_for_gear(gear.id)
    session.attach_meshes([part.mesh_id], source_element_id=gear.id)
    first = session.build_preview(test_angle_deg=90.0).meshes[0]
    second = session.build_preview(test_angle_deg=90.0).meshes[0]
    assert first.vertices == second.vertices
    assert all(isclose(actual, expected, abs_tol=1e-12) for actual, expected in zip(first.vertices[0], (0.0, 10.0, 0.0)))


def test_cancel_saves_recoverable_draft_and_reopen_restores_state() -> None:
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    _pick_horizontal_plane(tool, ctx)
    ctx.inspector.update_value("mechanical_mode", "place_gear", notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(20.0, 30.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    assert tool.on_cancel(ctx)
    assert len(store.committed_meshes) == 1
    draft = store.committed_meshes[0]
    assert draft.color == "#F44336"
    restored = assembly_from_mesh(draft)
    assert restored is not None
    assert len(restored.gears) == 1

    ctx2 = ToolContext()
    ctx2.document.bind(store)
    ctx2.scene_selection.set_selected((0,))
    reopened = MechanicalMotionCreatorTool()
    reopened.open(ctx2)
    assert len(reopened.assembly.gears) == 1
    assert next(iter(reopened.assembly.gears.values())).center == (20.0, 30.0, 3.0)


def test_chain_rebuild_preserves_driver_and_attachment_references() -> None:
    part = WorkMesh(name="output", vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], triangles=[(0, 1, 2)])
    session = MechanicalSession()
    session.begin([part])
    _set_horizontal_plane(session)
    chain = session.add_chain((0.0, 0.0, 0.0), (180.0, 0.0, 0.0), intermediate_shaft_count=2)
    input_id = chain.gear_ids[0]
    output_id = chain.gear_ids[-1]
    driver = session.add_driver_for_gear(input_id)
    attachment = session.attach_meshes([part.mesh_id], source_element_id=output_id)

    chain.total_reduction = 12.0
    session.rebuild_chain(chain.id)
    assert driver.target_gear_id == input_id
    assert attachment.source_gear_id == output_id
    assert driver.target_gear_id in session.assembly.gears
    assert attachment.source_gear_id in session.assembly.gears

    chain.intermediate_shaft_count = 4
    session.rebuild_chain(chain.id)
    assert driver.target_gear_id in session.assembly.gears
    assert attachment.source_gear_id in session.assembly.gears
    assert driver.target_gear_id == chain.gear_ids[0]
    assert attachment.source_gear_id == chain.gear_ids[-1]


def test_edit_after_apply_is_preserved_as_updated_draft_on_close() -> None:
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    _pick_horizontal_plane(tool, ctx)
    ctx.inspector.update_value("mechanical_mode", "place_gear", notify=True)
    tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(0.0, 0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    assert tool.on_apply(ctx)
    assert store.committed_meshes[0].color != "#F44336"

    current_teeth = next(iter(tool.assembly.gears.values())).teeth
    updated_teeth = current_teeth + 1
    ctx.inspector.update_value("gear_teeth", updated_teeth, notify=True)
    tool.on_close(ctx)
    assert len(store.committed_meshes) == 1
    assert store.committed_meshes[0].color == "#F44336"
    restored = assembly_from_mesh(store.committed_meshes[0])
    assert restored is not None
    assert next(iter(restored.gears.values())).teeth == updated_teeth


def test_zero_bore_builds_a_closed_solid_centre() -> None:
    mesh = build_gear_mesh(GearSpec(teeth=18, module_mm=2.0, bore_diameter_mm=0.0))
    assert set(_closed_edge_counts(mesh).values()) == {2}
    assert (0.0, 0.0, -3.0) in mesh.vertices
    assert (0.0, 0.0, 3.0) in mesh.vertices


def test_existing_driver_part_moves_and_reopens_without_disappearing() -> None:
    part = WorkMesh(name="motor", vertices=[(10.0, 0.0, 0.0), (12.0, 0.0, 0.0), (10.0, 2.0, 0.0)], triangles=[(0, 1, 2)])
    session = MechanicalSession()
    session.begin([part])
    _set_horizontal_plane(session)
    session.add_driver_for_mesh(part.mesh_id, (0.0, 0.0, 0.0), speed_rpm=20.0)
    moved = session.build_preview(test_angle_deg=90.0)
    assert len(moved.meshes) == 1
    assert all(isclose(a, b, abs_tol=1e-12) for a, b in zip(moved.meshes[0].vertices[0], (0.0, 10.0, 0.0)))

    applied = session.applied_meshes()
    assert len(applied) == 1
    assert assembly_from_mesh(applied[0]) is not None
    reopened = MechanicalSession()
    reopened.begin(applied, selected_meshes=applied)
    preview = reopened.build_preview(test_angle_deg=0.0)
    assert len(preview.meshes) == 1
    assert preview.meshes[0].mesh_id == part.mesh_id

    draft = reopened.draft_meshes()
    assert len(draft) == 2
    carriers = [mesh for mesh in draft if mesh.mesh_id == part.mesh_id]
    placeholders = [mesh for mesh in draft if mesh.mesh_id != part.mesh_id]
    assert len(carriers) == 1 and assembly_from_mesh(carriers[0]) is None
    assert len(placeholders) == 1 and assembly_from_mesh(placeholders[0]) is not None


def test_test_animation_reuses_cached_gear_geometry(monkeypatch) -> None:
    import laserprog_studio.tooling.mechanical_motion.compound_geometry as compound_module

    calls = 0
    original = compound_module.build_gear_mesh

    def counted(gear, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original(gear, *args, **kwargs)

    monkeypatch.setattr(compound_module, "build_gear_mesh", counted)
    session = MechanicalSession()
    session.begin([])
    _set_horizontal_plane(session)
    session.add_gear((0.0, 0.0, 0.0), teeth=40)
    session.build_preview(test_angle_deg=0.0)
    session.build_preview(test_angle_deg=45.0)
    session.build_preview(test_angle_deg=90.0)
    assert calls == 1

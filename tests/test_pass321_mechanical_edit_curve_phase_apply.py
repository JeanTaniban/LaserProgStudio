# -*- coding: utf-8 -*-
from __future__ import annotations

from math import atan2, degrees
from types import SimpleNamespace

from laserprog_studio.domain.work_model import ModelStore, WorkMesh
from laserprog_studio.tool_core import MouseButton, ToolContext, ToolEvent, ToolEventType
from laserprog_studio.tooling.mechanical_motion.gear_solver import solve_chain
from laserprog_studio.tooling.mechanical_motion.geometry import _outer_profile_points
from laserprog_studio.tooling.mechanical_motion.interactions import MechanicalInteractionService
from laserprog_studio.tooling.mechanical_motion.models import GearChainSpec, GearSpec, ToothProfile
from laserprog_studio.tooling.mechanical_motion.opening import MechanicalOpenService
from laserprog_studio.tooling.mechanical_motion.parameters import MechanicalParameterService
from laserprog_studio.tooling.mechanical_motion.plane import MechanicalWorkPlane
from laserprog_studio.tooling.mechanical_motion.rendering import MechanicalRenderer
from laserprog_studio.tooling.mechanical_motion.serialization import assembly_from_mesh
from laserprog_studio.tooling.mechanical_motion.session import MechanicalSession
from laserprog_studio.tooling.mechanical_motion.state_machine import MechanicalWorkflowMachine
from laserprog_studio.tooling.mechanical_motion_tool import MechanicalMotionCreatorTool


def _cyclic_error(value: float, target: float, period: float) -> float:
    return ((float(value) - float(target) + 0.5 * period) % period) - 0.5 * period


def _add_one_gear(tool: MechanicalMotionCreatorTool, ctx: ToolContext) -> None:
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(0.0, 0.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )
    ctx.inspector.update_value("mechanical_mode", "place_gear", notify=True)
    assert tool.on_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(20.0, 5.0, 0.0), button=MouseButton.LEFT),
        ctx,
    )


def test_selecting_construction_plane_never_aligns_or_locks_camera(monkeypatch) -> None:
    from laserprog_studio.tool_api import plan2d

    camera_calls: list[object] = []
    monkeypatch.setattr(
        plan2d,
        "align_camera_to_plan_surface",
        lambda *args, **kwargs: camera_calls.append((args, kwargs)),
    )
    session = MechanicalSession()
    session.begin([])
    parameters = MechanicalParameterService(session)
    interactions = MechanicalInteractionService(session, MechanicalWorkflowMachine(session.state), parameters)
    ctx = ToolContext()

    assert interactions.handle_event(
        ToolEvent(ToolEventType.MOUSE_RELEASE, world_pos=(3.0, 4.0, 5.0), button=MouseButton.LEFT),
        ctx,
        sync=lambda *_args, **_kwargs: None,
    )
    assert session.work_plane is not None
    assert camera_calls == []


def test_generic_host_apply_is_not_rewritten_as_a_red_draft_on_close() -> None:
    store = ModelStore()
    ctx = ToolContext()
    ctx.document.bind(store)
    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    _add_one_gear(tool, ctx)

    # Studio's main Apply button commits an existing Creator preview itself and
    # then closes the tool without calling MechanicalMotionCreatorTool.on_apply.
    assert ctx.document.has_preview
    assert ctx.document.commit_preview(label="Host Apply", operation_type="tool_apply")
    tool.on_close(ctx)

    assert len(store.committed_meshes) == 1
    applied = store.committed_meshes[0]
    assert applied.color != "#F44336"
    restored = assembly_from_mesh(applied)
    assert restored is not None
    assert restored.draft is False


def test_curve_drag_updates_only_the_bezier_until_release(monkeypatch) -> None:
    session = MechanicalSession()
    session.begin([])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    chain = session.add_chain((0.0, 0.0, 0.0), (160.0, 20.0, 0.0), intermediate_shaft_count=3)
    parameters = MechanicalParameterService(session)
    interactions = MechanicalInteractionService(session, MechanicalWorkflowMachine(session.state), parameters)

    rebuild_calls: list[str] = []
    original_rebuild = session.rebuild_chain

    def counted_rebuild(chain_id: str):
        rebuild_calls.append(chain_id)
        return original_rebuild(chain_id)

    monkeypatch.setattr(session, "rebuild_chain", counted_rebuild)
    actor = SimpleNamespace(
        points=[(42.0, 72.0, 9.0)],
        metadata={"mechanical_role": "chain_control_1", "mechanical_element_id": chain.id},
    )
    ctx = SimpleNamespace(
        selection=SimpleNamespace(actor=lambda _actor_id: actor),
        inspector=ToolContext().inspector,
    )
    sync_calls: list[dict[str, object]] = []

    def sync(_ctx, status=None, **kwargs):
        sync_calls.append({"status": status, **kwargs})

    interactions.handle_native_result(
        ctx,
        SimpleNamespace(action="drag", grabbed_ids=("control",)),
        sync=sync,
    )
    assert rebuild_calls == []
    assert chain.control_1 == (42.0, 72.0, 0.0)
    assert sync_calls[-1]["update_mesh_preview"] is False

    interactions.handle_native_result(
        ctx,
        SimpleNamespace(action="release", grabbed_ids=("control",)),
        sync=sync,
    )
    assert rebuild_calls == [chain.id]
    assert sync_calls[-1]["update_mesh_preview"] is True


def test_curved_chain_phase_uses_each_real_mesh_direction() -> None:
    plane = MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0))
    chain = GearChainSpec(
        start=(0.0, 0.0, 0.0),
        end=(190.0, 35.0, 0.0),
        control_1=(35.0, 105.0, 0.0),
        control_2=(145.0, -80.0, 0.0),
        intermediate_shaft_count=4,
        total_reduction=7.5,
    )
    result = solve_chain(chain, plane=plane)
    gears = {gear.id: gear for gear in result.gears}

    for stage in result.stages:
        driver = gears[stage.driver_gear_id]
        driven = gears[stage.driven_gear_id]
        theta = plane.angle_deg(result.chain.shafts[stage.index], result.chain.shafts[stage.index + 1])
        driver_pitch = 360.0 / driver.teeth
        driven_pitch = 360.0 / driven.teeth
        assert abs(_cyclic_error(driver.phase_deg, theta, driver_pitch)) < 1.0e-8
        driven_gap_angle = driven.phase_deg + 0.5 * driven_pitch
        assert abs(_cyclic_error(driven_gap_angle, theta + 180.0, driven_pitch)) < 1.0e-8


def test_backlash_keeps_the_rendered_tooth_centred_on_solved_phase() -> None:
    for profile, outer_indices in (
        (ToothProfile.TRAPEZOID, (2, 3)),
        (ToothProfile.INVOLUTE_APPROX, (4, 5)),
    ):
        gear = GearSpec(
            teeth=24,
            module_mm=2.0,
            backlash_mm=0.8,
            phase_deg=37.0,
            profile=profile,
        )
        points = _outer_profile_points(gear)
        flank_angles = [degrees(atan2(points[index][1], points[index][0])) for index in outer_indices]
        tooth_center = 0.5 * sum(flank_angles)
        assert abs(_cyclic_error(tooth_center, gear.phase_deg, 360.0)) < 1.0e-8


def test_driver_and_moving_parts_have_explicit_persistent_overlays() -> None:
    part = WorkMesh(
        name="arm",
        vertices=[(70.0, 0.0, 0.0), (90.0, 0.0, 0.0), (90.0, 8.0, 0.0), (70.0, 8.0, 0.0)],
        triangles=[(0, 1, 2), (0, 2, 3)],
    )
    session = MechanicalSession()
    session.begin([part])
    session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 0.0)))
    gear = session.add_gear((20.0, 20.0, 0.0), teeth=28)
    driver = session.add_driver_for_gear(gear.id, speed_rpm=24.0)
    attachment = session.attach_meshes([part.mesh_id], source_element_id=gear.id)

    ctx = ToolContext()
    store = ModelStore()
    store.set_meshes([part], push_undo=False)
    ctx.document.bind(store)
    renderer = MechanicalRenderer("mechanical_motion", session)
    renderer.sync_mesh_preview(ctx)
    renderer.sync_projected_markers(ctx)
    ids = {primitive.id for primitive in ctx.projected_drawing.for_tool("mechanical_motion").items()}

    assert f"mechanical:driver:{driver.id}:label" in ids
    assert f"mechanical:attachment:{attachment.id}:label" in ids
    assert f"mechanical:attachment:{attachment.id}:target:{part.mesh_id}:surface" in ids
    assert f"mechanical:attachment:{attachment.id}:link:{part.mesh_id}" in ids


def test_open_choice_supports_edit_new_on_same_plane_and_cancel() -> None:
    session = MechanicalSession()
    session.begin([])
    plane = session.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 4.0)))
    session.add_gear((10.0, 10.0, 4.0))
    source_mesh = session.applied_meshes()[-1]
    service = MechanicalOpenService()

    for decision in ("edit", "new", "cancel"):
        owner = SimpleNamespace(ask_mechanical_edit_or_new=lambda _mesh, _assembly, value=decision: value)
        result = service.resolve(SimpleNamespace(owner=owner), (source_mesh,))
        assert result.decision == decision
        if decision == "edit":
            assert result.edit_meshes == (source_mesh,)
        elif decision == "new":
            assert result.edit_meshes == ()
            assert result.inherited_plane is not None
            assert result.inherited_plane is not plane
            assert result.inherited_plane.normal == plane.normal
        else:
            assert result.cancelled


def test_new_assembly_choice_preserves_old_geometry_and_reuses_its_plane() -> None:
    original = MechanicalSession()
    original.begin([])
    plane = original.set_work_plane(MechanicalWorkPlane.horizontal_at((0.0, 0.0, 3.0)))
    original.add_gear((0.0, 0.0, 3.0))
    applied = list(original.applied_meshes())
    store = ModelStore()
    store.set_meshes(applied, push_undo=False)
    ctx = ToolContext(owner=SimpleNamespace(ask_mechanical_edit_or_new=lambda _mesh, _assembly: "new"))
    ctx.document.bind(store)
    ctx.scene_selection.set_selected((0,))

    tool = MechanicalMotionCreatorTool()
    tool.open(ctx)
    assert tool.assembly.id != original.assembly.id
    assert not tool.assembly.gears
    assert tool._session.work_plane is not None
    assert tool._session.work_plane.normal == plane.normal
    assert len(tool._session.base_without_current_assembly()) == len(applied)

# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from laserprog_studio.tool_api.core import MouseButton, ToolEvent, ToolEventType

from .models import MechanicalMode, point3
from .parameters import MechanicalParameterService
from .plane import MechanicalWorkPlane, pick_work_plane, placement_point
from .serialization import is_generated_mechanical_mesh, mesh_belongs_to_assembly
from .session import MechanicalSession
from .state_machine import MechanicalIntent, MechanicalWorkflowMachine
from .smart_snap import GearSnapCandidate

SyncCallback = Callable[..., None]


@dataclass(slots=True)
class _ActiveGearDrag:
    gear_id: str
    original_center: tuple[float, float, float]
    original_phase_deg: float
    last_candidate: GearSnapCandidate | None = None


class MechanicalInteractionService:
    """Coplanar mechanical interaction without taking ownership of the camera."""

    _SURFACE_PICK_CLICK_TOLERANCE_PX = 5.0

    def __init__(
        self,
        session: MechanicalSession,
        machine: MechanicalWorkflowMachine,
        parameters: MechanicalParameterService,
    ) -> None:
        self.session = session
        self.machine = machine
        self.parameters = parameters
        self._active_gear_drag: _ActiveGearDrag | None = None

    def replace_machine(self, machine: MechanicalWorkflowMachine) -> None:
        self.machine = machine

    def cancel_active_gear_drag(self) -> bool:
        active = self._active_gear_drag
        if active is None:
            return False
        gear = self.session.assembly.gears.get(active.gear_id)
        if gear is not None:
            gear.center = active.original_center
            gear.phase_deg = active.original_phase_deg
        self._active_gear_drag = None
        return True

    def _pick_work_plane(self, event: ToolEvent, ctx: Any, *, sync: SyncCallback) -> bool:
        state = self.session.state
        assembly = self.session.assembly
        if self.session.work_plane is not None and (assembly.gears or assembly.chains or assembly.racks or assembly.drivers):
            if event.type is ToolEventType.MOUSE_RELEASE and event.button in {MouseButton.LEFT, MouseButton.NONE}:
                self.machine.dispatch(MechanicalIntent.SELECT)
                sync(ctx, "The construction plane is already defined for this assembly. Reset it before choosing another face.", update_mesh_preview=False)
                return True
            return False
        if event.type is ToolEventType.MOUSE_PRESS and event.button in {MouseButton.LEFT, MouseButton.NONE}:
            state.surface_pick_press_screen_pos = tuple(event.screen_pos) if event.screen_pos is not None else None
            return False
        if event.type is not ToolEventType.MOUSE_RELEASE or event.button not in {MouseButton.LEFT, MouseButton.NONE}:
            return False
        if event.screen_pos is not None and state.surface_pick_press_screen_pos is not None:
            dx = abs(float(event.screen_pos[0]) - float(state.surface_pick_press_screen_pos[0]))
            dy = abs(float(event.screen_pos[1]) - float(state.surface_pick_press_screen_pos[1]))
            state.surface_pick_press_screen_pos = None
            if max(dx, dy) > self._SURFACE_PICK_CLICK_TOLERANCE_PX:
                return False
        plane: MechanicalWorkPlane | None = None
        if event.screen_pos is not None:
            plane = pick_work_plane(ctx, event.screen_pos, diagnostics=False)
        elif event.world_pos is not None:
            # Headless/test fallback. The production viewport always uses the
            # face raycast above; this keeps domain tests deterministic.
            plane = MechanicalWorkPlane.horizontal_at(point3(event.world_pos))
        if plane is None:
            sync(ctx, "No planar face was hit. Click a real model face to define the construction plane.", update_mesh_preview=False)
            return True
        self.session.set_work_plane(plane)
        self.machine.dispatch(MechanicalIntent.SELECT)
        self.parameters.sync_inspector(ctx)
        sync(ctx, "Mechanical construction plane selected. Geometry stays coplanar and the camera remains free to orbit.")
        return True

    def _placement(self, event: ToolEvent, ctx: Any) -> tuple[float, float, float] | None:
        plane = self.session.work_plane
        if plane is None:
            return None
        return placement_point(ctx, event.screen_pos, event.world_pos, plane)

    def handle_event(self, event: ToolEvent, ctx: Any, *, sync: SyncCallback) -> bool:
        if event.is_delete:
            if not self.session.remove_selected():
                sync(ctx, "No mechanical element is selected.")
                return False
            self.parameters.sync_inspector(ctx)
            sync(ctx, "Selected mechanical element deleted.")
            return True

        if self.session.state.mode is MechanicalMode.PICK_PLANE:
            return self._pick_work_plane(event, ctx, sync=sync)

        if event.type is not ToolEventType.MOUSE_RELEASE or event.button not in {MouseButton.LEFT, MouseButton.NONE}:
            return False
        position = self._placement(event, ctx)
        if position is None:
            self.machine.dispatch(MechanicalIntent.PICK_PLANE)
            sync(ctx, "Select the mechanical construction plane first.", update_mesh_preview=False)
            return True
        mode = self.session.state.mode
        if mode is MechanicalMode.PLACE_GEAR:
            self.session.add_gear(position, **self.parameters.gear_defaults(ctx))
            self.machine.dispatch(MechanicalIntent.SELECT)
            self.parameters.sync_inspector(ctx)
            sync(ctx, "Gear created on the construction plane.")
            return True
        if mode is MechanicalMode.PLACE_CHAIN_START:
            result = self.machine.accept_chain_start(position)
            sync(ctx, result.message, update_mesh_preview=False)
            return True
        if mode is MechanicalMode.PLACE_CHAIN_END:
            start = self.session.state.pending_chain_start
            if start is None:
                self.machine.dispatch(MechanicalIntent.START_CHAIN)
                sync(ctx, "Chain start was missing. Click the start shaft again.", update_mesh_preview=False)
                return True
            chain = self.session.add_chain(start, position, **self.parameters.chain_defaults(ctx))
            self.session.state.pending_chain_start = None
            self.session.state.mode = MechanicalMode.EDIT_CURVE
            self.session.state.last_status = "Gear chain created. Drag its two planar Bézier handles to adjust the route."
            self.parameters.sync_inspector(ctx)
            sync(ctx)
            if chain.warning:
                ctx.status.warning(chain.warning)
            return True
        if mode is MechanicalMode.PLACE_RACK_START:
            result = self.machine.accept_rack_start(position)
            sync(ctx, result.message, update_mesh_preview=False)
            return True
        if mode is MechanicalMode.PLACE_RACK_END:
            start = self.session.state.pending_rack_start
            pinion_id = str(self.session.state.pending_rack_pinion_gear_id or "")
            if start is None or pinion_id not in self.session.assembly.gears:
                result = self.machine.dispatch(MechanicalIntent.START_RACK)
                sync(ctx, result.message, update_mesh_preview=False)
                return True
            rack = self.session.add_rack(start, position, pinion_gear_id=pinion_id, **self.parameters.rack_defaults(ctx))
            self.session.state.pending_rack_start = None
            self.session.state.pending_rack_pinion_gear_id = None
            self.machine.dispatch(MechanicalIntent.SELECT)
            self.session.assembly.selected_element_id = rack.id
            self.parameters.sync_inspector(ctx)
            sync(ctx, "Rack created and snapped tangent to its pinion.")
            return True
        if mode is MechanicalMode.PLACE_DRIVER_CENTER:
            mesh_id = self.session.state.pending_driver_mesh_id
            if mesh_id:
                self.session.add_driver_for_mesh(mesh_id, position, **self.parameters.driver_defaults(ctx))
                self.session.state.pending_driver_mesh_id = None
                self.machine.dispatch(MechanicalIntent.SELECT)
                self.parameters.sync_inspector(ctx)
                sync(ctx, "Rotary driver created on the work-plane axis.")
                return True
        if mode is MechanicalMode.SELECT:
            selected = self.session.select_nearest_marker(position, tolerance_mm=10.0)
            if selected:
                self.parameters.sync_inspector(ctx)
                sync(ctx, "Mechanical element selected.", update_mesh_preview=False)
                return True
        return False

    def handle_scene_selection_changed(self, ctx: Any, *, sync: SyncCallback) -> None:
        mode = self.session.state.mode
        active = ctx.scene_selection.active_object()
        if active is None:
            if mode is MechanicalMode.PICK_ATTACHMENTS:
                result = self.machine.update_attachment_targets(())
                sync(ctx, result.message, update_mesh_preview=False)
            return
        mesh = getattr(active, "mesh", None)
        if mesh is None:
            return

        if mode is MechanicalMode.SELECT:
            if self.session.select_from_mesh(mesh):
                self.parameters.sync_inspector(ctx)
                sync(ctx, "Mechanical mesh selected.", update_mesh_preview=False)
            return

        if mode is MechanicalMode.PICK_RACK_PINION:
            gear_id = self.session.gear_id_from_mesh(mesh)
            result = self.machine.accept_rack_pinion(gear_id)
            sync(ctx, result.message, update_mesh_preview=False)
            return

        if mode is MechanicalMode.PICK_DRIVER_TARGET:
            gear_id = self.session.gear_id_from_mesh(mesh)
            if gear_id:
                self.session.add_driver_for_gear(gear_id, **self.parameters.driver_defaults(ctx))
                self.machine.dispatch(MechanicalIntent.SELECT)
                self.parameters.sync_inspector(ctx)
                sync(ctx, "Driver assigned to the clicked gear mesh. The previous driver was replaced.")
                return
            result = self.machine.accept_driver_target(active.id)
            sync(ctx, result.message, update_mesh_preview=False)
            return

        if mode is MechanicalMode.PICK_ATTACHMENT_SOURCE:
            source_id = self.session.attachment_source_from_mesh(mesh)
            result = self.machine.accept_attachment_source(source_id)
            sync(ctx, result.message, update_mesh_preview=False)
            return

        if mode is MechanicalMode.PICK_ATTACHMENTS:
            mesh_ids: list[str] = []
            assembly_id = self.session.assembly.id
            source_id = str(self.session.state.pending_attachment_source_id or "")
            source_driver = self.session.assembly.drivers.get(source_id)
            excluded_driver_mesh_id = str(source_driver.target_mesh_id or "") if source_driver is not None else ""
            for obj in ctx.scene_selection.selected_objects():
                candidate_mesh = getattr(obj, "mesh", None)
                if candidate_mesh is None:
                    continue
                candidate_id = str(getattr(obj, "id", "") or getattr(candidate_mesh, "mesh_id", "") or "")
                if not candidate_id or candidate_id == excluded_driver_mesh_id:
                    continue
                if mesh_belongs_to_assembly(candidate_mesh, assembly_id) and is_generated_mechanical_mesh(candidate_mesh):
                    continue
                mesh_ids.append(candidate_id)
            result = self.machine.update_attachment_targets(mesh_ids)
            sync(ctx, result.message, update_mesh_preview=False)

    def _manual_test_angle(self, ctx: Any, actor: Any, metadata: dict[str, Any]) -> bool:
        driver_id = str(metadata.get("mechanical_driver_id") or "")
        driver = self.session.assembly.drivers.get(driver_id)
        plane = self.session.work_plane
        if driver is None or plane is None or not getattr(actor, "points", ()):
            return False
        angle = plane.angle_deg(driver.center, point3(actor.points[0]))
        self.session.state.driver_angles_deg[driver_id] = angle
        self.session.state.test_angle_deg = angle
        self.session.state.test_playing = False
        return True

    def handle_native_result(self, ctx: Any, result: Any, *, sync: SyncCallback) -> None:
        action = str(getattr(result, "action", "") or "")
        if action == "select" and getattr(result, "hit", None) is not None:
            actor = ctx.selection.actor(str(result.hit.actor_id))
            metadata = (getattr(actor, "metadata", {}) or {}) if actor is not None else {}
            element_id = str(metadata.get("mechanical_element_id") or "")
            gear_id = str(metadata.get("mechanical_gear_id") or "")
            mode = self.session.state.mode
            if mode is MechanicalMode.PICK_RACK_PINION:
                accepted = self.machine.accept_rack_pinion(gear_id if gear_id in self.session.assembly.gears else None)
                sync(ctx, accepted.message, update_mesh_preview=False)
                return
            if mode is MechanicalMode.PICK_DRIVER_TARGET and gear_id in self.session.assembly.gears:
                self.session.add_driver_for_gear(gear_id, **self.parameters.driver_defaults(ctx))
                self.machine.dispatch(MechanicalIntent.SELECT)
                self.parameters.sync_inspector(ctx)
                sync(ctx, "Driver assigned to the clicked gear. The previous driver was replaced.")
                return
            if mode is MechanicalMode.PICK_ATTACHMENT_SOURCE:
                source_id = element_id if element_id in self.session.assembly.all_element_ids() else None
                accepted = self.machine.accept_attachment_source(source_id)
                sync(ctx, accepted.message, update_mesh_preview=False)
                return
            if element_id in self.session.assembly.all_element_ids():
                self.session.assembly.selected_element_id = element_id
                self.session.state.driver_candidate_gear_id = gear_id if gear_id in self.session.assembly.gears else None
                self.parameters.sync_inspector(ctx)
                message = "Mechanical gear selected as driver target." if self.session.state.driver_candidate_gear_id else "Mechanical element selected."
                sync(ctx, message, update_mesh_preview=False)
            return
        if action not in {"drag", "release"}:
            return
        plane = self.session.work_plane
        if plane is None:
            return
        changed = False
        manual_test = False
        curve_changed = False
        curve_preview_chain_id: str | None = None
        non_curve_changed = False
        gear_drag_changed = False
        gear_drag_id: str | None = None
        gear_snap_candidate: GearSnapCandidate | None = None
        for actor_id in tuple(getattr(result, "grabbed_ids", ()) or ()):
            actor = ctx.selection.actor(str(actor_id))
            if actor is None or not getattr(actor, "points", ()):
                continue
            metadata = getattr(actor, "metadata", {}) or {}
            element_id = str(metadata.get("mechanical_element_id") or "")
            role = str(metadata.get("mechanical_role") or "")
            if role == "test_rotation_handle":
                manual_test = self._manual_test_angle(ctx, actor, metadata) or manual_test
                changed = manual_test or changed
                continue
            position = plane.clamp(point3(actor.points[0]))
            if role == "gear_center" and element_id in self.session.assembly.gears:
                gear = self.session.assembly.gears[element_id]
                if self.session.is_unique_standalone_gear(gear.id):
                    active = self._active_gear_drag
                    if active is None or active.gear_id != gear.id:
                        active = _ActiveGearDrag(
                            gear_id=gear.id,
                            original_center=gear.center,
                            original_phase_deg=float(gear.phase_deg),
                        )
                        self._active_gear_drag = active
                    gear_snap_candidate = self.session.preview_move_unique_gear(
                        gear.id,
                        position,
                        unsnapped_phase_deg=active.original_phase_deg,
                    )
                    active.last_candidate = gear_snap_candidate
                    gear_drag_id = gear.id
                    gear_drag_changed = True
                    changed = True
                    if action == "release":
                        self.session.commit_unique_gear_drag(gear.id, gear_snap_candidate)
                        self.parameters.sync_attachment_centres_for_gear(gear)
                        self._active_gear_drag = None
                        non_curve_changed = True
                    continue
                gear.center = plane.gear_center(position, gear.thickness_mm, layer=0)
                self.parameters.sync_attachment_centres_for_gear(gear)
                self.session.resnap_racks_for_gear(gear.id)
                from .shafts import normalize_coaxial_shafts
                normalize_coaxial_shafts(self.session.assembly, plane=plane)
                changed = True
                non_curve_changed = True
            elif role in {"chain_control_1", "chain_control_2"} and element_id in self.session.assembly.chains:
                chain = self.session.assembly.chains[element_id]
                if role.endswith("1"):
                    chain.control_1 = position
                else:
                    chain.control_2 = position
                # During drag, only the inexpensive Bézier overlay follows the
                # pointer. Tooth solving and mesh generation happen once, on
                # release, so the viewport stays fluid.
                if action == "release":
                    self.session.rebuild_chain(chain.id)
                changed = True
                curve_changed = True
                curve_preview_chain_id = chain.id
            elif role in {"rack_start", "rack_end"} and element_id in self.session.assembly.racks:
                rack = self.session.assembly.racks[element_id]
                if role == "rack_start":
                    rack.start = position
                else:
                    rack.end = position
                if action == "release":
                    self.session.rebuild_rack(rack.id)
                changed = True
                non_curve_changed = action == "release" or non_curve_changed
            elif role == "driver_center" and element_id in self.session.assembly.drivers:
                driver = self.session.assembly.drivers[element_id]
                driver.center = position
                self.parameters.sync_attachment_centres_for_driver(driver)
                changed = True
                non_curve_changed = True
        if not changed:
            return
        self.session.state.dirty = True
        if action == "release" or (non_curve_changed and not gear_drag_changed) or manual_test:
            self.parameters.sync_inspector(ctx)
        if manual_test:
            sync(ctx, "Actuator rotated manually.", update_mesh_preview=False, test_motion_only=True)
        elif gear_drag_changed and action == "drag" and gear_drag_id:
            sync(
                ctx,
                (
                    "Smart snap active: pitch contact and tooth phase aligned."
                    if gear_snap_candidate is not None
                    else "Gear drag preview: move near a compatible gear to snap."
                ),
                update_mesh_preview=False,
                gear_drag_gear_id=gear_drag_id,
                gear_snap_candidate=gear_snap_candidate,
                gear_drag_origin_center=self._active_gear_drag.original_center if self._active_gear_drag else None,
                gear_drag_origin_phase_deg=self._active_gear_drag.original_phase_deg if self._active_gear_drag else None,
            )
        elif gear_drag_changed and action == "release":
            sync(
                ctx,
                (
                    "Gear snapped, phased and connected to the target motion."
                    if gear_snap_candidate is not None
                    else "Gear moved and detached from any previous smart mesh."
                ),
                update_mesh_preview=True,
            )
        elif curve_changed and action == "drag" and not non_curve_changed:
            sync(
                ctx,
                "Curve route preview updated.",
                update_mesh_preview=False,
                curve_preview_chain_id=curve_preview_chain_id,
            )
        elif curve_changed and action == "release":
            sync(ctx, "Curve released; gears recalculated once on the new route.", update_mesh_preview=True)
        elif action == "drag":
            sync(ctx, "Mechanical geometry constrained to the construction plane.", update_mesh_preview=True)
        else:
            sync(ctx, "Mechanical geometry updated on the construction plane.")


__all__ = ["MechanicalInteractionService"]

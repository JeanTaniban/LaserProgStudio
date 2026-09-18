# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool, ToolEvent

from .base import ToolSpec
from .editable_mesh_hover import EditableHoverMesh, EditableMeshHoverPreview
from .ids import TOOL_MECHANICAL_MOTION
from .mechanical_motion.animation import MechanicalAnimationController
from .mechanical_motion.chain_overlay import MechanicalChainOverlay
from .mechanical_motion.commands import MechanicalCommandService
from .mechanical_motion.feedback import action_from_button, mode_from_button, sync_mechanical_toolbar
from .mechanical_motion.interactions import MechanicalInteractionService
from .mechanical_motion.models import MechanicalMode
from .mechanical_motion.opening import MechanicalOpenResolution, MechanicalOpenService
from .mechanical_motion.panel import build_mechanical_panel
from .mechanical_motion.parameters import MechanicalParameterService
from .mechanical_motion.rendering import MechanicalRenderer
from .mechanical_motion.session import MechanicalSession
from .mechanical_motion.serialization import assembly_from_mesh, mesh_belongs_to_assembly
from .mechanical_motion.state_machine import MechanicalIntent, MechanicalWorkflowMachine
from .mechanical_motion.smart_snap import GearSnapCandidate
from .mechanical_motion.test_overlay import MechanicalTestOverlay
from .mechanical_motion.workflow_overlay import MechanicalWorkflowOverlay


class MechanicalMotionCreatorTool(CreatorTool):
    """Creator lifecycle coordinator for the modular mechanical-motion services."""

    id = TOOL_MECHANICAL_MOTION
    label = "Mechanical motion"

    def __init__(self) -> None:
        self._session = MechanicalSession()
        self._machine = MechanicalWorkflowMachine(self._session.state)
        self._parameters = MechanicalParameterService(self._session)
        self._renderer = MechanicalRenderer(self.id, self._session)
        self._editable_hover = EditableMeshHoverPreview(
            self.id,
            "mechanical:editable_hover",
            metadata_role="mechanical_editable_hover",
        )
        self._commands = MechanicalCommandService(self._session, self._machine, self._parameters)
        self._interactions = MechanicalInteractionService(self._session, self._machine, self._parameters)
        self._test_overlay = MechanicalTestOverlay(self.id, self._session)
        self._chain_overlay = MechanicalChainOverlay(self.id, self._session)
        self._workflow_overlay = MechanicalWorkflowOverlay(self.id, self._session)
        self._animation = MechanicalAnimationController(self._on_animation_angles)
        self._opening = MechanicalOpenService()
        self._ctx: Any | None = None
        self._open_cancelled = False

    @property
    def assembly(self):
        return self._session.assembly

    def _replace_machine(self, machine: MechanicalWorkflowMachine) -> None:
        self._machine = machine
        self._commands.replace_machine(machine)
        self._interactions.replace_machine(machine)

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        self._editable_hover.reset()
        self._ctx = ctx
        self._open_cancelled = False
        self._commands.reset_open_state()
        try:
            from laserprog_studio.tool_api import plan2d

            # Mechanical construction uses a persistent geometric plane, but it
            # must never take ownership of the camera. Orbit stays available.
            plan2d.release_plan_view_camera(ctx)
        except Exception:
            pass
        document_ready = bool(ctx.document.ensure())
        meshes, source_path = ctx.document.snapshot() if document_ready else ([], None)
        selected = ctx.scene_selection.selected_meshes() if document_ready else ()
        opening = self._opening.resolve(ctx, selected)
        if opening.cancelled:
            # Cancel dismisses the Edit/New prompt but keeps the startup phase
            # active, matching Plan Tracer's non-destructive surface selection.
            opening = MechanicalOpenResolution("new")
            try:
                ctx.scene_selection.clear()
            except Exception:
                pass
        self._session.begin(
            meshes,
            source_path,
            selected_meshes=opening.edit_meshes,
            initial_work_plane=opening.inherited_plane,
        )
        self._replace_machine(MechanicalWorkflowMachine(self._session.state))
        self._register_workflow(ctx)
        self._register_modes(ctx)
        ctx.inspector.set_panel(
            build_mechanical_panel(
                on_mode_changed=lambda field_id, value: self._set_mode(ctx, value),
                on_value_changed=lambda field_id, value: self._on_value_changed(ctx, field_id, value),
                on_action=lambda event: self._handle_action_id(ctx, str(getattr(event, "action_id", "") or "")),
            )
        )
        self._parameters.sync_inspector(ctx)
        if opening.decision == "edit":
            message = "Mechanical assembly opened for editing. Orbit remains available."
        elif opening.inherited_plane is not None:
            message = "New mechanical assembly created on the same construction plane. Orbit remains available."
        elif self._session.work_plane is None:
            message = "Select a planar face for a new assembly, or select an existing MEC mesh to edit it. Orbit remains available."
        else:
            message = "Mechanical assembly restored on its construction plane. Orbit remains available."
        self._sync_all(ctx, message)
        ctx.status.info(message)

    def _register_workflow(self, ctx: Any) -> None:
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("plane", "Select construction plane", help="Click a planar model face. Geometry stays coplanar while the camera remains free to orbit."),
                ctx.workflow.step("create", "Create mechanism", help="Place gears, gear-chain curves, and rack-and-pinion elements on the construction plane."),
                ctx.workflow.step("connect", "Connect motion", help="Add rotary drivers and attach scene parts to rotary or linear outputs.", optional=True),
                ctx.workflow.step("test", "Test motion", help="Scrub or play the mechanism before Apply.", optional=True),
            ),
        )

    def _register_modes(self, ctx: Any) -> None:
        ctx.modes.register(
            self.id,
            tuple(ctx.modes.define(mode.value, mode.value.replace("_", " ").title()) for mode in MechanicalMode),
            active=self._session.state.mode.value,
        )

    def on_close(self, ctx: Any) -> None:
        self._animation.stop()
        state = self._session.state
        if not self._open_cancelled and state.dirty and not state.applied_since_open:
            try:
                committed_meshes, _source_path = ctx.document.snapshot()
            except Exception:
                committed_meshes = []
            if self._session.is_current_assembly_committed(committed_meshes):
                # The host committed our preview through its generic Apply path
                # before closing this Creator tool. Do not overwrite it as a
                # red draft during cleanup.
                state.applied_since_open = True
                state.dirty = False
                self._commands.draft_saved = False
                self._select_committed_assembly(ctx)
        if state.dirty and not state.applied_since_open and not self._commands.draft_saved:
            self._commands.save_draft(ctx, status=False)
        try:
            if ctx.document.has_preview:
                ctx.document.discard_preview()
        except Exception:
            pass
        self._editable_hover.hide(ctx, render=False)
        self._renderer.clear(ctx)
        try:
            ctx.overlay.hide_window("mechanical.motion.test")
        except Exception:
            pass
        for window_id in ("mechanical.motion.chain", "mechanical.motion.workflow"):
            try:
                ctx.overlay.hide_window(window_id)
            except Exception:
                pass
        try:
            from laserprog_studio.tool_api import plan2d

            plan2d.release_plan_view_camera(ctx)
        except Exception:
            pass
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import clear_creator_viewport_ui

                clear_creator_viewport_ui(owner, self.id, render=True)
            except Exception:
                pass
        self._ctx = None
        ctx.inspector.clear()

    def can_apply(self, ctx: Any) -> bool:  # noqa: ARG002
        return bool(self.assembly.gears or self.assembly.racks or self.assembly.drivers)

    def on_apply(self, ctx: Any) -> bool:
        if not self.can_apply(ctx):
            ctx.status.warning("Add at least one mechanical element or rotary driver before applying.")
            return False
        self._animation.stop()
        self._renderer.end_gear_drag(ctx, render=False)
        self._renderer.end_live_motion(ctx, render=False)
        self._session.state.test_playing = False
        self._session.state.test_angle_deg = 0.0
        self._session.state.driver_angles_deg = {driver_id: 0.0 for driver_id in self.assembly.drivers}
        try:
            ctx.document.set_preview_meshes(self._session.applied_meshes())
            changed = ctx.document.commit_preview(label="Apply mechanical assembly", operation_type="mechanical_motion_apply")
        except Exception as exc:
            ctx.status.error(f"Mechanical assembly could not be applied: {exc}")
            return False
        if not changed:
            ctx.status.warning("Mechanical assembly did not change the document.")
            return False
        self._session.mark_applied()
        self._commands.draft_saved = False
        self._select_committed_assembly(ctx)
        self._sync_all(ctx, "Mechanical assembly applied and remains editable.")
        ctx.status.info("Mechanical assembly applied.")
        return True

    def on_cancel(self, ctx: Any) -> bool:
        self._animation.stop()
        self._interactions.cancel_active_gear_drag()
        self._renderer.end_gear_drag(ctx, render=False)
        self._renderer.end_live_motion(ctx, render=False)
        if self.assembly.gears or self.assembly.racks or self.assembly.drivers:
            return self._commands.save_draft(ctx)
        try:
            if ctx.document.has_preview:
                ctx.document.discard_preview()
        except Exception:
            pass
        return True

    def wants_native_actor_interaction(self, event: ToolEvent, ctx: Any) -> bool:  # noqa: ARG002
        return self._session.state.mode in {
            MechanicalMode.SELECT,
            MechanicalMode.EDIT_CURVE,
            MechanicalMode.PICK_DRIVER_TARGET,
            MechanicalMode.PICK_RACK_PINION,
            MechanicalMode.PICK_ATTACHMENT_SOURCE,
            MechanicalMode.TEST,
        }

    def on_event(self, event: ToolEvent, ctx: Any) -> bool:
        from laserprog_studio.tool_api.core import MouseButton, ToolEventType

        if event.is_escape:
            self._editable_hover.hide(ctx, render=False)
            if self._interactions.cancel_active_gear_drag():
                self._renderer.end_gear_drag(ctx, render=False)
                self._sync_all(ctx, "Gear drag cancelled; original position restored.")
                return True
            self._machine.dispatch(MechanicalIntent.CANCEL_STEP)
            self._set_playing(ctx, False)
            self._sync_all(ctx)
            return True
        if event.type is ToolEventType.MOUSE_MOVE:
            if self._startup_can_open_existing() and event.button is MouseButton.NONE:
                self._update_startup_editable_hover(ctx, event.screen_pos)
            elif self._editable_hover.visible:
                self._editable_hover.hide(ctx, render=True)
        if self._try_open_assembly_from_event(event, ctx):
            return True
        return self._interactions.handle_event(event, ctx, sync=self._sync_all)

    def on_scene_selection_changed(self, ctx: Any) -> None:
        if self._try_open_selected_assembly(ctx):
            return
        self._interactions.handle_scene_selection_changed(ctx, sync=self._sync_all)

    def on_native_interaction_result(self, event: ToolEvent, ctx: Any, result: Any) -> None:  # noqa: ARG002
        was_playing = self._session.state.test_playing
        self._interactions.handle_native_result(ctx, result, sync=self._sync_all)
        if was_playing and not self._session.state.test_playing:
            self._animation.stop()

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        workflow_action = self._workflow_overlay.action_from_button(button_id)
        if workflow_action:
            self._handle_action_id(ctx, workflow_action)
            return
        chain_action = self._chain_overlay.action_from_button(button_id)
        if chain_action == "edit_curve":
            self._set_mode(ctx, MechanicalMode.EDIT_CURVE.value)
            return
        if chain_action == "rebuild":
            self._handle_action_id(ctx, "refresh_preview")
            return
        test_action = self._test_overlay.action_from_button(button_id)
        if test_action == "play":
            self._set_playing(ctx, True)
            self._sync_all(ctx, "Motion test playing.", update_mesh_preview=False)
            return
        if test_action == "pause":
            self._set_playing(ctx, False)
            self._sync_all(ctx, "Motion test paused.", update_mesh_preview=False)
            return
        if test_action == "reset":
            self._set_playing(ctx, False)
            self._session.state.driver_angles_deg = {driver_id: 0.0 for driver_id in self.assembly.drivers}
            self._session.state.test_angle_deg = 0.0
            self._animation.set_angles(self._session.state.driver_angles_deg)
            self._parameters.sync_inspector(ctx)
            self._sync_all(ctx, "Motion test reset.", update_mesh_preview=False, test_motion_only=True)
            self._test_overlay.sync(ctx)
            return
        if test_action == "exit":
            self._set_mode(ctx, MechanicalMode.SELECT.value)
            return
        mode = mode_from_button(button_id)
        if mode is not None:
            self._set_mode(ctx, mode.value)
            return
        action = action_from_button(button_id)
        if action:
            self._handle_action_id(ctx, action)

    def on_overlay_field_changed(self, window_id: str, field_id: str, value: str, ctx: Any) -> bool:  # noqa: ARG002
        chain_change = self._chain_overlay.field_changed(field_id, value)
        if chain_change is not None:
            parameter_id, parsed = chain_change
            changed, _driver = self._parameters.apply_selected_value(parameter_id, parsed)
            if not changed:
                return False
            self._parameters.sync_inspector(ctx)
            self._sync_all(ctx, "Gear-chain parameters updated and solved.")
            return True
        changed = self._test_overlay.field_changed(field_id, value)
        if changed is None:
            return False
        driver_id, signed_rpm = changed
        self._animation.set_speed(driver_id, signed_rpm)
        self._parameters.sync_inspector(ctx)
        self._sync_all(ctx, "Driver speed updated.", update_mesh_preview=False, test_motion_only=True)
        return True

    def _set_mode(self, ctx: Any, value: Any) -> None:
        try:
            mode = value if isinstance(value, MechanicalMode) else MechanicalMode(str(value))
        except Exception:
            mode = MechanicalMode.SELECT
        previous_mode = self._session.state.mode
        if self._interactions.cancel_active_gear_drag():
            self._renderer.end_gear_drag(ctx, render=False)
        if previous_mode is MechanicalMode.TEST and mode is not MechanicalMode.TEST:
            self._set_playing(ctx, False)
            self._renderer.end_live_motion(ctx, render=False)
        if mode in {MechanicalMode.PICK_ATTACHMENT_SOURCE, MechanicalMode.PICK_ATTACHMENTS}:
            source_id = self._parameters.output_source_element_id()
            result = self._machine.dispatch(MechanicalIntent.START_ATTACHMENTS, source_id)
            self._sync_all(ctx, result.message, update_mesh_preview=False)
            return
        if mode in {
            MechanicalMode.PICK_RACK_PINION,
            MechanicalMode.PLACE_RACK_START,
            MechanicalMode.PLACE_RACK_END,
        }:
            pinion_id = self._parameters.input_gear_id_for_selection()
            result = self._machine.dispatch(MechanicalIntent.START_RACK, pinion_id)
            self._set_playing(ctx, False)
            try:
                ctx.inspector.update_value("mechanical_mode", self._parameters.visible_mode().value, notify=False)
            except Exception:
                pass
            self._sync_all(ctx, result.message, update_mesh_preview=False)
            return
        intent = {
            MechanicalMode.PICK_PLANE: MechanicalIntent.PICK_PLANE,
            MechanicalMode.SELECT: MechanicalIntent.SELECT,
            MechanicalMode.PLACE_GEAR: MechanicalIntent.START_GEAR,
            MechanicalMode.PLACE_CHAIN_START: MechanicalIntent.START_CHAIN,
            MechanicalMode.EDIT_CURVE: MechanicalIntent.EDIT_CURVE,
            MechanicalMode.PICK_DRIVER_TARGET: MechanicalIntent.START_DRIVER,
            MechanicalMode.PICK_ATTACHMENT_SOURCE: MechanicalIntent.START_ATTACHMENTS,
            MechanicalMode.TEST: MechanicalIntent.START_TEST,
        }.get(mode, MechanicalIntent.SELECT)
        result = self._machine.dispatch(intent)
        if mode is not MechanicalMode.TEST:
            self._set_playing(ctx, False)
        try:
            ctx.inspector.update_value("mechanical_mode", self._parameters.visible_mode().value, notify=False)
        except Exception:
            pass
        if mode is MechanicalMode.TEST:
            self._set_playing(ctx, False)
        self._sync_all(ctx, result.message)
        if mode is MechanicalMode.TEST:
            self._renderer.begin_live_motion(ctx)

    def _on_value_changed(self, ctx: Any, field_id: str, value: Any) -> None:
        if field_id == "test_angle_deg":
            angle = float(value) % 360.0
            driver = self.assembly.primary_driver()
            if driver is not None:
                self._session.state.driver_angles_deg = {driver.id: angle}
            self._session.state.test_angle_deg = angle
            self._animation.set_angles(self._session.state.driver_angles_deg)
            self._renderer.sync_test_motion(ctx, render=True)
            return
        if field_id == "test_playing":
            self._set_playing(ctx, bool(value))
            self._sync_all(
                ctx,
                "Motion test playing." if bool(value) else "Motion test paused.",
                update_mesh_preview=False,
                test_motion_only=True,
            )
            self._test_overlay.sync(ctx)
            return
        changed, driver = self._parameters.apply_selected_value(field_id, value)
        if not changed:
            return
        if driver is not None:
            self._animation.set_speed(driver.id, driver.speed_rpm * driver.direction)
        self._parameters.sync_inspector(ctx)
        self._sync_all(ctx, "Mechanical parameters updated.")

    def _handle_action_id(self, ctx: Any, action_id: str) -> None:
        self._commands.handle(
            ctx,
            action_id,
            sync=self._sync_all,
            stop_animation=self._animation.stop,
            replace_machine=self._replace_machine,
        )

    def _set_playing(self, ctx: Any, playing: bool) -> None:
        driver = self.assembly.primary_driver()
        drivers = (driver,) if driver is not None else ()
        if playing and not drivers:
            self._session.state.test_playing = False
            ctx.status.warning("Create at least one rotary driver before playing the motion test.")
            return
        self._session.state.test_playing = bool(playing)
        try:
            ctx.inspector.update_value("test_playing", bool(playing), notify=False)
        except Exception:
            pass
        if not playing:
            self._animation.stop()
            return
        self._session.state.mode = MechanicalMode.TEST
        active_driver = drivers[0]
        self._session.state.driver_angles_deg = {
            active_driver.id: float(self._session.state.driver_angles_deg.get(active_driver.id, 0.0))
        }
        self._renderer.begin_live_motion(ctx)
        if self._animation.start(
            angles_deg=self._session.state.driver_angles_deg,
            speeds_rpm=self._parameters.effective_driver_speeds(),
        ):
            return
        self._session.state.test_playing = False
        try:
            ctx.inspector.update_value("test_playing", False, notify=False)
        except Exception:
            pass
        ctx.status.warning("Live animation is unavailable in this host; drag an actuator handle or use the Test angle field.")

    def _on_animation_angles(self, angles_deg: dict[str, float]) -> None:
        ctx = self._ctx
        if ctx is None:
            return
        driver = self.assembly.primary_driver()
        if driver is None:
            return
        physical_angle = float(angles_deg.get(driver.id, 0.0))
        self._session.state.driver_angles_deg = {driver.id: physical_angle}
        # The inspector remains a compact 0..360 readout, while the solver and
        # actor matrices receive the accumulated angle for continuous reduction.
        self._session.state.test_angle_deg = physical_angle % 360.0
        # Do not touch the inspector or rebuild projected overlays every frame.
        # The actor matrix and the single rotation handle are the only changing
        # viewport data during playback.
        self._renderer.sync_test_motion(ctx, render=True)

    def _sync_all(
        self,
        ctx: Any,
        status: str | None = None,
        *,
        update_mesh_preview: bool = True,
        curve_preview_chain_id: str | None = None,
        gear_drag_gear_id: str | None = None,
        gear_snap_candidate: GearSnapCandidate | None = None,
        gear_drag_origin_center: tuple[float, float, float] | None = None,
        gear_drag_origin_phase_deg: float | None = None,
        test_motion_only: bool = False,
    ) -> None:
        if self._session.state.dirty:
            self._session.state.applied_since_open = False
            self._commands.draft_saved = False
        if status is not None:
            self._session.state.last_status = str(status)
        if gear_drag_gear_id:
            # High-frequency standalone-gear drag path: one actor matrix plus a
            # small projected silhouette. No WorkMesh generation, document
            # preview replacement, scene rebuild, inspector refresh or solve.
            self._renderer.sync_gear_drag(
                ctx,
                gear_drag_gear_id,
                gear_snap_candidate,
                origin_center=gear_drag_origin_center,
                origin_phase_deg=gear_drag_origin_phase_deg,
                render=True,
            )
            if status is not None:
                self._renderer.sync_status(ctx, status=status)
            return
        if curve_preview_chain_id:
            # High-frequency native drag path: update only the three Bézier
            # overlay primitives. Avoid inspector, toolbar, test-window and
            # full projected-registry rebuilds until pointer release.
            self._renderer.sync_curve_drag(ctx, curve_preview_chain_id, render=True)
            return
        if test_motion_only:
            self._renderer.sync_test_motion(ctx, render=True)
            if status is not None:
                self._renderer.sync_status(ctx, status=status)
            return
        try:
            ctx.modes.set(self.id, self._session.state.mode.value)
        except Exception:
            pass
        self._renderer.sync(ctx, status=status, update_mesh_preview=update_mesh_preview)
        if update_mesh_preview and self._session.state.mode is MechanicalMode.TEST:
            self._renderer.begin_live_motion(ctx)
        self._test_overlay.sync(ctx)
        self._chain_overlay.sync(ctx)
        self._workflow_overlay.sync(ctx)
        sync_mechanical_toolbar(
            ctx,
            active_mode=self._parameters.visible_mode(),
            status=status or self._session.state.last_status or "Mechanical assembly ready.",
            element_count=(
                len(self.assembly.gears)
                + len(self.assembly.chains)
                + len(self.assembly.racks)
                + len(self.assembly.drivers)
                + len(self.assembly.attachments)
            ),
        )

    def _startup_can_open_existing(self) -> bool:
        return (
            self._session.state.mode is MechanicalMode.PICK_PLANE
            and not (self.assembly.gears or self.assembly.chains or self.assembly.racks or self.assembly.drivers)
        )

    @staticmethod
    def _object_for_surface_pick(ctx: Any, picked: Any) -> Any | None:
        """Resolve a document object from the same raycast payload used at click."""

        try:
            objects = tuple(ctx.document.objects(include_preview=False))
        except Exception:
            return None
        object_index = getattr(picked, "object_index", None)
        if object_index is not None:
            try:
                index = int(object_index)
                if 0 <= index < len(objects):
                    return objects[index]
            except Exception:
                pass
        object_id = str(getattr(picked, "object_id", "") or "")
        if not object_id:
            return None
        for obj in objects:
            mesh = getattr(obj, "mesh", None)
            mesh_id = str(getattr(mesh, "mesh_id", "") or "") if mesh is not None else ""
            if object_id in {str(getattr(obj, "id", "") or ""), mesh_id}:
                return obj
        return None

    def _update_startup_editable_hover(self, ctx: Any, screen_pos: tuple[float, float] | None) -> None:
        """Outline the complete reopenable MEC assembly in yellow on hover."""

        if screen_pos is None:
            self._editable_hover.hide(ctx, render=True)
            return
        try:
            from laserprog_studio.tool_api import plan2d

            picked = plan2d.pick_plan_surface_anchor_by_raycast(
                ctx,
                screen_pos,
                log_diagnostics=False,
                diagnostics_label="mechanical-startup-hover",
            )
        except Exception:
            self._editable_hover.hide(ctx, render=True)
            return
        if not bool(getattr(picked, "hit", False)):
            self._editable_hover.hide(ctx, render=True)
            return
        candidate = self._object_for_surface_pick(ctx, picked)
        mesh = getattr(candidate, "mesh", None) if candidate is not None else None
        assembly = assembly_from_mesh(mesh) if mesh is not None else None
        if assembly is None:
            self._editable_hover.hide(ctx, render=True)
            return
        try:
            objects = tuple(ctx.document.objects(include_preview=False))
        except Exception:
            objects = (candidate,) if candidate is not None else ()
        members = tuple(
            EditableHoverMesh(str(getattr(obj, "id", "") or ""), obj.mesh)
            for obj in objects
            if getattr(obj, "mesh", None) is not None and mesh_belongs_to_assembly(obj.mesh, assembly.id)
        )
        if not members and candidate is not None:
            members = (EditableHoverMesh(str(getattr(candidate, "id", "") or ""), mesh),)
        self._editable_hover.show(
            ctx,
            group_key=str(assembly.id),
            meshes=members,
            render=True,
        )

    def _try_open_assembly_from_event(self, event: ToolEvent, ctx: Any) -> bool:
        """Recognize an old MEC directly from the initial face raycast.

        This mirrors Plan Tracer 2D: clicking an editable generated volume opens
        Edit / New / Cancel before the same click can be interpreted as a plain
        construction-face selection. Orbit gestures are ignored using the same
        click-distance guard as the mechanical plane picker.
        """

        if not self._startup_can_open_existing():
            return False
        from laserprog_studio.tool_api.core import MouseButton, ToolEventType

        if event.type is not ToolEventType.MOUSE_RELEASE or event.button not in {MouseButton.LEFT, MouseButton.NONE}:
            return False
        if event.screen_pos is None:
            return False
        press = self._session.state.surface_pick_press_screen_pos
        if press is not None:
            dx = abs(float(event.screen_pos[0]) - float(press[0]))
            dy = abs(float(event.screen_pos[1]) - float(press[1]))
            if max(dx, dy) > self._interactions._SURFACE_PICK_CLICK_TOLERANCE_PX:
                return False
        try:
            from laserprog_studio.tool_api import plan2d

            picked = plan2d.pick_plan_surface_anchor_by_raycast(
                ctx,
                event.screen_pos,
                log_diagnostics=False,
                diagnostics_label="mechanical-startup-editable",
            )
        except Exception:
            return False
        if not bool(getattr(picked, "hit", False)):
            return False
        candidate = self._object_for_surface_pick(ctx, picked)
        mesh = getattr(candidate, "mesh", None) if candidate is not None else None
        if mesh is None or assembly_from_mesh(mesh) is None:
            return False
        return self._open_existing_assembly_mesh(ctx, mesh)

    def _try_open_selected_assembly(self, ctx: Any) -> bool:
        """Resolve an old MEC selected during the startup face-pick phase."""

        if not self._startup_can_open_existing():
            return False
        active = ctx.scene_selection.active_object()
        mesh = getattr(active, "mesh", None) if active is not None else None
        if mesh is None or assembly_from_mesh(mesh) is None:
            return False
        return self._open_existing_assembly_mesh(ctx, mesh)

    def _open_existing_assembly_mesh(self, ctx: Any, mesh: Any) -> bool:
        self._editable_hover.hide(ctx, render=False)
        opening = self._opening.resolve(ctx, (mesh,))
        if opening.cancelled:
            try:
                ctx.scene_selection.clear()
            except Exception:
                pass
            self._machine.dispatch(MechanicalIntent.PICK_PLANE)
            self._sync_all(ctx, "Existing MEC selection cancelled. Select a face or another assembly.", update_mesh_preview=False)
            return True
        try:
            meshes, source_path = ctx.document.snapshot()
        except Exception:
            meshes, source_path = ([], None)
        self._animation.stop()
        self._renderer.end_live_motion(ctx, render=False)
        self._session.begin(
            meshes,
            source_path,
            selected_meshes=opening.edit_meshes,
            initial_work_plane=opening.inherited_plane,
        )
        self._replace_machine(MechanicalWorkflowMachine(self._session.state))
        self._parameters.sync_inspector(ctx)
        if opening.decision == "edit":
            message = "Existing mechanical assembly opened for editing."
        else:
            message = "New mechanical assembly started on the selected MEC construction plane."
        self._sync_all(ctx, message)
        return True

    def _select_committed_assembly(self, ctx: Any) -> None:
        indices = [
            obj.index
            for obj in ctx.document.objects(include_preview=False)
            if mesh_belongs_to_assembly(obj.mesh, self.assembly.id)
        ]
        if not indices:
            return
        try:
            ctx.scene_selection.set_selected(indices, active_index=indices[-1])
        except Exception:
            pass


class MechanicalMotionTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=MechanicalMotionCreatorTool())


__all__ = ["MechanicalMotionCreatorTool", "MechanicalMotionTool"]

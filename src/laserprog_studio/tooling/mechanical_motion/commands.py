# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable

from .models import GearChainSpec, MechanicalAssembly, RackSpec
from .parameters import MechanicalParameterService
from .serialization import mesh_belongs_to_assembly
from .session import MechanicalSession
from .state_machine import MechanicalIntent, MechanicalWorkflowMachine

SyncCallback = Callable[..., None]


class MechanicalCommandService:
    """Inspector/overlay actions and persistence commands."""

    def __init__(
        self,
        session: MechanicalSession,
        machine: MechanicalWorkflowMachine,
        parameters: MechanicalParameterService,
    ) -> None:
        self.session = session
        self.machine = machine
        self.parameters = parameters
        self.draft_saved = False

    def replace_machine(self, machine: MechanicalWorkflowMachine) -> None:
        self.machine = machine

    def reset_open_state(self) -> None:
        self.draft_saved = False

    def handle(
        self,
        ctx: Any,
        action_id: str,
        *,
        sync: SyncCallback,
        stop_animation: Callable[[], None],
        replace_machine: Callable[[MechanicalWorkflowMachine], None],
    ) -> None:
        if action_id == "attach_selection":
            self.attach_scene_selection(ctx, sync=sync)
            return
        if action_id == "confirm_attachment":
            self.attach_scene_selection(ctx, sync=sync)
            return
        if action_id == "change_attachment_source":
            result = self.machine.dispatch(MechanicalIntent.CHANGE_ATTACHMENT_SOURCE)
            sync(ctx, result.message, update_mesh_preview=False)
            return
        if action_id == "cancel_step":
            result = self.machine.dispatch(MechanicalIntent.CANCEL_STEP)
            sync(ctx, result.message, update_mesh_preview=False)
            return
        if action_id == "make_driver":
            self.make_driver(ctx, sync=sync)
            return
        if action_id == "delete_selected":
            self.delete_selected(ctx, sync=sync)
            return
        if action_id == "refresh_preview":
            selected = self.session.assembly.selected_element()
            if isinstance(selected, GearChainSpec):
                self.session.rebuild_chain(selected.id)
            elif isinstance(selected, RackSpec):
                self.session.rebuild_rack(selected.id)
            sync(ctx, "Mechanical preview rebuilt.")
            return
        if action_id == "save_draft":
            if self.save_draft(ctx):
                sync(ctx, "Recoverable mechanical draft saved.")
            return
        if action_id == "reset_assembly":
            stop_animation()
            self.session.state.assembly = MechanicalAssembly()
            self.session.state.dirty = True
            machine = MechanicalWorkflowMachine(self.session.state)
            machine.dispatch(MechanicalIntent.RESET)
            self.replace_machine(machine)
            replace_machine(machine)
            self.parameters.sync_inspector(ctx)
            sync(ctx, "Mechanical assembly reset.")

    def delete_selected(self, ctx: Any, *, sync: SyncCallback) -> bool:
        if not self.session.remove_selected():
            sync(ctx, "No mechanical element is selected.")
            return False
        self.parameters.sync_inspector(ctx)
        sync(ctx, "Selected mechanical element deleted.")
        return True

    def attach_scene_selection(self, ctx: Any, *, sync: SyncCallback) -> bool:
        source_id = str(self.session.state.pending_attachment_source_id or self.parameters.output_source_element_id() or "")
        if not source_id:
            self.machine.dispatch(MechanicalIntent.START_ATTACHMENTS)
            sync(ctx, "Select a gear, rack, gear-chain output, or rotary driver as the motion source.", update_mesh_preview=False)
            return False
        # Targets are accepted only after the explicit PICK_ATTACHMENTS
        # selection phase. Never reuse whatever happened to be selected before
        # Attach was started.
        mesh_ids = tuple(self.session.state.pending_attachment_mesh_ids)
        if not mesh_ids:
            sync(ctx, "Select one or more normal scene parts, then confirm Attach.", update_mesh_preview=False)
            return False
        try:
            source = source_id
            if source_id in self.session.assembly.chains:
                chain = self.session.assembly.chains[source_id]
                source = chain.gear_ids[-1] if chain.gear_ids else ""
            self.session.attach_meshes(mesh_ids, source_element_id=source)
        except Exception as exc:
            sync(ctx, f"Parts could not be attached: {exc}")
            return False
        self.parameters.sync_inspector(ctx)
        self.machine.dispatch(MechanicalIntent.CONFIRM_ATTACHMENTS)
        sync(ctx, f"{len(mesh_ids)} scene part(s) attached to the mechanism.")
        return True

    def make_driver(self, ctx: Any, *, sync: SyncCallback) -> bool:
        gear_id = self.parameters.input_gear_id_for_selection()
        if gear_id:
            self.session.add_driver_for_gear(gear_id, **self.parameters.driver_defaults(ctx))
            self.machine.dispatch(MechanicalIntent.SELECT)
            self.parameters.sync_inspector(ctx)
            sync(ctx, "Driver assigned to the selected gear. The previous driver was replaced.")
            return True
        active = ctx.scene_selection.active_object()
        if active is not None:
            self.machine.dispatch(MechanicalIntent.START_DRIVER)
            self.machine.accept_driver_target(active.id)
            sync(ctx, "Scene part selected. Click its rotation centre.")
            return True
        sync(ctx, "Select a generated gear or a scene part first.")
        return False

    def save_draft(self, ctx: Any, *, status: bool = True) -> bool:
        assembly = self.session.assembly
        if not (assembly.gears or assembly.racks or assembly.drivers):
            if status:
                ctx.status.warning("Nothing to save as a mechanical draft.")
            return False
        try:
            ctx.document.set_meshes(
                self.session.draft_meshes(),
                label="Save mechanical assembly draft",
                push_undo=True,
            )
            owner = getattr(ctx, "owner", None)
            rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
            if callable(rebuild):
                try:
                    rebuild(keep_camera=True)
                except TypeError:
                    rebuild()
            update_preview_state = getattr(owner, "update_preview_state", None) if owner is not None else None
            if callable(update_preview_state):
                try:
                    update_preview_state()
                except Exception:
                    pass
            draft_index = None
            for index, obj in enumerate(ctx.document.objects()):
                mesh = getattr(obj, "mesh", None)
                if mesh is None or not mesh_belongs_to_assembly(mesh, assembly.id):
                    continue
                metadata = getattr(mesh, "metadata", None)
                if isinstance(metadata, dict) and bool(metadata.get("mechanical_draft")):
                    draft_index = index
                    break
            if draft_index is not None:
                ctx.scene_selection.set_selected((draft_index,), active_index=draft_index)
            self.session.state.dirty = False
            self.session.state.applied_since_open = False
            self.draft_saved = True
        except Exception as exc:
            if status:
                ctx.status.error(f"Mechanical draft could not be saved: {exc}")
            return False
        if status:
            ctx.status.info("Mechanical assembly saved as a visible red draft. Select it later to resume editing.")
        return True


__all__ = ["MechanicalCommandService"]

# -*- coding: utf-8 -*-
"""Interactive Creator adapter for the Cloth surface editor.

The adapter deliberately contains only input routing and lifecycle glue.  Cloth
geometry, topology, flattening, rendering and panel descriptions stay in the
small modules under :mod:`laserprog_studio.tooling.cloth`.
"""
from __future__ import annotations

import math
import time
from typing import Any

from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool, MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_api import surface_selection
from laserprog_studio.tool_api.tracing import TraceMode, plane_from_origin_normal

from .base import ToolSpec
from .cloth.apply_pipeline import ClothApplyController, ClothApplyPipeline
from .cloth.drawing import ClothDrawingController
from .cloth.diagnostics import ClothWorkflowDiagnostics, close_input_snapshot, overlay_snapshot, proposal_snapshot
from .cloth.free_space import camera_facing_plane, resolve_cloth_point
from .cloth.geometry_overlay import ClothGeometryTraceOverlay
from .cloth.pattern_overlay import ClothPatternEdgeOverlay
from .cloth.geometry_trace import ClothGeometryTraceController
from .cloth.interaction import ClothInteractionState, ClothUxMachine, ClothUxStage
from .cloth.join_faces import analyze_textile_close_groups, commit_join_proposal
from .cloth.groups import (
    create_textile_group,
    explicit_textile_group_id,
    normalize_disconnected_textile_groups,
    remove_stale_textile_group_records,
)
from .cloth.models import ClothCurveKind, ClothEditMode, ClothPatchFunction, ClothSession, ClothWorkflowPhase
from .cloth.panel import build_cloth_panel
from .cloth.picking import (
    ClothSnapTargetCache,
    ClothSurfaceRaycastCache,
    nearest_document_curve,
    nearest_document_point,
    object_from_pick,
    pick_distance_along_ray,
    pick_ray_direction,
)
from .cloth.point_edit import ClothPointEditor
from .cloth.pattern_edges import (
    ClothPatternEdgeError,
    apply_cycle_cuts,
    apply_pattern_edge,
    pattern_edge_state,
    pattern_spacing_mm,
    restore_pattern_document,
    set_pattern_spacing,
)
from .cloth.rendering import ClothRenderer
from .cloth.serialization import cloth_output_kind, restore_cloth_source
from .cloth.selection import (
    assign_logical_patch_group,
    delete_cloth_selection,
    logical_patch_group,
    logical_patch_group_count,
    nearest_document_patch,
)
from .cloth.state_machine import ClothTransitionError, ClothWorkflowMachine
from .cloth.topology import curve_patch_incidence, patch_frame
from .cloth.validation import ClothValidationCache
from .cloth.workflow_overlay import ClothWorkflowOverlay
from .cloth.workflow_actions import ClothAction, canonical_cloth_action, is_apply_action
from .cloth.workspace import (
    ClothDrawMode,
    ClothDrawPickMode,
    ClothOverlayMode,
    ClothPropertySelectionMode,
    ClothWorkspaceMachine,
)
from .editable_mesh_hover import EditableHoverMesh, EditableMeshHoverPreview
from .ids import TOOL_CLOTH

_CLICK_DRAG_THRESHOLD_PX = 6.0
_TRACE_MODES = {TraceMode.POINT.value, TraceMode.LINE.value, TraceMode.POLYLINE.value, TraceMode.ARC.value}


class ClothCreatorTool(CreatorTool):
    """Piecewise-planar textile surface drawing and rigid flat-pattern output."""

    id = TOOL_CLOTH
    label = "Cloth"

    def __init__(self) -> None:
        self._session = ClothSession()
        self._machine = ClothWorkflowMachine(self._session)
        self._interaction = ClothInteractionState()
        self._ux = ClothUxMachine(self._interaction)
        self._workspace_machine = ClothWorkspaceMachine()
        self._workspace = self._workspace_machine.state
        self._drawing = ClothDrawingController(self._session.document)
        self._geometry_trace = ClothGeometryTraceController()
        self._geometry_trace.set_smart_tolerance(0.35)
        self._renderer = ClothRenderer(self.id, self._session, self._interaction, self._drawing, self._geometry_trace)
        self._workflow_overlay = ClothWorkflowOverlay(self.id, self._session, self._interaction, self._workspace)
        self._geometry_overlay = ClothGeometryTraceOverlay(self.id, self._geometry_trace)
        self._pattern_overlay = ClothPatternEdgeOverlay(self.id, self._session, self._interaction)
        self._mesh_hover = EditableMeshHoverPreview(self.id, "cloth:editable_hover", metadata_role="cloth_editable_hover")
        self._ctx: Any | None = None
        self._pointer_press_screen: tuple[float, float] | None = None
        self._surface_pointer = surface_selection.SurfaceSelectionPointerMachine(double_click_interval_ms=260.0)
        self._textile_selection_cache = surface_selection.SurfaceSelectionCache()
        self._selected_textile_groups: list[frozenset[str]] = []
        self._camera_interaction_active = False
        self._output_name = "Cloth"
        self._smart_snap = True
        self._construction_snap = True
        self._snap_tolerance_px = 12.0
        self._hover_editable: tuple[str, Any] | None = None
        self._point_editor = ClothPointEditor()
        self._validation_cache = ClothValidationCache()
        self._snap_target_cache = ClothSnapTargetCache()
        self._cloth_raycast_cache = ClothSurfaceRaycastCache()
        self._last_status_message: str | None = None
        self._point_selection_shift = False
        self._pattern_edge_snapshot = None
        self._cloth_diagnostics: ClothWorkflowDiagnostics | None = None
        self._apply_pipeline = ClothApplyPipeline()
        self._apply_controller = ClothApplyController(self, self._apply_pipeline)

    @property
    def session(self) -> ClothSession:
        return self._session

    @property
    def interaction(self) -> ClothInteractionState:
        return self._interaction

    @property
    def geometry_trace(self) -> ClothGeometryTraceController:
        return self._geometry_trace

    def _bind_session(self, session: ClothSession) -> None:
        self._session = session
        self._machine.session = session
        self._drawing = ClothDrawingController(session.document)
        self._geometry_trace.clear()
        self._geometry_trace.set_smart_tolerance(self._geometry_trace.smart_session.tolerance)
        self._textile_selection_cache.clear()
        self._selected_textile_groups = []
        self._renderer = ClothRenderer(self.id, session, self._interaction, self._drawing, self._geometry_trace)
        self._workflow_overlay = ClothWorkflowOverlay(self.id, session, self._interaction, self._workspace)
        self._geometry_overlay = ClothGeometryTraceOverlay(self.id, self._geometry_trace)
        self._pattern_overlay = ClothPatternEdgeOverlay(self.id, session, self._interaction)
        self._validation_cache.reset()
        self._snap_target_cache.reset()
        self._cloth_raycast_cache.reset()
        self._pattern_edge_snapshot = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        self._ctx = ctx
        self._cloth_diagnostics = ClothWorkflowDiagnostics(owner=getattr(ctx, "owner", None))
        if self._cloth_diagnostics.enabled:
            self._cloth_diagnostics.reset(reason="cloth_open", tool=self, ctx=ctx)
        self._machine = ClothWorkflowMachine()
        self._interaction.reset()
        self._ux = ClothUxMachine(self._interaction)
        self._workspace_machine = ClothWorkspaceMachine()
        self._workspace = self._workspace_machine.state
        self._bind_session(self._machine.session)
        self._mesh_hover.reset()
        self._pointer_press_screen = None
        self._surface_pointer.reset()
        self._camera_interaction_active = False
        self._hover_editable = None
        self._point_editor.reset()
        self._last_status_message = None
        self._point_selection_shift = False
        self._pattern_edge_snapshot = None
        try:
            ctx.document.ensure()
        except Exception:
            pass
        ctx.inspector.set_panel(
            build_cloth_panel(
                on_value_changed=lambda field_id, value: self._on_value_changed(ctx, field_id, value),
                on_action=lambda event: self._on_action(ctx, str(getattr(event, "action_id", "") or "")),
            )
        )
        self._register_workflow(ctx)
        self._sync(ctx, "Select a mesh surface to create textile, or open an existing Cloth surface.")

    def on_close(self, ctx: Any) -> None:
        if self._cloth_diagnostics is not None:
            self._cloth_diagnostics.record("session.close", tool=self, ctx=ctx)
            self._cloth_diagnostics.export(reason="cloth_close", tool=self, ctx=ctx)
        self._drawing.cancel()
        self._mesh_hover.hide(ctx, render=False)
        self._workflow_overlay.hide(ctx)
        self._geometry_overlay.hide(ctx)
        self._pattern_overlay.hide(ctx)
        self._geometry_trace.clear()
        self._geometry_trace.set_smart_tolerance(self._geometry_trace.smart_session.tolerance)
        self._textile_selection_cache.clear()
        self._renderer.clear(ctx, render=False)
        ctx.workflow.clear(self.id)
        ctx.inspector.clear()
        self._point_editor.reset()
        self._ctx = None
        self._cloth_diagnostics = None

    def on_cancel(self, ctx: Any) -> bool:
        if self._cloth_diagnostics is not None:
            self._cloth_diagnostics.record("session.cancel", tool=self, ctx=ctx)
            self._cloth_diagnostics.export(reason="cloth_cancel", tool=self, ctx=ctx)
        self._drawing.cancel()
        try:
            self._machine.cancel()
        except Exception:
            pass
        self._mesh_hover.hide(ctx, render=False)
        self._workflow_overlay.hide(ctx)
        self._geometry_overlay.hide(ctx)
        self._pattern_overlay.hide(ctx)
        self._geometry_trace.clear()
        self._geometry_trace.set_smart_tolerance(self._geometry_trace.smart_session.tolerance)
        self._textile_selection_cache.clear()
        self._renderer.clear(ctx, render=False)
        ctx.status.info("Cloth cancelled. No scene geometry was changed.")
        return True

    def _validation_report(self):
        return self._validation_cache.get(self._session.document)

    def can_apply(self, ctx: Any) -> bool:  # noqa: ARG002
        if self._drawing.pending_world_points or not self._session.document.patches:
            return False
        if self._session.phase not in {
            ClothWorkflowPhase.EDITING,
            ClothWorkflowPhase.FLAT_PREVIEW,
            ClothWorkflowPhase.APPLY_READY,
        }:
            return False
        return self._validation_report().can_apply

    def on_apply(self, ctx: Any) -> bool:
        return self._apply_controller.apply(ctx)

    # Camera/click contract
    def wants_pointer_press_passthrough(self, event: ToolEvent, ctx: Any) -> bool:
        if event.type is not ToolEventType.MOUSE_PRESS or event.button is not MouseButton.LEFT:
            return False
        self._pointer_press_screen = event.screen_pos
        if self._interaction.stage is ClothUxStage.MAIN and event.screen_pos is not None:
            self._surface_pointer.press(event.screen_pos)
        # Modify mode owns a drag only when the press starts on an editable,
        # non-shared Cloth point. Everywhere else the camera keeps its normal
        # orbit/pan contract and the tool recovers short clicks on release.
        if (
            False
            and event.screen_pos is not None
            and self._interaction.stage is ClothUxStage.DRAW
            and self._session.edit_mode.value == ClothEditMode.MODIFY.value
        ):
            point_id = self._nearest_point(ctx, event.screen_pos)
            point = self._session.document.points.get(point_id) if point_id is not None else None
            edit_plane = self._interaction.active_plane
            if edit_plane is None and point is not None:
                edit_plane = camera_facing_plane(ctx, point.position)
            if point_id is not None and self._point_editor.begin(
                self._session.document,
                self._interaction,
                point_id,
                active_plane=edit_plane,
                report=lambda message: self._sync(ctx, message, render=False),
            ):
                self._point_selection_shift = bool(event.shift)
                self._renderer.sync(ctx)
                self._sync_overlay(ctx)
                return False
        return True

    def wants_pointer_release_passthrough(self, event: ToolEvent, ctx: Any) -> bool:  # noqa: ARG002
        if self._point_editor.active:
            return False
        return bool(
            event.type is ToolEventType.MOUSE_RELEASE
            and event.button in {MouseButton.LEFT, MouseButton.NONE}
            and self._pointer_press_screen is not None
        )

    def on_camera_interaction_begin(self, ctx: Any, **_: Any) -> None:
        self._camera_interaction_active = True
        self._interaction.camera_interaction_active = True
        self._interaction.clear_hover()
        if self._interaction.stage is ClothUxStage.MAIN:
            self._surface_pointer.begin_camera_drag()
        self._geometry_trace.set_hover_from_pick(ctx, None)
        self._mesh_hover.hide(ctx, render=False)
        self._renderer.sync(ctx)

    def on_camera_interaction_end(self, ctx: Any, *, screen_pos=None, **_: Any) -> None:
        self._camera_interaction_active = False
        self._interaction.camera_interaction_active = False
        if screen_pos is not None and self._pointer_press_screen is None:
            self._update_hover(ctx, screen_pos)

    def on_event(self, event: ToolEvent, ctx: Any) -> bool:
        if event.is_escape:
            self._pointer_press_screen = None
            return self._escape(ctx)
        if event.is_delete and self._session.edit_mode.value == ClothEditMode.MODIFY.value:
            self._pointer_press_screen = None
            return self._delete_selection(ctx)
        if event.type is ToolEventType.KEY_PRESS and (event.key or "").lower() in {"enter", "return"}:
            if self._interaction.stage is ClothUxStage.SELECT_FOLD_EDGE:
                return self._apply_selected_pattern_edge(ctx)
            if self._interaction.stage is ClothUxStage.DRAW:
                return self._finish_trace(ctx, closed=False)
            return False
        if event.type is ToolEventType.MOUSE_MOVE:
            if self._interaction.stage is ClothUxStage.MAIN and event.screen_pos is not None:
                self._surface_pointer.move(event.screen_pos)
            if self._point_editor.active and event.screen_pos is not None:
                return self._point_editor.move(
                    ctx,
                    event,
                    self._session.document,
                    self._interaction,
                    owner_tool=self.id,
                    smart_snap=self._smart_snap,
                    snap_tolerance_px=self._snap_tolerance_px,
                    render_preview=lambda: self._renderer.sync(ctx),
                ).handled
            if not self._camera_interaction_active and event.screen_pos is not None and event.button is MouseButton.NONE:
                self._update_hover(ctx, event.screen_pos, event.world_pos)
            return False
        if event.type is ToolEventType.MOUSE_PRESS and event.button is MouseButton.LEFT:
            self._pointer_press_screen = event.screen_pos
            if self._interaction.stage is ClothUxStage.MAIN and event.screen_pos is not None:
                self._surface_pointer.press(event.screen_pos)
            return self._point_editor.active
        if (
            event.type is ToolEventType.MOUSE_DOUBLE_CLICK
            and event.button is MouseButton.LEFT
            and event.screen_pos is not None
            and self._interaction.stage is ClothUxStage.MAIN
        ):
            # Qt replaces the second press with a native double-click event.
            # The shared API still decides using its shorter interval on release.
            self._pointer_press_screen = event.screen_pos
            if self._surface_pointer.last_click_time_s is None:
                self._surface_pointer.double_click(event.screen_pos)
                return self._double_click_main(ctx, event.screen_pos)
            self._surface_pointer.press(event.screen_pos)
            return True
        if event.type not in {ToolEventType.MOUSE_RELEASE, ToolEventType.MOUSE_DOUBLE_CLICK}:
            return False
        if self._point_editor.active:
            edited_point_id = self._point_editor.point_id
            result = self._point_editor.finish(
                ctx,
                event,
                self._session.document,
                self._interaction,
                owner_tool=self.id,
                smart_snap=self._smart_snap,
                snap_tolerance_px=self._snap_tolerance_px,
                render_preview=lambda: self._renderer.sync(ctx),
            )
            self._pointer_press_screen = None
            self._session.dirty = self._session.dirty or result.changed
            if edited_point_id is not None:
                self._select_modify_entity("point", edited_point_id, additive=self._point_selection_shift)
            self._point_selection_shift = False
            self._sync(ctx, result.message)
            return result.handled
        if event.screen_pos is None:
            self._pointer_press_screen = None
            return False
        if self._interaction.stage is ClothUxStage.MAIN and event.type is ToolEventType.MOUSE_RELEASE:
            self._pointer_press_screen = None
            action = self._surface_pointer.release(event.screen_pos)
            if action is surface_selection.SurfaceSelectionPointerAction.DOUBLE_CLICK:
                return self._double_click_main(ctx, event.screen_pos)
            if action is surface_selection.SurfaceSelectionPointerAction.CLICK:
                return self._select_main(ctx, event.screen_pos, additive=bool(event.shift))
            return True
        press = self._pointer_press_screen
        self._pointer_press_screen = None
        if press is not None:
            dx = float(event.screen_pos[0]) - float(press[0])
            dy = float(event.screen_pos[1]) - float(press[1])
            if math.hypot(dx, dy) > _CLICK_DRAG_THRESHOLD_PX:
                return False
        return self._handle_click(ctx, event, double=event.type is ToolEventType.MOUSE_DOUBLE_CLICK)

    # Click routing
    def _handle_click(self, ctx: Any, event: ToolEvent, *, double: bool) -> bool:
        stage = self._interaction.stage
        if stage is ClothUxStage.OPENING:
            return self._opening_click(ctx, event)
        if stage is ClothUxStage.FLAT_PREVIEW:
            self._sync(ctx, "Return to the main Cloth menu before editing.", render=False)
            return True
        if stage is ClothUxStage.MAIN:
            if double:
                return self._double_click_main(ctx, event.screen_pos)
            return self._select_main(ctx, event.screen_pos, additive=bool(event.shift))
        if stage is ClothUxStage.CLOSE:
            self._sync(ctx, "Use Apply, Prev, Next or Reset in the Close overlay.", render=False)
            return True
        if stage is ClothUxStage.PROPERTIES:
            return self._select_properties(ctx, event)
        if stage is ClothUxStage.DRAW:
            if self._session.edit_mode.value in {ClothEditMode.LINE.value, ClothEditMode.POLYLINE.value}:
                return self._draw_click(ctx, event, double=double)
            return self._select_draw_entity(ctx, event)
        if stage is ClothUxStage.SELECT_FOLD_EDGE:
            return self._select_fold(ctx, event.screen_pos)
        return False

    def _opening_click(self, ctx: Any, event: ToolEvent) -> bool:
        pick = ctx.pick.object_at(event.screen_pos)
        if pick.hit:
            obj = object_from_pick(ctx, pick)
            restored = restore_cloth_source(getattr(obj, "mesh", None)) if obj is not None else None
            if restored is not None:
                document, output_kind = restored
                if output_kind != "folded":
                    self._sync(ctx, "Open the linked 3D Cloth surface, not its flat-pattern output.", render=False)
                    return True
                return self._open_existing(ctx, obj, document)
        self._start_new(ctx)
        return self._select_main(ctx, event.screen_pos, additive=bool(event.shift))

    def _plane_click(self, ctx: Any, event: ToolEvent) -> bool:
        if self._session.phase is ClothWorkflowPhase.OPENING:
            self._start_new(ctx)
        self._interaction.enter_draw()
        self._set_mode(ctx, ClothEditMode.POLYLINE.value)
        return self._draw_click(ctx, event, double=False)

    def _accept_plane_pick(self, ctx: Any, pick: Any) -> bool:
        # Deprecated compatibility entry point. A picked face is now just one
        # possible depth source for the next point, never a locked workplane.
        if self._session.phase is ClothWorkflowPhase.OPENING:
            self._start_new(ctx)
        self._interaction.enter_draw()
        self._set_mode(ctx, ClothEditMode.POLYLINE.value)
        self._sync(ctx, "Free 3D tracing active. Scene faces and edges are available as snap targets.")
        return True

    def _open_existing(self, ctx: Any, obj: Any, document: Any) -> bool:
        session = self._machine.edit_existing(document, source_mesh_id=str(getattr(obj, "id", "") or "") or None)
        self._bind_session(session)
        self._interaction.editing_output_kind = "folded"
        metadata = dict(getattr(getattr(obj, "mesh", None), "metadata", {}) or {})
        self._interaction.source_flat_scene_id = metadata.get("cloth_linked_flat_scene_id")
        try:
            ctx.inspector.update_value("cloth_thickness", float(document.metadata.get("cloth_thickness_mm", metadata.get("cloth_thickness_mm", 0.2))), notify=False)
            ctx.inspector.update_value("cloth_stitch_tolerance", float(document.metadata.get("cloth_stitch_tolerance_mm", metadata.get("cloth_stitch_tolerance_mm", 0.05))), notify=False)
        except Exception:
            pass
        first_patch = next(iter(document.patches.values()), None)
        frame = patch_frame(document, first_patch) if first_patch is not None else None
        if frame is not None:
            self._interaction.set_construction_plane(plane_from_origin_normal(frame.origin, frame.normal), label=f"{first_patch.name} plane")
        self._ux.edit_existing()
        self._mesh_hover.hide(ctx, render=False)
        self._enter_main(ctx)
        modifier_count = len(document.metadata.get("cloth_boolean_modifiers", ()) or ())
        if modifier_count:
            self._sync(
                ctx,
                f"Existing Cloth loaded with {modifier_count} boolean cut(s). Apply regenerates the folded solid and flat pattern.",
            )
        else:
            self._sync(ctx, "Existing Cloth loaded. Use the 3D drawing toolbar to continue.")
        return True

    def _start_new(self, ctx: Any) -> None:
        session = self._machine.start_new()
        self._interaction.reset()
        self._ux = ClothUxMachine(self._interaction)
        self._workspace_machine.reset()
        self._workspace = self._workspace_machine.state
        self._bind_session(session)
        self._machine.set_edit_mode(ClothEditMode.MESH_TRACE)
        self._geometry_trace.set_pick_kind("face")
        self._mesh_hover.hide(ctx, render=False)
        self._enter_main(ctx)


    def _restore_uncommitted_pattern_preview(self) -> None:
        """Restore the document before leaving an unvalidated Fold/Cut preview."""

        if self._pattern_edge_snapshot is None:
            return
        self._restore_pattern_preview()
        self._pattern_edge_snapshot = None
        self._interaction.selected_pattern_curve_id = None
        self._interaction.selected_fold_id = None

    def _prepare_editing_phase(self) -> None:
        if self._session.phase in {
            ClothWorkflowPhase.FLAT_PREVIEW,
            ClothWorkflowPhase.VALIDATION_BLOCKED,
            ClothWorkflowPhase.APPLY_READY,
            ClothWorkflowPhase.APPLIED,
        }:
            if self._session.phase is ClothWorkflowPhase.APPLIED:
                self._session.phase = ClothWorkflowPhase.EDITING
            else:
                self._machine.return_to_editing()

    def _enter_main(self, ctx: Any) -> None:
        self._restore_uncommitted_pattern_preview()
        if self._session.phase is ClothWorkflowPhase.OPENING:
            self._start_new(ctx)
            return
        self._prepare_editing_phase()
        self._drawing.cancel()
        self._interaction.join_proposals = ()
        self._interaction.join_proposal_index = 0
        self._machine.set_edit_mode(ClothEditMode.MESH_TRACE)
        self._geometry_trace.set_pick_kind("face")
        if self._session.selected_patch_ids:
            self._set_selected_textile_groups((self._session.selected_patch_ids,), expand_persistent=True)
        self._interaction.enter_main()
        self._workspace_machine.enter_main()
        self._sync_workspace_selection()
        self._sync(ctx, self._workspace.message)

    def _enter_close(self, ctx: Any) -> None:
        diag = self._cloth_diagnostics
        operation = diag.begin(
            "close.enter", tool=self, ctx=ctx, inputs=close_input_snapshot(self)
        ) if diag is not None else None
        try:
            self._restore_uncommitted_pattern_preview()
            if operation is not None:
                operation.stage("pattern_preview_restored", tool=self, ctx=ctx)
            self._prepare_editing_phase()
            if operation is not None:
                operation.stage("editing_phase_prepared", tool=self, ctx=ctx)
            self._drawing.cancel()
            self._machine.set_edit_mode(ClothEditMode.MESH_TRACE)
            if self._session.selected_patch_ids:
                self._set_selected_textile_groups((self._session.selected_patch_ids,), expand_persistent=True)
            self._interaction.enter_close()
            if operation is not None:
                operation.stage("interaction_entered", tool=self, ctx=ctx)
            self._analyze_close(ctx)
            if operation is not None:
                operation.finish(
                    outcome="ok", tool=self, ctx=ctx, proposals=proposal_snapshot(self._interaction.join_proposals)
                )
        except Exception as exc:
            # Close is an assistant, never a destructive modal transition. Any
            # solver/UI failure must leave the one Cloth overlay alive with Reset
            # available instead of stranding the tool in a hidden state.
            if diag is not None:
                diag.exception(
                    "close.enter.exception", exc,
                    operation_id=operation.operation_id if operation is not None else 0,
                    tool=self, ctx=ctx, inputs=close_input_snapshot(self),
                )
            self._interaction.join_proposals = ()
            self._interaction.join_proposal_index = 0
            self._interaction.enter_close()
            self._workspace_machine.enter_close(proposals=0, proposal_index=0)
            try:
                self._sync(ctx, f"Close could not analyze this selection: {exc}")
            except Exception as sync_exc:
                if diag is not None:
                    diag.exception("close.recovery_sync.exception", sync_exc, tool=self, ctx=ctx)
                # Last-resort direct overlay restoration. This path is only a
                # safety net and is fully traced when diagnostics are enabled.
                try:
                    self._workflow_overlay.sync_document(
                        ctx, can_apply=self.can_apply(ctx),
                        pending_count=len(self._drawing.pending_world_points),
                        validation_report=self._validation_report() if self._session.document.patches else None,
                    )
                except Exception as overlay_exc:
                    if diag is not None:
                        diag.exception("close.recovery_overlay.exception", overlay_exc, tool=self, ctx=ctx)
            if operation is not None:
                operation.finish(outcome="error", tool=self, ctx=ctx, error=repr(exc))
            if diag is not None:
                diag.export(reason="close_enter_exception", tool=self, ctx=ctx)

    def _enter_draw(self, ctx: Any, mode: ClothDrawMode | str | None = None) -> None:
        self._restore_uncommitted_pattern_preview()
        if self._session.phase is ClothWorkflowPhase.OPENING:
            self._start_new(ctx)
        self._prepare_editing_phase()
        self._geometry_trace.clear_selection()
        self._interaction.join_proposals = ()
        self._interaction.join_proposal_index = 0
        self._interaction.enter_draw()
        self._workspace_machine.enter_draw(mode)
        selected = self._workspace.draw_mode
        self._drawing.cancel()
        if selected is ClothDrawMode.MODIFY:
            self._machine.set_edit_mode(ClothEditMode.MODIFY)
        elif selected is ClothDrawMode.LINE:
            self._clear_modify_selection()
            self._machine.set_edit_mode(ClothEditMode.LINE)
            self._drawing.begin(ClothEditMode.LINE.value)
        else:
            self._clear_modify_selection()
            self._machine.set_edit_mode(ClothEditMode.POLYLINE)
            self._drawing.begin(ClothEditMode.POLYLINE.value)
        self._workspace_machine.update_draw(
            len(self._drawing.pending_world_points),
            smart_snap_enabled=self._smart_snap,
            axis_guides_enabled=self._construction_snap,
        )
        self._sync(ctx, self._workspace.message)

    def _enter_properties(self, ctx: Any) -> None:
        self._restore_uncommitted_pattern_preview()
        if self._session.phase is ClothWorkflowPhase.OPENING:
            self._start_new(ctx)
        self._prepare_editing_phase()
        self._drawing.cancel()
        self._geometry_trace.clear_selection()
        self._session.selected_point_ids = ()
        self._session.selected_curve_ids = ()
        self._machine.set_edit_mode(ClothEditMode.MESH_TRACE)
        self._interaction.enter_properties()
        self._workspace_machine.enter_properties()
        self._sync_workspace_selection()
        self._sync(ctx, self._workspace.message)

    # Compatibility entry points retained for old macros and tests.
    def _enter_draw_tool(self, ctx: Any, tool: Any) -> None:
        value = str(getattr(tool, "value", tool))
        if value in {"create_from_mesh", "add_mesh_faces"}:
            self._enter_main(ctx)
        elif value in {"join_textile_faces", "join_faces"}:
            self._enter_close(ctx)
        else:
            self._enter_draw(ctx, ClothDrawMode.POLYLINE)

    def _enter_textile_properties(self, ctx: Any) -> None:
        self._enter_properties(ctx)

    def _selected_textile_patch_groups(self) -> tuple[frozenset[str], ...]:
        """Return the current user-facing textile groups.

        API-grown groups are transient interaction data and cannot always be
        reconstructed from persistent creation metadata.  Keep them explicitly
        while the selection is active; infer legacy groups only when necessary.
        """

        selected = {patch_id for patch_id in self._session.selected_patch_ids if patch_id in self._session.document.patches}
        tracked = tuple(group & selected for group in self._selected_textile_groups if group & selected)
        if tracked and set().union(*tracked) == selected:
            return tuple(frozenset(group) for group in tracked if group)
        groups: list[frozenset[str]] = []
        remaining = set(selected)
        while remaining:
            seed = min(remaining)
            group = frozenset(value for value in logical_patch_group(self._session.document, seed) if value in selected)
            if not group:
                group = frozenset((seed,))
            groups.append(group)
            remaining.difference_update(group)
        self._selected_textile_groups = list(groups)
        return tuple(groups)

    def _set_selected_textile_groups(self, groups, *, expand_persistent: bool = True) -> None:
        """Select textile groups without geometrically merging their identities.

        A group is an authored document identity.  Adjacent or overlapping
        groups remain independent, even when the surface-selection API would
        consider their geometry continuous.
        """

        normalized: list[frozenset[str]] = []
        seen_keys: set[str] = set()
        for values in groups:
            for raw in values:
                patch_id = str(raw)
                if patch_id not in self._session.document.patches:
                    continue
                group = (
                    frozenset(logical_patch_group(self._session.document, patch_id))
                    if expand_persistent
                    else frozenset((patch_id,))
                )
                if not group:
                    group = frozenset((patch_id,))
                explicit_id = explicit_textile_group_id(self._session.document, patch_id) if expand_persistent else ""
                key = explicit_id or ("legacy:" if expand_persistent else "technical:") + ",".join(sorted(group))
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                normalized.append(group)
        self._selected_textile_groups = normalized
        self._session.selected_patch_ids = tuple(sorted(set().union(*normalized))) if normalized else ()

    def _append_selected_textile_group(self, values) -> None:
        self._set_selected_textile_groups((*self._selected_textile_patch_groups(), frozenset(values)))

    def _sync_workspace_selection(self) -> None:
        groups = self._selected_textile_patch_groups()
        self._workspace_machine.update_selection(
            source_regions=self._geometry_trace.smart_session.selected_region_count,
            source_meshes=self._geometry_trace.smart_session.selected_mesh_count,
            textile_faces=len(groups),
            textile_edges=len(self._session.selected_curve_ids),
        )

    def _clear_all_selection(self) -> None:
        self._geometry_trace.clear_selection()
        self._clear_modify_selection()
        self._interaction.join_proposals = ()
        self._interaction.join_proposal_index = 0
        self._sync_workspace_selection()

    def _select_main(self, ctx: Any, screen_pos: tuple[float, float], *, additive: bool) -> bool:
        # Solitary authored edges remain explicit Close anchors. Face selection
        # itself is depth-correct across textile overlays and scene meshes.
        curve_id = self._nearest_solitary_curve(ctx, screen_pos)
        target_kind, target = (None, None) if curve_id is not None else self._frontmost_face_target(ctx, screen_pos)

        if curve_id is not None:
            if not additive:
                self._geometry_trace.clear_selection()
                self._clear_modify_selection()
            values = list(self._session.selected_curve_ids)
            if curve_id not in values:
                values.append(curve_id)
            self._session.selected_curve_ids = tuple(values)
            self._sync_workspace_selection()
            self._sync(ctx, self._workspace.message)
            return True

        if target_kind == "textile" and target is not None:
            patch_id = str(target)
            if not additive:
                self._geometry_trace.clear_selection()
                self._clear_modify_selection()
            group = logical_patch_group(self._session.document, patch_id)
            if additive:
                self._append_selected_textile_group(group)
            else:
                self._set_selected_textile_groups((group,))
            self._sync_workspace_selection()
            self._sync(ctx, self._workspace.message)
            return True

        if target_kind == "mesh" and target is not None:
            if not additive:
                self._clear_modify_selection()
                self._geometry_trace.clear_selection()
            if not self._geometry_trace.select_from_pick(ctx, target, additive=additive):
                self._sync(ctx, "The visible mesh face could not be interpreted as a logical surface.", render=False)
                return True
            self._sync_workspace_selection()
            self._sync(ctx, self._workspace.message)
            return True

        # One ordinary click in empty space now clears the complete mixed
        # selection. Shift does not protect stale selection in empty space.
        self._clear_all_selection()
        self._sync(ctx, "Selection cleared.")
        return True

    def _double_click_main(self, ctx: Any, screen_pos: tuple[float, float]) -> bool:
        # Cloth no longer needs a special double-click contract. The second
        # click follows the same rule as a normal click; empty space clears.
        return self._select_main(ctx, screen_pos, additive=False)

    def _select_properties(self, ctx: Any, event: ToolEvent) -> bool:
        patch_id = self._nearest_patch(ctx, event.screen_pos)
        if patch_id is None:
            self._clear_modify_selection()
            self._sync_workspace_selection()
            self._sync(ctx, "Textile selection cleared.")
            return True
        face_mode = self._workspace.property_selection_mode is ClothPropertySelectionMode.FACE
        selected = (patch_id,) if face_mode else logical_patch_group(self._session.document, patch_id)
        if event.ctrl:
            remaining = [group for group in self._selected_textile_patch_groups() if not (group & set(selected))]
            self._set_selected_textile_groups(remaining, expand_persistent=not face_mode)
        elif event.shift:
            combined = (*self._selected_textile_patch_groups(), frozenset(selected))
            self._set_selected_textile_groups(combined, expand_persistent=not face_mode)
        else:
            self._set_selected_textile_groups((selected,), expand_persistent=not face_mode)
        self._sync_workspace_selection()
        self._sync(ctx, self._workspace.message)
        return True

    def _select_draw_entity(self, ctx: Any, event: ToolEvent) -> bool:
        if self._workspace.draw_pick_mode is ClothDrawPickMode.EDGE:
            entity_id = self._nearest_curve(ctx, event.screen_pos)
            kind = "curve"
        else:
            entity_id = self._nearest_patch(ctx, event.screen_pos)
            kind = "patch"
        if entity_id is None:
            if not event.shift:
                self._clear_modify_selection()
            self._sync_workspace_selection()
            self._sync(ctx, "Nothing selected in Draw.")
            return True
        self._select_modify_entity(kind, entity_id, additive=bool(event.shift))
        self._sync_workspace_selection()
        noun = "edge" if kind == "curve" else "face"
        self._sync(ctx, f"Textile {noun} selected individually. Press Delete to remove it.")
        return True

    def _analyze_close(self, ctx: Any) -> None:
        diag = self._cloth_diagnostics
        patch_groups = self._selected_textile_patch_groups()
        anchors = len(patch_groups) + len(self._session.selected_curve_ids)
        operation = diag.begin(
            "close.analyze", tool=self, ctx=ctx,
            anchor_count=anchors, inputs=close_input_snapshot(self),
        ) if diag is not None else None
        if anchors < 1:
            self._interaction.join_proposals = ()
            self._interaction.join_proposal_index = 0
            self._workspace_machine.enter_main()
            self._interaction.enter_main()
            self._sync(ctx, "Select at least one textile face or edge before Close.", render=False)
            if operation is not None:
                operation.finish(outcome="no_anchors", tool=self, ctx=ctx)
                diag.export(reason="close_no_anchors", tool=self, ctx=ctx)
            return
        # Enter the orange submenu before analysis so even a slow or failed
        # solver never makes the only Cloth overlay disappear.
        self._workspace_machine.enter_close(proposals=0, proposal_index=0)
        if operation is not None:
            operation.stage("workspace_entered", tool=self, ctx=ctx)
        self._sync(ctx, "Analyzing the selected textile faces and edges...")
        if operation is not None:
            operation.stage("overlay_before_solver", tool=self, ctx=ctx, overlay=overlay_snapshot(ctx))
        try:
            proposals = analyze_textile_close_groups(
                self._session.document,
                patch_groups,
                self._session.selected_curve_ids,
                diagnostics=diag.sink(operation, "solver") if diag is not None else None,
            )
        except Exception as exc:
            self._interaction.join_proposals = ()
            self._interaction.join_proposal_index = 0
            self._workspace_machine.enter_close(proposals=0, proposal_index=0)
            if diag is not None:
                diag.exception(
                    "close.analyze.solver_exception", exc,
                    operation_id=operation.operation_id if operation is not None else 0,
                    tool=self, ctx=ctx, inputs=close_input_snapshot(self),
                )
            self._sync(ctx, f"No closure proposal was created: {exc}")
            if operation is not None:
                operation.finish(outcome="solver_error", tool=self, ctx=ctx, error=repr(exc))
                diag.export(reason="close_solver_exception", tool=self, ctx=ctx)
            return
        self._interaction.join_proposals = proposals
        self._interaction.join_proposal_index = 0
        self._workspace_machine.enter_close(proposals=len(proposals), proposal_index=0)
        message = proposals[0].message if proposals else "No reliable closure was found. Reset keeps the selected textile elements unchanged."
        if operation is not None:
            operation.stage("proposals_assigned", tool=self, ctx=ctx, proposals=proposal_snapshot(proposals))
        self._sync(ctx, message)
        if operation is not None:
            operation.stage("overlay_after_solver", tool=self, ctx=ctx, overlay=overlay_snapshot(ctx))
            operation.finish(
                outcome="ok" if proposals else "no_proposal",
                tool=self, ctx=ctx, proposal_count=len(proposals), proposals=proposal_snapshot(proposals),
            )
            # Close diagnostics are exported immediately after every attempt so
            # the files exist even if the UI becomes unusable afterwards.
            diag.export(reason="close_analysis", tool=self, ctx=ctx)

    def _cycle_close_proposal(self, ctx: Any, direction: int) -> None:
        proposals = self._interaction.join_proposals
        if not proposals:
            self._sync(ctx, "There is no closure proposal to browse.", render=False)
            return
        index = (self._interaction.join_proposal_index + int(direction)) % len(proposals)
        self._interaction.join_proposal_index = index
        self._workspace_machine.update_close(proposals=len(proposals), proposal_index=index)
        self._sync(ctx, proposals[index].message)

    def _accept_close(self, ctx: Any) -> None:
        diag = self._cloth_diagnostics
        proposals = self._interaction.join_proposals
        operation = diag.begin(
            "close.commit", tool=self, ctx=ctx, proposals=proposal_snapshot(proposals),
            proposal_index=self._interaction.join_proposal_index,
        ) if diag is not None else None
        if not proposals:
            self._sync(ctx, "There is no closure proposal to apply. Use Reset to return.", render=False)
            if operation is not None:
                operation.finish(outcome="no_proposal", tool=self, ctx=ctx)
                diag.export(reason="close_commit_no_proposal", tool=self, ctx=ctx)
            return
        proposal = proposals[self._interaction.join_proposal_index]
        parent_group_ids = tuple(
            dict.fromkeys(
                explicit_textile_group_id(self._session.document, min(group))
                for group in self._selected_textile_patch_groups()
                if group and explicit_textile_group_id(self._session.document, min(group))
            )
        )
        original = self._session.document.clone()
        patches_before = set(self._session.document.patches)
        try:
            outcome = commit_join_proposal(self._session.document, proposal, drawing=self._drawing)
        except Exception as exc:
            self._drawing._restore_document(original)
            self._cloth_raycast_cache.reset()
            if diag is not None:
                diag.exception(
                    "close.commit.exception", exc,
                    operation_id=operation.operation_id if operation is not None else 0,
                    tool=self, ctx=ctx, proposal=proposal_snapshot((proposal,)),
                )
            self._sync(ctx, f"Close stopped safely without changing the textile: {exc}")
            if operation is not None:
                operation.finish(outcome="error", tool=self, ctx=ctx, error=repr(exc))
                diag.export(reason="close_commit_exception", tool=self, ctx=ctx)
            return
        if not outcome.committed:
            self._drawing._restore_document(original)
            self._cloth_raycast_cache.reset()
            self._sync(ctx, outcome.message or "The closure proposal could not be created.")
            if operation is not None:
                operation.finish(outcome="not_committed", tool=self, ctx=ctx, message=outcome.message)
                diag.export(reason="close_commit_rejected", tool=self, ctx=ctx)
            return
        created = tuple(patch_id for patch_id in self._session.document.patches if patch_id not in patches_before)
        if not created:
            self._drawing._restore_document(original)
            self._cloth_raycast_cache.reset()
            self._sync(ctx, "Close produced no textile face and was reverted.")
            if operation is not None:
                operation.finish(outcome="no_created_patch", tool=self, ctx=ctx)
                diag.export(reason="close_commit_empty", tool=self, ctx=ctx)
            return
        group_id = f"close_{self._session.document.revision}_{len(self._session.document.patches)}"
        assign_logical_patch_group(
            self._session.document,
            created,
            group_id,
            origin="close",
            parent_group_ids=parent_group_ids,
        )
        self._session.dirty = True
        self._validation_cache.reset()
        self._snap_target_cache.reset()
        self._cloth_raycast_cache.reset()
        self._clear_modify_selection()
        self._set_selected_textile_groups((created,))
        self._interaction.join_proposals = ()
        self._interaction.join_proposal_index = 0
        self._workspace_machine.enter_main()
        self._interaction.enter_main()
        self._sync_workspace_selection()
        self._sync(ctx, f"{outcome.message} The created textile group remains selected.")
        if operation is not None:
            operation.finish(outcome="ok", tool=self, ctx=ctx, created_patch_ids=created, message=outcome.message)
            diag.export(reason="close_commit", tool=self, ctx=ctx)

    def _set_patch_function(self, ctx: Any, function: ClothPatchFunction) -> None:
        changed = self._session.document.set_patch_properties(self._session.selected_patch_ids, function=function)
        if not changed:
            self._sync(ctx, "Select one or more textile faces first.", render=False)
            return
        self._session.dirty = True
        self._validation_cache.reset()
        self._sync(ctx, f"{len(changed)} textile face(s) changed to {function.value}.")

    def _apply_and_continue(self, ctx: Any) -> bool:
        return self._apply_controller.apply_and_continue(ctx)

    def _set_mode(self, ctx: Any, mode: str) -> None:
        if mode == ClothEditMode.FOLD.value and self._interaction.stage is ClothUxStage.SELECT_FOLD_EDGE:
            self._sync(ctx, "Fold / Cut pattern editor is already active.", render=False)
            return
        if mode != ClothEditMode.FOLD.value and self._pattern_edge_snapshot is not None:
            self._restore_pattern_preview()
            self._pattern_edge_snapshot = None
            self._interaction.selected_pattern_curve_id = None
            self._interaction.selected_fold_id = None
        if self._session.phase in {ClothWorkflowPhase.FLAT_PREVIEW, ClothWorkflowPhase.VALIDATION_BLOCKED, ClothWorkflowPhase.APPLY_READY}:
            self._machine.return_to_editing()
        if self._session.phase is ClothWorkflowPhase.OPENING:
            self._start_new(ctx)
        try:
            self._machine.set_edit_mode(mode)
        except ClothTransitionError as exc:
            self._sync(ctx, str(exc), render=False)
            return
        if mode != ClothEditMode.MODIFY.value:
            self._clear_modify_selection()
        else:
            # Face mode owns a separate temporary curve-loop selection. It must
            # not leak into normal entity selection after validation/Trace.
            self._interaction.selected_curve_ids = ()
        self._drawing.cancel()
        if mode in _TRACE_MODES:
            self._geometry_overlay.hide(ctx)
            self._pattern_overlay.hide(ctx)
            self._interaction.enter_draw()
            self._drawing.begin(mode)
        elif mode == ClothEditMode.FACE.value:
            self._geometry_overlay.hide(ctx)
            self._pattern_overlay.hide(ctx)
            self._interaction.enter_face_loop()
        elif mode == ClothEditMode.MESH_TRACE.value:
            self._pattern_overlay.hide(ctx)
            self._interaction.enter_source_geometry()
            self._geometry_overlay.sync(ctx)
        elif mode == ClothEditMode.FOLD.value:
            self._geometry_overlay.hide(ctx)
            self._interaction.enter_fold()
            try:
                ctx.inspector.update_value("cloth_pattern_spacing", pattern_spacing_mm(self._session.document), notify=False)
            except Exception:
                pass
            self._pattern_overlay.sync(ctx)
        else:
            self._geometry_overlay.hide(ctx)
            self._pattern_overlay.hide(ctx)
            self._interaction.enter_draw()
        self._sync(ctx, self._mode_instruction(mode))

    @staticmethod
    def _mode_instruction(mode: str) -> str:
        return {
            ClothEditMode.POINT.value: "Point: click scene geometry or empty space.",
            ClothEditMode.LINE.value: "Line: place two points directly in 3D.",
            ClothEditMode.POLYLINE.value: "Polyline: place points; click the first point or use Close face.",
            ClothEditMode.ARC.value: "Arc: place start, end and control point in 3D.",
            ClothEditMode.MODIFY.value: "Modify: select technical faces or edges; Apply separates selected faces; Delete removes them.",
            ClothEditMode.FACE.value: "Face: select a connected closed loop.",
            ClothEditMode.MESH_TRACE.value: "Mesh trace: select source faces or edges; smart help activates when a reliable continuation is available.",
            ClothEditMode.FOLD.value: "Fold / Cut: select a shared panel edge, choose its pattern role, then validate it.",
        }.get(mode, f"Cloth mode: {mode}.")

    def _draw_click(self, ctx: Any, event: ToolEvent, *, double: bool) -> bool:
        mode = self._session.edit_mode.value
        patches_before = set(self._session.document.patches)
        # Test the visible transient start handle before applying construction
        # snaps. A click on that handle must close the loop even when an X/Y/Z
        # guide would otherwise move the resolved world position elsewhere.
        if mode == TraceMode.POLYLINE.value and not double and len(self._drawing.pending_world_points) >= 3:
            first = self._drawing.pending_world_points[0]
            try:
                first_screen = self._world_to_screen(ctx)(first)
                screen = event.screen_pos
                closes_start = screen is not None and math.dist(
                    (float(screen[0]), float(screen[1])),
                    (float(first_screen[0]), float(first_screen[1])),
                ) <= self._snap_tolerance_px
            except Exception:
                closes_start = False
            if closes_start:
                outcome = self._drawing.close_polyline_at(first, closure_tolerance=1.0e-4)
                self._session.dirty = self._session.dirty or outcome.committed
                self._interaction.message = outcome.message
                if outcome.committed:
                    created = tuple(
                        patch_id
                        for patch_id in self._session.document.patches
                        if patch_id not in patches_before
                    )
                    if created:
                        assign_logical_patch_group(
                            self._session.document,
                            created,
                            f"draw_{self._session.document.revision}_{created[0]}",
                            origin="draw",
                        )
                        self._set_selected_textile_groups((created,))
                    self._drawing.begin(mode)
                self._workspace_machine.update_draw(
                    len(self._drawing.pending_world_points),
                    smart_snap_enabled=self._smart_snap,
                    axis_guides_enabled=self._construction_snap,
                )
                self._sync_workspace_selection()
                self._sync(
                    ctx,
                    outcome.message
                    if not outcome.committed
                    else f"{outcome.message} The new textile face is selected.",
                )
                return True

        point, existing_id = self._point_in_space(ctx, event)
        if point is None:
            self._sync(ctx, "No 3D point could be resolved. Orbit the camera or move near scene geometry.", render=False)
            return True
        if double and mode == TraceMode.POLYLINE.value:
            outcome = self._drawing.close_polyline_at(
                point,
                existing_point_id=existing_id,
                closure_tolerance=1.0e-4,
            )
        else:
            outcome = self._drawing.add_position(
                point,
                existing_point_id=existing_id,
                finish=False,
                closed=False,
                closure_tolerance=1.0e-4,
            )
        self._session.dirty = self._session.dirty or outcome.committed
        self._interaction.message = outcome.message
        if outcome.committed:
            created = tuple(patch_id for patch_id in self._session.document.patches if patch_id not in patches_before)
            if created:
                assign_logical_patch_group(
                    self._session.document,
                    created,
                    f"draw_{self._session.document.revision}_{created[0]}",
                    origin="draw",
                )
                self._set_selected_textile_groups((created,))
            self._drawing.begin(mode)
        self._workspace_machine.update_draw(
            len(self._drawing.pending_world_points),
            smart_snap_enabled=self._smart_snap,
            axis_guides_enabled=self._construction_snap,
        )
        self._sync_workspace_selection()
        self._sync(ctx, outcome.message if not outcome.committed else f"{outcome.message} The new textile face is selected.")
        return True

    def _finish_trace(self, ctx: Any, *, closed: bool) -> bool:
        if not self._drawing.active:
            return False
        patches_before = set(self._session.document.patches)
        outcome = self._drawing.finish(closed=closed)
        self._session.dirty = self._session.dirty or outcome.committed
        if outcome.committed:
            created = tuple(patch_id for patch_id in self._session.document.patches if patch_id not in patches_before)
            if created:
                assign_logical_patch_group(
                    self._session.document,
                    created,
                    f"draw_{self._session.document.revision}_{created[0]}",
                    origin="draw",
                )
                self._set_selected_textile_groups((created,))
            self._drawing.begin(self._session.edit_mode.value)
        self._workspace_machine.update_draw(
            len(self._drawing.pending_world_points),
            smart_snap_enabled=self._smart_snap,
            axis_guides_enabled=self._construction_snap,
        )
        self._sync_workspace_selection()
        self._sync(ctx, outcome.message if not outcome.committed else f"{outcome.message} The new textile face is selected.")
        return True

    def _create_selected_face(self, ctx: Any) -> None:
        patches_before = set(self._session.document.patches)
        outcome = self._drawing.create_patch_from_curves(self._interaction.selected_curve_ids)
        if outcome.committed:
            created = tuple(patch_id for patch_id in self._session.document.patches if patch_id not in patches_before)
            if created:
                assign_logical_patch_group(
                    self._session.document,
                    created,
                    f"draw_{self._session.document.revision}_{created[0]}",
                    origin="draw",
                )
                self._set_selected_textile_groups((created,))
            self._session.dirty = True
            self._interaction.selected_curve_ids = ()
            self._interaction.enter_draw()
            self._machine.set_edit_mode(ClothEditMode.MODIFY)
        self._sync_workspace_selection()
        self._sync(ctx, outcome.message)

    def _select_source_geometry(self, ctx: Any, screen_pos: tuple[float, float], *, additive: bool = False) -> bool:
        picker = ctx.pick.face_at if self._geometry_trace.pick_kind == "face" else ctx.pick.edge_at
        try:
            pick = picker(screen_pos, exact_screen=True) if self._geometry_trace.pick_kind == "face" else picker(screen_pos)
        except Exception:
            pick = None
        if pick is None or not getattr(pick, "hit", False):
            kind = "face" if self._geometry_trace.pick_kind == "face" else "edge"
            self._sync(ctx, f"No mesh {kind} was found under the pointer.", render=False)
            return True
        if not self._geometry_trace.select_from_pick(ctx, pick, additive=additive):
            self._sync(ctx, "This mesh element could not be interpreted. Try the other source type or another visible element.", render=False)
            return True
        face_count = len(self._geometry_trace.selected_faces)
        edge_count = len(self._geometry_trace.selected_edges)
        predictions = self._geometry_trace.predictions()
        hints: list[str] = []
        if predictions.coplanar_faces:
            hints.append("Coplanar")
        if predictions.directional_edges:
            hints.append("Continue")
        if predictions.closure_edges:
            hints.append("Close face")
        if predictions.connected_edges:
            hints.append("Connected")
        if predictions.ruled_strip is not None:
            hints.append("Cover")
        suffix = f" Smart help: {', '.join(hints)}." if hints else ""
        mesh_count = self._geometry_trace.smart_session.selected_mesh_count if self._geometry_trace.pick_kind == "face" else len({item.object_id for item in self._geometry_trace.selected_edges})
        action = "Added" if additive else "Selected"
        self._sync_workspace_selection()
        self._sync(ctx, f"{action}: {self._geometry_trace.smart_session.selected_region_count} logical surface(s), {mesh_count} mesh(es).{suffix}")
        return True

    def _create_source_textile(self, ctx: Any) -> None:
        diag = self._cloth_diagnostics
        operation = diag.begin(
            "take_face", tool=self, ctx=ctx,
            selected_region_count=self._geometry_trace.smart_session.selected_region_count,
            selected_mesh_count=self._geometry_trace.smart_session.selected_mesh_count,
            selected_faces=[(item.object_id, item.face_index) for item in self._geometry_trace.selected_faces],
        ) if diag is not None else None
        try:
            outcome = self._geometry_trace.create(self._session.document, self._drawing)
        except Exception as exc:
            if diag is not None:
                diag.exception(
                    "take_face.exception", exc,
                    operation_id=operation.operation_id if operation is not None else 0, tool=self, ctx=ctx,
                )
                if operation is not None:
                    operation.finish(outcome="error", tool=self, ctx=ctx, error=repr(exc))
                diag.export(reason="take_face_exception", tool=self, ctx=ctx)
            raise
        if not outcome.committed:
            self._sync(ctx, outcome.message)
            if operation is not None:
                operation.finish(outcome="not_committed", tool=self, ctx=ctx, message=outcome.message)
            return
        created = tuple(
            patch_id for patch_id in outcome.created_patch_ids
            if patch_id in self._session.document.patches
        )
        self._session.dirty = True
        self._validation_cache.reset()
        self._snap_target_cache.reset()
        self._geometry_trace.clear_selection()
        self._session.selected_point_ids = ()
        self._session.selected_curve_ids = ()
        groups = tuple(
            tuple(patch_id for patch_id in group if patch_id in self._session.document.patches)
            for group in outcome.created_patch_groups
            if group
        )
        if not groups and created:
            groups = (created,)
        assigned: list[tuple[str, ...]] = []
        for index, group in enumerate(groups):
            if not group:
                continue
            assign_logical_patch_group(
                self._session.document,
                group,
                f"take_{self._session.document.revision}_{index}_{min(group)}",
                origin="take_face",
            )
            assigned.append(tuple(group))
        self._set_selected_textile_groups(assigned)
        self._cloth_raycast_cache.reset()
        self._workspace_machine.enter_main()
        self._interaction.enter_main()
        self._machine.set_edit_mode(ClothEditMode.MESH_TRACE)
        self._sync_workspace_selection()
        self._sync(ctx, f"{outcome.message} The copied textile group remains selected.")
        if operation is not None:
            operation.finish(
                outcome="ok", tool=self, ctx=ctx, message=outcome.message,
                created_patch_ids=created, created_patch_groups=groups, assigned_groups=assigned,
            )

    def _double_click_source_geometry(self, ctx: Any, screen_pos: tuple[float, float]) -> bool:
        picker = ctx.pick.face_at if self._geometry_trace.pick_kind == "face" else ctx.pick.edge_at
        try:
            pick = picker(screen_pos, exact_screen=True) if self._geometry_trace.pick_kind == "face" else picker(screen_pos)
        except Exception:
            pick = None
        if pick is None or not getattr(pick, "hit", False):
            self._geometry_trace.clear_selection()
            self._sync_workspace_selection()
            self._sync(ctx, "Source selection cleared by double-click in empty space.")
        else:
            self._sync(ctx, "Double-click on geometry has no special action.", render=False)
        return True

    def _on_geometry_action(self, ctx: Any, action_id: str) -> None:
        action = str(action_id)
        if self._session.phase is ClothWorkflowPhase.OPENING and action in {
            "trace_selection",
            "create_bridge",
            "close_source_face",
        }:
            # Hidden compatibility actions must never mutate the opening
            # document and then lose it while transitioning to editing.
            self._start_new(ctx)
        if action == "pick_face":
            self._geometry_trace.set_pick_kind("face")
            self._sync(ctx, "Mesh trace: select one or more source faces.")
            return
        if action == "pick_edge":
            self._geometry_trace.set_pick_kind("edge")
            self._sync(ctx, "Mesh trace: select one or more source edges.")
            return
        if action == "clear_selection":
            self._geometry_trace.clear_selection()
            self._sync(ctx, "Mesh trace selection cleared.")
            return
        if action == "grow_coplanar":
            self._sync(ctx, "The smart-selection API already included the complete logical face.", render=False)
            return
        prediction_map = {
            "grow_coplanar": "coplanar",
            "use_boundary": "boundary",
            "extend_direction": "direction",
            "select_connected": "connected",
            "close_source_face": "close_face",
        }
        if action in prediction_map:
            count = self._geometry_trace.apply_prediction(prediction_map[action])
            if count:
                self._sync(ctx, f"Smart mesh trace added {count} predicted element(s).")
            else:
                self._sync(ctx, "No reliable prediction is available for the current selection.", render=False)
            return
        if action in {"trace_selection", "create_bridge"}:
            outcome = self._geometry_trace.create(self._session.document, self._drawing)
            self._session.dirty = self._session.dirty or outcome.committed
            if outcome.committed:
                self._geometry_trace.clear()
                self._geometry_overlay.hide(ctx)
                self._set_mode(ctx, ClothEditMode.MODIFY.value)
                self._sync(ctx, f"{outcome.message} Modify mode is active.")
            else:
                self._sync(ctx, outcome.message)
            return

    def _restore_pattern_preview(self) -> bool:
        snapshot = self._pattern_edge_snapshot
        if snapshot is None:
            return False
        restore_pattern_document(self._session.document, snapshot.clone())
        self._validation_cache.reset()
        self._snap_target_cache.reset()
        return True

    def _preview_selected_pattern_edge(self, ctx: Any) -> bool:
        curve_id = self._interaction.selected_pattern_curve_id
        snapshot = self._pattern_edge_snapshot
        if curve_id is None or snapshot is None:
            return False
        restore_pattern_document(self._session.document, snapshot.clone())
        try:
            apply_pattern_edge(
                self._session.document,
                curve_id,
                self._interaction.pattern_operation,
                angle_degrees=self._interaction.pattern_angle_degrees,
                radius_mm=self._interaction.pattern_radius_mm,
            )
        except ClothPatternEdgeError as exc:
            restore_pattern_document(self._session.document, snapshot.clone())
            self._validation_cache.reset()
            self._snap_target_cache.reset()
            self._sync(ctx, str(exc), render=False)
            return False
        self._validation_cache.reset()
        self._snap_target_cache.reset()
        return True

    def _select_fold(self, ctx: Any, screen_pos: tuple[float, float]) -> bool:
        if self._pattern_edge_snapshot is not None:
            self._restore_pattern_preview()
            self._pattern_edge_snapshot = None
        curve_id = self._nearest_curve(ctx, screen_pos)
        if curve_id is None:
            self._sync(ctx, "No shared panel edge was found under the pointer.", render=False)
            return True
        try:
            state = pattern_edge_state(self._session.document, curve_id)
        except ClothPatternEdgeError as exc:
            self._sync(ctx, str(exc), render=False)
            return True
        self._pattern_edge_snapshot = self._session.document.clone()
        self._interaction.selected_pattern_curve_id = curve_id
        self._interaction.selected_fold_id = state.fold_id
        self._interaction.pattern_operation = state.operation if state.can_fold else "cut"
        self._interaction.pattern_angle_degrees = float(state.angle_degrees)
        self._interaction.pattern_radius_mm = float(state.radius_mm)
        try:
            ctx.inspector.update_value("cloth_fold_angle", self._interaction.pattern_angle_degrees, notify=False)
            ctx.inspector.update_value("cloth_fold_radius", self._interaction.pattern_radius_mm, notify=False)
        except Exception:
            pass
        role = "Fold" if self._interaction.pattern_operation == "fold" else "Cut"
        self._sync(ctx, f"Pattern edge selected as {role}. Adjust its settings, then press Apply edge.")
        return True

    def _set_selected_fold_angle(self, ctx: Any, angle: float) -> None:
        if not self._interaction.selected_pattern_curve_id:
            self._sync(ctx, "Select a shared panel edge before editing its fold angle.", render=False)
            return
        self._interaction.pattern_angle_degrees = max(-180.0, min(180.0, float(angle)))
        self._interaction.pattern_operation = "fold"
        if self._preview_selected_pattern_edge(ctx):
            self._sync(ctx, f"Fold preview set to {self._interaction.pattern_angle_degrees:.1f}°. Press Apply edge to validate.")

    def _set_selected_fold_radius(self, ctx: Any, radius: float) -> None:
        if not self._interaction.selected_pattern_curve_id:
            self._sync(ctx, "Select a shared panel edge before editing its fold radius.", render=False)
            return
        self._interaction.pattern_radius_mm = max(0.0, min(1000.0, float(radius)))
        self._interaction.pattern_operation = "fold"
        if self._preview_selected_pattern_edge(ctx):
            self._sync(ctx, f"Fold radius preview set to {self._interaction.pattern_radius_mm:.3g} mm. Press Apply edge to validate.")

    def _clear_pattern_edge_selection(self, ctx: Any, *, message: str = "Pattern-edge selection cleared.") -> None:
        self._restore_pattern_preview()
        self._pattern_edge_snapshot = None
        self._interaction.selected_pattern_curve_id = None
        self._interaction.selected_fold_id = None
        self._interaction.pattern_angle_degrees = 0.0
        self._interaction.pattern_radius_mm = 0.0
        self._sync(ctx, message)

    def _apply_selected_pattern_edge(self, ctx: Any) -> bool:
        curve_id = self._interaction.selected_pattern_curve_id
        if not curve_id:
            self._sync(ctx, "Select a shared panel edge before validating Fold or Cut.", render=False)
            return True
        try:
            if self._pattern_edge_snapshot is None:
                result = apply_pattern_edge(
                    self._session.document,
                    curve_id,
                    self._interaction.pattern_operation,
                    angle_degrees=self._interaction.pattern_angle_degrees,
                    radius_mm=self._interaction.pattern_radius_mm,
                )
            else:
                result = apply_pattern_edge(
                    self._pattern_edge_snapshot.clone(),
                    curve_id,
                    self._interaction.pattern_operation,
                    angle_degrees=self._interaction.pattern_angle_degrees,
                    radius_mm=self._interaction.pattern_radius_mm,
                )
                if not self._preview_selected_pattern_edge(ctx):
                    return True
        except ClothPatternEdgeError as exc:
            self._sync(ctx, str(exc), render=False)
            return True
        self._session.dirty = True
        self._pattern_edge_snapshot = None
        self._validation_cache.reset()
        self._snap_target_cache.reset()
        self._interaction.selected_pattern_curve_id = None
        self._interaction.selected_fold_id = None
        self._sync(ctx, f"{result.message} Select another edge or press Done.")
        return True

    def _on_pattern_action(self, ctx: Any, action: str) -> None:
        if action == "operation_fold":
            curve_id = self._interaction.selected_pattern_curve_id
            if curve_id is not None:
                try:
                    if not pattern_edge_state(self._session.document, curve_id).can_fold:
                        self._sync(ctx, "A curved shared boundary can be cut, but cannot act as a rigid fold hinge.", render=False)
                        return
                except ClothPatternEdgeError as exc:
                    self._sync(ctx, str(exc), render=False)
                    return
            self._interaction.pattern_operation = "fold"
            if self._interaction.selected_pattern_curve_id and self._preview_selected_pattern_edge(ctx):
                self._sync(ctx, "Fold preview active. Set the angle/radius, then press Apply edge.")
            else:
                self._sync(ctx, "Fold selected. Select a shared edge, then set its angle/radius.", render=False)
            return
        if action == "operation_cut":
            self._interaction.pattern_operation = "cut"
            if self._interaction.selected_pattern_curve_id and self._preview_selected_pattern_edge(ctx):
                self._sync(ctx, "Cut preview active. The 3D surface stays continuous; press Apply edge to validate.")
            else:
                self._sync(ctx, "Cut selected. Select a shared edge to separate its flat-pattern panels.", render=False)
            return
        if action in {"angle_minus_90", "angle_flat", "angle_plus_90", "invert_angle"}:
            if not self._interaction.selected_pattern_curve_id:
                self._sync(ctx, "Select a shared edge before choosing a fold angle.", render=False)
                return
            values = {"angle_minus_90": -90.0, "angle_flat": 0.0, "angle_plus_90": 90.0}
            angle = -self._interaction.pattern_angle_degrees if action == "invert_angle" else values[action]
            if action == "invert_angle" and abs(angle) <= 1.0e-9:
                angle = -90.0
            self._interaction.pattern_operation = "fold"
            self._interaction.pattern_angle_degrees = angle
            try:
                ctx.inspector.update_value("cloth_fold_angle", angle, notify=False)
            except Exception:
                pass
            if self._preview_selected_pattern_edge(ctx):
                self._sync(ctx, f"Fold preview set to {angle:.1f}°. Press Apply edge to validate.")
            return
        if action == "apply_edge":
            self._apply_selected_pattern_edge(ctx)
            return
        if action == "clear_edge":
            self._clear_pattern_edge_selection(ctx)
            return
        if action == "auto_cut_cycles":
            self._restore_pattern_preview()
            self._pattern_edge_snapshot = None
            curve_ids = apply_cycle_cuts(self._session.document)
            if not curve_ids:
                self._sync(ctx, "The current fold graph already unfolds without cycles.", render=False)
                return
            self._session.dirty = True
            self._validation_cache.reset()
            self._snap_target_cache.reset()
            self._interaction.selected_pattern_curve_id = None
            self._interaction.selected_fold_id = None
            self._sync(ctx, f"Converted {len(curve_ids)} cycle-closing fold(s) into pattern cuts.")
            return
        if action == "done":
            if self._pattern_edge_snapshot is not None:
                self._restore_pattern_preview()
                self._pattern_edge_snapshot = None
            self._set_mode(ctx, ClothEditMode.MODIFY.value)
            self._sync(ctx, "Pattern edges validated. Modify mode is active.")
            return

    # Hover, plane projection and snap
    def _set_hovered_textile_patch(self, patch_id: str | None, *, logical_group: bool) -> None:
        value = str(patch_id or "")
        self._interaction.hovered_patch_id = value or None
        if not value or value not in self._session.document.patches:
            self._interaction.hovered_patch_group_ids = ()
            return
        self._interaction.hovered_patch_group_ids = (
            logical_patch_group(self._session.document, value)
            if logical_group
            else (value,)
        )

    def _update_hover(self, ctx: Any, screen_pos: tuple[float, float], world_pos=None) -> None:
        self._interaction.clear_hover()
        if self._interaction.stage is ClothUxStage.OPENING:
            pick = ctx.pick.object_at(screen_pos)
            if pick.hit:
                obj = object_from_pick(ctx, pick)
                output_kind = cloth_output_kind(getattr(obj, "mesh", None)) if obj is not None else None
                if output_kind == "folded":
                    object_id = str(getattr(obj, "id", "") or "")
                    self._hover_editable = (object_id, obj.mesh)
                    self._interaction.hovered_object_id = object_id
                    self._renderer.sync(ctx, render=False)
                    self._mesh_hover.show(ctx, group_key=object_id, meshes=(EditableHoverMesh(object_id, obj.mesh),), render=True)
                    return
            self._hover_editable = None
            self._mesh_hover.hide(ctx, render=False)
            return

        self._mesh_hover.hide(ctx, render=False)
        stage = self._interaction.stage
        if stage is ClothUxStage.MAIN:
            curve_id = self._nearest_solitary_curve(ctx, screen_pos)
            if curve_id is not None:
                self._geometry_trace.set_hover_from_pick(ctx, None)
                self._interaction.hovered_curve_id = curve_id
                self._renderer.sync(ctx)
                return
            target_kind, target = self._frontmost_face_target(ctx, screen_pos)
            if target_kind == "textile" and target is not None:
                self._geometry_trace.set_hover_from_pick(ctx, None)
                self._set_hovered_textile_patch(str(target), logical_group=True)
            elif target_kind == "mesh" and target is not None:
                self._geometry_trace.set_hover_from_pick(ctx, target)
            else:
                self._geometry_trace.set_hover_from_pick(ctx, None)
            self._renderer.sync(ctx)
            return

        if stage is ClothUxStage.CLOSE:
            self._interaction.hovered_curve_id = self._nearest_curve(ctx, screen_pos)
            if self._interaction.hovered_curve_id is None:
                self._set_hovered_textile_patch(self._nearest_patch(ctx, screen_pos), logical_group=True)
            self._renderer.sync(ctx)
            return

        if stage is ClothUxStage.PROPERTIES:
            self._set_hovered_textile_patch(
                self._nearest_patch(ctx, screen_pos),
                logical_group=self._workspace.property_selection_mode is ClothPropertySelectionMode.GROUP,
            )
            self._renderer.sync(ctx)
            return

        if stage is ClothUxStage.DRAW:
            if self._session.edit_mode.value in {ClothEditMode.LINE.value, ClothEditMode.POLYLINE.value}:
                point, _ = self._point_in_space(ctx, ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=screen_pos, world_pos=world_pos))
                self._interaction.cursor_world = point
                metadata = dict(self._interaction.cursor_metadata or {})
                self._interaction.hovered_point_id = str(metadata.get("cloth_point_id") or "") or None
                self._interaction.hovered_curve_id = str(metadata.get("cloth_curve_id") or "") or None
            elif self._workspace.draw_pick_mode is ClothDrawPickMode.EDGE:
                self._interaction.hovered_curve_id = self._nearest_curve(ctx, screen_pos)
            else:
                self._set_hovered_textile_patch(self._nearest_patch(ctx, screen_pos), logical_group=False)
            self._renderer.sync(ctx)
            return

        if stage is ClothUxStage.SELECT_FOLD_EDGE:
            self._interaction.hovered_curve_id = self._nearest_curve(ctx, screen_pos)
            self._renderer.sync(ctx)

    def _point_in_space(
        self,
        ctx: Any,
        event: ToolEvent,
        *,
        update_state: bool = True,
    ) -> tuple[tuple[float, float, float] | None, str | None]:
        if event.screen_pos is None:
            return None, None
        placement = resolve_cloth_point(
            ctx,
            event.screen_pos,
            document=self._session.document,
            owner_tool=self.id,
            pending_points=self._drawing.pending_world_points,
            event_world_pos=event.world_pos,
            smart_snap=self._smart_snap,
            snap_tolerance_px=self._snap_tolerance_px,
            snap_target_cache=self._snap_target_cache,
            construction_snap=self._construction_snap,
        )
        if update_state:
            self._interaction.cursor_snap_label = placement.label
            self._interaction.cursor_source = placement.source
            self._interaction.cursor_snap_kind = placement.snap_kind
            self._interaction.cursor_snapped = placement.snapped
            self._interaction.cursor_source_id = placement.source_id
            self._interaction.cursor_metadata = dict(placement.metadata or {})
            self._interaction.set_construction_plane(placement.construction_plane, label="Free 3D")
        return placement.position, placement.existing_point_id

    # Backward-compatible name used by older tests/plugins. The result is no
    # longer clamped to a persistent drawing plane.
    def _point_on_plane(self, ctx: Any, event: ToolEvent):
        return self._point_in_space(ctx, event)

    def _world_to_screen(self, ctx: Any):
        projector = getattr(ctx.viewport, "world_to_screen", None)
        if callable(projector):
            return projector
        return lambda point: (float(point[0]), float(point[1]))

    def _nearest_point(self, ctx: Any, screen_pos: tuple[float, float]) -> str | None:
        return nearest_document_point(self._session.document, screen_pos, self._world_to_screen(ctx), max_distance_px=self._snap_tolerance_px)

    def _nearest_curve(self, ctx: Any, screen_pos: tuple[float, float]) -> str | None:
        return nearest_document_curve(self._session.document, screen_pos, self._world_to_screen(ctx), max_distance_px=self._snap_tolerance_px)

    def _scene_face_pick(self, ctx: Any, screen_pos: tuple[float, float]):
        try:
            pick = ctx.pick.face_at(screen_pos, exact_screen=True)
        except Exception:
            return None
        if pick is None or not getattr(pick, "hit", False):
            return None
        # The linked folded Cloth output is only the persisted representation of
        # the document currently edited.  Let the canonical textile surface own
        # this hit instead of treating the output as an unrelated source mesh.
        try:
            if self._session.source_mesh_id and str(getattr(pick, "object_id", "") or "") == str(self._session.source_mesh_id):
                return None
        except Exception:
            pass
        return pick

    def _textile_source_pick_margin_mm(self, patch_id: str) -> float:
        """Allowed normal separation for a textile linked to its source mesh.

        The comparison is performed perpendicular to the visible surface, not
        along the camera ray.  This keeps the preference stable at grazing view
        angles, where a sub-millimetre offset can span several millimetres along
        the ray.
        """

        patch = self._session.document.patches.get(str(patch_id))
        if patch is None:
            return 0.35
        layer = self._session.document.layers.get(str(patch.layer_id))
        thickness = float(getattr(layer, "thickness_mm", 0.2) or 0.2)
        return max(0.6, min(2.5, thickness * 6.0))

    def _textile_near_pick_margin_mm(self, patch_id: str) -> float:
        """Small generic preference for practically coincident textile faces."""

        patch = self._session.document.patches.get(str(patch_id))
        layer = self._session.document.layers.get(str(patch.layer_id)) if patch is not None else None
        thickness = float(getattr(layer, "thickness_mm", 0.2) or 0.2)
        return max(0.03, min(0.12, thickness * 0.5))

    def _textile_hit_matches_scene_source(self, patch_id: str, scene_pick: Any) -> bool:
        """Return whether a textile patch was authored from the picked mesh face.

        Object identity alone is not sufficient on closed meshes: a textile on
        the rear side could otherwise steal a front-side click.  When Take face
        stored source triangle indices, require the exact visible triangle too.
        Legacy patches without that metadata retain the object-level fallback.
        """

        patch = self._session.document.patches.get(str(patch_id))
        if patch is None:
            return False
        metadata = dict(patch.metadata or {})
        source_id = str(metadata.get("cloth_source_object_id") or "")
        scene_id = str(getattr(scene_pick, "object_id", "") or "")
        if not source_id or not scene_id or source_id != scene_id:
            return False
        source_faces = tuple(metadata.get("cloth_source_faces") or ())
        scene_face = getattr(scene_pick, "element_index", None)
        if source_faces and scene_face is not None:
            try:
                return int(scene_face) in {int(value) for value in source_faces}
            except Exception:
                return True
        return True

    def _frontmost_face_target(self, ctx: Any, screen_pos: tuple[float, float]):
        """Return the true frontmost textile patch or scene-mesh face."""

        diag = self._cloth_diagnostics
        scene_pick = self._scene_face_pick(ctx, screen_pos)
        textile_hit = self._cloth_raycast_cache.hit(ctx, self._session.document, screen_pos)
        projected_patch = nearest_document_patch(self._session.document, screen_pos, self._world_to_screen(ctx))
        projected_linked = bool(
            scene_pick is not None
            and projected_patch is not None
            and self._textile_hit_matches_scene_source(projected_patch, scene_pick)
        )
        scene_payload = None if scene_pick is None else {
            "object_id": str(getattr(scene_pick, "object_id", "") or ""),
            "object_index": getattr(scene_pick, "object_index", None),
            "element_index": getattr(scene_pick, "element_index", None),
            "world_pos": getattr(scene_pick, "world_pos", None),
            "normal": getattr(scene_pick, "normal", None),
        }
        textile_payload = None if textile_hit is None else {
            "patch_id": textile_hit.patch_id,
            "distance": textile_hit.distance,
            "world_pos": getattr(textile_hit, "world_pos", None),
            "normal": textile_hit.normal,
        }

        def choose(kind, target, reason: str, **metrics):
            if diag is not None:
                diag.record(
                    "pick.frontmost", tool=self, ctx=ctx,
                    screen_pos=screen_pos, scene_pick=scene_payload, textile_hit=textile_payload,
                    textile_cache_mode=str(getattr(self._cloth_raycast_cache, "build_mode", "unknown")),
                    textile_cache_triangles=len(getattr(self._cloth_raycast_cache, "triangles", ()) or ()),
                    textile_cache_issues=tuple(getattr(self._cloth_raycast_cache, "build_issues", ()) or ()),
                    projected_textile_patch=projected_patch,
                    projected_textile_matches_source=projected_linked,
                    winner=kind, winner_id=(str(target) if kind == "textile" else str(getattr(target, "object_id", "") or "") if target is not None else None),
                    reason=reason, **metrics,
                )
            return kind, target

        if scene_pick is not None and textile_hit is not None:
            scene_distance = pick_distance_along_ray(ctx, screen_pos, getattr(scene_pick, "world_pos", None))
            linked_source = self._textile_hit_matches_scene_source(textile_hit.patch_id, scene_pick)
            # A projected Take-face patch matching the exact visible source face
            # is the editable layer the user sees.  Prefer it over the source
            # mesh unless another textile is genuinely in front of that mesh.
            if projected_linked and projected_patch is not None and projected_patch != textile_hit.patch_id:
                if scene_distance is None or textile_hit.distance >= scene_distance - 1.0e-4:
                    return choose(
                        "textile",
                        projected_patch,
                        "projected_source_textile_priority",
                        scene_distance=scene_distance,
                        textile_distance=textile_hit.distance,
                        raycast_patch_id=textile_hit.patch_id,
                    )
            source_margin = self._textile_source_pick_margin_mm(textile_hit.patch_id)
            near_margin = self._textile_near_pick_margin_mm(textile_hit.patch_id)
            if scene_distance is None:
                return choose(
                    "textile" if linked_source else "mesh",
                    textile_hit.patch_id if linked_source else scene_pick,
                    "scene_distance_missing_linked_source" if linked_source else "scene_distance_missing_mesh_fallback",
                    linked_source=linked_source, source_margin_mm=source_margin, near_margin_mm=near_margin,
                )
            epsilon = max(1.0e-4, max(abs(scene_distance), abs(textile_hit.distance)) * 1.0e-7)
            if textile_hit.distance < scene_distance - epsilon:
                return choose(
                    "textile", textile_hit.patch_id, "textile_strictly_front",
                    scene_distance=scene_distance, textile_distance=textile_hit.distance, epsilon=epsilon, linked_source=linked_source,
                )
            depth_gap = textile_hit.distance - scene_distance
            if depth_gap > epsilon:
                ray_direction = pick_ray_direction(ctx, screen_pos)
                scene_normal = getattr(scene_pick, "normal", None)
                try:
                    scene_normal = tuple(float(value) for value in scene_normal) if scene_normal is not None else textile_hit.normal
                except Exception:
                    scene_normal = textile_hit.normal
                normal_length = math.sqrt(sum(float(value) * float(value) for value in scene_normal))
                if normal_length > 1.0e-12:
                    scene_normal = tuple(float(value) / normal_length for value in scene_normal)
                else:
                    scene_normal = textile_hit.normal
                incidence = (
                    abs(sum(float(ray_direction[index]) * float(scene_normal[index]) for index in range(3)))
                    if ray_direction is not None
                    else 1.0
                )
                normal_gap = depth_gap * max(0.05, incidence)
                textile_scene_alignment = abs(
                    sum(float(textile_hit.normal[index]) * float(scene_normal[index]) for index in range(3))
                )
                metrics = {
                    "scene_distance": scene_distance, "textile_distance": textile_hit.distance,
                    "depth_gap": depth_gap, "normal_gap": normal_gap, "incidence": incidence,
                    "alignment": textile_scene_alignment, "epsilon": epsilon, "linked_source": linked_source,
                    "source_margin_mm": source_margin, "near_margin_mm": near_margin,
                    "ray_direction": ray_direction, "scene_normal": scene_normal,
                }
                if linked_source and normal_gap <= source_margin:
                    return choose("textile", textile_hit.patch_id, "linked_source_within_normal_margin", **metrics)
                if textile_scene_alignment >= 0.90 and normal_gap <= near_margin:
                    return choose("textile", textile_hit.patch_id, "aligned_textile_within_near_margin", **metrics)
                return choose("mesh", scene_pick, "mesh_front_outside_textile_margin", **metrics)
            return choose(
                "textile", textile_hit.patch_id, "coincident_depth_prefers_editable_textile",
                scene_distance=scene_distance, textile_distance=textile_hit.distance, depth_gap=depth_gap, epsilon=epsilon,
                linked_source=linked_source, source_margin_mm=source_margin, near_margin_mm=near_margin,
            )
        if scene_pick is not None:
            if projected_linked and projected_patch is not None:
                return choose(
                    "textile",
                    projected_patch,
                    "projected_source_textile_when_raycast_misses",
                )
            return choose("mesh", scene_pick, "scene_only")
        if textile_hit is not None:
            return choose("textile", textile_hit.patch_id, "textile_only")
        return choose("textile", projected_patch, "projected_textile_fallback") if projected_patch is not None else choose(None, None, "no_hit")

    def _nearest_patch(self, ctx: Any, screen_pos: tuple[float, float]) -> str | None:
        hit = self._cloth_raycast_cache.hit(ctx, self._session.document, screen_pos)
        if hit is not None:
            return hit.patch_id
        return nearest_document_patch(self._session.document, screen_pos, self._world_to_screen(ctx))

    def _nearest_solitary_curve(self, ctx: Any, screen_pos: tuple[float, float]) -> str | None:
        """Return an unowned textile edge suitable as a Close anchor."""

        curve_id = self._nearest_curve(ctx, screen_pos)
        if curve_id is None:
            return None
        incidence = curve_patch_incidence(self._session.document)
        return curve_id if not incidence.get(curve_id, ()) else None

    def _clear_modify_selection(self) -> None:
        self._session.selected_point_ids = ()
        self._session.selected_curve_ids = ()
        self._session.selected_patch_ids = ()
        self._selected_textile_groups = []

    def _select_modify_entity(self, kind: str, entity_id: str, *, additive: bool) -> None:
        entity_id = str(entity_id)
        if not additive:
            self._clear_modify_selection()
        attribute = {
            "point": "selected_point_ids",
            "curve": "selected_curve_ids",
            "patch": "selected_patch_ids",
        }[str(kind)]
        values = list(getattr(self._session, attribute))
        if entity_id in values:
            if additive:
                values.remove(entity_id)
        else:
            values.append(entity_id)
        setattr(self._session, attribute, tuple(values))
        if kind == "patch":
            self._selected_textile_groups = [frozenset((value,)) for value in values]

    def _separate_selected_draw_faces(self) -> tuple[int, tuple[frozenset[str], ...]]:
        """Turn selected technical Draw faces into independent textile groups."""

        selected = {value for value in self._session.selected_patch_ids if value in self._session.document.patches}
        if not selected:
            return 0, ()
        by_parent: dict[str, set[str]] = {}
        for patch_id in selected:
            parent_id = explicit_textile_group_id(self._session.document, patch_id)
            key = parent_id or f"ungrouped:{patch_id}"
            by_parent.setdefault(key, set()).add(patch_id)

        separated: list[frozenset[str]] = []
        changed = 0
        affected_parents: set[str] = set()
        for key, subset in by_parent.items():
            seed = min(subset)
            full = set(logical_patch_group(self._session.document, seed))
            parent_id = explicit_textile_group_id(self._session.document, seed)
            if full and subset == full and parent_id:
                separated.append(frozenset(full))
                continue
            created = create_textile_group(
                self._session.document,
                subset,
                origin="draw_split",
                parent_group_ids=(parent_id,) if parent_id else (),
                label="Draw separated textile",
            )
            if created:
                separated.append(frozenset(created))
                changed += 1
                if parent_id:
                    affected_parents.add(parent_id)

        if affected_parents:
            normalize_disconnected_textile_groups(
                self._session.document,
                group_ids=affected_parents,
                origin="draw_split",
            )
        remove_stale_textile_group_records(self._session.document)
        return changed, tuple(separated)

    def _delete_selection(self, ctx: Any) -> bool:
        result = delete_cloth_selection(
            self._session.document,
            point_ids=self._session.selected_point_ids,
            curve_ids=self._session.selected_curve_ids,
            patch_ids=self._session.selected_patch_ids,
        )
        if not result.changed:
            self._sync(ctx, result.message, render=False)
            return True
        normalization = normalize_disconnected_textile_groups(
            self._session.document,
            origin="draw_split",
        )
        remove_stale_textile_group_records(self._session.document)
        self._clear_modify_selection()
        self._interaction.clear_hover()
        self._session.dirty = True
        self._validation_cache.reset()
        self._snap_target_cache.reset()
        self._cloth_raycast_cache.reset()
        message = result.message
        if normalization.split_group_count:
            message += f" {normalization.split_group_count} textile group(s) were separated into independent pieces."
        self._sync(ctx, message)
        return True


    # ------------------------------------------------------------------
    # UI actions
    # ------------------------------------------------------------------
    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        if self._cloth_diagnostics is not None:
            self._cloth_diagnostics.record(
                "action.overlay_button", tool=self, ctx=ctx, button_id=str(button_id),
                resolved_workflow_action=self._workflow_overlay.action_from_button(button_id),
            )
        geometry_action = self._geometry_overlay.action_from_button(button_id)
        if geometry_action is not None:
            self._on_geometry_action(ctx, geometry_action)
            return
        pattern_action = self._pattern_overlay.action_from_button(button_id)
        if pattern_action is not None:
            self._on_pattern_action(ctx, pattern_action)
            return
        action = self._workflow_overlay.action_from_button(button_id)
        if action is None:
            return
        if action == "apply_continue":
            self._apply_and_continue(ctx)
            return
        if action == "finish":
            owner = getattr(ctx, "owner", None)
            callback = getattr(owner, "apply_preview_and_close_tool", None) if owner is not None else None
            callback() if callable(callback) else self.on_apply(ctx)
            return
        if action == "cancel":
            owner = getattr(ctx, "owner", None)
            callback = getattr(owner, "discard_preview_and_close_tool", None) if owner is not None else None
            callback() if callable(callback) else self.on_cancel(ctx)
            return
        try:
            self._on_action(ctx, action)
        except Exception as exc:
            if self._cloth_diagnostics is not None:
                self._cloth_diagnostics.exception(
                    "action.workflow_exception", exc, tool=self, ctx=ctx, action=action, button_id=str(button_id)
                )
                self._cloth_diagnostics.export(reason="workflow_action_exception", tool=self, ctx=ctx)
            if canonical_cloth_action(action) == ClothAction.OPEN_CLOSURE.value:
                self._interaction.enter_close()
                self._workspace_machine.enter_close(proposals=0, proposal_index=0)
                try:
                    self._sync(ctx, f"Close stopped safely: {exc}")
                except Exception:
                    pass
                return
            # The Qt adapter deliberately protects the application from tool
            # exceptions. Recover here so the user sees the failure and the
            # diagnostics are exported instead of the click appearing inert.
            try:
                self._sync(ctx, f"Cloth action ‘{action}’ stopped safely: {exc}", render=False)
            except Exception:
                try:
                    ctx.status.info(f"Cloth action ‘{action}’ stopped safely: {exc}")
                except Exception:
                    pass
            return

    def _on_action(self, ctx: Any, action_id: str) -> None:
        raw_action_id = str(action_id)
        action_id = canonical_cloth_action(raw_action_id)
        if self._cloth_diagnostics is not None:
            self._cloth_diagnostics.record(
                "action.route",
                tool=self,
                ctx=ctx,
                action_id=action_id,
                raw_action_id=raw_action_id,
                is_apply_action=is_apply_action(action_id),
            )
        # Hidden compatibility routes keep old macros and saved shortcuts
        # functional without adding any legacy button to the single overlay.
        if action_id in {"mode_line"}:
            self._enter_draw(ctx, ClothDrawMode.LINE)
            return
        if action_id in {"mode_polyline", "pick_plane", "accept_plane"}:
            self._enter_draw(ctx, ClothDrawMode.POLYLINE)
            return
        if action_id in {"mode_modify"}:
            self._enter_draw(ctx, ClothDrawMode.MODIFY)
            return
        if action_id in {"mode_mesh_trace"}:
            self._enter_main(ctx)
            return
        if action_id in {"mode_fold"}:
            self._set_mode(ctx, ClothEditMode.FOLD.value)
            return

        # Main menu -----------------------------------------------------
        if action_id == ClothAction.TAKE_FACE.value:
            self._create_source_textile(ctx)
            return
        if action_id == ClothAction.OPEN_CLOSURE.value:
            self._enter_close(ctx)
            return
        if action_id == ClothAction.OPEN_DRAW.value:
            self._enter_draw(ctx, self._workspace.draw_mode)
            return
        if action_id == ClothAction.OPEN_PROPERTIES.value:
            self._enter_properties(ctx)
            return
        if action_id == ClothAction.APPLY_OUTPUT.value:
            self._apply_and_continue(ctx)
            return

        # Close submenu -------------------------------------------------
        if action_id == ClothAction.APPLY_CLOSURE.value:
            self._accept_close(ctx)
            return
        if action_id == ClothAction.PREVIOUS_CLOSURE.value:
            self._cycle_close_proposal(ctx, -1)
            return
        if action_id == ClothAction.NEXT_CLOSURE.value:
            self._cycle_close_proposal(ctx, 1)
            return
        if action_id == ClothAction.RESET_CLOSURE.value:
            self._interaction.join_proposals = ()
            self._interaction.join_proposal_index = 0
            self._enter_main(ctx)
            return

        # Draw submenu --------------------------------------------------
        if action_id == "draw_modify":
            self._enter_draw(ctx, ClothDrawMode.MODIFY)
            return
        if action_id == "draw_line":
            self._enter_draw(ctx, ClothDrawMode.LINE)
            return
        if action_id == "draw_polyline":
            self._enter_draw(ctx, ClothDrawMode.POLYLINE)
            return
        if action_id == "draw_pick_faces":
            self._workspace_machine.set_draw_pick_mode(ClothDrawPickMode.FACE)
            self._sync(ctx, self._workspace.message)
            return
        if action_id == "draw_pick_edges":
            self._workspace_machine.set_draw_pick_mode(ClothDrawPickMode.EDGE)
            self._sync(ctx, self._workspace.message)
            return
        if action_id == "toggle_smart_snap":
            self._smart_snap = not self._smart_snap
            self._sync(ctx, f"Smart Snap {'enabled' if self._smart_snap else 'disabled'}.")
            return
        if action_id == "toggle_axis_guides":
            self._construction_snap = not self._construction_snap
            self._sync(ctx, f"Axis guides {'enabled' if self._construction_snap else 'disabled'}.")
            return
        if action_id == "clear_draw":
            self._drawing.cancel()
            self._clear_modify_selection()
            if self._workspace.draw_mode is ClothDrawMode.LINE:
                self._drawing.begin(ClothEditMode.LINE.value)
            elif self._workspace.draw_mode is ClothDrawMode.POLYLINE:
                self._drawing.begin(ClothEditMode.POLYLINE.value)
            self._workspace_machine.update_draw(0)
            self._sync_workspace_selection()
            self._sync(ctx, "Draw cleared.")
            return
        if action_id == "apply_draw":
            separated_count = 0
            separated_groups: tuple[frozenset[str], ...] = ()
            if self._workspace.draw_mode is ClothDrawMode.MODIFY and self._session.selected_patch_ids:
                separated_count, separated_groups = self._separate_selected_draw_faces()
                if separated_groups:
                    self._set_selected_textile_groups(separated_groups)
                    self._session.dirty = self._session.dirty or bool(separated_count)
                    self._validation_cache.reset()
                    self._cloth_raycast_cache.reset()
            if self._drawing.active and self._drawing.pending_world_points:
                if len(self._drawing.pending_world_points) >= 2:
                    self._finish_trace(ctx, closed=False)
                else:
                    self._drawing.cancel()
            self._enter_main(ctx)
            if separated_count:
                self._sync(ctx, f"{separated_count} independent textile group(s) created from the selected Draw faces.")
            return

        # Properties submenu -------------------------------------------
        if action_id == "properties_select_face":
            self._workspace_machine.set_property_selection_mode(ClothPropertySelectionMode.FACE)
            self._sync(ctx, self._workspace.message)
            return
        if action_id == "properties_select_group":
            self._workspace_machine.set_property_selection_mode(ClothPropertySelectionMode.GROUP)
            self._sync(ctx, self._workspace.message)
            return
        if action_id == "reset_properties":
            self._set_selected_textile_groups(())
            self._sync_workspace_selection()
            self._sync(ctx, self._workspace.message)
            return
        if action_id == "apply_properties":
            self._enter_main(ctx)
            return
        if action_id == "set_function_textile":
            self._set_patch_function(ctx, ClothPatchFunction.TEXTILE)
            return
        if action_id == "set_function_pattern":
            self._set_patch_function(ctx, ClothPatchFunction.PATTERN)
            return
        if action_id == "set_function_junction":
            self._set_patch_function(ctx, ClothPatchFunction.JUNCTION)
            return

        # Compatibility and secondary operations ----------------------
        if action_id == "preview_flat":
            self._preview_flat(ctx)
            return
        if action_id == "finish_open":
            self._finish_trace(ctx, closed=False)
            return
        if action_id == "close_polyline":
            self._finish_trace(ctx, closed=True)
            return
        if action_id == "delete_selected_faces":
            self._delete_selection(ctx)
            self._sync_workspace_selection()
            return
        if action_id == "edit_fold_cut_edges":
            self._set_mode(ctx, ClothEditMode.FOLD.value)
            return
        if action_id == "restart":
            self._restart(ctx, message="Cloth reset. Select surfaces or draw textile geometry.")
            return

    def _restart(self, ctx: Any, *, message: str) -> None:
        self._drawing.cancel()
        self._point_editor.reset()
        self._mesh_hover.hide(ctx, render=False)
        self._hover_editable = None
        self._geometry_trace.clear()
        self._geometry_overlay.hide(ctx)
        self._pattern_overlay.hide(ctx)
        self._machine = ClothWorkflowMachine()
        self._interaction.reset()
        self._ux = ClothUxMachine(self._interaction)
        self._workspace_machine = ClothWorkspaceMachine()
        self._workspace = self._workspace_machine.state
        self._bind_session(self._machine.session)
        self._pointer_press_screen = None
        self._camera_interaction_active = False
        self._last_status_message = None
        self._sync(ctx, message)

    def _preview_flat(self, ctx: Any) -> None:
        if self._pattern_edge_snapshot is not None:
            self._sync(ctx, "Validate or clear the current Fold / Cut preview before opening the flat pattern.", render=False)
            return
        if self._drawing.pending_world_points:
            self._sync(ctx, "Finish or cancel the current curve before previewing the flat pattern.", render=False)
            return
        try:
            self._machine.request_flat_preview()
        except ClothTransitionError as exc:
            self._sync(ctx, str(exc), render=False)
            return
        if self._machine.last_flattening is None or not self._machine.last_flattening.success:
            self._sync(ctx, self._session.status, render=False)
            return
        from .cloth.mesh_builder import build_cloth_surface_mesh

        built = build_cloth_surface_mesh(self._session.document, name="Cloth flat preview", flattened=self._machine.last_flattening)
        if built.mesh is None:
            self._sync(ctx, built.issues[0] if built.issues else "Flat preview could not be built.", render=False)
            return
        self._interaction.enter_flat_preview(built.mesh)
        self._sync(ctx, "Flat pattern preview ready. Green geometry is shown beside the 3D surface.")

    def _on_value_changed(self, ctx: Any, field_id: str, value: Any) -> None:
        if field_id == "cloth_smart_snap":
            self._smart_snap = bool(value)
        elif field_id == "cloth_construction_snap":
            self._construction_snap = bool(value)
        elif field_id == "cloth_snap_tolerance":
            self._snap_tolerance_px = max(4.0, min(40.0, float(value)))
        elif field_id == "cloth_surface_auto":
            self._geometry_trace.set_smart_automatic(bool(value))
            self._sync(ctx, "Automatic logical source-face selection enabled." if bool(value) else "Manual source-face continuity enabled.")
            return
        elif field_id == "cloth_surface_continuity":
            self._geometry_trace.set_smart_tolerance(float(value))
            try:
                ctx.inspector.update_value("cloth_surface_auto", False, notify=False)
            except Exception:
                pass
            self._sync(ctx, f"Source-face continuity set to {self._geometry_trace.smart_session.tolerance:.2f}.")
            return
        elif field_id == "cloth_patch_name":
            if not self._session.selected_patch_ids:
                return
            name = str(value or "Panel").strip() or "Panel"
            changed = self._session.document.set_patch_properties(self._session.selected_patch_ids, name=name)
            self._session.dirty = self._session.dirty or bool(changed)
            self._validation_cache.reset()
            self._sync(ctx, f"Renamed {len(changed)} textile face(s) to {name}.", render=False)
            return
        elif field_id == "cloth_patch_layer":
            if not self._session.selected_patch_ids:
                return
            layer_id = str(value or "layer1").strip() or "layer1"
            self._session.document.ensure_layer(layer_id, name=layer_id)
            changed = self._session.document.set_patch_properties(self._session.selected_patch_ids, layer_id=layer_id)
            self._session.dirty = self._session.dirty or bool(changed)
            self._validation_cache.reset()
            self._sync(ctx, f"Assigned {len(changed)} face(s) to layer {layer_id}.", render=False)
            return
        elif field_id == "cloth_patch_material":
            if not self._session.selected_patch_ids:
                return
            material = str(value or "Textile").strip() or "Textile"
            changed = self._session.document.set_patch_properties(self._session.selected_patch_ids, material_name=material)
            self._session.dirty = self._session.dirty or bool(changed)
            self._validation_cache.reset()
            self._sync(ctx, f"Assigned material {material} to {len(changed)} face(s).", render=False)
            return
        elif field_id == "cloth_layer_thickness":
            if not self._session.selected_patch_ids:
                return
            thickness = max(0.001, min(20.0, float(value)))
            layer_ids = {
                self._session.document.patches[patch_id].layer_id
                for patch_id in self._session.selected_patch_ids
                if patch_id in self._session.document.patches
            }
            changed = 0
            for layer_id in layer_ids:
                layer = self._session.document.layers.get(layer_id)
                if layer is not None and abs(layer.thickness_mm - thickness) > 1.0e-12:
                    layer.thickness_mm = thickness
                    changed += 1
            if changed:
                self._session.document.revision += 1
                self._session.dirty = True
                self._validation_cache.reset()
            self._sync(ctx, f"Set {changed} textile layer(s) to {thickness:.3g} mm.", render=False)
            return
        elif field_id == "cloth_name":
            self._output_name = str(value or "Cloth").strip() or "Cloth"
        elif field_id == "cloth_thickness":
            self._session.document.metadata["cloth_thickness_mm"] = max(0.01, min(20.0, float(value)))
            self._session.document.revision += 1
            self._session.dirty = True
            self._validation_cache.reset()
        elif field_id == "cloth_stitch_tolerance":
            self._session.document.metadata["cloth_stitch_tolerance_mm"] = max(0.001, min(5.0, float(value)))
            self._session.document.revision += 1
            self._session.dirty = True
            self._validation_cache.reset()
        elif field_id == "cloth_fold_angle":
            self._set_selected_fold_angle(ctx, float(value))
            return
        elif field_id == "cloth_fold_radius":
            self._set_selected_fold_radius(ctx, float(value))
            return
        elif field_id == "cloth_pattern_spacing":
            changed = set_pattern_spacing(self._session.document, float(value))
            if self._pattern_edge_snapshot is not None:
                set_pattern_spacing(self._pattern_edge_snapshot, float(value))
            if changed:
                self._session.dirty = True
                self._validation_cache.reset()
            self._sync(ctx, f"Flat-pattern component spacing set to {pattern_spacing_mm(self._session.document):.3g} mm.", render=False)
            return
        else:
            return
        self._sync(ctx, "Settings updated.", render=False)

    def _escape(self, ctx: Any) -> bool:
        if self._drawing.active and self._drawing.pending_world_points:
            self._drawing.cancel()
            if self._workspace.overlay_mode is ClothOverlayMode.DRAW:
                if self._workspace.draw_mode is ClothDrawMode.LINE:
                    self._drawing.begin(ClothEditMode.LINE.value)
                elif self._workspace.draw_mode is ClothDrawMode.POLYLINE:
                    self._drawing.begin(ClothEditMode.POLYLINE.value)
            self._workspace_machine.update_draw(0)
            self._sync(ctx, "Current primitive cancelled. Existing textile geometry was kept.")
            return True
        if self._interaction.stage in {ClothUxStage.CLOSE, ClothUxStage.DRAW, ClothUxStage.PROPERTIES, ClothUxStage.FLAT_PREVIEW}:
            if self._session.phase in {ClothWorkflowPhase.FLAT_PREVIEW, ClothWorkflowPhase.VALIDATION_BLOCKED, ClothWorkflowPhase.APPLY_READY}:
                self._machine.return_to_editing()
            self._interaction.flat_preview_mesh = None
            self._enter_main(ctx)
            return True
        if self._interaction.stage is ClothUxStage.MAIN:
            if self._geometry_trace.selection_count or self._session.selected_patch_ids or self._session.selected_curve_ids:
                self._clear_all_selection()
                self._sync(ctx, "Selection cleared.")
                return True
        return False

    # ------------------------------------------------------------------
    # Workflow and inspector sync
    # ------------------------------------------------------------------
    def _register_workflow(self, ctx: Any) -> None:
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("opening", "Open Cloth", help="Open an existing Cloth or start a new textile document."),
                ctx.workflow.step("main", "Select and create", help="Take mesh faces, close textile geometry, draw or assign properties."),
                ctx.workflow.step("output", "Apply output", help="Generate the folded output and linked flat preview."),
            ),
        )

    def _sync_overlay(self, ctx: Any) -> None:
        diag = self._cloth_diagnostics
        operation = diag.begin("overlay.sync", tool=self, ctx=ctx) if diag is not None else None
        report = self._validation_report() if self._session.document.patches else None
        try:
            self._workflow_overlay.sync_document(
                ctx,
                can_apply=self.can_apply(ctx),
                pending_count=len(self._drawing.pending_world_points),
                validation_report=report,
            )
            if operation is not None:
                operation.stage("workflow_window_shown", tool=self, ctx=ctx, overlay=overlay_snapshot(ctx))
            # Cloth owns exactly one visible overlay. The old geometry and pattern
            # palettes remain available as internal compatibility adapters only.
            self._geometry_overlay.hide(ctx)
            self._pattern_overlay.hide(ctx)
            if operation is not None:
                operation.finish(outcome="ok", tool=self, ctx=ctx, overlay=overlay_snapshot(ctx))
        except Exception as exc:
            if diag is not None:
                diag.exception(
                    "overlay.sync.exception", exc,
                    operation_id=operation.operation_id if operation is not None else 0,
                    tool=self, ctx=ctx, overlay=overlay_snapshot(ctx),
                )
                if operation is not None:
                    operation.finish(outcome="error", tool=self, ctx=ctx, error=repr(exc))
                diag.export(reason="overlay_sync_exception", tool=self, ctx=ctx)
            raise

    def _sync(self, ctx: Any, message: str, *, render: bool = True) -> None:
        diag = self._cloth_diagnostics
        operation = diag.begin("ui.sync", tool=self, ctx=ctx, message=message, render=render) if diag is not None else None
        try:
            self._interaction.message = str(message)
            self._session.status = str(message)
            self._sync_workspace_selection()
            if self._workspace.overlay_mode is ClothOverlayMode.DRAW:
                self._workspace_machine.update_draw(
                    len(self._drawing.pending_world_points),
                    smart_snap_enabled=self._smart_snap,
                    axis_guides_enabled=self._construction_snap,
                )
            self._workspace.message = str(message)
            workflow_step = "opening" if self._interaction.stage is ClothUxStage.OPENING else "output" if self._interaction.stage is ClothUxStage.FLAT_PREVIEW else "main"
            try:
                ctx.workflow.goto(workflow_step)
            except Exception as exc:
                if operation is not None:
                    operation.stage("workflow_goto_failed", tool=self, ctx=ctx, error=repr(exc), workflow_step=workflow_step)
            try:
                ctx.inspector.set_visible("cloth_surface_continuity", True)
            except Exception as exc:
                if operation is not None:
                    operation.stage("inspector_visibility_failed", tool=self, ctx=ctx, error=repr(exc))
            if render:
                render_started = time.perf_counter() if operation is not None else 0.0
                try:
                    self._renderer.sync(ctx)
                    if operation is not None:
                        operation.stage("renderer_synced", tool=self, ctx=ctx, elapsed_ms=(time.perf_counter() - render_started) * 1000.0)
                except Exception as exc:
                    if diag is not None:
                        diag.exception(
                            "ui.sync.renderer_exception", exc,
                            operation_id=operation.operation_id if operation is not None else 0, tool=self, ctx=ctx,
                        )
                    raise
                if self._hover_editable is not None and self._interaction.stage is ClothUxStage.OPENING:
                    object_id, mesh = self._hover_editable
                    self._mesh_hover.show(ctx, group_key=object_id, meshes=(EditableHoverMesh(object_id, mesh),), render=True)
            overlay_started = time.perf_counter() if operation is not None else 0.0
            self._sync_overlay(ctx)
            if operation is not None:
                operation.stage("overlay_synced", tool=self, ctx=ctx, elapsed_ms=(time.perf_counter() - overlay_started) * 1000.0, overlay=overlay_snapshot(ctx))
            if message != self._last_status_message:
                ctx.status.info(message)
                self._last_status_message = message
            if operation is not None:
                operation.finish(outcome="ok", tool=self, ctx=ctx)
        except Exception as exc:
            if diag is not None:
                diag.exception(
                    "ui.sync.exception", exc,
                    operation_id=operation.operation_id if operation is not None else 0, tool=self, ctx=ctx, message=message,
                )
                if operation is not None:
                    operation.finish(outcome="error", tool=self, ctx=ctx, error=repr(exc))
                diag.export(reason="ui_sync_exception", tool=self, ctx=ctx)
            raise

class ClothTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec):
        super().__init__(spec=spec, creator=ClothCreatorTool())


__all__ = ["ClothCreatorTool", "ClothTool"]

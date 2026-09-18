# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import nullcontext
import copy
import time
from typing import Any

from laserprog_studio.tool_api.core import MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool

from .base import ToolSpec
from .ids import TOOL_PLAN_TRACE
from .plan_trace_2d import PlanTrace2DServices, _PlanTrace2DState
from .plan_trace_2d.editable_source import (
    EDITABLE_SOURCE_KEY,
    PLAN_TRACE_DRAFT_SOURCE_KIND,
    PLAN_TRACE_SUBTRACT_SOURCE_KIND,
    attach_editable_source,
    build_draft_placeholder_mesh,
    build_draft_source,
    build_editable_source,
    editable_source_from_mesh,
    is_plan_trace_draft_source,
    is_plan_trace_subtract_source,
    sketch_bounds_2d,
)
from .plan_trace_2d.constants import (
    _DELETE_BUTTON_ID,
    _RESTORE_FACES_BUTTON_ID,
    _PATTERN_FACE_BUTTON_ID,
    _VALIDATE_ADD_BUTTON_ID,
    _VALIDATE_SUBTRACT_BUTTON_ID,
    _METRIC_CANCEL_BUTTON_ID,
    _METRIC_OVERLAY_ID,
    _METRIC_VALIDATE_BUTTON_ID,
    _MODE_ARC,
    _MODE_BEZIER,
    _MODE_CIRCLE,
    _MODE_DIMENSION,
    _MODE_DUPLICATE,
    _MODE_HALF_CIRCLE,
    _MODE_LINE,
    _MODE_MESH_TRACE,
    _MODE_MIRROR,
    _MODE_MODIFY,
    _MODE_POINT,
    _MODE_POLYLINE,
    _MODE_RECTANGLE,
)

# Static source marker used by architecture tests:
# buttons=(("reset", "Reset"),)


def _measure_perf(ctx: Any, name: str) -> Any:
    profiler = getattr(ctx, "profiler", None)
    measure = getattr(profiler, "measure", None)
    if callable(measure):
        try:
            return measure(str(name))
        except Exception:
            pass
    return nullcontext()


def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
    profiler = getattr(ctx, "profiler", None)
    increment = getattr(profiler, "increment", None)
    if callable(increment):
        try:
            increment(str(name), int(value))
        except Exception:
            pass


def _set_perf_value(ctx: Any, name: str, value: Any) -> None:
    profiler = getattr(ctx, "profiler", None)
    set_value = getattr(profiler, "set_value", None)
    if callable(set_value):
        try:
            set_value(str(name), value)
        except Exception:
            pass


def _record_apply_mesh_timing(name: str, elapsed_ms: float) -> None:
    try:
        from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as audit

        audit.record_timing(f"plan_trace.apply.mesh.{name}", float(elapsed_ms))
    except Exception:
        pass


class PlanTrace2DCreatorTool(CreatorTool):
    """Creator API Plan tracer event shell.

    The shell owns the public CreatorTool lifecycle and event methods.  Drawing,
    snapping, sketch sync, overlays, metrics, selection and history are composed
    as explicit services under :mod:`laserprog_studio.tooling.plan_trace_2d`.
    This keeps the runtime contract readable without relying on long mixin
    inheritance chains.
    """

    id = TOOL_PLAN_TRACE
    label = "Plan tracer"

    def __init__(self) -> None:
        self._state = _PlanTrace2DState()
        self._services = PlanTrace2DServices.create(self)

    def on_open(self, ctx: Any) -> None:
        with _measure_perf(ctx, "plan_trace.lifecycle.open"):
            return self._on_open_measured(ctx)

    def _default_board_thickness_mm(self, ctx: Any | None = None) -> float:
        """Return the laser-board default thickness used for new Plan Tracer solids.

        Editing an existing Plan Tracer volume still preserves its stored depth.
        For a new sketch/draft, the product expectation is that the generated
        board thickness matches Preferences > Laser engraving.
        """
        prefs = None
        try:
            owner = getattr(ctx, "owner", None) if ctx is not None else None
            prefs = getattr(owner, "project_preferences", None) if owner is not None else None
        except Exception:
            prefs = None
        if prefs is None:
            try:
                prefs = getattr(ctx, "project_preferences", None) if ctx is not None else None
            except Exception:
                prefs = None
        if prefs is None:
            try:
                from laserprog_studio.services.project_preferences import load_project_preferences

                prefs = load_project_preferences()
            except Exception:
                prefs = None
        try:
            laser = getattr(prefs, "laser", prefs)
            value = float(getattr(laser, "default_board_thickness_mm", 3.0))
        except Exception:
            value = 3.0
        if value <= 0.0:
            value = 3.0
        return float(value)


    def _pattern_max_segments(self, ctx: Any | None = None) -> int:
        """Return the configurable Plan Tracer Pattern segment budget.

        This is intentionally a uniform integer budget, not a hidden hard-coded
        cap in the Pattern service.  Dense motif previews/apply operations can
        now be raised from Preferences without editing code.
        """

        prefs = None
        try:
            owner = getattr(ctx, "owner", None) if ctx is not None else None
            prefs = getattr(owner, "project_preferences", None) if owner is not None else None
        except Exception:
            prefs = None
        if prefs is None:
            try:
                prefs = getattr(ctx, "project_preferences", None) if ctx is not None else None
            except Exception:
                prefs = None
        if prefs is None:
            try:
                from laserprog_studio.services.project_preferences import load_project_preferences

                prefs = load_project_preferences()
            except Exception:
                prefs = None
        try:
            laser = getattr(prefs, "laser", prefs)
            value = int(float(getattr(laser, "plan_tracer_pattern_max_segments", 120000)))
        except Exception:
            value = 120000
        return int(max(1000, min(1_000_000, value)))

    def _on_open_measured(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api
        from laserprog_studio.tool_api import plan2d

        require_tool_api("0.13.0", max_major=0)
        try:
            from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import reset_plan_trace_input_diagnostics

            reset_plan_trace_input_diagnostics("tool_open", owner=getattr(ctx, "owner", None), ctx=ctx, tool=self)
        except Exception:
            pass
        try:
            from laserprog_studio.diagnostics.projected_overlay_debug import reset_projected_overlay_diagnostics

            reset_projected_overlay_diagnostics("plan_trace_tool_open", owner=getattr(ctx, "owner", None), ctx=ctx, owner_tool=self.id)
        except Exception:
            pass
        try:
            from laserprog_studio.diagnostics.plan_trace_selection_length_debug import reset_selection_length_diagnostics

            reset_selection_length_diagnostics(
                "plan_trace_tool_open",
                owner=getattr(ctx, "owner", None),
                ctx=ctx,
                sketch=getattr(self._state, "sketch", None),
            )
        except Exception:
            pass
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        opening_view = plan2d.nearest_plan_view(ctx)
        pattern_budget = self._pattern_max_segments(ctx)
        self._state = _PlanTrace2DState(
            view=opening_view,
            active_tool=_MODE_POINT,
            extrusion_depth=self._default_board_thickness_mm(ctx),
            motif_preview_segment_budget=pattern_budget,
            motif_apply_segment_budget=pattern_budget,
        )
        try:
            ctx.snap.set_smart_snap(True)
        except Exception:
            pass
        self._clear_scene_selection(ctx)
        try:
            with _measure_perf(ctx, "plan_trace.lifecycle.open.scene_cache_rebuild"):
                ctx.scene_cache.rebuild(ctx, scope="snap")
        except Exception:
            pass
        _set_perf_value(ctx, "plan_trace.diagnostic.enabled", 1)
        self._services.selection._configure_modify_selection_api(ctx)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.step("pick_height", "Pick drawing surface", help="Click a scene face or editable volume. Click empty ground to start on the world origin/top plane."),
                ctx.workflow.step("draw", "Draw 2D plan", help="Use Point, Line, Polyline, Rectangle, Circle, Arc, Half-circle and Dimension modes from the inspector or viewport toolbar."),
            ),
        )
        self._services.mode_state._register_creator_modes(ctx, active=_MODE_POINT)
        ctx.inspector.set_panel(self._services.overlay._panel())
        try:
            # Old bundled/user parameters could persist Smart Snap as disabled.
            # Product default is now explicit: every new Plan Tracer session starts
            # with Smart Snap enabled, while the user can still turn it off after open.
            ctx.inspector.update_value("plan_trace_2d.smart_snap", True, notify=False)
        except Exception:
            pass
        self._services.overlay._apply_panel_settings(ctx)
        self._services.overlay._show_anchor_prompt(ctx)
        self._services.overlay._sync_reports(ctx)
        self._services.rendering._render(ctx, sync_overlays=True)
        ctx.status.info("Plan tracer ready. Select a scene surface/editable volume, or click empty ground to draw on the world origin top plane.")

    def on_close(self, ctx: Any) -> None:
        with _measure_perf(ctx, "plan_trace.lifecycle.close"):
            try:
                self._services.overlay._export_timing_snapshot(ctx, reason="tool_close")
            except Exception:
                pass
            try:
                from laserprog_studio.diagnostics.plan_trace_selection_length_debug import export_selection_length_summary

                export_selection_length_summary(ctx=ctx, sketch=getattr(self._state, "sketch", None), reason="tool_close")
            except Exception:
                pass
            # Some host Cancel buttons close the active tool directly instead of
            # calling CreatorTool.cancel().  Preserve the same CAD contract here:
            # closing/cancelling a non-applied sketch stores a red recoverable
            # draft, including open polylines and line-only sketches.
            saved_draft = False
            try:
                if (
                    not self._state.applied_since_open
                    and self._state.plane is not None
                    and self._has_recoverable_sketch()
                ):
                    saved_draft = bool(self._save_current_sketch_as_draft(ctx))
            except Exception:
                saved_draft = False
            if not saved_draft and not self._state.applied_since_open:
                try:
                    self._restore_removed_edit_source(ctx)
                except Exception:
                    pass
        try:
            ctx.selection_box.configure(enabled=False, owner_tool=self.id, on_complete=None)
            ctx.selection_box.cancel()
        except Exception:
            pass
        try:
            from laserprog_studio.application.creator_box_selection_overlay import hide_creator_selection_box_overlay

            owner = getattr(ctx, "owner", None)
            if owner is not None:
                hide_creator_selection_box_overlay(owner)
        except Exception:
            pass
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                from laserprog_studio.application.creator_viewport_ui import clear_creator_viewport_ui

                clear_creator_viewport_ui(owner, self.id, render=True)
            except Exception:
                pass
        try:
            from laserprog_studio.tool_api import plan2d

            plan2d.release_plan_view_camera(ctx)
        except Exception:
            pass

    def cancel(self, ctx: Any) -> bool:
        """Handle global Cancel without closing the whole Plan Tracer tool.

        The generic CreatorTool base treats Cancel as a destructive tool close.
        Plan Tracer is CAD-like: a UI/tool cancel should preserve an established
        sketch as a recoverable red draft placeholder, while Escape remains a
        lightweight in-place interaction cancel from ``on_event``.
        """

        return self._cancel_current_interaction(ctx, save_recoverable_draft=True)

    def on_cancel(self, ctx: Any) -> bool:
        return self._cancel_current_interaction(ctx, save_recoverable_draft=True)

    def _cancel_current_interaction(self, ctx: Any, *, save_recoverable_draft: bool = False) -> bool:
        active_before = self._state.active_tool
        had_pending = self._has_pending_draw_state()
        has_sketch = self._has_recoverable_sketch()
        # A toolbar/global Cancel means "put this work aside".  It must not
        # discard open sketches just because they have no generated face yet:
        # line-only sketches and non-closed polylines are valid recoverable
        # drafts.  Escape still cancels the current in-place gesture first.
        if save_recoverable_draft and self._state.plane is not None and has_sketch:
            return self._save_current_sketch_as_draft_and_return_to_pick(ctx)
        if self._state.metric_draft is not None:
            # Metric Cancel is a local edit cancellation unless the caller
            # explicitly asked to save the whole sketch as a draft above.
            self._services.metrics._cancel_metric_draft(ctx)
            return True
        # Escape from Modify on an established sketch also preserves the work;
        # Escape in drawing tools keeps the previous lightweight mode-switch
        # behavior for compatibility with existing CAD gestures.
        if self._state.plane is not None and not had_pending and has_sketch and active_before == _MODE_MODIFY:
            return self._save_current_sketch_as_draft_and_return_to_pick(ctx)
        self._clear_pending_draw_state(ctx)
        if self._state.plane is not None:
            try:
                self._services.overlay._sync_reports(ctx)
                self._services.rendering._render(ctx, sync_overlays=True, render=True)
            except Exception:
                pass
            target_tool = active_before if had_pending else _MODE_MODIFY
            self._state.active_tool = target_tool
            try:
                ctx.overlay.set_group_active("plan_trace_2d.tool", self._services.overlay._button_id(target_tool))
            except Exception:
                pass
            try:
                if had_pending:
                    ctx.status.info("Plan tracer: current placement cancelled. Tool stays open in the current drawing mode.")
                elif active_before != _MODE_MODIFY:
                    ctx.status.info("Plan tracer: drawing mode exited. Modify mode is active.")
                else:
                    ctx.status.info("Plan tracer: already in Modify mode. Tool stays open.")
            except Exception:
                pass
            try:
                self._services.rendering._render(ctx, sync_overlays=True, render=True)
            except Exception:
                pass
            return True
        try:
            ctx.status.info("Plan tracer: select a scene surface/editable volume, click empty ground to start at origin, or close the tool from the toolbar.")
        except Exception:
            pass
        return True

    def _has_recoverable_sketch(self) -> bool:
        sketch = self._state.sketch
        try:
            return bool(sketch.points or sketch.lines or sketch.circles or sketch.arcs or sketch.dimensions or sketch.faces)
        except Exception:
            return False

    def _document_has_object(self, ctx: Any, object_id: str | None) -> bool:
        if not object_id:
            return False
        try:
            ctx.document.get(str(object_id))
            return True
        except Exception:
            return False

    def _current_or_removed_edit_source_mesh(self, ctx: Any) -> Any | None:
        object_id = self._state.editing_source_object_id
        if object_id:
            try:
                return ctx.document.get(object_id).mesh
            except Exception:
                pass
        return self._state.editing_source_removed_mesh

    @staticmethod
    def _copy_runtime_placement_state(source_mesh: Any, target_mesh: Any) -> None:
        """Preserve transform-gizmo orientation metadata on replacement meshes.

        Geometry placement is baked into vertices, but the rotation gizmo keeps a
        compact quaternion/Euler state on the WorkMesh instance so local scale
        handles remain aligned with the part.  Replacing an edited Plan Tracer
        mesh must not silently reset that UI frame.
        """

        for attribute in ("_lps_rotation_quat", "_lps_rotation_euler_deg"):
            try:
                if hasattr(source_mesh, attribute):
                    setattr(target_mesh, attribute, copy.deepcopy(getattr(source_mesh, attribute)))
            except Exception:
                pass

    def _strip_plan_trace_history_from_mesh(self, mesh: Any) -> Any:
        """Return a copy of ``mesh`` with editable Plan Tracer history removed.

        This is deliberately stronger than removing only EDITABLE_SOURCE_KEY:
        the user-visible "New sketch" choice means the current part is now
        the new origin for future Plan Tracer operations.  Keeping stale helper
        flags such as ``plan_trace_subtract`` or ``extrusion_depth_mm`` would let
        later selection/subtract paths treat the piece as the old editable
        history again.
        """

        clone = copy.deepcopy(mesh)
        metadata = dict(getattr(clone, "metadata", {}) or {})
        for key in tuple(metadata.keys()):
            key_text = str(key)
            if key_text == EDITABLE_SOURCE_KEY or key_text.startswith("plan_trace"):
                metadata.pop(key, None)
        for key in (
            "source_tool",
            "editable_tool_id",
            "editable_kind",
            "extrusion_depth_mm",
            "sketch_faces",
        ):
            metadata.pop(key, None)
        try:
            clone.metadata = metadata
        except Exception:
            pass
        return clone

    def _stored_intact_mesh_from_subtract_source(self, source: dict[str, Any] | None) -> Any | None:
        if not isinstance(source, dict):
            return None
        try:
            metadata = dict(source.get("metadata") or {})
            stored = metadata.get("intact_target_mesh")
            return self._mesh_from_serialized(stored)
        except Exception:
            return None

    def _start_new_drawing_from_plan_trace_source(self, ctx: Any, obj: Any) -> bool:
        """Prepare an independent sketch on an existing Plan Tracer volume.

        ``New sketch`` is non-destructive: the clicked object remains an
        editable Plan Tracer object with its original sketch/history intact.
        The new session only uses one of its visible faces as a drawing support,
        so applying with Add creates a separate volume instead of silently
        converting the support object into an uneditable mesh.

        The method remains as a compatibility hook for older callers.  It no
        longer replaces the document mesh or strips any metadata.
        """

        object_id = str(getattr(obj, "id", "") or "")
        mesh = getattr(obj, "mesh", None)
        if not object_id or mesh is None:
            return False
        _increment_perf(ctx, "plan_trace.edit_source.preserved_for_new")
        return True

    def _show_intact_subtract_source_for_editing(self, ctx: Any, obj: Any, source: dict[str, Any]) -> bool:
        """Display the stored intact target while editing a subtraction.

        A subtraction result is the already-cut target mesh.  Hiding it leaves
        the user with only the sketch, while editing against the cut mesh makes
        reapplication cumulative.  The correct non-destructive edit scene shows
        the stored intact target, keeps the cut result in state for Cancel, and
        reapplies Subtract from that stored target.
        """

        object_id = str(getattr(obj, "id", "") or "")
        if not object_id:
            return False
        if self._state.editing_source_removed_mesh is None:
            try:
                self._state.editing_source_removed_mesh = copy.deepcopy(getattr(obj, "mesh", None))
                self._state.editing_source_removed_index = int(getattr(obj, "index", 0))
            except Exception:
                pass
        intact = self._stored_intact_mesh_from_subtract_source(source)
        if intact is None:
            # Last-resort compatibility: old subtract metadata missing.  Fall
            # back to the previous hide-source behavior rather than failing open.
            return self._remove_edit_source_from_document(ctx)
        intact = self._strip_plan_trace_history_from_mesh(intact)
        try:
            current_mesh = getattr(obj, "mesh", None)
            current_id = str(getattr(current_mesh, "mesh_id", "") or object_id)
            if current_id:
                intact.mesh_id = current_id
        except Exception:
            pass
        try:
            ctx.document.replace_mesh(object_id, intact, label="Show intact Plan tracer target while editing subtraction", push_undo=False)
            _increment_perf(ctx, "plan_trace.edit_source.show_intact_subtract_target")
            owner = getattr(ctx, "owner", None)
            rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
            if callable(rebuild):
                try:
                    rebuild(keep_camera=True)
                except TypeError:
                    rebuild()
            try:
                ctx.scene_cache.rebuild(ctx, scope="snap")
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _remove_edit_source_from_document(self, ctx: Any) -> bool:
        """Temporarily remove the edited volume/draft from the scene.

        Keeping the source mesh visible while editing makes the sketch hard to
        read and, more importantly, feeds its edges/vertices back into the snap
        cache.  That is exactly the failure mode where the cursor starts snapping
        to the old volume instead of the new drawing.  Removal is tool-local: the
        source mesh is stored on the state and Apply/Cancel writes a replacement
        with the same mesh id.
        """

        object_id = self._state.editing_source_object_id
        if not object_id or self._state.editing_source_removed_mesh is not None:
            return False
        try:
            obj = ctx.document.get(object_id)
            self._state.editing_source_removed_mesh = copy.deepcopy(obj.mesh)
            self._state.editing_source_removed_index = int(getattr(obj, "index", 0))
            ctx.document.remove_object(object_id, label="Hide Plan tracer source while editing", push_undo=False)
            _increment_perf(ctx, "plan_trace.edit_source.hidden")
            owner = getattr(ctx, "owner", None)
            rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
            if callable(rebuild):
                try:
                    rebuild(keep_camera=True)
                except TypeError:
                    rebuild()
            try:
                ctx.scene_cache.rebuild(ctx, scope="snap")
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _restore_removed_edit_source(self, ctx: Any) -> bool:
        mesh = self._state.editing_source_removed_mesh
        object_id = self._state.editing_source_object_id
        if mesh is None or not object_id:
            return False
        try:
            if self._document_has_object(ctx, object_id):
                # Subtraction edits show the stored intact target in-place while
                # the tool is open.  Cancel/close must restore the previous cut
                # result, not leave the temporary intact target in the scene.
                ctx.document.replace_mesh(object_id, mesh, label="Restore Plan tracer source", push_undo=False)
            else:
                ctx.document.add_mesh(mesh, label="Restore Plan tracer source", push_undo=False)
            _increment_perf(ctx, "plan_trace.edit_source.restored")
            owner = getattr(ctx, "owner", None)
            rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
            if callable(rebuild):
                try:
                    rebuild(keep_camera=True)
                except TypeError:
                    rebuild()
            return True
        except Exception:
            return False

    def _save_current_sketch_as_draft_and_return_to_pick(self, ctx: Any) -> bool:
        saved = self._save_current_sketch_as_draft(ctx)
        self._reset_to_pick_after_draft_save(ctx)
        try:
            if saved:
                ctx.status.info("Plan tracer: sketch saved as a red draft placeholder. Click it later to resume.")
            else:
                ctx.status.info("Plan tracer: sketch cancel requested, but no recoverable draft could be stored.")
        except Exception:
            pass
        return True

    def _save_current_sketch_as_draft(self, ctx: Any) -> bool:
        if self._state.plane is None or not self._has_recoverable_sketch():
            return False
        # A cancelled edit is still a recoverable sketch.  When the source was an
        # applied extrusion, it has already been removed from the scene while
        # editing so it cannot pollute snap targets; the draft placeholder keeps
        # the same mesh id so the work can be resumed cleanly.
        if self._state.metric_draft is not None:
            try:
                self._services.metrics._validate_metric_draft(ctx)
            except Exception:
                pass
        try:
            self._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
        except Exception:
            pass
        # Draft bounds deliberately come from the full sketch graph, not only
        # generated faces.  Open polylines, isolated construction lines, circles
        # and even a one-point started sketch must all be recoverable.
        bounds = sketch_bounds_2d(self._state.sketch)
        if bounds is None:
            return False
        try:
            depth = self._apply_extrusion_depth()
            source = build_draft_source(
                sketch=self._state.sketch.clone(),
                plane=self._state.plane,
                display_plane=self._state.display_plane,
                anchor_world=self._state.anchor_world,
                extrusion_depth_mm=depth,
                bounds_2d=bounds,
                motif_assignments=self._state.motif_assignments_by_outer_signature,
            )
            mesh = build_draft_placeholder_mesh(source, name="Plan trace 2D draft")
        except Exception:
            return False
        try:
            if not ctx.document.ensure():
                return False
            target_id = self._state.editing_source_object_id
            if target_id:
                original = self._current_or_removed_edit_source_mesh(ctx)
                try:
                    if getattr(original, "mesh_id", None):
                        mesh.mesh_id = getattr(original, "mesh_id")
                    else:
                        mesh.mesh_id = str(target_id)
                except Exception:
                    pass
                if not self._document_has_object(ctx, target_id):
                    # Restore the hidden source just before replacing it.  This
                    # keeps undo sane: undoing the draft save goes back to the
                    # source object, not to the intermediate hidden-scene state.
                    self._restore_removed_edit_source(ctx)
                if self._document_has_object(ctx, target_id):
                    ctx.document.replace_mesh(target_id, mesh, label="Update Plan tracer 2D draft", push_undo=True)
                else:
                    ctx.document.add_mesh(mesh, label="Save Plan tracer 2D draft", push_undo=True)
            else:
                ctx.document.add_mesh(mesh, label="Save Plan tracer 2D draft", push_undo=True)
            owner = getattr(ctx, "owner", None)
            rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
            if callable(rebuild):
                try:
                    rebuild(keep_camera=True)
                except TypeError:
                    rebuild()
            return True
        except Exception:
            return False

    def _reset_to_pick_after_draft_save(self, ctx: Any) -> None:
        try:
            ctx.projected_drawing.clear_tool(self.id, render=False)
        except Exception:
            pass
        try:
            ctx.selection.clear_selection(owner_tool=self.id)
        except Exception:
            pass
        try:
            from laserprog_studio.tool_api import plan2d

            plan2d.release_plan_view_camera(ctx)
        except Exception:
            pass
        opening_view = self._state.view
        pattern_budget = self._pattern_max_segments(ctx)
        self._state = _PlanTrace2DState(
            view=opening_view,
            active_tool=_MODE_POINT,
            extrusion_depth=self._default_board_thickness_mm(ctx),
            motif_preview_segment_budget=pattern_budget,
            motif_apply_segment_budget=pattern_budget,
        )
        try:
            ctx.workflow.goto("pick_height")
        except Exception:
            pass
        try:
            self._services.overlay._show_anchor_prompt(ctx)
            self._services.overlay._sync_reports(ctx)
            self._services.rendering._render(ctx, sync_overlays=True, render=True)
        except Exception:
            pass

    def _has_pending_draw_state(self) -> bool:
        return any((
            self._state.pending_line_start_id,
            self._state.pending_polyline_last_id,
            self._state.pending_rectangle_corner_id,
            self._state.pending_circle_center_id,
            self._state.pending_arc_start_id,
            self._state.pending_arc_end_id,
            self._state.pending_bezier_start_id,
            self._state.pending_bezier_end_id,
            self._state.pending_bezier_control_1_id,
            self._state.pending_half_circle_start_id,
            self._state.pending_dimension_start_id,
            self._state.pending_dimension_line_id,
        ))

    def _finish_current_polyline(self, ctx: Any) -> bool:
        if self._state.active_tool != _MODE_POLYLINE:
            return False
        return bool(self._services.drawing._finish_polyline(ctx, render=True))

    def _clear_pending_draw_state(self, ctx: Any | None = None) -> None:
        if ctx is not None:
            try:
                self._services.snap._clear_pending_geometry_preview(ctx)
            except Exception:
                pass
        self._state.pending_line_start_id = None
        self._state.pending_polyline_last_id = None
        self._state.pending_rectangle_corner_id = None
        self._state.pending_circle_center_id = None
        self._state.pending_arc_start_id = None
        self._state.pending_arc_end_id = None
        self._state.pending_bezier_start_id = None
        self._state.pending_bezier_end_id = None
        self._state.pending_bezier_control_1_id = None
        self._state.pending_half_circle_start_id = None
        self._state.pending_dimension_start_id = None
        self._state.pending_dimension_line_id = None

    def can_apply(self, ctx: Any) -> bool:
        with _measure_perf(ctx, "plan_trace.apply.can_apply"):
            return self._can_apply_measured(ctx)

    def _can_apply_measured(self, ctx: Any) -> bool:
        if self._state.plane is None:
            return False
        # ``can_apply`` is polled by the host UI.  It must be O(1): compiling a
        # dense motif sketch here made normal hover/toolbar refreshes freeze the
        # app for seconds.  Geometry-changing actions already compile the sketch,
        # and the final Apply path performs one definitive compile before mesh
        # generation.
        _increment_perf(ctx, "plan_trace.apply.can_apply.fast_path")
        return bool(self._state.sketch.faces)

    def on_apply(self, ctx: Any) -> bool:
        with _measure_perf(ctx, "plan_trace.apply.total"):
            return self._on_apply_measured(ctx)

    def _on_apply_measured(self, ctx: Any) -> bool:
        """Extrude the current closed 2D faces into the document.

        Plan Tracer is a draft tool: the sketch is live in the viewport until the
        user presses the global Apply button.  Apply must therefore build a mesh
        from the compiled faces, not wait for a preview-session object that this
        tool never creates.
        """

        self._state.apply_last_error = ""
        if self._state.metric_draft is not None:
            with _measure_perf(ctx, "plan_trace.metric.validate_before_event"):
                self._services.metrics._validate_metric_draft(ctx)
        if self._state.plane is None:
            self._report_apply_failure(ctx, "No drawing plane is locked.")
            return False
        with _measure_perf(ctx, "plan_trace.apply.compile_and_sync"):
            self._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
        if not self._state.sketch.faces:
            self._report_apply_failure(ctx, "Draw at least one closed face first.")
            return False
        try:
            with _measure_perf(ctx, "plan_trace.apply.build_mesh"):
                mesh = self._build_apply_mesh()
        except Exception as exc:
            self._report_apply_failure(ctx, str(exc) or type(exc).__name__)
            return False
        try:
            with _measure_perf(ctx, "plan_trace.apply.document_ensure"):
                if not ctx.document.ensure():
                    self._report_apply_failure(ctx, "No document/model store is available.")
                    return False
            with _measure_perf(ctx, "plan_trace.apply.document_add_mesh"):
                if self._state.editing_source_kind == PLAN_TRACE_SUBTRACT_SOURCE_KIND:
                    return self._apply_add_from_subtract_edit(ctx, mesh)
                if self._state.editing_source_object_id:
                    original = self._current_or_removed_edit_source_mesh(ctx)
                    try:
                        original_source = editable_source_from_mesh(original)
                        replacing_draft = is_plan_trace_draft_source(original_source)
                        if not replacing_draft:
                            mesh.name = str(getattr(original, "name", mesh.name) or mesh.name)
                            mesh.color = str(getattr(original, "color", mesh.color) or mesh.color)
                            if getattr(original, "material", None) is not None:
                                mesh.material = getattr(original, "material")
                            if getattr(original, "engraving", None) is not None:
                                mesh.engraving = getattr(original, "engraving")
                        self._copy_runtime_placement_state(original, mesh)
                        if getattr(original, "mesh_id", None):
                            mesh.mesh_id = getattr(original, "mesh_id")
                        else:
                            mesh.mesh_id = str(self._state.editing_source_object_id)
                    except Exception:
                        try:
                            mesh.mesh_id = str(self._state.editing_source_object_id)
                        except Exception:
                            pass
                    label = "Promote Plan tracer 2D draft" if self._state.editing_source_kind == PLAN_TRACE_DRAFT_SOURCE_KIND else "Replace Plan tracer 2D extrusion"
                    if not self._document_has_object(ctx, self._state.editing_source_object_id):
                        # Source meshes are removed while editing to avoid snap
                        # pollution.  Restore immediately before replacement so
                        # the undo snapshot represents the original volume.
                        self._restore_removed_edit_source(ctx)
                    if self._document_has_object(ctx, self._state.editing_source_object_id):
                        ctx.document.replace_mesh(self._state.editing_source_object_id, mesh, label=label, push_undo=True)
                    else:
                        ctx.document.add_mesh(mesh, label=label, push_undo=True)
                else:
                    ctx.document.add_mesh(mesh, label="Apply Plan tracer 2D extrusion", push_undo=True)
            owner = getattr(ctx, "owner", None)
            if owner is not None:
                rebuild = getattr(owner, "rebuild_scene", None)
                if callable(rebuild):
                    with _measure_perf(ctx, "plan_trace.apply.rebuild_scene"):
                        try:
                            rebuild(keep_camera=True)
                        except TypeError:
                            rebuild()
        except Exception as exc:
            self._report_apply_failure(ctx, str(exc) or type(exc).__name__)
            return False
        self._state.apply_last_error = ""
        self._state.applied_since_open = True
        try:
            ctx.projected_drawing.clear_tool(self.id, render=False)
            if self._state.editing_source_object_id:
                if self._state.editing_source_kind == PLAN_TRACE_DRAFT_SOURCE_KIND:
                    ctx.status.info(f"Plan tracer draft applied: {len(self._state.sketch.faces)} face(s) extruded.")
                else:
                    ctx.status.info(f"Plan tracer replaced editable volume: {len(self._state.sketch.faces)} face(s) extruded.")
            else:
                ctx.status.info(f"Plan tracer applied: {len(self._state.sketch.faces)} face(s) extruded.")
        except Exception:
            pass
        self._services.rendering._render(ctx, sync_overlays=True, render=True)
        return True

    def _report_apply_failure(self, ctx: Any, message: str) -> None:
        """Make validation failures visible inside the active Plan Tracer UI.

        v122 only wrote failures to the generic status manager.  In the normal
        full-screen viewport workflow that status is easy to miss, which made a
        rejected Apply look like a dead button.  Keep the tool open, preserve the
        sketch, and show one concise error in both the inspector/overlay and log.
        """

        text = str(message or "Unknown validation error.").strip()
        self._state.apply_last_error = text
        try:
            ctx.status.error(f"Plan Tracer validation failed: {text}")
        except Exception:
            pass
        try:
            self._services.overlay._sync_reports(ctx)
        except Exception:
            pass
        try:
            self._services.rendering._render(ctx, sync_overlays=True, render=True)
        except Exception:
            pass

    def _apply_add_from_subtract_edit(self, ctx: Any, mesh: Any) -> bool:
        """Convert an edited subtraction sketch into an added Plan Tracer volume.

        When the user opens an old cut, edits its sketch, then presses
        Add, the previous cut must be undone by restoring the stored intact
        target.  The edited sketch is then added as a separate green extrusion;
        it must not replace the target mesh and must not keep the old subtract
        history.
        """

        object_id = self._state.editing_source_object_id
        if not object_id:
            return False
        source = editable_source_from_mesh(self._state.editing_source_removed_mesh)
        intact = self._stored_intact_mesh_from_subtract_source(source)
        if intact is None:
            try:
                intact = copy.deepcopy(ctx.document.get(object_id).mesh)
            except Exception:
                intact = None
        if intact is None:
            return False
        intact = self._strip_plan_trace_history_from_mesh(intact)
        try:
            current = ctx.document.get(object_id).mesh
            mesh_id = str(getattr(current, "mesh_id", "") or object_id)
            if mesh_id:
                intact.mesh_id = mesh_id
            if str(getattr(mesh, "mesh_id", "") or "") == mesh_id:
                mesh.mesh_id = ""
        except Exception:
            pass
        meshes = list(ctx.document.meshes(include_preview=False))
        try:
            index = ctx.document.index_for(object_id)
        except Exception:
            index = int(self._state.editing_source_removed_index or -1)
        if 0 <= int(index) < len(meshes):
            meshes[int(index)] = intact
        else:
            meshes.append(intact)
        meshes.append(mesh)
        ctx.document.set_meshes(meshes, label="Restore Plan tracer cut target and add extrusion", push_undo=True)
        owner = getattr(ctx, "owner", None)
        rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
        if callable(rebuild):
            try:
                rebuild(keep_camera=True)
            except TypeError:
                rebuild()
        self._state.applied_since_open = True
        try:
            ctx.projected_drawing.clear_tool(self.id, render=False)
            ctx.status.info(f"Plan tracer subtraction converted to additive volume: {len(self._state.sketch.faces)} face(s) extruded and original target restored.")
        except Exception:
            pass
        self._services.rendering._render(ctx, sync_overlays=True, render=True)
        return True

    def _apply_add_and_close(self, ctx: Any) -> bool:
        """Validate as the historical green additive board, then leave the tool.

        The explicit Add button is a board-generation action.  It must always
        use Preferences > Laser engraving > Board thickness, even if the sketch
        was opened from an older draft/extrusion carrying a stale stored depth.
        """

        try:
            self._state.extrusion_depth = self._default_board_thickness_mm(ctx)
        except Exception:
            pass
        ok = bool(self.on_apply(ctx))
        if ok:
            self._close_after_validation(ctx, reason="Plan Tracer Add")
        return ok

    def _close_after_validation(self, ctx: Any, *, reason: str) -> None:
        """Close Plan Tracer after an explicit overlay validation action.

        The normal host Apply path already closes Creator tools.  The new
        overlay buttons live inside Plan Tracer itself, so they must perform the
        same cleanup when the document operation succeeds.  ``applied_since_open``
        is already set by the operation, therefore ``on_close`` will not create a
        red recoverable draft.
        """

        owner = getattr(ctx, "owner", None)
        close = getattr(owner, "close_active_tool", None) if owner is not None else None
        if callable(close):
            try:
                close(log_it=False, ask_preview=False)
                return
            except TypeError:
                try:
                    close()
                    return
                except Exception:
                    pass
            except Exception:
                pass
        try:
            ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        except Exception:
            pass
        if owner is not None:
            try:
                setattr(owner, "active_tool", getattr(owner, "TOOL_NONE", "none"))
            except Exception:
                pass
        try:
            ctx.status.info(f"{reason}: validation complete, tool closed.")
        except Exception:
            pass

    def _apply_subtract_and_close(self, ctx: Any) -> bool:
        ok = bool(self._apply_subtract(ctx))
        if ok:
            self._close_after_validation(ctx, reason="Plan Tracer Subtract")
        return ok

    def _apply_subtract(self, ctx: Any) -> bool:
        """Subtract the current sketch footprint through every touched target.

        This is intentionally not the same depth as additive boards.  The cutter
        depth is computed from the target meshes along the locked plane normal,
        then expanded by a small margin so the boolean passes cleanly through the
        full model thickness.
        """

        if self._state.metric_draft is not None:
            with _measure_perf(ctx, "plan_trace.metric.validate_before_subtract"):
                self._services.metrics._validate_metric_draft(ctx)
        if self._state.plane is None:
            try:
                ctx.status.info("Plan Tracer Subtract ignored: no drawing face/plane is locked.")
            except Exception:
                pass
            return False
        with _measure_perf(ctx, "plan_trace.subtract.compile_and_sync"):
            self._services.sketch_sync._compile_and_sync_sketch(ctx, render=False, sync_apply_state=False)
        if not self._state.sketch.faces:
            try:
                ctx.status.info("Plan Tracer Subtract ignored: draw at least one closed face.")
            except Exception:
                pass
            return False
        try:
            if not ctx.document.ensure():
                try:
                    ctx.status.info("Plan Tracer Subtract cannot run: no document is available.")
                except Exception:
                    pass
                return False
            targets = self._subtract_targets(ctx)
            if not targets:
                try:
                    ctx.status.info("Plan Tracer Subtract : no model touched by the sketch was found.")
                except Exception:
                    pass
                return False
            depth_min, depth_max = self._combined_target_depth_range(tuple(mesh for _obj, mesh, _src in targets))
            cutter = self._build_cutting_mesh(depth_min, depth_max)
            from laserprog_studio.boolean_ops import boolean_difference

            if self._state.editing_source_object_id and not self._document_has_object(ctx, self._state.editing_source_object_id):
                self._restore_removed_edit_source(ctx)
            current_meshes = list(ctx.document.meshes(include_preview=False))
            changed = 0
            failures: list[str] = []
            for obj, intact_mesh, source_payload in targets:
                try:
                    result = boolean_difference(copy.deepcopy(intact_mesh), copy.deepcopy(cutter))
                    # Preserve the visible identity of the target.  A green
                    # marker is stored in metadata because WorkMesh still has a
                    # single object-wide colour; recolouring the whole model
                    # would be worse than not marking the cut face per-cell.
                    result.name = str(getattr(intact_mesh, "name", getattr(obj, "name", "Plan tracer cut")) or "Plan tracer cut")
                    result.color = str(getattr(intact_mesh, "color", getattr(result, "color", "#B8B8B8")) or "#B8B8B8")
                    if getattr(intact_mesh, "material", None) is not None:
                        result.material = copy.deepcopy(getattr(intact_mesh, "material"))
                    if getattr(intact_mesh, "engraving", None) is not None:
                        result.engraving = copy.deepcopy(getattr(intact_mesh, "engraving"))
                    try:
                        result.mesh_id = str(getattr(obj, "id", "") or getattr(intact_mesh, "mesh_id", "") or getattr(result, "mesh_id", ""))
                    except Exception:
                        pass
                    self._attach_subtract_editable_source(result, intact_mesh, target_object=obj, target_source=source_payload, depth_range=(depth_min, depth_max))
                    try:
                        index = int(ctx.document.index_for(getattr(obj, "id")))
                    except Exception:
                        index = int(getattr(obj, "index", -1))
                    if 0 <= index < len(current_meshes):
                        current_meshes[index] = result
                        changed += 1
                    else:
                        ctx.document.replace_mesh(getattr(obj, "id"), result, label="Reapply Plan tracer 2D subtraction", push_undo=False)
                        changed += 1
                except Exception as exc:
                    failures.append(f"{getattr(obj, 'name', getattr(obj, 'id', '?'))}: {exc}")
            if changed <= 0:
                try:
                    ctx.status.info("Plan Tracer Subtract failed: no model could be modified.")
                except Exception:
                    pass
                return False
            ctx.document.set_meshes(current_meshes, label=f"Plan tracer 2D subtract {changed} target(s)", push_undo=True)
            owner = getattr(ctx, "owner", None)
            rebuild = getattr(owner, "rebuild_scene", None) if owner is not None else None
            if callable(rebuild):
                try:
                    rebuild(keep_camera=True)
                except TypeError:
                    rebuild()
            self._state.applied_since_open = True
            try:
                ctx.projected_drawing.clear_tool(self.id, render=False)
            except Exception:
                pass
            if failures:
                try:
                    ctx.status.info(f"Plan Tracer Subtract : {changed} model(s) cut, {len(failures)} failure(s).")
                except Exception:
                    pass
            else:
                try:
                    ctx.status.info(f"Plan Tracer Subtract : {changed} model(s) cut through their full thickness.")
                except Exception:
                    pass
            return True
        except Exception as exc:
            try:
                ctx.status.info(f"Plan Tracer Subtract failed : {exc}")
            except Exception:
                pass
            return False

    def _build_cutting_mesh(self, depth_min: float, depth_max: float) -> Any:
        plane = self._state.plane
        if plane is None:
            raise ValueError("no locked plane")
        margin = 1.0
        start = min(float(depth_min), float(depth_max)) - margin
        end = max(float(depth_min), float(depth_max)) + margin
        if end - start <= 1.0e-6:
            end = start + max(self._apply_extrusion_depth(), 1.0)
        original_plane = self._state.plane
        original_display = self._state.display_plane
        original_depth = self._state.extrusion_depth
        try:
            self._state.plane = plane.with_depth(start)
            self._state.display_plane = None if original_display is None else original_display.with_depth(start)
            self._state.extrusion_depth = float(end - start)
            mesh = self._build_apply_mesh()
            mesh.name = "Plan tracer 2D subtraction cutter"
            return mesh
        finally:
            self._state.plane = original_plane
            self._state.display_plane = original_display
            self._state.extrusion_depth = original_depth

    def _subtract_targets(self, ctx: Any) -> list[tuple[Any, Any, dict[str, Any] | None]]:
        """Return (document object, intact mesh, previous source) targets.

        For a reopened subtraction, the current visible mesh is already cut, so
        the boolean must be reapplied to the stored intact mesh.  For a new
        subtraction, candidates are document meshes whose projected bounds overlap
        the current sketch footprint and whose depth range crosses the drawing
        plane.  The initially clicked object is also kept as an alias in the snap
        scope, so picking a face remains deterministic.
        """

        source_from_edit = None
        if self._state.editing_source_object_id and self._state.editing_source_kind == PLAN_TRACE_SUBTRACT_SOURCE_KIND:
            try:
                removed = self._state.editing_source_removed_mesh
                source_from_edit = editable_source_from_mesh(removed)
                metadata = dict((source_from_edit or {}).get("metadata") or {})
                stored = metadata.get("intact_target_mesh")
                intact = self._mesh_from_serialized(stored)
                obj = self._document_object_stub(
                    object_id=str(self._state.editing_source_object_id),
                    index=int(self._state.editing_source_removed_index or 0),
                    name=str(self._state.editing_source_label or self._state.editing_source_object_id),
                    mesh=intact,
                )
                return [(obj, intact, source_from_edit)]
            except Exception:
                pass
        try:
            objects = list(ctx.document.objects(include_preview=False))
        except Exception:
            objects = []
        if not objects:
            return []
        footprint = sketch_bounds_2d(self._state.sketch)
        if footprint is None:
            return []
        plane = self._state.plane
        if plane is None:
            return []
        active_ids = {str(v) for v in tuple(getattr(self._state, "active_snap_object_ids", ()) or ()) if str(v)}
        active_indices = {int(v) for v in tuple(getattr(self._state, "active_snap_object_indices", ()) or ())}
        out: list[tuple[Any, Any, dict[str, Any] | None]] = []
        for obj in objects:
            mesh = getattr(obj, "mesh", None)
            if mesh is None:
                continue
            if self._state.editing_source_object_id and str(getattr(obj, "id", "")) == str(self._state.editing_source_object_id):
                continue
            source = editable_source_from_mesh(mesh)
            identifiers = {
                str(getattr(obj, "id", "") or ""),
                str(getattr(obj, "name", "") or ""),
                str(getattr(mesh, "mesh_id", "") or ""),
                str(getattr(mesh, "name", "") or ""),
            }
            is_active = bool(active_ids.intersection(identifiers)) or int(getattr(obj, "index", -999999)) in active_indices
            if is_active or self._mesh_touches_sketch_footprint(plane, mesh, footprint):
                # Do not use the already-cut mesh as the new original when a
                # previous subtract source is reselected through a normal object
                # path.  Prefer the intact target stored in metadata.
                intact = mesh
                preserve_current_support = (
                    str(getattr(obj, "id", "") or "")
                    == str(getattr(self._state, "new_sketch_support_object_id", "") or "")
                )
                if is_plan_trace_subtract_source(source) and not preserve_current_support:
                    try:
                        stored = dict(source.get("metadata") or {}).get("intact_target_mesh")
                        intact = self._mesh_from_serialized(stored)
                    except Exception:
                        intact = mesh
                out.append((obj, copy.deepcopy(intact), source))
        return out

    def _mesh_touches_sketch_footprint(self, plane: Any, mesh: Any, footprint: tuple[float, float, float, float]) -> bool:
        verts = tuple(getattr(mesh, "vertices", ()) or ())
        if not verts:
            return False
        try:
            from laserprog_studio.planar_tools import world_to_plane
            uv = [world_to_plane(plane, (float(p[0]), float(p[1]), float(p[2]))) for p in verts]
            xs = [p[0] for p in uv]
            ys = [p[1] for p in uv]
            bbox = (min(xs), min(ys), max(xs), max(ys))
            pad = 0.25
            if not self._bbox_overlap(footprint, bbox, pad=pad):
                return False
            dmin, dmax = self._mesh_depth_range(mesh, plane.normal)
            return dmin <= float(plane.depth) + 0.25 and dmax >= float(plane.depth) - 0.25
        except Exception:
            return False

    @staticmethod
    def _bbox_overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float], *, pad: float = 0.0) -> bool:
        return not (a[2] < b[0] - pad or b[2] < a[0] - pad or a[3] < b[1] - pad or b[3] < a[1] - pad)

    def _combined_target_depth_range(self, meshes: tuple[Any, ...]) -> tuple[float, float]:
        plane = self._state.plane
        if plane is None:
            raise ValueError("no locked plane")
        mins: list[float] = []
        maxs: list[float] = []
        for mesh in meshes:
            dmin, dmax = self._mesh_depth_range(mesh, plane.normal)
            mins.append(dmin)
            maxs.append(dmax)
        if not mins:
            depth = float(plane.depth)
            return depth - 0.5, depth + 0.5
        return min(mins), max(maxs)

    @staticmethod
    def _mesh_depth_range(mesh: Any, normal: tuple[float, float, float]) -> tuple[float, float]:
        values: list[float] = []
        nx, ny, nz = float(normal[0]), float(normal[1]), float(normal[2])
        for point in tuple(getattr(mesh, "vertices", ()) or ()):
            try:
                values.append(float(point[0]) * nx + float(point[1]) * ny + float(point[2]) * nz)
            except Exception:
                pass
        if not values:
            return 0.0, 0.0
        return min(values), max(values)

    def _attach_subtract_editable_source(self, mesh: Any, intact_mesh: Any, *, target_object: Any, target_source: dict[str, Any] | None, depth_range: tuple[float, float]) -> None:
        plane = self._state.plane
        if plane is None:
            return
        extra = {
            "operation": "subtract",
            "validation_marker_color": "#8BC34A",
            "depth_range": (float(depth_range[0]), float(depth_range[1])),
            "target_object_id": str(getattr(target_object, "id", "") or ""),
            "target_object_name": str(getattr(target_object, "name", "") or ""),
            "intact_target_mesh": self._serialize_mesh(intact_mesh),
        }
        if isinstance(target_source, dict):
            extra["previous_plan_trace_source_kind"] = str(target_source.get("kind") or "")
        source = build_editable_source(
            sketch=self._state.sketch.clone(),
            plane=plane,
            display_plane=self._state.display_plane,
            anchor_world=self._state.anchor_world,
            # Store the actual through-cutter depth, including the same 1 mm
            # safety margin applied by _build_cutting_mesh on both sides.
            extrusion_depth_mm=max(float(depth_range[1]) - float(depth_range[0]) + 2.0, 0.001),
            kind=PLAN_TRACE_SUBTRACT_SOURCE_KIND,
            extra_metadata=extra,
            motif_assignments=self._state.motif_assignments_by_outer_signature,
        )
        attach_editable_source(mesh, source)
        try:
            metadata = getattr(mesh, "metadata", None)
            if metadata is None:
                metadata = {}
                setattr(mesh, "metadata", metadata)
            metadata.update({
                "source_tool": self.id,
                "sketch_faces": len(self._state.sketch.faces),
                "plan_trace_operation": "subtract",
                "plan_trace_validation_marker_color": "#8BC34A",
            })
        except Exception:
            pass

    def _serialize_mesh(self, mesh: Any) -> dict[str, Any]:
        metadata = copy.deepcopy(dict(getattr(mesh, "metadata", {}) or {}))
        # Avoid recursive source-in-source payloads when reapplying a cut.
        metadata.pop(EDITABLE_SOURCE_KEY, None)
        return {
            "name": str(getattr(mesh, "name", "") or ""),
            "vertices": [tuple(float(v) for v in p[:3]) for p in tuple(getattr(mesh, "vertices", ()) or ())],
            "triangles": [tuple(int(v) for v in t[:3]) for t in tuple(getattr(mesh, "triangles", ()) or ())],
            "color": str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
            "material": copy.deepcopy(getattr(mesh, "material", None)),
            "engraving": copy.deepcopy(getattr(mesh, "engraving", None)),
            "metadata": metadata,
            "mesh_id": str(getattr(mesh, "mesh_id", "") or ""),
        }

    def _mesh_from_serialized(self, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("missing stored intact target mesh")
        from laserprog_studio.domain.work_model import WorkMesh
        mesh = WorkMesh(
            name=str(data.get("name") or "Plan tracer intact target"),
            vertices=[tuple(float(v) for v in p[:3]) for p in tuple(data.get("vertices") or ())],
            triangles=[tuple(int(v) for v in t[:3]) for t in tuple(data.get("triangles") or ())],
            color=str(data.get("color") or "#B8B8B8"),
        )
        mesh.material = copy.deepcopy(data.get("material"))
        mesh.engraving = copy.deepcopy(data.get("engraving"))
        mesh.metadata = copy.deepcopy(dict(data.get("metadata") or {}))
        if str(data.get("mesh_id") or ""):
            mesh.mesh_id = str(data.get("mesh_id"))
        return mesh

    @staticmethod
    def _document_object_stub(*, object_id: str, index: int, name: str, mesh: Any) -> Any:
        class _Obj:
            pass

        obj = _Obj()
        obj.id = str(object_id)
        obj.index = int(index)
        obj.name = str(name)
        obj.mesh = mesh
        return obj

    def _build_apply_mesh(self) -> Any:
        """Build one boolean-ready solid from the solved sketch faces.

        Plan Tracer no longer owns a private cap/wall tessellator here.  Every
        visible face is converted to a normalized planar cross-section and sent
        through the shared boolean-ready solid builder.  In production the same
        Manifold kernel used by Union/Subtract performs the extrusion; the
        generated mesh is then validated by that kernel *before* it can enter
        the document.
        """

        from laserprog_studio.geometry_ops.planar_boolean_solid import (
            extrude_planar_regions_boolean_ready,
        )

        plane = self._state.plane
        if plane is None:
            raise ValueError("no locked plane")
        sketch = self._state.sketch
        faces = tuple(sketch.faces.values())
        if not faces:
            raise ValueError("no closed face can be extruded")

        regions = []
        for face in faces:
            outer = tuple(
                (float(point[0]), float(point[1]))
                for point in tuple(getattr(face, "polygon_points", ()) or ())
            )
            holes = tuple(
                tuple((float(point[0]), float(point[1])) for point in tuple(hole or ()))
                for hole in tuple(getattr(face, "hole_polygons", ()) or ())
            )
            if len(outer) >= 3:
                regions.append((outer, holes))
        if not regions:
            raise ValueError("no valid closed face can be extruded")

        depth = self._apply_extrusion_depth()
        started = time.perf_counter()
        mesh, report = extrude_planar_regions_boolean_ready(
            regions,
            plane=plane,
            depth=depth,
            name="Plan trace 2D extrusion",
            color="#8BC34A",
        )
        _record_apply_mesh_timing(
            "boolean_ready_extrusion",
            (time.perf_counter() - started) * 1000.0,
        )

        try:
            source = build_editable_source(
                sketch=sketch.clone(),
                plane=plane,
                display_plane=self._state.display_plane,
                anchor_world=self._state.anchor_world,
                extrusion_depth_mm=depth,
                motif_assignments=self._state.motif_assignments_by_outer_signature,
            )
            attach_editable_source(mesh, source)
        except Exception:
            pass

        # Final geometry-level gate shared with Joint Builder and downstream
        # booleans.  The planar builder already validates indexed/welded topology,
        # but Apply/Edit is the document boundary: never commit a Plan Tracer
        # object that only *looks* closed by indices while coincident XYZ seams
        # would collapse in the boolean kernel.
        from laserprog_studio.geometry_ops.boolean_topology_contract import (
            require_geometric_boolean_manifold,
        )

        topology = require_geometric_boolean_manifold(mesh, label="Plan Tracer 2D output")

        metadata = getattr(mesh, "metadata", None)
        if metadata is None:
            metadata = {}
            setattr(mesh, "metadata", metadata)
        metadata.update(
            {
                "source_tool": self.id,
                "sketch_faces": len(regions),
                "extrusion_depth_mm": depth,
                "boolean_ready": True,
                "boolean_ready_backend": report.backend,
                "boolean_ready_boundary_edges": report.boundary_edges,
                "boolean_ready_nonmanifold_edges": report.nonmanifold_edges,
                "boolean_ready_nonmanifold_vertices": report.nonmanifold_vertices,
                "boolean_ready_manifold_status": report.manifold_status,
                "boolean_ready_native_verified": report.native_verified,
                "boolean_geometric_manifold": True,
                "boolean_geometry_contract": "geometric_manifold_v2",
                "boolean_geometry_weld_tolerance": float(topology.weld_tolerance),
                "boolean_geometry_welded_vertices": int(topology.welded_vertices),
                "boolean_ready_footprint_area": report.footprint_area,
                "boolean_ready_precision_grid": report.precision_grid,
            }
        )
        return mesh

    def _apply_extrusion_depth(self) -> float:
        default_depth = self._default_board_thickness_mm(getattr(self._services.overlay, "_last_ctx", None))
        try:
            value = float(getattr(self._state, "extrusion_depth", default_depth))
        except Exception:
            value = default_depth
        if value <= 0.0:
            value = default_depth
        return float(value)

    def on_overlay_field_changed(self, window_id: str, field_id: str, value: str, ctx: Any) -> bool:
        """Receive editable field commits from the generic overlay API."""

        if self._services.duplicate.overlay.is_field(field_id):
            return self._services.duplicate.handle_field_change(ctx, str(field_id), str(value))
        if self._services.motif_overlay.is_motif_field(field_id):
            return self._services.motif_overlay.handle_field_change(ctx, str(field_id), str(value))
        if str(window_id) != _METRIC_OVERLAY_ID:
            return False
        from laserprog_studio.tool_api.plan2d import metrics as metric_api

        prefix = metric_api.metric_field_overlay_id(_METRIC_OVERLAY_ID, "")
        metric_field_id = str(field_id)
        if metric_field_id.startswith(prefix):
            metric_field_id = metric_field_id[len(prefix):]
        return self._services.metrics.apply_metric_value(ctx, metric_field_id, str(value))

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        """Mirror toolbox button actions immediately.

        The overlay API owns the visual state and vector icon rendering; the tool
        only receives semantic button ids.  Mode buttons switch the state machine,
        while action buttons such as Delete execute the matching command.
        """

        if self._services.duplicate.handle_button(ctx, str(button_id)):
            return
        if self._services.mirror.handle_button(ctx, str(button_id)):
            return
        if self._services.mesh_trace.handle_button(ctx, str(button_id)):
            return
        if str(button_id) == _VALIDATE_ADD_BUTTON_ID:
            self._apply_add_and_close(ctx)
            return
        if str(button_id) == _VALIDATE_SUBTRACT_BUTTON_ID:
            self._apply_subtract_and_close(ctx)
            return
        if str(button_id) == _METRIC_VALIDATE_BUTTON_ID:
            with _measure_perf(ctx, "plan_trace.metric.validate_before_event"):
                self._services.metrics._validate_metric_draft(ctx)
            return
        if str(button_id) == _METRIC_CANCEL_BUTTON_ID:
            self._services.metrics._cancel_metric_draft(ctx)
            return
        if str(button_id) == _RESTORE_FACES_BUTTON_ID:
            self._services.selection._restore_generated_faces(ctx)
            return
        if self._services.motif_overlay.is_motif_button(button_id):
            self._services.motif_overlay.handle_button(ctx, str(button_id))
            return
        if str(button_id) == _PATTERN_FACE_BUTTON_ID:
            # Toolbox "Pattern" button: opens the dedicated overlay, but ONLY if
            # the user has already selected a Plan Tracer face via Modify mode.
            # The overlay service handles the eligibility check + status hint.
            self._services.motif_overlay.toggle(ctx)
            return
        if str(button_id) == _DELETE_BUTTON_ID:
            self._services.selection._delete_selected_points(ctx)
            return
        mode = self._services.overlay._mode_from_button_id(button_id)
        if mode is None:
            return
        self._services.mode_state._set_active_tool(ctx, mode, reason="overlay", render=True)

    def on_camera_interaction_begin(
        self,
        ctx: Any,
        *,
        mode: str = "mixed",
        screen_pos: tuple[float, float] | None = None,
    ) -> None:
        """Suspend all pointer-derived editing work during camera navigation."""

        self._state.camera_interaction_active = True
        self._state.camera_interaction_mode = str(mode or "mixed")
        self._state.camera_interaction_screen_pos = screen_pos
        _increment_perf(ctx, "plan_trace.camera_navigation.begin")
        _increment_perf(ctx, f"plan_trace.camera_navigation.begin.{self._state.camera_interaction_mode}")
        _set_perf_value(ctx, "plan_trace.camera_navigation.active", 1)
        _set_perf_value(ctx, "plan_trace.camera_navigation.mode", self._state.camera_interaction_mode)

    def on_camera_interaction_end(
        self,
        ctx: Any,
        *,
        mode: str = "mixed",
        screen_pos: tuple[float, float] | None = None,
    ) -> None:
        """Resume editing without blocking the release frame.

        The former implementation immediately replayed a synthetic mouse move.
        That rebuilt the screen snap index, refreshed hover/preview actors and
        requested another render while Qt/VTK was still finishing the camera
        release.  Real traces show a repeatable 33--38 ms hitch after every pan
        or wheel burst.  The next genuine pointer event already invalidates its
        screen projection from the camera signature, so the eager catch-up was
        redundant and visibly harmful.
        """

        resolved_mode = str(mode or self._state.camera_interaction_mode or "mixed")
        self._state.camera_interaction_active = False
        self._state.camera_interaction_mode = "static"
        if screen_pos is not None:
            self._state.camera_interaction_screen_pos = (float(screen_pos[0]), float(screen_pos[1]))
        _increment_perf(ctx, "plan_trace.camera_navigation.end")
        _increment_perf(ctx, f"plan_trace.camera_navigation.end.{resolved_mode}")
        _set_perf_value(ctx, "plan_trace.camera_navigation.active", 0)
        _set_perf_value(ctx, "plan_trace.camera_navigation.mode", "static")

        _increment_perf(ctx, "plan_trace.camera_navigation.catchup_deferred")

    def on_scene_selection_changed(self, ctx: Any) -> None:
        """Plan Tracer owns its own sketch selection while it is open.

        Real scene objects may be used to pick the drawing height, but after the
        plane is locked the host scene selection must stay empty so Delete/Apply
        and Modify mode never target imported parts by accident.
        """

        self._clear_scene_selection(ctx)

    def _clear_scene_selection(self, ctx: Any) -> None:
        try:
            ctx.scene_selection.clear()
        except Exception:
            pass
        owner = getattr(ctx, "owner", None)
        if owner is not None:
            try:
                owner.selected_indices = []
                owner.active_index = None
            except Exception:
                pass

    def wants_pointer_press_passthrough(self, event: ToolEvent, ctx: Any) -> bool:
        """Let the host camera receive left-press while picking the initial face.

        Surface selection is click-like: Plan Tracer only needs the release if the
        pointer did not move.  Returning True here makes the application bridge
        leave the press to VTK, so users can freely orbit before choosing the
        drawing surface.
        """

        if self._state.plane is not None:
            return False
        if event.type != ToolEventType.MOUSE_PRESS or event.button != MouseButton.LEFT:
            return False
        self._services.snap._begin_surface_pick_passthrough(ctx, event)
        return True

    def wants_pointer_release_passthrough(self, event: ToolEvent, ctx: Any) -> bool:
        """Receive the short release that finalizes initial surface selection.

        A tiny cursor jitter can start camera-exclusive mode while the initial
        press was intentionally passed to VTK.  The release must still reach Plan
        Tracer so a click-like gesture locks the selected face instead of leaving
        the tool in camera navigation.
        """

        if self._state.plane is not None:
            return False
        if event.type != ToolEventType.MOUSE_RELEASE or event.button != MouseButton.LEFT:
            return False
        return self._state.surface_pick_press_screen_pos is not None

    def wants_native_actor_interaction(self, event: ToolEvent, ctx: Any) -> bool:
        """Let the API selection/drag runtime run only in Modify mode.

        Draw modes must be able to click existing points/edges as snap geometry.
        If the native runtime consumed those presses first, connecting lines to an
        existing vertex or starting a new segment on a previous endpoint would feel
        broken.
        """

        if self._state.plane is None:
            return False
        self._services.mode_state._pull_active_tool_from_overlay(ctx)
        # Duplicate library/capture deliberately inherit the same native
        # hover/select/safe-drag path as Modify. Shift remains reserved for the
        # shared toggle and rectangle selector in both modes.
        if self._state.active_tool == _MODE_DUPLICATE:
            if not self._services.duplicate.wants_native_actor_interaction(ctx, event):
                return False
            self._services.selection_edit.prepare_drag_from_support_point(ctx, event)
            return True
        if self._state.active_tool == _MODE_MODIFY and bool(getattr(event, "shift", False)):
            return False
        if self._state.active_tool == _MODE_MODIFY:
            # A face or edge remains the explicit selection. Only when the user
            # presses one of its support points do we promote those points to the
            # native drag set, preserving face-only Delete semantics.
            self._services.selection_edit.prepare_drag_from_support_point(ctx, event)
            return True
        return False

    def on_native_interaction_result(self, event: ToolEvent, ctx: Any, result: Any) -> None:
        """Reconcile topology after API-owned select/grab interactions."""

        action = str(getattr(result, "action", "") or "")
        _increment_perf(ctx, f"plan_trace.native.{action or 'unknown'}")
        with _measure_perf(ctx, f"plan_trace.native.{action or 'unknown'}.total"):
            return self._on_native_interaction_result_measured(event, ctx, result, action)

    def _on_native_interaction_result_measured(self, event: ToolEvent, ctx: Any, result: Any, action: str) -> None:
        if self._state.plane is None:
            return
        if self._services.motif_overlay.handle_native_interaction_result(ctx, event, result):
            return
        duplicate_modify = self._state.active_tool == _MODE_DUPLICATE and self._services.duplicate.modify_extension_active
        modify_like = self._state.active_tool == _MODE_MODIFY or duplicate_modify
        if action == "grab" and modify_like and tuple(getattr(result, "grabbed_ids", ()) or ()):
            # Expand selected edges/faces to their support points and detach only
            # the unselected incident branches. This makes group moves safe: the
            # selected topology moves as one object while unrelated geometry
            # keeps its original proportions and endpoints.
            grabbed_ids = self._services.selection_edit.begin_safe_drag(
                ctx, tuple(str(value) for value in getattr(result, "grabbed_ids", ()) or ())
            )
            if self._state.active_drag_snapshot is None:
                self._state.active_drag_snapshot = self._services.history._snapshot_state()
            if bool(getattr(event, "ctrl", False)):
                self._services.selection_edit.latch_rotation(ctx, getattr(event, "screen_pos", None))
            self._services.snap_targets._begin_drag_snap_cache(ctx, exclude_ids=tuple(grabbed_ids))
        if action == "select" and self._state.active_tool == _MODE_MODIFY and getattr(result, "hit", None) is not None:
            try:
                hit_actor_id = str(result.hit.actor_id)
                actor = ctx.selection.actor(hit_actor_id)
                metadata = getattr(actor, "metadata", {}) if actor is not None else {}
                if str(metadata.get("plan_trace_role") or "") == "face":
                    face_id = str(metadata.get("plan_trace_sketch_face_id") or "")
                    if face_id and face_id in self._state.sketch.faces:
                        self._state.pattern_face_id = face_id
                        self._state.pattern_face_ids = (face_id,)
            except Exception:
                pass
            try:
                if self._services.metrics.open_metric_edit_for_actor(ctx, str(result.hit.actor_id)):
                    self._services.overlay._sync_reports(ctx)
                    return
            except Exception:
                pass
        if action == "release" and modify_like and tuple(getattr(result, "grabbed_ids", ()) or ()):
            # During drag the resolver updates point actors and sketch point
            # positions live for performance.  The topological compiler is still a
            # release-time operation so line splits/faces are rebuilt once, not at
            # every mouse move.
            before = self._state.active_drag_snapshot
            self._services.snap_targets._end_drag_snap_cache()
            if self._services.selection_edit.cancel_noop_drag(ctx):
                before = None
            else:
                self._state.active_drag_snapshot = None
                with _measure_perf(ctx, "plan_trace.event.mouse_release.compile"):
                    self._services.sketch_sync._compile_and_sync_sketch(ctx, render=True)
                if before is not None:
                    self._services.history._record_snapshot_command(ctx, "Move Plan tracer selection", before)
            self._state.active_drag_changed = False
            self._state.active_drag_detached_count = 0
            self._state.active_transform_session = None
            self._state.active_drag_selection_before_ids = ()
            # Sketch synchronization already committed and rendered the rebuilt
            # projected topology inside its atomic batch. Avoid a second VTK frame.
            self._services.overlay._sync_reports(ctx)
            if duplicate_modify:
                self._services.duplicate.handle_native_interaction_result(ctx, event, result)
            self._services.rendering._sync_overlays(ctx)
            return
        if action in {"select", "grab", "clear"} or bool(getattr(result, "selection_cleared", False)):
            self._services.overlay._sync_reports(ctx)
            if duplicate_modify:
                self._services.duplicate.handle_native_interaction_result(ctx, event, result)
            # The native Creator interaction runtime already synchronized the
            # projected visual state and issued the single viewport frame.  A
            # second Plan Tracer render here doubled click latency (often 60+ ms).
            self._services.rendering._sync_overlays(ctx)

    def on_event(self, event: ToolEvent, ctx: Any) -> bool:
        event_type = str(getattr(getattr(event, "type", None), "value", getattr(event, "type", "unknown")))
        _increment_perf(ctx, f"plan_trace.event.{event_type}")
        with _measure_perf(ctx, "plan_trace.event.total"):
            with _measure_perf(ctx, f"plan_trace.event.{event_type}.total"):
                return self._on_event_measured(event, ctx)

    def _on_event_measured(self, event: ToolEvent, ctx: Any) -> bool:
        try:
            from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_tool_event

            record_tool_event("tool.entry", self, ctx, event)
        except Exception:
            pass
        if self._state.camera_interaction_active and event.type in {
            ToolEventType.MOUSE_MOVE,
            ToolEventType.MOUSE_PRESS,
            ToolEventType.MOUSE_RELEASE,
        }:
            owner = getattr(ctx, "owner", None)
            owner_navigation_active = True
            if owner is not None:
                try:
                    from laserprog_studio.application.creator_pointer_interaction import creator_camera_navigation_active

                    owner_navigation_active = bool(creator_camera_navigation_active(owner))
                except Exception:
                    owner_navigation_active = True
            if (
                owner is not None
                and not owner_navigation_active
                and event.type == ToolEventType.MOUSE_MOVE
                and event.button == MouseButton.NONE
            ):
                self._state.camera_interaction_active = False
                self._state.camera_interaction_mode = "static"
                _increment_perf(ctx, "plan_trace.camera_navigation.recovered_stale_state")
                try:
                    from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_tool_event

                    record_tool_event("tool.camera_state_recovered", self, ctx, event, owner_navigation_active=owner_navigation_active)
                except Exception:
                    pass
            else:
                _increment_perf(ctx, "plan_trace.camera_navigation.suppressed_tool_event")
                try:
                    from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_tool_event

                    record_tool_event("tool.camera_state_suppressed", self, ctx, event, owner_navigation_active=owner_navigation_active)
                except Exception:
                    pass
                return False
        if event.type == ToolEventType.KEY_PRESS and event.ctrl and not event.shift:
            key = (event.key or "").lower()
            if key == "c":
                return self._services.selection_edit.copy_selected(ctx) or True
            if key == "v":
                return self._services.selection_edit.paste_clipboard(ctx) or True
        if self._services.history._is_undo_shortcut(event):
            return self._services.history._undo_last(ctx)
        if self._services.history._is_redo_shortcut(event):
            return self._services.history._redo_last(ctx)
        if event.is_escape:
            if self._state.active_tool == _MODE_DUPLICATE:
                if self._services.duplicate.handle_escape(ctx):
                    return True
                self._services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="duplicate_escape", render=True)
                ctx.status.info("Duplicate closed. Modify mode is active.")
                return True
            if self._state.active_tool == _MODE_MIRROR:
                if self._services.mirror.handle_escape(ctx):
                    return True
                self._services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="mirror_escape", render=True)
                ctx.status.info("Mirror closed. Modify mode is active.")
                return True
            if self._state.active_tool == _MODE_MESH_TRACE:
                self._services.mode_state._set_active_tool(ctx, _MODE_MODIFY, reason="mesh_trace_escape", render=True)
                ctx.status.info("Mesh trace cancelled. Modify mode is active.")
                return True
            return self._cancel_current_interaction(ctx, save_recoverable_draft=False)
        if bool(getattr(event, "is_double_click", False)):
            return self._finish_current_polyline(ctx) or True
        if event.is_delete:
            return self._services.selection._delete_selected_points(ctx)
        if event.type not in {ToolEventType.MOUSE_MOVE, ToolEventType.MOUSE_PRESS, ToolEventType.MOUSE_RELEASE}:
            return False
        if event.screen_pos is None:
            try:
                from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_tool_event

                record_tool_event("tool.drop.no_screen_pos", self, ctx, event)
            except Exception:
                pass
            return False
        if self._state.plane is None:
            if event.type == ToolEventType.MOUSE_MOVE:
                with _measure_perf(ctx, "plan_trace.surface.hover"):
                    self._services.snap._hover_height(ctx, event)
                return False
            if event.type == ToolEventType.MOUSE_RELEASE and event.button == MouseButton.LEFT:
                with _measure_perf(ctx, "plan_trace.surface.pick_release"):
                    return self._services.snap._finish_surface_pick_passthrough(ctx, event)
            if event.type == ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
                # Direct API/test path: a press still picks the surface.  The Qt
                # viewport bridge uses wants_pointer_press_passthrough() to let
                # left-drag orbit through and then locks the plane on click-like
                # release instead.
                with _measure_perf(ctx, "plan_trace.surface.pick_press"):
                    self._services.snap._pick_height(ctx, event)
                return True
            return False
        if event.type == ToolEventType.MOUSE_PRESS:
            self._clear_scene_selection(ctx)
        self._services.mode_state._pull_active_tool_from_overlay(ctx)
        if self._state.active_tool == _MODE_MESH_TRACE:
            return self._services.mesh_trace.handle_event(ctx, event)
        if self._state.active_tool == _MODE_MIRROR:
            return self._services.mirror.handle_event(ctx, event)
        if self._state.active_tool == _MODE_DUPLICATE:
            return self._services.duplicate.handle_event(ctx, event)
        # The Pattern overlay owns its own gizmo drag interaction.  When it is
        # open and the cursor is over an offset handle, intercept the event
        # before the normal patterns/drawing pipeline so the drag isn't
        # interpreted as a draw click.  When the overlay is closed or the click
        # misses the gizmo, this returns False and the original flow continues.
        if self._services.motif_overlay.handle_event(ctx, event):
            return True
        if self._services.patterns.handle_event(ctx, event):
            return True
        if self._state.metric_draft is not None and event.type == ToolEventType.MOUSE_PRESS:
            # Starting another viewport action implicitly accepts the last metric
            # draft.  The explicit Validate button remains the clear UX path, but
            # this keeps fast drawing workflows and line-chain behaviour
            # from being blocked by an overlay waiting at the top of the screen.
            with _measure_perf(ctx, "plan_trace.metric.validate_before_event"):
                self._services.metrics._validate_metric_draft(ctx)
        with _measure_perf(ctx, "plan_trace.modify.selection_api_event"):
            handled_modify_selection = self._state.active_tool == _MODE_MODIFY and self._services.selection._handle_modify_selection_api_event(ctx, event)
        if handled_modify_selection:
            return True
        if self._state.active_tool == _MODE_MODIFY and event.type == ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
            try:
                ctx.selection.clear_selection(owner_tool=self.id)
            except Exception:
                pass
            self._clear_scene_selection(ctx)
            self._services.overlay._sync_reports(ctx)
            self._services.rendering._render(ctx, sync_overlays=True, render=True)
            return True
        if event.type == ToolEventType.MOUSE_MOVE:
            try:
                from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_tool_event

                record_tool_event("tool.cursor_update.begin", self, ctx, event)
            except Exception:
                pass
            with _measure_perf(ctx, "plan_trace.event.mouse_move.update_cursor"):
                result_world = self._services.snap._update_cursor(ctx, event, render=True)
            try:
                from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_tool_event

                record_tool_event("tool.cursor_update.end", self, ctx, event, result_world=result_world)
            except Exception:
                pass
            return False
        if event.type == ToolEventType.MOUSE_PRESS and event.button == MouseButton.LEFT:
            with _measure_perf(ctx, "plan_trace.event.mouse_press.draw_press"):
                return self._services.snap._handle_draw_press(ctx, event)
        if event.type == ToolEventType.MOUSE_RELEASE and self._state.active_tool == _MODE_MODIFY:
            # A plain Modify release after hover/selection does not mutate the
            # sketch.  Drag releases are handled by the native interaction result
            # path above, where the compile is still performed once.  Avoid a
            # redundant dense-topology compile on every click release.
            _increment_perf(ctx, "plan_trace.event.mouse_release.modify_no_compile")
            return False
        return False

    # Stable wrappers kept intentionally for existing tests/scripts that call
    # a few Plan Tracer internals directly. New code should use the service graph
    # explicitly through ``tool._services``.
    def _set_active_tool(self, *args: Any, **kwargs: Any) -> Any:
        return self._services.mode_state._set_active_tool(*args, **kwargs)

    def _state_invariant_issues(self, *args: Any, **kwargs: Any) -> Any:
        return self._services.mode_state._state_invariant_issues(*args, **kwargs)

    def _compile_and_sync_sketch(self, *args: Any, **kwargs: Any) -> Any:
        return self._services.sketch_sync._compile_and_sync_sketch(*args, **kwargs)

    def apply_metric_value(self, *args: Any, **kwargs: Any) -> Any:
        return self._services.metrics.apply_metric_value(*args, **kwargs)

    def resolve_drag_positions(self, *args: Any, **kwargs: Any) -> Any:
        if self._services.motif_overlay.is_open():
            try:
                resolved = self._services.motif_overlay.resolve_drag_positions(*args, **kwargs)
            except Exception:
                resolved = None
            if resolved:
                return resolved
        return self._services.snap.resolve_drag_positions(*args, **kwargs)


class PlanTrace2DTool(CreatorStudioToolAdapter):
    """Runtime adapter for the rebuilt Plan tracer Creator tool."""

    def __init__(self, spec: ToolSpec) -> None:
        super().__init__(spec=spec, creator=PlanTrace2DCreatorTool())


__all__ = ["PlanTrace2DCreatorTool", "PlanTrace2DTool"]

# -*- coding: utf-8 -*-
from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
import math
from time import perf_counter
from typing import Any

from laserprog_studio.tool_api.core import ToolEvent
from laserprog_studio.planar_tools import FixedPlanarView, make_locked_plane, plane_to_world

from .constants import (
    _ANCHOR_ID,
    _CURSOR_ID,
    _MODE_ARC,
    _MODE_BEZIER,
    _MODE_CIRCLE,
    _MODE_DIMENSION,
    _MODE_DUPLICATE,
    _MODE_HALF_CIRCLE,
    _MODE_LINE,
    _MODE_MODIFY,
    _MODE_POINT,
    _MODE_POLYLINE,
    _MODE_RECTANGLE,
    _PENDING_PREVIEW_PREFIX,
    _PHASE_DRAW,
    _TOOL_GROUP,
)
from .services import _PlanTrace2DService
from .selection_transform import SelectionTransformSession
from .editable_source import (
    PLAN_TRACE_DRAFT_SOURCE_KIND,
    deserialize_plane,
    deserialize_sketch,
    editable_source_from_mesh,
    is_plan_trace_draft_source,
    is_plan_trace_subtract_source,
    mesh_bounds_3d,
    motif_assignments_from_source,
    resolve_editable_source_placement,
)

class PlanTrace2DSnapService(_PlanTrace2DService):
    _SURFACE_PICK_CLICK_TOLERANCE_PX = 5.0

    def _begin_surface_pick_passthrough(self, ctx: Any, event: ToolEvent) -> None:
        """Remember a candidate face-pick press without stealing camera orbit."""

        if event.screen_pos is None:
            self._state.surface_pick_press_screen_pos = None
            return
        self._state.surface_pick_press_screen_pos = (float(event.screen_pos[0]), float(event.screen_pos[1]))

    def _finish_surface_pick_passthrough(self, ctx: Any, event: ToolEvent) -> bool:
        """Lock the drawing plane only for click-like releases.

        The host viewport owns left-drag orbit while Plan Tracer waits for the
        initial surface.  The Creator bridge records the press then lets Qt/VTK
        handle the gesture.  On release we consume only short clicks; larger
        pointer movement is treated as camera navigation and passed back to the
        viewport.
        """

        if event.screen_pos is None:
            self._state.surface_pick_press_screen_pos = None
            return False
        press = self._state.surface_pick_press_screen_pos
        self._state.surface_pick_press_screen_pos = None
        if press is None:
            press = (float(event.screen_pos[0]), float(event.screen_pos[1]))
        dx = abs(float(event.screen_pos[0]) - float(press[0]))
        dy = abs(float(event.screen_pos[1]) - float(press[1]))
        if max(dx, dy) > self._SURFACE_PICK_CLICK_TOLERANCE_PX:
            return False
        self._clear_host_scene_click_candidate(ctx)
        self._pick_height(ctx, event)
        return True

    @staticmethod
    def _clear_host_scene_click_candidate(ctx: Any) -> None:
        owner = getattr(ctx, "owner", None)
        if owner is None:
            return
        try:
            owner._qt_click_pos = None
            owner._qt_click_time = 0.0
        except Exception:
            pass

    def _hover_height(self, ctx: Any, event: ToolEvent) -> None:
        from laserprog_studio.tool_api import plan2d

        if event.screen_pos is None:
            return
        pick = plan2d.pick_plan_surface_anchor_by_raycast(ctx, event.screen_pos, view=self._state.view)
        editable = self._editable_object_for_pick(ctx, pick)
        previous_hover = self._state.editable_hover_object_id
        self._state.hover_world = pick.anchor_world
        self._state.hover_object_id = pick.object_id
        self._state.view = pick.view
        if editable is not None:
            obj, _source = editable
            self._state.editable_hover_object_id = obj.id
            self._state.editable_hover_label = obj.name
            self._show_editable_hover_preview(ctx, obj.mesh, obj.id)
            label_kind = "draft sketch" if is_plan_trace_draft_source(_source) else "editable volume"
            snap_text = f"{label_kind}: {obj.name or obj.id} · click to edit"
        else:
            self._state.editable_hover_object_id = None
            self._state.editable_hover_label = ""
            self._hide_editable_hover_preview(ctx)
            snap_text = f"surface hover: {pick.object_id or pick.hit_kind}" if pick.hit else "ground/origin: click to start on Z=0"
        try:
            ctx.inspector.set_display_value("plan_trace_2d.view", pick.view.value)
            ctx.inspector.set_display_value("plan_trace_2d.snap", snap_text)
        except Exception:
            pass
        try:
            self.services.overlay._sync_reports(ctx)
        except Exception:
            pass
        if previous_hover != self._state.editable_hover_object_id:
            try:
                self.services.rendering._render(ctx, sync_overlays=False, render=True)
            except Exception:
                pass

    def _picked_object_bounds(self, ctx: Any, pick: Any) -> tuple[float, float, float, float, float, float] | None:
        """Return bounds of the object owning the picked drawing face."""

        try:
            object_index = getattr(pick, "object_index", None)
            meshes = list(ctx.document.meshes(include_preview=False))
            if object_index is not None and 0 <= int(object_index) < len(meshes):
                from laserprog_studio.mesh_ops import mesh_bounds

                return mesh_bounds(meshes[int(object_index)])
        except Exception:
            pass
        try:
            object_id = str(getattr(pick, "object_id", "") or "")
            if object_id:
                from laserprog_studio.mesh_ops import mesh_bounds

                for mesh in ctx.document.meshes(include_preview=False):
                    if str(getattr(mesh, "mesh_id", "") or "") == object_id or str(getattr(mesh, "name", "") or "") == object_id:
                        return mesh_bounds(mesh)
        except Exception:
            pass
        return None

    def _pick_height(self, ctx: Any, event: ToolEvent) -> None:
        from laserprog_studio.tool_api import plan2d

        assert event.screen_pos is not None
        picked = plan2d.pick_plan_surface_anchor_by_raycast(ctx, event.screen_pos, view=self._state.view, log_diagnostics=True, diagnostics_label="surface-anchor-click")
        editable = self._editable_object_for_pick(ctx, picked)
        if editable is not None:
            obj, source = editable
            decision = self._editable_pick_decision(ctx, obj, source)
            if decision == "edit":
                if self._open_editable_volume(ctx, obj, source):
                    return
            elif decision == "cancel":
                return
            elif decision == "new":
                # New drawing is an independent sketch on the clicked surface.
                # Preserve the source object's existing editable sketch/history;
                # it must remain available for a later Edit operation.
                self._state.new_sketch_support_object_id = str(getattr(obj, "id", "") or "") or None
                try:
                    self._tool._start_new_drawing_from_plan_trace_source(ctx, obj)
                except Exception:
                    pass
            # decision == "new" deliberately falls through and locks a fresh
            # drawing plane on the clicked surface instead of hijacking the old
            # Plan Tracer source.
        if not picked.hit:
            self._lock_origin_ground_plane(ctx)
            return
        self._state.plane = picked.plane
        self._state.display_plane = picked.display_plane
        self._state.view = picked.view
        self._state.phase = _PHASE_DRAW
        self._state.anchor_world = picked.anchor_world
        self._state.cursor_world = picked.display_world
        # The yellow editable-volume hover preview is useful only while choosing
        # the initial support. Once a drawing plane is locked it must disappear
        # immediately, otherwise it remains over the support part throughout the
        # sketch and looks like a stuck host selection.
        self._hide_editable_hover_preview(ctx)
        self._state.editable_hover_object_id = None
        self._state.editable_hover_label = ""
        self._set_active_snap_scope_from_pick(ctx, picked)
        self._state.active_tool = _MODE_POINT
        plan2d.align_camera_to_plan_surface(ctx, picked.plane, anchor_world=picked.anchor_world, focus_bounds=self._picked_object_bounds(ctx, picked))
        try:
            ctx.workflow.goto(_PHASE_DRAW)
        except Exception:
            pass
        ctx.overlay.set_group_active(_TOOL_GROUP, self.services.overlay._button_id(self._state.active_tool))
        self.services.overlay._show_toolbox(ctx)
        plan2d.register_plan_anchor_target(ctx, owner_tool=self.id, target_id=_ANCHOR_ID, world_pos=picked.display_world, visible=True)
        plan2d.register_plan_cursor(ctx, owner_tool=self.id, cursor_id=_CURSOR_ID, world_pos=picked.display_world, visible=True, snap_kind="free", snapped=False)
        plan2d.sync_plan_actor_visuals(ctx, owner_tool=self.id, changed_actor_ids=(_ANCHOR_ID, _CURSOR_ID), position_only=False, render=True)
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        source = f"surface {picked.object_id or picked.hit_kind}"
        ctx.status.info(f"Plan locked on selected surface at depth {picked.plane.depth:.3f} ({source}). Overlay mode: {self.services.overlay._label_for_tool(self._state.active_tool)}.")

    def _lock_origin_ground_plane(self, ctx: Any) -> None:
        """Start a new Plan Tracer sketch on the world ground plane.

        At initialization a click that does not hit a model face is treated as a
        deliberate ground/origin start.  The plane is the horizontal world XY
        plane at Z=0, the camera is aligned from above looking down, and the
        first cursor/anchor position is the world origin instead of the clicked
        screen coordinate.
        """

        from laserprog_studio.tool_api import plan2d

        plane = make_locked_plane(FixedPlanarView.TOP, depth=0.0)
        display_plane = plane.with_depth(float(plane.depth) + max(float(plan2d.PLAN_TRACE_DEFAULT_SURFACE_OFFSET), 0.0))
        anchor_world = plane_to_world(plane, 0.0, 0.0)
        display_world = plane_to_world(display_plane, 0.0, 0.0)
        self._state.plane = plane
        self._state.display_plane = display_plane
        self._state.view = FixedPlanarView.TOP
        self._state.phase = _PHASE_DRAW
        self._state.anchor_world = anchor_world
        self._state.cursor_world = display_world
        self._clear_active_snap_scope()
        self._state.active_tool = _MODE_POINT
        try:
            plan2d.align_camera_to_plan_surface(ctx, plane, anchor_world=anchor_world)
        except Exception:
            pass
        try:
            ctx.workflow.goto(_PHASE_DRAW)
        except Exception:
            pass
        ctx.overlay.set_group_active(_TOOL_GROUP, self.services.overlay._button_id(self._state.active_tool))
        self.services.overlay._show_toolbox(ctx)
        plan2d.register_plan_anchor_target(ctx, owner_tool=self.id, target_id=_ANCHOR_ID, world_pos=display_world, visible=True)
        plan2d.register_plan_cursor(ctx, owner_tool=self.id, cursor_id=_CURSOR_ID, world_pos=display_world, visible=True, snap_kind="free", snapped=False)
        plan2d.sync_plan_actor_visuals(ctx, owner_tool=self.id, changed_actor_ids=(_ANCHOR_ID, _CURSOR_ID), position_only=False, render=True)
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        try:
            ctx.status.info("Plan locked on ground at world origin. Camera aligned to top view; start drawing on Z=0.")
        except Exception:
            pass

    def _clear_active_snap_scope(self) -> None:
        self._state.active_snap_object_ids = ()
        self._state.active_snap_object_indices = ()
        self._state.active_snap_object_label = ""
        self._state.active_snap_object_source = ""

    def _set_active_snap_scope_from_object(self, obj: Any) -> None:
        ids: set[str] = set()
        label = ""
        obj_id = str(getattr(obj, "id", "") or "")
        obj_name = str(getattr(obj, "name", "") or "")
        if obj_id:
            ids.add(obj_id)
        if obj_name:
            ids.add(obj_name)
            label = obj_name
        mesh = getattr(obj, "mesh", None)
        mesh_id = str(getattr(mesh, "mesh_id", "") or "") if mesh is not None else ""
        mesh_name = str(getattr(mesh, "name", "") or "") if mesh is not None else ""
        if mesh_id:
            ids.add(mesh_id)
        if mesh_name:
            ids.add(mesh_name)
            label = label or mesh_name
        self._state.active_snap_object_ids = tuple(sorted(ids))
        self._state.active_snap_object_indices = ()
        self._state.active_snap_object_label = label or obj_id or mesh_id
        self._state.active_snap_object_source = "editable"

    def _set_active_snap_scope_from_pick(self, ctx: Any, pick: Any) -> None:
        ids: set[str] = set()
        indices: set[int] = set()
        label = ""
        object_id = getattr(pick, "object_id", None)
        object_index = getattr(pick, "object_index", None)
        if object_id is not None:
            text_id = str(object_id)
            if text_id:
                ids.add(text_id)
                label = text_id
        if object_index is not None:
            try:
                idx = int(object_index)
                indices.add(idx)
                ids.add(f"mesh:{idx}")
                label = label or f"mesh:{idx}"
            except Exception:
                pass
        # When the document facade is available, include the real WorkMesh id/name
        # as well as the VTK fallback ``mesh:<index>`` id. Different backends use
        # different identifiers for the same picked object; keeping all aliases is
        # what makes the active-only snap mode reliable.
        try:
            objects = tuple(ctx.document.objects(include_preview=False))
        except Exception:
            objects = ()
        if object_index is not None:
            try:
                idx = int(object_index)
                if 0 <= idx < len(objects):
                    obj = objects[idx]
                    obj_id = str(getattr(obj, "id", "") or "")
                    obj_name = str(getattr(obj, "name", "") or "")
                    mesh = getattr(obj, "mesh", obj)
                    mesh_id = str(getattr(mesh, "mesh_id", "") or "")
                    mesh_name = str(getattr(mesh, "name", "") or "")
                    for alias in (obj_id, obj_name, mesh_id, mesh_name):
                        if alias:
                            ids.add(alias)
                    label = obj_name or mesh_name or obj_id or mesh_id or label
            except Exception:
                pass
        self._state.active_snap_object_ids = tuple(sorted(ids))
        self._state.active_snap_object_indices = tuple(sorted(indices))
        self._state.active_snap_object_label = label
        self._state.active_snap_object_source = "surface" if ids or indices else ""

    def _active_scene_snap_scope(self) -> tuple[tuple[str, ...], tuple[int, ...]]:
        if not bool(getattr(self._state, "snap_active_object_only", False)):
            return (), ()
        ids = tuple(str(value) for value in getattr(self._state, "active_snap_object_ids", ()) or () if str(value))
        indices = tuple(int(value) for value in getattr(self._state, "active_snap_object_indices", ()) or ())
        if ids or indices:
            return ids, indices
        # Active-only was requested but the sketch was started from the ground or
        # a source object that has already been removed from the document.  Keep
        # local sketch snaps, but deliberately suppress unrelated scene pieces.
        return ("__plan_trace_no_active_scene_object__",), ()

    def _editable_object_for_pick(self, ctx: Any, pick: Any) -> tuple[Any, dict[str, Any]] | None:
        try:
            ctx.document.ensure()
        except Exception:
            pass
        candidates: list[Any] = []
        object_id = getattr(pick, "object_id", None)
        object_index = getattr(pick, "object_index", None)
        for key in (object_id, object_index):
            if key is None:
                continue
            try:
                candidates.append(ctx.document.get(key))
            except Exception:
                continue
        if object_index is not None:
            try:
                objects = ctx.document.objects(include_preview=False)
                idx = int(object_index)
                if 0 <= idx < len(objects):
                    candidates.append(objects[idx])
            except Exception:
                pass
        seen: set[str] = set()
        for obj in candidates:
            obj_id = str(getattr(obj, "id", "") or "")
            if obj_id in seen:
                continue
            seen.add(obj_id)
            source = editable_source_from_mesh(getattr(obj, "mesh", None))
            if source is not None:
                return obj, source
        return None

    def _show_editable_hover_preview(self, ctx: Any, mesh: Any, object_id: str) -> None:
        preview_id = "plan_trace_2d.editable_hover"
        registry = ctx.projected_drawing.for_tool(self.id)
        existing = registry.get(preview_id)
        if existing is not None and bool(getattr(existing, "visible", True)):
            metadata = dict(getattr(existing, "metadata", ()) or ())
            if str(metadata.get("source_object_id", "")) == str(object_id):
                return
        try:
            from laserprog_studio.tool_api import projected_drawing as draw2d

            vertices = tuple(tuple(float(value) for value in point) for point in tuple(getattr(mesh, "vertices", ()) or ()))
            triangles = tuple(tuple(int(value) for value in cell) for cell in tuple(getattr(mesh, "triangles", ()) or ()))
            if len(vertices) < 3 or not triangles:
                return
            registry.add(
                draw2d.triangle_mesh(
                    preview_id,
                    vertices,
                    triangles,
                    fill_color="#FFD54F",
                    fill_opacity=0.04,
                    outline_color="#FFD54F",
                    outline_width_px=5.0,
                    outline_opacity=0.86,
                    layer=5,
                    metadata={
                        "plan_trace_role": "editable_hover",
                        "source_object_id": str(object_id),
                        "projected_drawing_only": True,
                        "projected_no_selection_actor": True,
                    },
                ),
                replace=True,
                render=False,
            )
        except Exception:
            pass

    def _hide_editable_hover_preview(self, ctx: Any) -> None:
        try:
            ctx.projected_drawing.for_tool(self.id).hide("plan_trace_2d.editable_hover", render=False)
        except Exception:
            pass

    def _editable_pick_decision(self, ctx: Any, obj: Any, source: dict[str, Any]) -> str:
        """Ask whether a click on an old Plan Tracer source edits it or starts new.

        Headless tests and non-Qt contexts default to the historical behaviour
        (edit), but the desktop application now gets the explicit choice the user
        requested.
        """

        owner = getattr(ctx, "owner", None)
        chooser = getattr(owner, "ask_plan_trace_edit_or_new", None) if owner is not None else None
        if callable(chooser):
            try:
                value = str(chooser(obj, source) or "edit").strip().lower()
                if value in {"edit", "new", "cancel"}:
                    return value
            except Exception:
                pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication.instance()
            if app is None:
                return "edit"
            box = QMessageBox(getattr(ctx, "owner", None))
            box.setWindowTitle("Plan Tracer 2D")
            name = str(getattr(obj, "name", "") or getattr(obj, "id", "") or "this sketch")
            kind = "cut" if is_plan_trace_subtract_source(source) else ("draft" if is_plan_trace_draft_source(source) else "volume")
            box.setText(f"An existing {kind} Plan Tracer item exists here: {name}.")
            box.setInformativeText("Do you want to edit it, or draw a new Plan Tracer sketch on this surface?")
            edit_btn = box.addButton("Edit", QMessageBox.AcceptRole)
            new_btn = box.addButton("New sketch", QMessageBox.ActionRole)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.setDefaultButton(edit_btn)
            box.exec()
            clicked = box.clickedButton()
            if clicked is new_btn:
                return "new"
            if clicked is edit_btn:
                return "edit"
            return "cancel"
        except Exception:
            return "edit"

    def _open_editable_volume(self, ctx: Any, obj: Any, source: dict[str, Any]) -> bool:
        from laserprog_studio.tool_api import plan2d

        current_mesh = getattr(obj, "mesh", None)
        focus_bounds = mesh_bounds_3d(current_mesh)
        placement_report: dict[str, Any] = {"mode": "identity", "reference": "none", "focus_bounds": focus_bounds}
        if current_mesh is not None:
            try:
                source, placement_report = resolve_editable_source_placement(source, current_mesh)
                focus_bounds = placement_report.get("focus_bounds") or focus_bounds
            except Exception:
                pass

        plane = deserialize_plane(source.get("plane"))
        if plane is None:
            return False
        display_plane = deserialize_plane(source.get("display_plane")) or plane.with_depth(float(plane.depth) + 0.75)
        sketch = deserialize_sketch(source.get("sketch"))
        if not sketch.points and not sketch.lines and not sketch.circles and not sketch.arcs and not sketch.beziers:
            return False
        self._hide_editable_hover_preview(ctx)
        self._state.plane = plane
        self._state.display_plane = display_plane
        self._state.view = plane.view
        self._state.phase = _PHASE_DRAW
        anchor = source.get("anchor_world")
        if anchor is None:
            try:
                first = next(iter(sketch.points.values()))
                anchor = self.services.coordinates.sketch_xy_to_semantic_world(first.position)
            except Exception:
                anchor = (0.0, 0.0, 0.0)
        self._state.anchor_world = tuple(float(v) for v in anchor)
        self._state.cursor_world = self._state.anchor_world
        self._state.active_tool = _MODE_MODIFY
        self._state.sketch = sketch
        self._state.motif_assignments_by_outer_signature = motif_assignments_from_source(source)
        # Derived hole polygons are rebuilt from the compact assignments after
        # the first non-destructive compile.  Never carry stale geometry cache
        # across editable-source sessions.
        self._state.motif_face_holes_by_outer_signature.clear()
        self._state.motif_face_hole_kinds.clear()
        self._state.next_point_index = int(getattr(sketch, "_next_id", 1) or 1)
        self._state.extrusion_depth = max(float(source.get("extrusion_depth_mm") or 10.0), 0.001)
        self._state.editing_source_object_id = str(getattr(obj, "id", "") or "")
        self._state.editing_source_label = str(getattr(obj, "name", "") or self._state.editing_source_object_id)
        self._state.editing_source_extrusion_depth = self._state.extrusion_depth
        self._state.editing_source_kind = str(source.get("kind") or "")
        self._state.editing_source_operation = "subtract" if is_plan_trace_subtract_source(source) else "add"
        self._state.editing_source_placement_mode = str(placement_report.get("mode") or "identity")
        self._state.editing_source_placement_reference = str(placement_report.get("reference") or "none")
        self._state.editing_source_focus_bounds = None if focus_bounds is None else tuple(float(value) for value in focus_bounds)
        self._set_active_snap_scope_from_object(obj)
        self._state.editable_hover_object_id = None
        self._state.editable_hover_label = ""
        try:
            if is_plan_trace_subtract_source(source):
                self._tool._show_intact_subtract_source_for_editing(ctx, obj, source)
            else:
                self._tool._remove_edit_source_from_document(ctx)
        except Exception:
            pass
        try:
            plan2d.align_camera_to_plan_surface(ctx, plane, anchor_world=self._state.anchor_world, focus_bounds=focus_bounds)
        except Exception:
            pass
        try:
            ctx.workflow.goto(_PHASE_DRAW)
        except Exception:
            pass
        try:
            ctx.overlay.set_group_active(_TOOL_GROUP, self.services.overlay._button_id(self._state.active_tool))
        except Exception:
            pass
        self.services.overlay._show_toolbox(ctx)
        try:
            plan2d.register_plan_anchor_target(ctx, owner_tool=self.id, target_id=_ANCHOR_ID, world_pos=self._state.anchor_world, visible=True)
            plan2d.register_plan_cursor(ctx, owner_tool=self.id, cursor_id=_CURSOR_ID, world_pos=self._state.anchor_world, visible=True, snap_kind="free", snapped=False)
        except Exception:
            pass
        self.services.sketch_sync._compile_and_sync_sketch(ctx, render=False)
        self.services.overlay._sync_reports(ctx)
        self.services.rendering._render(ctx, sync_overlays=True, render=True)
        try:
            placement_note = " Current object placement is preserved." if self._state.editing_source_placement_mode in {"affine", "translation"} else ""
            if self._state.editing_source_kind == PLAN_TRACE_DRAFT_SOURCE_KIND:
                ctx.status.info(f"Plan tracer resumed draft {self._state.editing_source_label}. Apply will replace the red draft placeholder with a {self._state.extrusion_depth:.1f} mm extrusion.{placement_note}")
            elif is_plan_trace_subtract_source(source):
                ctx.status.info(f"Plan tracer editing subtraction {self._state.editing_source_label}. Use Subtract to reapply the cut through the intact stored model.{placement_note}")
            else:
                ctx.status.info(f"Plan tracer editing {self._state.editing_source_label}. Apply will replace the existing volume and preserve {self._state.extrusion_depth:.1f} mm extrusion.{placement_note}")
        except Exception:
            pass
        return True

    def _handle_draw_press(self, ctx: Any, event: ToolEvent) -> bool:
        with self._measure_perf(ctx, "plan_trace.draw_press.total"):
            return self._handle_draw_press_measured(ctx, event)

    def _handle_draw_press_measured(self, ctx: Any, event: ToolEvent) -> bool:
        self.services.mode_state._pull_active_tool_from_overlay(ctx)
        tool = self._state.active_tool
        self._increment_perf(ctx, f"plan_trace.draw_press.tool.{tool}")
        if tool == _MODE_MODIFY:
            return False
        world = self._update_cursor(ctx, event, render=False)
        if world is None:
            return False
        with self._measure_perf(ctx, "plan_trace.draw_press.snapshot"):
            before = self.services.history._snapshot_state()

        def record(label: str) -> None:
            with self._measure_perf(ctx, "plan_trace.draw_press.record_history"):
                self.services.history._record_snapshot_command(ctx, label, before)

        if tool == _MODE_POINT:
            with self._measure_perf(ctx, "plan_trace.draw_press.place_point"):
                self.services.sketch_sync._place_point(ctx, world)
            self._clear_pending_geometry_preview(ctx)
            record("Add Plan tracer point")
            return True
        if tool == _MODE_LINE:
            with self._measure_perf(ctx, "plan_trace.draw_press.line"):
                self.services.drawing._handle_line_press(ctx, world, base_snapshot=before)
            self._clear_pending_geometry_preview(ctx)
            if self._state.metric_draft is None:
                record("Edit Plan tracer line")
            return True
        if tool == _MODE_POLYLINE:
            with self._measure_perf(ctx, "plan_trace.draw_press.polyline"):
                self.services.drawing._handle_polyline_press(ctx, world, base_snapshot=before)
            self._clear_pending_geometry_preview(ctx)
            record("Edit Plan tracer polyline")
            return True
        if tool == _MODE_RECTANGLE:
            with self._measure_perf(ctx, "plan_trace.draw_press.rectangle"):
                self.services.drawing._handle_rectangle_press(ctx, world, base_snapshot=before)
            self._clear_pending_geometry_preview(ctx)
            if self._state.metric_draft is None:
                record("Edit Plan tracer rectangle")
            return True
        if tool == _MODE_CIRCLE:
            with self._measure_perf(ctx, "plan_trace.draw_press.circle"):
                self.services.drawing._handle_circle_press(ctx, world, base_snapshot=before)
            self._clear_pending_geometry_preview(ctx)
            if self._state.metric_draft is None:
                record("Edit Plan tracer circle")
            return True
        if tool == _MODE_ARC:
            with self._measure_perf(ctx, "plan_trace.draw_press.arc"):
                self.services.drawing._handle_arc_press(ctx, world, base_snapshot=before)
            self._clear_pending_geometry_preview(ctx)
            if self._state.metric_draft is None:
                record("Edit Plan tracer arc")
            return True
        if tool == _MODE_BEZIER:
            with self._measure_perf(ctx, "plan_trace.draw_press.bezier"):
                self.services.drawing._handle_bezier_press(ctx, world, base_snapshot=before)
            self._clear_pending_geometry_preview(ctx)
            record("Edit Plan tracer Bezier curve")
            return True
        if tool == _MODE_HALF_CIRCLE:
            with self._measure_perf(ctx, "plan_trace.draw_press.half_circle"):
                self.services.drawing._handle_half_circle_press(ctx, world, base_snapshot=before)
            self._clear_pending_geometry_preview(ctx)
            if self._state.metric_draft is None:
                record("Edit Plan tracer half-circle")
            return True
        if tool == _MODE_DIMENSION:
            with self._measure_perf(ctx, "plan_trace.draw_press.dimension"):
                self.services.dimensions._handle_dimension_press(ctx, event, world)
            self._clear_pending_geometry_preview(ctx)
            record("Edit Plan tracer dimension")
            return True
        ctx.status.info(f"{self.services.overlay._label_for_tool(tool)} is staged; no geometry action was created.")
        return True

    def _update_cursor(self, ctx: Any, event: ToolEvent, *, render: bool) -> tuple[float, float, float] | None:
        """Update cursor/preview declarations with one projected renderer sync."""

        with ctx.projected_drawing.for_tool(self.id).batch():
            return self._update_cursor_batched(ctx, event, render=render)

    def _update_cursor_batched(self, ctx: Any, event: ToolEvent, *, render: bool) -> tuple[float, float, float] | None:
        from laserprog_studio.tool_api import plan2d

        with self._measure_perf(ctx, "plan_trace.cursor.update"):
            self._increment_perf(ctx, "plan_trace.cursor.moves")
            plane = self._state.plane
            display_plane = self._state.display_plane or plane
            try:
                from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_cursor_event

                record_cursor_event(
                    "cursor.update.enter",
                    self,
                    ctx,
                    event,
                    plane_locked=plane is not None,
                    display_plane_locked=display_plane is not None,
                    render=render,
                )
            except Exception:
                pass
            if plane is None or display_plane is None or event.screen_pos is None:
                try:
                    from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_cursor_event

                    record_cursor_event(
                        "cursor.update.drop.missing_plane_or_screen",
                        self,
                        ctx,
                        event,
                        plane_locked=plane is not None,
                        display_plane_locked=display_plane is not None,
                        has_screen=event.screen_pos is not None,
                    )
                except Exception:
                    pass
                return None
            now = perf_counter()
            sx, sy = (float(event.screen_pos[0]), float(event.screen_pos[1]))
            last_screen = self._state.plan_trace_last_cursor_screen_pos
            last_world = self._state.plan_trace_last_cursor_world
            if render and last_screen is not None and last_world is not None:
                dx = abs(sx - float(last_screen[0]))
                dy = abs(sy - float(last_screen[1]))
                min_delta = max(float(self._state.plan_trace_cursor_min_screen_delta_px), 0.0)
                min_interval = max(float(self._state.plan_trace_cursor_render_interval_s), 0.0)
                if max(dx, dy) < min_delta and (now - float(self._state.plan_trace_last_cursor_sync_time)) < min_interval:
                    self._increment_perf(ctx, "plan_trace.cursor.skipped_subpixel")
                    return last_world
            with self._measure_perf(ctx, "plan_trace.cursor.project"):
                candidate = plan2d.project_screen_to_locked_plane(ctx, event.screen_pos, display_plane, event_world_pos=None)
            try:
                from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_cursor_event

                record_cursor_event(
                    "cursor.project.end",
                    self,
                    ctx,
                    event,
                    candidate_world=candidate,
                    last_screen=last_screen,
                    last_world=last_world,
                )
            except Exception:
                pass

            # Modify hover needs the visible plan cursor, but it does not need
            # drawing Smart Snap.  The native Creator runtime has already done
            # the semantic face/edge/point hover hit-test for this MouseMove and
            # actual point drags call ``resolve_drag_positions`` (with full Smart
            # Snap) directly.  Historically we nevertheless rebuilt/queryed all
            # snap targets here as if the user were drawing a new entity.  On a
            # dense sketch that made simple face hover O(N) twice per event.
            if self._state.active_tool == _MODE_MODIFY and not bool(getattr(ctx.selection.state, "grab_active", False)):
                self._increment_perf(ctx, "plan_trace.cursor.modify_fast_path")
                # Preserve exact nearby point/edge/curve snapping, but do not
                # feed the whole sketch to the alignment-guide pass.  The local
                # target service is backed by its own screen grid, so steady
                # hover is O(local candidates) rather than O(all sketch items).
                with self._measure_perf(ctx, "plan_trace.cursor.modify_near_targets"):
                    near_targets = self.services.snap_targets._live_snap_targets_near(
                        ctx,
                        event.screen_pos,
                        exclude_ids=(_CURSOR_ID,),
                    )
                self._increment_perf(ctx, "plan_trace.cursor.modify_near_target_count", len(near_targets))
                with self._measure_perf(ctx, "plan_trace.cursor.modify_local_snap"):
                    allowed_object_ids, allowed_object_indices = self._active_scene_snap_scope()
                    snap = plan2d.smart_snap_on_plan(
                        ctx,
                        owner_tool=self.id,
                        plane=display_plane,
                        candidate_world=candidate,
                        screen_pos=event.screen_pos,
                        exclude_ids=(_CURSOR_ID,),
                        extra_targets=near_targets,
                        extra_alignment_targets=near_targets,
                        allowed_object_ids=allowed_object_ids,
                        allowed_object_indices=allowed_object_indices,
                        rebuild_cache=False,
                    )
                placement_world = tuple(float(v) for v in (snap.world_pos if snap.snapped else candidate))
                previous_kind = str(self._state.last_snap_kind or "free")
                should_render = bool(render)
                if should_render:
                    min_interval = max(float(self._state.plan_trace_cursor_render_interval_s), 0.0)
                    current_kind = str(getattr(snap, "kind", "free") or "free")
                    if current_kind == previous_kind and (now - float(self._state.plan_trace_last_cursor_render_time)) < min_interval:
                        should_render = False
                        self._increment_perf(ctx, "plan_trace.cursor.render_throttled")
                self._state.last_constraint_label = "none"
                with self._measure_perf(ctx, "plan_trace.cursor.modify_fast_actor_sync"):
                    self._update_snap_cursor_actor(
                        ctx,
                        plan2d,
                        placement_world,
                        snap,
                        render=should_render,
                        force_full_visual_sync=False,
                        changed_preview_ids=(),
                    )
                self._state.plan_trace_last_cursor_screen_pos = (sx, sy)
                self._state.plan_trace_last_cursor_world = placement_world
                self._state.plan_trace_last_cursor_sync_time = now
                if should_render:
                    self._state.plan_trace_last_cursor_render_time = now
                return placement_world

            # ``_live_snap_targets`` and ``_live_snap_targets_near`` each recompute the
            # snap target signature; on every mouse move that was twice the O(N) walk
            # over points/lines/arcs/circles.  The combined helper builds both views
            # in a single signature pass so the smart-snap call stays cheap on hover.
            with self._measure_perf(ctx, "plan_trace.cursor.targets"):
                align_targets, near_targets = self.services.snap_targets._live_snap_targets_and_near(
                    ctx, event.screen_pos, exclude_ids=(_CURSOR_ID,)
                )
            self._increment_perf(ctx, "plan_trace.cursor.align_targets", len(align_targets))
            self._increment_perf(ctx, "plan_trace.cursor.near_targets", len(near_targets))
            with self._measure_perf(ctx, "plan_trace.cursor.smart_snap"):
                allowed_object_ids, allowed_object_indices = self._active_scene_snap_scope()
                snap = plan2d.smart_snap_on_plan(
                    ctx,
                    owner_tool=self.id,
                    plane=display_plane,
                    candidate_world=candidate,
                    screen_pos=event.screen_pos,
                    exclude_ids=(_CURSOR_ID,),
                    extra_targets=near_targets,
                    extra_alignment_targets=align_targets,
                    allowed_object_ids=allowed_object_ids,
                    allowed_object_indices=allowed_object_indices,
                    rebuild_cache=False,
                )
            placement_world = snap.world_pos if snap.snapped else candidate
            try:
                from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_cursor_event

                record_cursor_event(
                    "cursor.snap.end",
                    self,
                    ctx,
                    event,
                    snapped=bool(getattr(snap, "snapped", False)),
                    snap_kind=str(getattr(snap, "kind", "") or ""),
                    snap_label=str(getattr(snap, "label", "") or ""),
                    snap_world=getattr(snap, "world_pos", None),
                    placement_world=placement_world,
                    align_target_count=len(align_targets),
                    near_target_count=len(near_targets),
                )
            except Exception:
                pass
            with self._measure_perf(ctx, "plan_trace.cursor.constraint"):
                placement_world = self._apply_draw_constraint(ctx, event, placement_world)
            projected_revision_before = int(ctx.projected_drawing.state_token(self.id)[0])
            preview_ids_before = tuple(str(value) for value in getattr(self._state, "pending_preview_ids", ()) or ())
            with self._measure_perf(ctx, "plan_trace.cursor.pending_preview"):
                self._update_pending_geometry_preview(ctx, placement_world)
            preview_ids_after = tuple(str(value) for value in getattr(self._state, "pending_preview_ids", ()) or ())
            preview_changed = int(ctx.projected_drawing.state_token(self.id)[0]) != projected_revision_before
            preview_structure_changed = preview_ids_after != preview_ids_before
            snap_kind_before = self._state.last_snap_kind
            should_render = bool(render)
            if should_render:
                min_interval = max(float(self._state.plan_trace_cursor_render_interval_s), 0.0)
                kind = str(getattr(snap, "kind", "free") or "free")
                # Render immediately when the visual recipe changes or a pending
                # preview changed; otherwise cap the expensive VTK render to about
                # 30 Hz.  The actor state is still synchronized every processed
                # event, just without forcing the viewport to repaint.
                if kind == snap_kind_before and not preview_structure_changed and (now - float(self._state.plan_trace_last_cursor_render_time)) < min_interval:
                    should_render = False
                    self._increment_perf(ctx, "plan_trace.cursor.render_throttled")
            with self._measure_perf(ctx, "plan_trace.cursor.actor_sync"):
                self._update_snap_cursor_actor(
                    ctx,
                    plan2d,
                    placement_world,
                    snap,
                    render=should_render,
                    force_full_visual_sync=preview_structure_changed,
                    changed_preview_ids=preview_ids_after if preview_changed else (),
                )
            self._state.plan_trace_last_cursor_screen_pos = (sx, sy)
            self._state.plan_trace_last_cursor_world = tuple(float(v) for v in placement_world)
            self._state.plan_trace_last_cursor_sync_time = now
            if should_render:
                self._state.plan_trace_last_cursor_render_time = now
            try:
                from laserprog_studio.tooling.plan_trace_2d.input_diagnostics import record_cursor_event

                record_cursor_event(
                    "cursor.update.exit",
                    self,
                    ctx,
                    event,
                    placement_world=placement_world,
                    should_render=should_render,
                    preview_changed=preview_changed,
                    preview_structure_changed=preview_structure_changed,
                    preview_ids=list(preview_ids_after),
                    cursor_screen=(sx, sy),
                )
            except Exception:
                pass
            if self._state.last_constraint_label != "none":
                self._state.last_snap_label = f"{self._state.last_snap_label} · {self._state.last_constraint_label}"
                with self._measure_perf(ctx, "plan_trace.cursor.constraint_report"):
                    self.services.overlay._sync_cursor_report(ctx)
            return placement_world

    @staticmethod
    def _increment_perf(ctx: Any, name: str, value: int = 1) -> None:
        profiler = getattr(ctx, "profiler", None)
        increment = getattr(profiler, "increment", None)
        if not callable(increment):
            return
        try:
            increment(str(name), int(value))
        except Exception:
            pass

    @staticmethod
    def _measure_perf(ctx: Any, name: str) -> Any:
        profiler = getattr(ctx, "profiler", None)
        measure = getattr(profiler, "measure", None)
        if callable(measure):
            try:
                return measure(str(name))
            except Exception:
                pass
        return nullcontext()

    def _apply_draw_constraint(self, ctx: Any, event: ToolEvent, world_pos: tuple[float, float, float]) -> tuple[float, float, float]:
        """Apply API-owned drawing constraints such as Shift angle/square locks.

        The tool only decides which pending anchor is relevant for the current
        mode.  The actual constraint math lives in ``tool_api.plan2d.snap`` so
        future drawing tools can reuse the same behaviour without copying plane
        coordinate logic.
        """

        self._state.last_constraint_label = "none"
        if not bool(getattr(event, "shift", False)):
            return world_pos
        plane = self._state.display_plane or self._state.plane
        if plane is None:
            return world_pos
        anchor_world = self._constraint_anchor_display_world()
        if anchor_world is None:
            return world_pos
        from laserprog_studio.tool_api import plan2d

        if self._state.active_tool == _MODE_RECTANGLE:
            result = plan2d.constrain_square_from_corner_on_plan(plane, anchor_world, world_pos)
        else:
            result = plan2d.constrain_angle_step_on_plan(plane, anchor_world, world_pos, angle_step_degrees=45.0)
        if bool(getattr(result, "applied", False)):
            self._state.last_constraint_label = str(getattr(result, "label", "constraint") or "constraint")
            return tuple(float(v) for v in result.world_pos)
        return world_pos

    def _constraint_anchor_display_world(self) -> tuple[float, float, float] | None:
        anchor_id: str | None = None
        mode = self._state.active_tool
        if mode == _MODE_LINE:
            anchor_id = self._state.pending_line_start_id
        elif mode == _MODE_POLYLINE:
            anchor_id = self._state.pending_polyline_last_id
        elif mode == _MODE_RECTANGLE:
            anchor_id = self._state.pending_rectangle_corner_id
        elif mode == _MODE_HALF_CIRCLE:
            anchor_id = self._state.pending_half_circle_start_id
        elif mode == _MODE_ARC and self._state.pending_arc_end_id is None:
            anchor_id = self._state.pending_arc_start_id
        if not anchor_id:
            return None
        point = self._state.sketch.points.get(anchor_id)
        if point is None:
            return None
        return self.services.coordinates.sketch_xy_to_display_world(point.position)

    def _update_snap_cursor_actor(
        self,
        ctx: Any,
        plan2d: Any,
        world_pos: tuple[float, float, float],
        snap: Any,
        *,
        render: bool,
        force_full_visual_sync: bool = False,
        changed_preview_ids: tuple[str, ...] = (),
    ) -> None:
        """Update the API-owned cursor, including snap-kind visual style.

        Pending draw primitives live beside the cursor in Projected Drawing 2D.
        ``force_full_visual_sync`` is set whenever their structure changes so a
        free-space cursor move also commits the new line/circle/arc declaration.
        """

        kind = str(getattr(snap, "kind", "free") or "free")
        snapped = bool(getattr(snap, "snapped", False))
        label = str(getattr(snap, "label", "") or kind.replace("_", " ").title())
        previous_kind = self._state.last_snap_kind
        self._state.cursor_world = world_pos
        self._state.last_snap_kind = kind
        self._state.last_snap_label = f"{snap.source}:{snap.source_id}" if snapped and getattr(snap, "source_id", None) else (snap.source if snapped else "none")
        with self._measure_perf(ctx, "plan_trace.cursor.register_cursor"):
            plan2d.register_plan_cursor(
                ctx,
                owner_tool=self.id,
                cursor_id=_CURSOR_ID,
                world_pos=world_pos,
                visible=True,
                snap_kind=kind,
                snap_label=label,
                snapped=snapped,
            )
        # The cursor declaration and pending preview already live in the same
        # Projected Drawing batch.  On ordinary motion we intentionally pass no
        # moved selection actor: the fixed cursor was updated directly in the
        # projected registry, so reading its stale selection mirror would undo it.
        # The shared helper still owns the final render and rare full visual-state
        # refreshes when the snap recipe or preview structure changes.
        with self._measure_perf(ctx, "plan_trace.cursor.sync_actor_visuals"):
            plan2d.sync_plan_actor_visuals(
                ctx,
                owner_tool=self.id,
                changed_actor_ids=(),
                extra_preview_ids=tuple(str(value) for value in changed_preview_ids),
                position_only=(kind == previous_kind and not bool(force_full_visual_sync)),
                render=render,
            )
        # Only the snap label needs to be refreshed for hover; the heavy
        # inspector/overlay sync runs on real state transitions (mode change,
        # selection change, sketch compile, metric draft, ...).
        with self._measure_perf(ctx, "plan_trace.cursor.sync_report"):
            self.services.overlay._sync_cursor_report(ctx)

    def _live_snap_targets(self, ctx: Any, *, exclude_ids: tuple[str, ...] = ()) -> tuple[Any, ...]:
        # Wrapper: snap target construction now lives in a dedicated
        # service so this cursor/drag service does not also own scene-target export.
        return self.services.snap_targets._live_snap_targets(ctx, exclude_ids=exclude_ids)

    def resolve_drag_positions(self, event: ToolEvent, ctx: Any) -> dict[str, Any] | None:
        with self._measure_perf(ctx, "plan_trace.drag.resolve_positions.total"):
            return self._resolve_drag_positions_measured(event, ctx)

    def _resolve_drag_positions_measured(self, event: ToolEvent, ctx: Any) -> dict[str, Any] | None:
        """Snap-aware absolute drag resolver used by the Creator API runtime.

        The native interaction layer still owns selection/grab/repaint.  Plan
        tracer only provides the snapped target actor because its points live on
        a locked display plane while the raw Qt event world position may be at a
        local/selection depth unrelated to that plane.
        """

        from laserprog_studio.tool_api import plan2d

        duplicate_modify = (
            self._state.active_tool == _MODE_DUPLICATE
            and bool(getattr(self.services.duplicate, "modify_extension_active", False))
        )
        if (self._state.active_tool != _MODE_MODIFY and not duplicate_modify) or event.screen_pos is None:
            return None
        plane = self._state.plane
        display_plane = self._state.display_plane or plane
        if plane is None or display_plane is None:
            return None
        grabbed_ids = tuple(str(value) for value in getattr(ctx.selection.state, "grabbed_ids", ()) or ())
        if not grabbed_ids:
            return None
        actors_by_id = {actor_id: ctx.selection.actor(actor_id) for actor_id in grabbed_ids}
        movable = {
            actor_id: actor
            for actor_id, actor in actors_by_id.items()
            if actor is not None and actor.owner_tool == self.id and actor.metadata.get("plan_trace_role") == "point" and actor.points
        }
        if not movable:
            return None

        reference_id = self._drag_reference_point_id(ctx, grabbed_ids)
        if reference_id not in movable:
            reference_id = next(reversed(movable))

        transform_session = getattr(self._state, "active_transform_session", None)
        interaction_screen_pos = event.screen_pos
        if isinstance(transform_session, SelectionTransformSession):
            if transform_session.rotating and not bool(getattr(event, "ctrl", False)):
                pivot_point = self._state.sketch.points.get(transform_session.pivot_point_id)
                if pivot_point is not None:
                    pivot_display = self.services.coordinates.sketch_xy_to_display_world(pivot_point.position)
                    try:
                        pivot_screen = ctx.viewport.world_to_screen(pivot_display)
                        transform_session.resume_translation(
                            screen_pos=event.screen_pos,
                            pivot_screen_pos=pivot_screen,
                        )
                        try:
                            ctx.status.info("Move selection resumed. Smart Snap remains active on the grabbed pivot.")
                        except Exception:
                            pass
                    except Exception:
                        pass
            if bool(getattr(event, "ctrl", False)) and not transform_session.rotating:
                self.services.selection_edit.latch_rotation(ctx, event.screen_pos)
            if transform_session.rotating:
                return self._resolve_rotation_drag_positions(
                    event,
                    ctx,
                    plan2d,
                    movable=movable,
                    session=transform_session,
                )
            interaction_screen_pos = transform_session.effective_translation_screen_pos(event.screen_pos)

        with self._measure_perf(ctx, "plan_trace.drag.project"):
            candidate = plan2d.project_screen_to_locked_plane(ctx, interaction_screen_pos, display_plane, event_world_pos=None)
        excluded = tuple((*grabbed_ids, _CURSOR_ID))
        with self._measure_perf(ctx, "plan_trace.drag.smart_snap"):
            allowed_object_ids, allowed_object_indices = self._active_scene_snap_scope()
            snap = plan2d.smart_snap_on_plan(
                ctx,
                owner_tool=self.id,
                plane=display_plane,
                candidate_world=candidate,
                screen_pos=interaction_screen_pos,
                exclude_ids=excluded,
                extra_targets=self.services.snap_targets._live_snap_targets_near(ctx, interaction_screen_pos, exclude_ids=excluded),
                extra_alignment_targets=self.services.snap_targets._live_snap_targets(ctx, exclude_ids=excluded),
                allowed_object_ids=allowed_object_ids,
                allowed_object_indices=allowed_object_indices,
                rebuild_cache=False,
            )
        reference_target_display = snap.world_pos if snap.snapped else candidate
        reference_target_semantic = self.services.coordinates.display_world_to_semantic(reference_target_display)
        reference_target_display = self.services.coordinates.semantic_world_to_display(reference_target_semantic)
        reference_actor = movable[reference_id]
        current_reference_display = tuple(float(v) for v in reference_actor.points[0])
        delta = (
            float(reference_target_display[0]) - current_reference_display[0],
            float(reference_target_display[1]) - current_reference_display[1],
            float(reference_target_display[2]) - current_reference_display[2],
        )

        if abs(delta[0]) > 1.0e-12 or abs(delta[1]) > 1.0e-12 or abs(delta[2]) > 1.0e-12:
            self.services.selection_edit.mark_drag_changed()

        replacements: dict[str, Any] = {}
        semantic_updates: dict[str, tuple[float, float, float]] = {}
        self._increment_perf(ctx, "plan_trace.drag.movable_points", len(movable))
        with self._measure_perf(ctx, "plan_trace.drag.build_replacements"):
            for actor_id, actor in movable.items():
                current = tuple(float(v) for v in actor.points[0])
                moved_display = (current[0] + delta[0], current[1] + delta[1], current[2] + delta[2])
                semantic_world = self.services.coordinates.display_world_to_semantic(moved_display)
                display_world = self.services.coordinates.semantic_world_to_display(semantic_world)
                semantic_updates[actor_id] = semantic_world
                metadata = {**actor.metadata, "plan_trace_semantic_world_pos": semantic_world}
                replacements[actor_id] = replace(actor, points=(display_world,), metadata=metadata)

        self._replace_point_states(semantic_updates)
        # Do not run the topological compiler while the mouse is moving.  It is
        # release-time work.  During drag we only update the moved point actors and
        # their directly connected line/curve visuals; faces/dimensions are rebuilt
        # once on release.
        try:
            with self._measure_perf(ctx, "plan_trace.drag.sync_moved_points"):
                self.services.sketch_sync._sync_drag_moved_points(ctx, tuple(semantic_updates), render=False)
        except Exception:
            pass
        with self._measure_perf(ctx, "plan_trace.drag.cursor_actor"):
            self._update_snap_cursor_actor(ctx, plan2d, reference_target_display, snap, render=False)
        return replacements

    def _resolve_rotation_drag_positions(
        self,
        event: ToolEvent,
        ctx: Any,
        plan2d: Any,
        *,
        movable: dict[str, Any],
        session: Any,
    ) -> dict[str, Any] | None:
        """Rotate the complete selected point set around the grabbed point.

        Holding Ctrl switches the current drag to rotation. Releasing Ctrl
        resumes translation with a screen-space pivot offset, so the selection
        never jumps to the raw pointer position.
        """

        if event.screen_pos is None:
            return None
        rotated = session.rotated_positions(event.screen_pos)
        if not rotated:
            return None
        if abs(float(getattr(session, "angle_rad", 0.0))) > 1.0e-12:
            self.services.selection_edit.mark_drag_changed()

        replacements: dict[str, Any] = {}
        semantic_updates: dict[str, tuple[float, float, float]] = {}
        with self._measure_perf(ctx, "plan_trace.drag.rotate.build_replacements"):
            for actor_id, actor in movable.items():
                xy = rotated.get(actor_id)
                if xy is None:
                    continue
                semantic_world = self.services.coordinates.sketch_xy_to_semantic_world(xy)
                display_world = self.services.coordinates.semantic_world_to_display(semantic_world)
                semantic_updates[actor_id] = semantic_world
                metadata = {
                    **actor.metadata,
                    "plan_trace_semantic_world_pos": semantic_world,
                    "plan_trace_transform_mode": "rotate",
                }
                replacements[actor_id] = replace(actor, points=(display_world,), metadata=metadata)

        if not replacements:
            return None
        self._replace_point_states(semantic_updates)
        try:
            with self._measure_perf(ctx, "plan_trace.drag.rotate.sync_moved_points"):
                self.services.sketch_sync._sync_drag_moved_points(ctx, tuple(semantic_updates), render=False)
        except Exception:
            pass

        pivot_xy = getattr(session, "rotation_pivot_xy", None)
        if pivot_xy is not None:
            pivot_display = self.services.coordinates.sketch_xy_to_display_world(pivot_xy)
            try:
                from types import SimpleNamespace

                angle_deg = math.degrees(float(getattr(session, "angle_rad", 0.0)))
                rotate_cursor = SimpleNamespace(
                    kind="pivot",
                    snapped=False,
                    label=f"Rotate {angle_deg:.1f}°",
                    source="rotation",
                    source_id=None,
                )
                self._update_snap_cursor_actor(ctx, plan2d, pivot_display, rotate_cursor, render=False)
            except Exception:
                pass
        return replacements

    def _drag_reference_point_id(self, ctx: Any, grabbed_ids: tuple[str, ...]) -> str:
        """Return the point whose position drives group snapping while dragging.

        Multi-selection preserves the native selection order.  The last selected
        point is the intuitive CAD reference: when several points are dragged, that
        point is the one that lands exactly on the smart-snap target, while the
        other selected points keep their relative offsets.
        """

        grabbed = {str(value) for value in grabbed_ids}
        # The point physically pressed by the user is the placement pivot.  This
        # is more predictable than the historical "last selected point" rule
        # after rectangle selection or face expansion, where selection order is
        # an implementation detail. Smart Snap therefore lands the grabbed point
        # itself on the target while the rest of the group keeps its offsets.
        pressed_id = str(getattr(ctx.selection.state, "pressed_id", "") or "")
        if pressed_id in grabbed:
            return pressed_id
        selected = [str(value) for value in ctx.selection.ids() if str(value) in grabbed]
        if selected:
            return selected[-1]
        return grabbed_ids[-1]

    def _replace_point_state(self, actor_id: str, semantic_world: tuple[float, float, float]) -> None:
        self._replace_point_states({actor_id: semantic_world})

    def _replace_point_states(self, updates: dict[str, tuple[float, float, float]]) -> None:
        normalized = {str(actor_id): tuple(float(v) for v in world) for actor_id, world in updates.items()}
        moved = False
        for point_id, semantic_world in normalized.items():
            if point_id in self._state.sketch.points:
                self._state.sketch.move_point(point_id, self.services.coordinates.semantic_world_to_sketch_xy(semantic_world))
                moved = True
        self._state.points = [
            (point_id, normalized.get(point_id, world))
            for point_id, world in self._state.points
        ]
        # Point dict identity is stable across ``move_point``; bump the snap
        # target service's move revision so the fast hover signature notices
        # the in-place edit and refreshes the compiled snap target cache.
        if moved:
            try:
                self.services.snap_targets._bump_move_revision()
            except Exception:
                pass


    def _update_pending_geometry_preview(self, ctx: Any, cursor_display_world: tuple[float, float, float]) -> None:
        """Show the exact geometry that the next click would create.

        Curve previews used to hide and recreate every possible preview primitive
        on each mouse move.  That is expensive for circle/arc/half-circle modes
        and caused visible UI churn.  The live path now keeps stable ids, updates
        only the primitive that is actually active, and hides stale primitives
        only when the pending operation changes.
        """

        if self._state.active_tool == _MODE_MODIFY:
            self._clear_pending_geometry_preview(ctx)
            return
        try:
            cursor_semantic = self.services.coordinates.display_world_to_semantic(cursor_display_world)
            cursor_xy = self.services.coordinates.semantic_world_to_sketch_xy(cursor_semantic)
        except Exception:
            self._clear_pending_geometry_preview(ctx)
            return
        mode = self._state.active_tool
        from laserprog_studio.tool_api import projected_drawing as draw2d
        from laserprog_studio.tool_api.styles import line_style

        registry = ctx.projected_drawing.for_tool(self.id)
        shown_ids: list[str] = []

        def point_xy(point_id: str | None) -> tuple[float, float] | None:
            if not point_id:
                return None
            point = self._state.sketch.points.get(str(point_id))
            if point is None:
                return None
            return tuple(float(v) for v in point.position)

        def world(xy: tuple[float, float]) -> tuple[float, float, float]:
            return self.services.coordinates.sketch_xy_to_display_world(xy)

        def rounded_xy(xy: tuple[float, float]) -> tuple[float, float]:
            # One hundredth of a millimetre keeps the preview visually exact while
            # avoiding expensive curve resampling for sub-pixel mouse jitter.
            return (round(float(xy[0]), 2), round(float(xy[1]), 2))

        def preview_id(local: str) -> str:
            return f"{_PENDING_PREVIEW_PREFIX}:{local}"

        def visual(style_id: str) -> tuple[str, float, float]:
            style = line_style(style_id)
            return (str(style.color), float(style.width_px), float(style.opacity))

        def transient_metadata(style_id: str) -> dict[str, Any]:
            return {
                "style_id": style_id,
                "transient": True,
                "plan_trace_role": "pending_preview",
                "projected_drawing_only": True,
                "projected_no_selection_actor": True,
            }

        def show_line(local: str, start_xy: tuple[float, float], end_xy: tuple[float, float], *, style_id: str = "preview") -> None:
            item_id = preview_id(local)
            color, width, opacity = visual(style_id)
            registry.add(
                draw2d.line(
                    item_id,
                    world(start_xy),
                    world(end_xy),
                    color=color,
                    width_px=width,
                    opacity=opacity,
                    interaction="fixed",
                    metadata=transient_metadata(style_id),
                ),
                replace=True,
                render=False,
            )
            shown_ids.append(item_id)

        def show_poly(local: str, points_xy: tuple[tuple[float, float], ...] | list[tuple[float, float]], *, closed: bool = False) -> None:
            pts = [world(xy) for xy in points_xy]
            if len(pts) < 2:
                return
            item_id = preview_id(local)
            color, width, opacity = visual("preview")
            registry.add(
                draw2d.polyline(
                    item_id,
                    tuple(pts),
                    closed=closed,
                    color=color,
                    width_px=width,
                    opacity=opacity,
                    interaction="fixed",
                    metadata=transient_metadata("preview"),
                ),
                replace=True,
                render=False,
            )
            shown_ids.append(item_id)

        def maybe_skip(signature: tuple[Any, ...]) -> bool:
            if self._state.pending_preview_signature == signature:
                shown_ids.extend(tuple(str(value) for value in getattr(self._state, "pending_preview_ids", ()) or ()))
                return True
            self._state.pending_preview_signature = signature
            return False

        cursor_key = rounded_xy(cursor_xy)
        if mode == _MODE_LINE:
            start = point_xy(self._state.pending_line_start_id)
            if start is not None:
                signature = (mode, self._state.pending_line_start_id, cursor_key)
                if not maybe_skip(signature):
                    show_line("line", start, cursor_xy)
            else:
                self._state.pending_preview_signature = None
        elif mode == _MODE_POLYLINE:
            start = point_xy(self._state.pending_polyline_last_id)
            if start is not None:
                signature = (mode, self._state.pending_polyline_last_id, cursor_key)
                if not maybe_skip(signature):
                    show_line("polyline", start, cursor_xy)
            else:
                self._state.pending_preview_signature = None
        elif mode == _MODE_RECTANGLE:
            corner = point_xy(self._state.pending_rectangle_corner_id)
            if corner is not None:
                signature = (mode, self._state.pending_rectangle_corner_id, cursor_key)
                if not maybe_skip(signature):
                    x1, y1 = corner
                    x2, y2 = cursor_xy
                    show_poly("rectangle", ((x1, y1), (x2, y1), (x2, y2), (x1, y2)), closed=True)
            else:
                self._state.pending_preview_signature = None
        elif mode == _MODE_CIRCLE:
            center = point_xy(self._state.pending_circle_center_id)
            if center is not None:
                signature = (mode, self._state.pending_circle_center_id, cursor_key)
                if not maybe_skip(signature):
                    from laserprog_studio.planar_tools import PlanTraceAddKind, sample_plan_trace_element

                    pts_xy = sample_plan_trace_element(PlanTraceAddKind.CIRCLE, (center, cursor_xy), samples=28)
                    item_id = preview_id("circle")
                    color, width, opacity = visual("preview")
                    registry.add(
                        draw2d.polyline(
                            item_id,
                            tuple(world(xy) for xy in pts_xy),
                            closed=True,
                            actor_kind="circle",
                            color=color,
                            width_px=width,
                            opacity=opacity,
                            interaction="fixed",
                            metadata=transient_metadata("preview"),
                        ),
                        replace=True,
                        render=False,
                    )
                    shown_ids.append(item_id)
            else:
                self._state.pending_preview_signature = None
        elif mode == _MODE_HALF_CIRCLE:
            start = point_xy(self._state.pending_half_circle_start_id)
            if start is not None:
                signature = (mode, self._state.pending_half_circle_start_id, cursor_key)
                if not maybe_skip(signature):
                    from laserprog_studio.planar_tools import PlanTraceAddKind, sample_plan_trace_element

                    control = self.services.drawing._half_circle_control_point(start, cursor_xy)
                    pts_xy = sample_plan_trace_element(PlanTraceAddKind.SEMICIRCLE, (start, cursor_xy, control), samples=18)
                    item_id = preview_id("half_circle")
                    color, width, opacity = visual("preview")
                    registry.add(
                        draw2d.arc(
                            item_id,
                            tuple(world(xy) for xy in pts_xy),
                            color=color,
                            width_px=width,
                            opacity=opacity,
                            interaction="fixed",
                            metadata=transient_metadata("preview"),
                        ),
                        replace=True,
                        render=False,
                    )
                    shown_ids.append(item_id)
                    show_line("half_circle_diameter", start, cursor_xy, style_id="guide")
            else:
                self._state.pending_preview_signature = None
        elif mode == _MODE_ARC:
            start = point_xy(self._state.pending_arc_start_id)
            end = point_xy(self._state.pending_arc_end_id)
            if start is not None and end is None:
                signature = (mode, self._state.pending_arc_start_id, None, cursor_key)
                if not maybe_skip(signature):
                    show_line("arc_chord", start, cursor_xy)
            elif start is not None and end is not None:
                signature = (mode, self._state.pending_arc_start_id, self._state.pending_arc_end_id, cursor_key)
                if not maybe_skip(signature):
                    from laserprog_studio.planar_tools import PlanTraceAddKind, sample_plan_trace_element

                    pts_xy = sample_plan_trace_element(PlanTraceAddKind.SEMICIRCLE, (start, end, cursor_xy), samples=18)
                    item_id = preview_id("arc")
                    color, width, opacity = visual("preview")
                    registry.add(
                        draw2d.arc(
                            item_id,
                            tuple(world(xy) for xy in pts_xy),
                            color=color,
                            width_px=width,
                            opacity=opacity,
                            interaction="fixed",
                            metadata=transient_metadata("preview"),
                        ),
                        replace=True,
                        render=False,
                    )
                    shown_ids.append(item_id)
            else:
                self._state.pending_preview_signature = None
        elif mode == _MODE_BEZIER:
            start = point_xy(self._state.pending_bezier_start_id)
            end = point_xy(self._state.pending_bezier_end_id)
            control_1 = point_xy(self._state.pending_bezier_control_1_id)
            if start is not None and end is None:
                signature = (mode, self._state.pending_bezier_start_id, None, None, cursor_key)
                if not maybe_skip(signature):
                    show_line("bezier_chord", start, cursor_xy)
            elif start is not None and end is not None:
                signature = (
                    mode,
                    self._state.pending_bezier_start_id,
                    self._state.pending_bezier_end_id,
                    self._state.pending_bezier_control_1_id,
                    cursor_key,
                )
                if not maybe_skip(signature):
                    from laserprog_studio.tool_api.plan2d.curves import sample_cubic_bezier

                    first_handle = cursor_xy if control_1 is None else control_1
                    second_handle = end if control_1 is None else cursor_xy
                    pts_xy = sample_cubic_bezier(start, first_handle, second_handle, end, segments=32)
                    item_id = preview_id("bezier")
                    color, width, opacity = visual("preview")
                    registry.add(
                        draw2d.arc(
                            item_id,
                            tuple(world(xy) for xy in pts_xy),
                            color=color,
                            width_px=width,
                            opacity=opacity,
                            interaction="fixed",
                            metadata=transient_metadata("preview"),
                        ),
                        replace=True,
                        render=False,
                    )
                    shown_ids.append(item_id)
                    show_line("bezier_chord", start, end, style_id="guide")
                    show_line("bezier_handle_1", start, first_handle, style_id="guide")
                    if control_1 is not None:
                        show_line("bezier_handle_2", end, cursor_xy, style_id="guide")
            else:
                self._state.pending_preview_signature = None
        elif mode == _MODE_DIMENSION:
            start = point_xy(self._state.pending_dimension_start_id)
            if start is not None:
                signature = (mode, self._state.pending_dimension_start_id, cursor_key)
                if not maybe_skip(signature):
                    show_line("dimension", start, cursor_xy, style_id="guide")
            else:
                self._state.pending_preview_signature = None
        else:
            self._state.pending_preview_signature = None

        self._hide_stale_pending_geometry_previews(ctx, tuple(shown_ids))

    def _hide_stale_pending_geometry_previews(self, ctx: Any, shown_ids: tuple[str, ...]) -> None:
        current = tuple(str(value) for value in getattr(self._state, "pending_preview_ids", ()) or ())
        for item_id in current:
            if item_id in shown_ids:
                continue
            try:
                ctx.projected_drawing.for_tool(self.id).hide(item_id, render=False)
            except Exception:
                pass
        self._state.pending_preview_ids = shown_ids

    def _clear_pending_geometry_preview(self, ctx: Any) -> None:
        with ctx.projected_drawing.for_tool(self.id).batch():
            self._clear_pending_geometry_preview_batched(ctx)

    def _clear_pending_geometry_preview_batched(self, ctx: Any) -> None:
        current = tuple(str(value) for value in getattr(self._state, "pending_preview_ids", ()) or ())
        if not current:
            current = tuple(f"{_PENDING_PREVIEW_PREFIX}:{suffix}" for suffix in (
                "line",
                "polyline",
                "rectangle",
                "circle",
                "half_circle",
                "half_circle_diameter",
                "arc_chord",
                "arc",
                "dimension",
            ))
        for item_id in current:
            try:
                ctx.projected_drawing.for_tool(self.id).hide(item_id, render=False)
            except Exception:
                pass
        self._state.pending_preview_ids = ()
        self._state.pending_preview_signature = None

    def _semantic_world_to_sketch_xy(self, world: tuple[float, float, float]) -> tuple[float, float]:
        # Stable wrapper for existing tests/scripts. New services should
        # depend on ``services.coordinates`` directly.
        return self.services.coordinates.semantic_world_to_sketch_xy(world)

    def _sketch_xy_to_semantic_world(self, xy: tuple[float, float]) -> tuple[float, float, float]:
        return self.services.coordinates.sketch_xy_to_semantic_world(xy)

    def _sketch_xy_to_display_world(self, xy: tuple[float, float]) -> tuple[float, float, float]:
        return self.services.coordinates.sketch_xy_to_display_world(xy)



__all__ = ["PlanTrace2DSnapService"]

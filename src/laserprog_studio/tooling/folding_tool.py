# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
import math
import uuid
from dataclasses import replace
from typing import Any

from laserprog_studio.planar_tools import clamp_world_point_to_plane
from laserprog_studio.tool_api import plan2d
from laserprog_studio.tool_api.core import CreatorStudioToolAdapter, CreatorTool, MouseButton, ToolEvent, ToolEventType
from laserprog_studio.tool_api.tracing import plane_from_origin_normal

from .base import ToolSpec
from .editable_mesh_hover import EditableHoverMesh, EditableMeshHoverPreview
from .folding.geometry import (
    arbitrary_face_plane,
    build_folding_frame,
    deform_mesh,
    fold_angle_from_handle,
    hinge_handle_point,
    normalized_fold_angle_deg,
    resample_shape_angles,
    shape_handle_normals,
    shape_handle_points,
)
from .folding.models import FoldingDeformationMode, FoldingFixedSide, FoldingPhase, FoldingSession, Point3, new_living_hinge_curve
from .folding.panel import build_folding_panel
from .folding.preview_debounce import FoldingPreviewDebouncer
from .folding.rendering import FoldingRenderer
from .folding.serialization import attach_folding_source, folding_group_info, has_folding_source, restore_folding_source
from .folding.state_machine import FoldingWorkflowMachine
from .folding.workflow_overlay import FoldingWorkflowOverlay
from .ids import TOOL_FOLDING


_PHASE_LABELS = {
    FoldingPhase.SELECT_MESH: "Select mesh",
    FoldingPhase.SELECT_FACE: "Select face",
    FoldingPhase.PLACE_START: "Place start",
    FoldingPhase.PLACE_END: "Place end",
    FoldingPhase.ADJUST_CURVE: "Adjust curve",
}

_PHASE_WORKFLOW_IDS = {
    FoldingPhase.SELECT_MESH: "mesh",
    FoldingPhase.SELECT_FACE: "face",
    FoldingPhase.PLACE_START: "start",
    FoldingPhase.PLACE_END: "end",
    FoldingPhase.ADJUST_CURVE: "curve",
}

_LEGACY_CONTROL_IDS = {"folding:control:1", "folding:control:2"}


def _is_control_id(value: str) -> bool:
    if value == "folding:angle" or value in _LEGACY_CONTROL_IDS:
        return True
    parts = value.split(":")
    return len(parts) == 3 and parts[0] == "folding" and parts[1] == "shape" and parts[2].isdigit()
_PREVIEW_IDLE_DELAY_MS = 1500
_CLICK_DRAG_THRESHOLD_PX = 6.0
_FOLDING_CURSOR_ID = "folding:cursor"


class FoldingCreatorTool(CreatorTool):
    """Bend one mesh along a curve with an explicit five-step UX workflow."""

    id = TOOL_FOLDING
    label = "Folding"

    def __init__(self) -> None:
        self._session = FoldingSession()
        self._machine = FoldingWorkflowMachine(self._session)
        self._renderer = FoldingRenderer(self.id, self._session)
        self._workflow_overlay = FoldingWorkflowOverlay(self.id, self._session)
        self._mesh_hover = EditableMeshHoverPreview(
            self.id,
            "folding:mesh_hover",
            metadata_role="folding_selectable_mesh_hover",
        )
        self._preview: Any | None = None
        self._ctx: Any | None = None
        self._preview_signature: tuple[Any, ...] | None = None
        self._preview_debouncer = FoldingPreviewDebouncer(self._on_preview_idle, delay_ms=_PREVIEW_IDLE_DELAY_MS)
        self._pointer_press_screen: tuple[float, float] | None = None
        self._camera_interaction_active = False
        self._cursor_snap_kind = "free"
        self._cursor_snap_label = "Free"
        self._cursor_snapped = False

    @property
    def session(self) -> FoldingSession:
        return self._session

    def on_open(self, ctx: Any) -> None:
        from laserprog_studio.tool_api.versioning import require_tool_api

        require_tool_api("0.13.0", max_major=0)
        ctx.cleanup_tool(self.id, include_persistent_overlays=True)
        self._preview_debouncer.cancel()
        self._preview_signature = None
        self._mesh_hover.reset()
        self._ctx = ctx
        self._session.reset()
        self._machine = FoldingWorkflowMachine(self._session)
        self._preview = None
        self._pointer_press_screen = None
        self._camera_interaction_active = False
        self._reset_cursor_snap_state()
        try:
            ctx.document.ensure()
        except Exception:
            pass
        self._register_workflow(ctx)
        ctx.inspector.set_panel(
            build_folding_panel(
                on_value_changed=lambda field_id, value: self._on_value_changed(ctx, field_id, value),
                on_action=lambda event: self._on_action(ctx, str(getattr(event, "action_id", "") or "")),
            )
        )
        try:
            selected = ctx.scene_selection.selected_objects()
        except Exception:
            selected = ()
        if selected:
            self._select_targets(ctx, selected)
        else:
            self._sync(ctx, "Yellow outline: select one or more meshes, then click a highlighted mesh.")

    def on_close(self, ctx: Any) -> None:
        self._preview_debouncer.cancel()
        self._cancel_preview()
        self._mesh_hover.hide(ctx, render=False)
        self._workflow_overlay.hide(ctx)
        self._renderer.clear(ctx, render=False)
        try:
            ctx.selection.end_grab()
            ctx.selection.clear()
        except Exception:
            pass
        ctx.workflow.clear(self.id)
        ctx.inspector.clear()
        self._ctx = None

    def on_cancel(self, ctx: Any) -> bool:
        self._preview_debouncer.cancel()
        self._cancel_preview()
        self._mesh_hover.hide(ctx, render=False)
        self._workflow_overlay.hide(ctx)
        self._renderer.clear(ctx, render=False)
        if self._session.applied_since_open:
            ctx.status.info("Folding cancelled. The last applied mesh was kept.")
        else:
            ctx.status.info("Folding cancelled. The original mesh was restored.")
        return True

    def can_apply(self, ctx: Any) -> bool:  # noqa: ARG002
        return bool(
            self._session.phase is FoldingPhase.ADJUST_CURVE
            and bool(self._session.target_rows())
            and self._session.plane is not None
            and self._session.curve.complete
        )

    def on_apply(self, ctx: Any) -> bool:
        if not self.can_apply(ctx):
            self._sync(ctx, "Finish defining the hinge before applying.", render=False)
            return False
        self._preview_debouncer.cancel()
        self._session.preview_pending = False
        try:
            if not self._update_preview(ctx, force=False):
                if self._preview is None or not bool(getattr(self._preview, "active", False)):
                    self._update_preview(ctx, force=True)
            if self._preview is None or not bool(getattr(self._preview, "active", False)):
                raise RuntimeError("The folded mesh preview is not available.")
            label = "Apply living-hinge fold" if self._session.curve.is_living_hinge else "Apply folding deformation"
            changed = bool(self._preview.apply(label=label, operation_type="folding_apply"))
        except Exception as exc:
            self._sync(ctx, f"Folding could not be applied: {exc}", render=False)
            return False
        if not changed:
            self._sync(ctx, "The current fold does not change the mesh.", render=False)
            return False
        self._preview = None
        self._session.applied_since_open = True
        self._session.dirty = False
        self._session.preview_ready = True
        try:
            indices = tuple(int(value) for value in self._session.target_indices)
            if not indices and self._session.target_index is not None:
                indices = (int(self._session.target_index),)
            if indices:
                ctx.scene_selection.select_indices(indices, active_index=indices[-1])
        except Exception:
            pass
        self._sync(ctx, "Fold applied. Adjust the angle to create another revision.")
        return True

    def wants_pointer_press_passthrough(self, event: ToolEvent, ctx: Any) -> bool:  # noqa: ARG002
        """Give left press to VTK while retaining the click candidate.

        The Qt bridge may classify even a tiny jitter as camera navigation. The
        matching release hook below is therefore mandatory; without it Folding
        never receives the click that selects the mesh/face/point.
        """

        if self._session.phase is FoldingPhase.ADJUST_CURVE:
            return False
        if event.type is not ToolEventType.MOUSE_PRESS or event.button is not MouseButton.LEFT:
            return False
        self._pointer_press_screen = event.screen_pos
        return True

    def wants_pointer_release_passthrough(self, event: ToolEvent, ctx: Any) -> bool:  # noqa: ARG002
        if self._session.phase is FoldingPhase.ADJUST_CURVE:
            return False
        return bool(
            event.type is ToolEventType.MOUSE_RELEASE
            and event.button in {MouseButton.LEFT, MouseButton.NONE}
            and self._pointer_press_screen is not None
        )

    def on_camera_interaction_begin(
        self,
        ctx: Any,
        *,
        mode: str = "mixed",  # noqa: ARG002
        screen_pos: tuple[float, float] | None = None,  # noqa: ARG002
    ) -> None:
        self._camera_interaction_active = True
        self._mesh_hover.hide(ctx, render=False)
        self._session.clear_transient_hover()
        self._renderer.sync(ctx, render=True)

    def on_camera_interaction_end(
        self,
        ctx: Any,
        *,
        mode: str = "mixed",  # noqa: ARG002
        screen_pos: tuple[float, float] | None = None,
    ) -> None:
        self._camera_interaction_active = False
        if screen_pos is None or self._pointer_press_screen is not None:
            return
        self._update_phase_hover(ctx, screen_pos)

    def on_scene_selection_changed(self, ctx: Any) -> None:
        # A viewport click may change host selection between press and release.
        # The release is the Folding authority, otherwise one physical click can
        # select a mesh and immediately be reused as the face click.
        if self._session.phase is not FoldingPhase.SELECT_MESH or self._pointer_press_screen is not None:
            return
        try:
            selected = ctx.scene_selection.selected_objects()
        except Exception:
            return
        if selected:
            self._select_targets(ctx, selected)

    def on_event(self, event: ToolEvent, ctx: Any) -> bool:
        if event.is_escape:
            self._pointer_press_screen = None
            self._mesh_hover.hide(ctx, render=False)
            self._session.clear_transient_hover()
            self._go_back(ctx)
            return True

        if event.type is ToolEventType.MOUSE_MOVE:
            if not self._camera_interaction_active and event.button is MouseButton.NONE:
                self._update_phase_hover(ctx, event.screen_pos, event=event)
            return False

        if self._session.phase is FoldingPhase.ADJUST_CURVE:
            return False

        if event.type is ToolEventType.MOUSE_PRESS and event.button is MouseButton.LEFT:
            # Direct API/tests reach this path. The Qt application normally calls
            # wants_pointer_press_passthrough() first.
            self._pointer_press_screen = event.screen_pos
            return False

        if event.type is not ToolEventType.MOUSE_RELEASE or event.button not in {MouseButton.LEFT, MouseButton.NONE}:
            return False
        if event.screen_pos is None:
            self._pointer_press_screen = None
            return False

        press = self._pointer_press_screen
        self._pointer_press_screen = None
        if press is not None:
            dx = abs(float(event.screen_pos[0]) - float(press[0]))
            dy = abs(float(event.screen_pos[1]) - float(press[1]))
            if max(dx, dy) > _CLICK_DRAG_THRESHOLD_PX:
                self._session.clear_transient_hover()
                self._renderer.sync(ctx)
                return False

        phase = self._session.phase
        if phase is FoldingPhase.SELECT_MESH:
            pick = ctx.pick.object_at(event.screen_pos)
            if not pick.hit:
                self._sync(ctx, "No mesh was found under the pointer. Hover until yellow edges appear, then click.", render=False)
                return True
            selected = self._selected_objects_containing_pick(ctx, pick)
            if selected:
                return self._select_targets(ctx, selected, primary_object_id=getattr(pick, "object_id", None))
            return self._select_target(ctx, pick.object_id, pick.object_index)

        if phase is FoldingPhase.SELECT_FACE:
            pick = ctx.pick.face_at(event.screen_pos)
            if not pick.hit or pick.world_pos is None or pick.normal is None:
                self._sync(ctx, "No face was found. Click a highlighted face of the selected mesh.", render=False)
                return True
            if not self._pick_matches_target(pick):
                self._sync(ctx, "That face belongs to another mesh. Choose a face on the blue outlined target.", render=False)
                return True
            try:
                self._session.plane = arbitrary_face_plane(pick.world_pos, pick.normal)
                self._session.plane_origin = tuple(float(v) for v in pick.world_pos)
                self._session.selected_face_index = pick.element_index
                self._session.selected_face_object_id = str(getattr(pick, "object_id", "") or "") or None
                self._session.selected_face_object_index = getattr(pick, "object_index", None)
                self._session.selected_face_vertices = self._face_vertices_for_pick(pick)
                self._session.hovered_face_index = None
                self._session.hovered_face_vertices = ()
            except Exception as exc:
                self._sync(ctx, f"This face cannot define a folding plane: {exc}", render=False)
                return True
            transition = self._machine.select_face()
            self._goto_workflow_phase(ctx)
            self._sync(ctx, transition.message)
            return True

        if phase in {FoldingPhase.PLACE_START, FoldingPhase.PLACE_END}:
            point = self._point_on_plane(ctx, event)
            if point is None:
                self._sync(ctx, "The point could not be projected onto the selected face plane.", render=False)
                return True
            self._session.hover_point = None
            if phase is FoldingPhase.PLACE_START:
                self._session.curve.start = point
                transition = self._machine.place_start()
            else:
                if self._session.curve.start is not None and math.dist(point, self._session.curve.start) <= 1.0e-4:
                    self._sync(ctx, "Start and end must be separated. Move the pointer farther along the face.", render=False)
                    return True
                self._session.curve.end = point
                try:
                    build_folding_frame(self._session.plane, self._session.curve)
                except Exception as exc:
                    self._session.curve.end = None
                    self._sync(ctx, str(exc), render=False)
                    return True
                transition = self._machine.place_end()
                self._schedule_preview(ctx)
            self._goto_workflow_phase(ctx)
            self._sync(ctx, transition.message)
            return True
        return False

    # ------------------------------------------------------------------
    # Native curve-handle interaction
    # ------------------------------------------------------------------
    def wants_native_actor_interaction(self, event: ToolEvent, ctx: Any) -> bool:  # noqa: ARG002
        return self._session.phase is FoldingPhase.ADJUST_CURVE

    def resolve_drag_positions(self, event: ToolEvent, ctx: Any) -> dict[str, Any] | None:
        if self._session.phase is not FoldingPhase.ADJUST_CURVE or self._session.plane is None or not self._session.curve.complete:
            return None
        grabbed = tuple(str(value) for value in getattr(ctx.selection.state, "grabbed_ids", ()) or ())
        handle_id = next((value for value in reversed(grabbed) if _is_control_id(value)), None)
        if handle_id is None or event.screen_pos is None:
            return None
        actor = ctx.selection.actor(handle_id)
        if actor is None:
            return None
        frame = build_folding_frame(self._session.plane, self._session.curve)

        if self._session.curve.is_living_hinge and (handle_id == "folding:angle" or handle_id.startswith("folding:shape:")):
            curve_plane = plane_from_origin_normal(frame.start, frame.bend_axis)
            hit = ctx.pick.plane_intersection(event.screen_pos, curve_plane)
            if not hit.hit or hit.world_pos is None:
                return None
            hit_point = tuple(float(v) for v in hit.world_pos)
            if handle_id == "folding:angle":
                self._session.curve.fold_angle_deg = normalized_fold_angle_deg(
                    fold_angle_from_handle(self._session.plane, self._session.curve, hit_point)
                )
                point = hinge_handle_point(self._session.plane, self._session.curve)
            else:
                shape_index = int(handle_id.rsplit(":", 1)[-1]) - 1
                shape_points = shape_handle_points(self._session.plane, self._session.curve)
                shape_normals = shape_handle_normals(self._session.plane, self._session.curve)
                if shape_index < 0 or shape_index >= len(shape_points):
                    return None
                current = shape_points[shape_index]
                direction = shape_normals[shape_index]
                delta_mm = sum((float(hit_point[i]) - float(current[i])) * float(direction[i]) for i in range(3))
                degrees_per_mm = 180.0 / max(8.0, frame.length_mm)
                values = list(self._session.curve.normalized_shape_angles())
                values[shape_index] = max(-270.0, min(270.0, float(values[shape_index]) + delta_mm * degrees_per_mm))
                self._session.curve.shape_angles_deg = tuple(values)
                point = shape_handle_points(self._session.plane, self._session.curve)[shape_index]
        else:
            hit = ctx.pick.plane_intersection(event.screen_pos, self._session.plane)
            if not hit.hit or hit.world_pos is None:
                return None
            index = 1 if handle_id.endswith(":1") else 2
            base_fraction = 1.0 / 3.0 if index == 1 else 2.0 / 3.0
            base = tuple(float(frame.start[i]) + float(frame.axis[i]) * frame.length_mm * base_fraction for i in range(3))
            delta = tuple(float(hit.world_pos[i]) - float(base[i]) for i in range(3))
            offset = sum(delta[i] * float(frame.bend_axis[i]) for i in range(3))
            point = tuple(float(base[i]) + float(frame.bend_axis[i]) * offset for i in range(3))
            if index == 1:
                self._session.curve.control_1_offset_mm = float(offset)
            else:
                self._session.curve.control_2_offset_mm = float(offset)

        self._session.dirty = True
        self._sync_curve_fields(ctx)
        try:
            return {handle_id: replace(actor, points=(point,))}
        except Exception:
            return None

    def _scheduled_preview_message(self) -> str:
        message = "Mesh update scheduled."
        if self._session.curve.is_living_hinge and abs(float(self._session.curve.fold_angle_deg)) > 180.0:
            message += " Over-fold: self-intersections are possible."
        return message

    def on_native_interaction_result(self, event: ToolEvent, ctx: Any, result: Any) -> None:  # noqa: ARG002
        action = str(getattr(result, "action", "") or "")
        grabbed = tuple(str(value) for value in getattr(result, "grabbed_ids", ()) or ())
        handles = tuple(value for value in grabbed if _is_control_id(value))
        if action in {"drag", "release"} and handles:
            self._renderer.sync_adjustment(ctx, render=action == "release")
            self._schedule_preview(ctx)
            if action == "release":
                self._sync(ctx, self._scheduled_preview_message(), render=False)

    def _update_phase_hover(
        self,
        ctx: Any,
        screen_pos: tuple[float, float] | None,
        *,
        event: ToolEvent | None = None,
    ) -> None:
        if screen_pos is None:
            return
        phase = self._session.phase
        if phase is FoldingPhase.SELECT_MESH:
            self._update_mesh_hover(ctx, screen_pos)
        elif phase is FoldingPhase.SELECT_FACE:
            self._mesh_hover.hide(ctx, render=False)
            self._update_face_hover(ctx, screen_pos)
        elif phase in {FoldingPhase.PLACE_START, FoldingPhase.PLACE_END}:
            self._mesh_hover.hide(ctx, render=False)
            previous_feedback = (
                self._session.hover_point,
                self._cursor_snap_kind,
                self._cursor_snap_label,
                self._cursor_snapped,
            )
            pointer_event = event or ToolEvent(ToolEventType.MOUSE_MOVE, screen_pos=screen_pos, button=MouseButton.NONE)
            point = self._point_on_plane(ctx, pointer_event)
            current_feedback = (
                point,
                self._cursor_snap_kind,
                self._cursor_snap_label,
                self._cursor_snapped,
            )
            if current_feedback != previous_feedback:
                self._session.hover_point = point
                self._sync_pointer_feedback(ctx, render=True)
        elif self._mesh_hover.visible:
            self._mesh_hover.hide(ctx, render=True)

    def _update_mesh_hover(self, ctx: Any, screen_pos: tuple[float, float]) -> None:
        try:
            pick = ctx.pick.object_at(screen_pos)
        except Exception:
            pick = None
        if pick is None or not bool(getattr(pick, "hit", False)):
            if self._mesh_hover.hide(ctx, render=True):
                self._session.hovered_object_id = None
                self._session.hovered_object_name = ""
            return
        obj = self._object_from_pick(ctx, pick)
        mesh = getattr(obj, "mesh", None) if obj is not None else None
        if mesh is None or not self._valid_mesh(mesh):
            self._mesh_hover.hide(ctx, render=True)
            return
        group_objects = self._objects_for_existing_group(ctx, obj)
        key_info = folding_group_info(mesh)
        key = str(key_info[0] if key_info is not None else (getattr(obj, "id", "") or getattr(mesh, "mesh_id", "") or "folding"))
        changed = self._mesh_hover.show(
            ctx,
            group_key=key,
            meshes=tuple(
                EditableHoverMesh(str(getattr(item, "id", "") or ""), getattr(item, "mesh", None))
                for item in group_objects
                if self._valid_mesh(getattr(item, "mesh", None))
            ),
            render=True,
        )
        if changed:
            self._session.hovered_object_id = key
            count = len(group_objects)
            self._session.hovered_object_name = (
                f"{count} meshes"
                if count > 1
                else str(getattr(obj, "name", "") or getattr(mesh, "name", "") or "Mesh")
            )
            suffix = " Click to reopen its existing Folding deformation." if has_folding_source(mesh) else " Click to start a new Folding deformation."
            self._session.status_message = f"Ready: {self._session.hovered_object_name}.{suffix}"
            self._workflow_overlay.sync(ctx, can_apply=self.can_apply(ctx))

    def _update_face_hover(self, ctx: Any, screen_pos: tuple[float, float]) -> None:
        try:
            pick = ctx.pick.face_at(screen_pos)
        except Exception:
            pick = None
        valid = bool(pick is not None and getattr(pick, "hit", False) and self._pick_matches_target(pick))
        face_index = getattr(pick, "element_index", None) if valid else None
        vertices = self._face_vertices_for_pick(pick) if valid else ()
        if face_index == self._session.hovered_face_index and vertices == self._session.hovered_face_vertices:
            return
        self._session.hovered_face_index = face_index
        self._session.hovered_face_vertices = vertices
        self._renderer.sync(ctx)

    @staticmethod
    def _valid_mesh(mesh: Any) -> bool:
        try:
            return len(getattr(mesh, "vertices", ())) >= 3 and len(getattr(mesh, "triangles", ())) >= 1
        except Exception:
            return False

    @staticmethod
    def _object_from_pick(ctx: Any, pick: Any) -> Any | None:
        try:
            if getattr(pick, "object_id", None) is not None:
                return ctx.document.get(str(pick.object_id))
            if getattr(pick, "object_index", None) is not None:
                return ctx.document.get(int(pick.object_index))
        except Exception:
            pass
        return None

    def _selected_objects_containing_pick(self, ctx: Any, pick: Any) -> tuple[Any, ...]:
        """Return the host multi-selection when the clicked mesh belongs to it."""

        try:
            selected = tuple(ctx.scene_selection.selected_objects())
        except Exception:
            return ()
        if len(selected) <= 1:
            return ()
        pick_id = str(getattr(pick, "object_id", "") or "")
        pick_index = getattr(pick, "object_index", None)
        for obj in selected:
            if pick_id and str(getattr(obj, "id", "") or "") == pick_id:
                return selected
            if pick_index is not None and int(getattr(obj, "index", -1)) == int(pick_index):
                return selected
        return ()

    def _objects_for_existing_group(self, ctx: Any, obj: Any) -> tuple[Any, ...]:
        info = folding_group_info(getattr(obj, "mesh", None))
        if info is None:
            return (obj,)
        group_id, member_ids, _member_index = info
        try:
            objects = tuple(ctx.document.objects(include_preview=False))
        except Exception:
            return (obj,)
        by_id = {str(item.id): item for item in objects}
        ordered = tuple(by_id[value] for value in member_ids if value in by_id)
        if ordered:
            return ordered
        scanned = tuple(
            item
            for item in objects
            if (folding_group_info(getattr(item, "mesh", None)) or (None, (), 0))[0] == group_id
        )
        return scanned or (obj,)

    def _source_mesh_for_target(self, *, object_id: str | None = None, object_index: int | None = None) -> Any | None:
        rows = self._session.target_rows()
        if object_id is not None:
            for row_id, _row_index, _name, mesh in rows:
                if str(row_id) == str(object_id):
                    return mesh
        if object_index is not None:
            for _row_id, row_index, _name, mesh in rows:
                if int(row_index) == int(object_index):
                    return mesh
        return rows[0][3] if rows else self._session.source_mesh

    def _face_vertices_for_pick(self, pick: Any) -> tuple[Point3, ...]:
        try:
            raw = dict(getattr(pick, "metadata", {}) or {}).get("face_vertices")
            if raw:
                return tuple(tuple(float(value) for value in point) for point in raw)
        except Exception:
            pass
        return self._face_vertices(
            getattr(pick, "element_index", None),
            object_id=getattr(pick, "object_id", None),
            object_index=getattr(pick, "object_index", None),
        )

    def _face_vertices(
        self,
        element_index: Any,
        *,
        object_id: str | None = None,
        object_index: int | None = None,
    ) -> tuple[Point3, ...]:
        mesh = self._source_mesh_for_target(object_id=object_id, object_index=object_index)
        if mesh is None or element_index is None:
            return ()
        try:
            triangle = tuple(int(v) for v in getattr(mesh, "triangles", ())[int(element_index)])
            vertices = getattr(mesh, "vertices", ())
            if len(triangle) != 3:
                return ()
            return tuple(tuple(float(value) for value in vertices[index]) for index in triangle)
        except Exception:
            return ()

    # ------------------------------------------------------------------
    # Target, preview and editing actions
    # ------------------------------------------------------------------
    def _select_target(self, ctx: Any, object_id: str | None, object_index: int | None) -> bool:
        try:
            if object_id is not None:
                obj = ctx.document.get(object_id)
            elif object_index is not None:
                obj = ctx.document.get(int(object_index))
            else:
                raise KeyError("No scene object was identified.")
        except Exception as exc:
            self._sync(ctx, f"The selected mesh could not be opened: {exc}", render=False)
            return True
        return self._select_targets(ctx, (obj,), primary_object_id=str(getattr(obj, "id", "") or ""))

    def _select_targets(
        self,
        ctx: Any,
        objects: Any,
        *,
        primary_object_id: str | None = None,
    ) -> bool:
        self._preview_debouncer.cancel()
        self._preview_signature = None
        self._mesh_hover.hide(ctx, render=False)
        unique: list[Any] = []
        seen_ids: set[str] = set()
        for obj in tuple(objects or ()):
            object_id = str(getattr(obj, "id", "") or "")
            if not object_id or object_id in seen_ids:
                continue
            seen_ids.add(object_id)
            unique.append(obj)
        if not unique:
            self._sync(ctx, "Select at least one valid mesh.", render=False)
            return True

        invalid = [str(getattr(obj, "name", "") or getattr(obj, "id", "") or "Mesh") for obj in unique if not self._valid_mesh(getattr(obj, "mesh", None))]
        if invalid:
            self._sync(ctx, f"These selected objects have no valid triangle mesh: {', '.join(invalid)}.", render=False)
            return True

        # Clicking one member of a previously applied group reopens the entire
        # group, even when only that member was selected in the scene.
        if len(unique) == 1:
            unique = list(self._objects_for_existing_group(ctx, unique[0]))

        if primary_object_id:
            unique.sort(key=lambda item: 0 if str(getattr(item, "id", "")) == str(primary_object_id) else 1)

        restored_rows = [(obj, restore_folding_source(obj.mesh), folding_group_info(obj.mesh)) for obj in unique]
        group_ids = {info[0] for _obj, restored, info in restored_rows if restored is not None and info is not None}
        all_restored = bool(restored_rows and all(restored is not None for _obj, restored, _info in restored_rows))
        editing_existing = bool(
            all_restored
            and (
                len(unique) == 1
                or (
                    len(group_ids) == 1
                    and all(info is not None for _obj, _restored, info in restored_rows)
                )
            )
        )

        if editing_existing:
            first_restored = restored_rows[0][1]
            assert first_restored is not None
            _first_source, plane, curve = first_restored
            source_meshes = tuple(copy.deepcopy(restored[0]) for _obj, restored, _info in restored_rows if restored is not None)
            group_id = next(iter(group_ids), "") or uuid.uuid4().hex
        else:
            plane = None
            curve = new_living_hinge_curve()
            source_meshes = tuple(copy.deepcopy(obj.mesh) for obj in unique)
            group_id = uuid.uuid4().hex

        object_ids = tuple(str(obj.id) for obj in unique)
        indices = tuple(int(obj.index) for obj in unique)
        names = tuple(str(obj.name) for obj in unique)
        primary = unique[0]

        self._session.clear_transient_hover()
        self._session.target_object_ids = object_ids
        self._session.target_indices = indices
        self._session.target_names = names
        self._session.source_meshes = source_meshes
        self._session.group_id = group_id
        self._session.target_object_id = str(primary.id)
        self._session.target_index = int(primary.index)
        self._session.target_name = str(primary.name) if len(unique) == 1 else f"{len(unique)} meshes"
        self._session.source_mesh = source_meshes[0]
        self._session.selected_face_index = None
        self._session.selected_face_object_id = None
        self._session.selected_face_object_index = None
        self._session.selected_face_vertices = ()
        self._session.preview_pending = False
        self._session.preview_ready = False
        if editing_existing:
            normalized_sources: list[Any] = []
            for obj, source_mesh in zip(unique, source_meshes):
                source_mesh.mesh_id = str(getattr(obj.mesh, "mesh_id", obj.id) or obj.id)
                source_mesh.name = str(getattr(obj.mesh, "name", obj.name) or obj.name)
                normalized_sources.append(source_mesh)
            self._session.source_meshes = tuple(normalized_sources)
            self._session.source_mesh = normalized_sources[0]
            self._session.plane = plane
            self._session.curve = curve
            self._session.plane_origin = curve.start
            self._session.editing_existing = True
            self._session.preview_ready = True
        else:
            self._session.plane = None
            self._session.plane_origin = None
            self._session.curve = curve
            self._session.editing_existing = False
        transition = self._machine.select_mesh()
        try:
            ctx.scene_selection.select_indices(indices, active_index=indices[0])
        except Exception:
            pass
        self._goto_workflow_phase(ctx)
        if len(unique) > 1:
            message = (
                f"{len(unique)} meshes loaded as one Folding group. "
                + ("Adjust the existing fold or Apply." if editing_existing else "Choose a face on any group member.")
            )
        else:
            message = transition.message
        self._sync(ctx, message)
        return True

    def _pick_matches_target(self, pick: Any) -> bool:
        if getattr(pick, "object_id", None) is not None:
            ids = set(self._session.target_object_ids or (() if self._session.target_object_id is None else (str(self._session.target_object_id),)))
            return str(pick.object_id) in ids
        if getattr(pick, "object_index", None) is not None:
            indices = set(self._session.target_indices or (() if self._session.target_index is None else (int(self._session.target_index),)))
            return int(pick.object_index) in indices
        return bool(self._session.target_rows())

    def _point_on_plane(self, ctx: Any, event: ToolEvent) -> Point3 | None:
        if self._session.plane is None:
            self._reset_cursor_snap_state()
            return None
        candidate: Point3 | None = None
        if event.screen_pos is not None:
            hit = ctx.pick.plane_intersection(event.screen_pos, self._session.plane)
            if hit.hit and hit.world_pos is not None:
                candidate = tuple(float(v) for v in hit.world_pos)
        if candidate is None and event.world_pos is not None:
            try:
                candidate = tuple(float(v) for v in clamp_world_point_to_plane(self._session.plane, event.world_pos))
            except Exception:
                pass
        if candidate is None:
            self._reset_cursor_snap_state()
            return None

        placement = candidate
        self._reset_cursor_snap_state()
        if event.screen_pos is not None:
            snap = plan2d.smart_snap_on_plan(
                ctx,
                owner_tool=self.id,
                plane=self._session.plane,
                candidate_world=candidate,
                screen_pos=event.screen_pos,
                exclude_ids=(_FOLDING_CURSOR_ID,),
            )
            if bool(getattr(snap, "snapped", False)):
                placement = tuple(float(v) for v in snap.world_pos)
            self._cursor_snap_kind = str(getattr(snap, "kind", "free") or "free")
            self._cursor_snap_label = str(getattr(snap, "label", "Free") or "Free")
            self._cursor_snapped = bool(getattr(snap, "snapped", False))

        # Match Plan Tracer: Shift constrains the second point to 45-degree
        # increments in the selected face plane.  Horizontal and vertical are
        # therefore easy to force while diagonal construction remains possible.
        if (
            self._session.phase is FoldingPhase.PLACE_END
            and bool(getattr(event, "shift", False))
            and self._session.curve.start is not None
        ):
            constraint = plan2d.constrain_angle_step_on_plan(
                self._session.plane,
                self._session.curve.start,
                placement,
                angle_step_degrees=45.0,
            )
            if bool(getattr(constraint, "applied", False)):
                placement = tuple(float(v) for v in constraint.world_pos)
                self._cursor_snap_kind = "angle"
                self._cursor_snap_label = str(getattr(constraint, "label", "Angle 45°") or "Angle 45°")
                self._cursor_snapped = True

        return tuple(float(v) for v in clamp_world_point_to_plane(self._session.plane, placement))

    def _reset_cursor_snap_state(self) -> None:
        self._cursor_snap_kind = "free"
        self._cursor_snap_label = "Free"
        self._cursor_snapped = False

    def _sync_pointer_feedback(self, ctx: Any, *, render: bool) -> None:
        """Render folding feedback and the official API-owned Plan 2D cursor."""

        self._renderer.sync(ctx, render=False)
        if (
            self._session.phase in {FoldingPhase.PLACE_START, FoldingPhase.PLACE_END}
            and self._session.hover_point is not None
        ):
            plan2d.register_plan_cursor(
                ctx,
                owner_tool=self.id,
                cursor_id=_FOLDING_CURSOR_ID,
                world_pos=self._session.hover_point,
                visible=True,
                snap_kind=self._cursor_snap_kind,
                snap_label=self._cursor_snap_label,
                snapped=self._cursor_snapped,
            )
            plan2d.sync_plan_actor_visuals(
                ctx,
                owner_tool=self.id,
                changed_actor_ids=(_FOLDING_CURSOR_ID,),
                position_only=False,
                render=render,
            )
            return
        ctx.projected_drawing.for_tool(self.id).render(render=render)

    def _curve_signature(self) -> tuple[Any, ...]:
        curve = self._session.curve
        return (
            tuple(str(value) for value in (self._session.target_object_ids or (() if self._session.target_object_id is None else (self._session.target_object_id,)))),
            str(self._session.group_id or ""),
            tuple(curve.start or ()),
            tuple(curve.end or ()),
            str(curve.mode),
            round(float(curve.fold_angle_deg), 9),
            curve.normalized_fixed_side(),
            curve.normalized_deformation_mode(),
            round(float(curve.control_1_offset_mm), 9),
            round(float(curve.control_2_offset_mm), 9),
            tuple(round(float(value), 9) for value in curve.normalized_shape_angles()),
        )

    def _schedule_preview(self, ctx: Any) -> None:
        if not self.can_apply(ctx):
            return
        self._session.preview_pending = True
        self._session.preview_ready = False
        self._preview_debouncer.schedule(ctx)

    def _on_preview_idle(self, ctx: Any) -> None:
        if self._ctx is not ctx or not self.can_apply(ctx):
            return
        self._session.preview_pending = False
        updated = self._update_preview(ctx, force=False)
        if updated or self._session.preview_ready:
            self._sync(ctx, "3D preview ready.", render=False)

    def flush_deferred_preview(self, ctx: Any | None = None) -> bool:
        """Run a pending idle preview immediately (also useful for headless tests)."""

        return self._preview_debouncer.flush(ctx or self._ctx)

    def _update_preview(self, ctx: Any, *, force: bool) -> bool:
        rows = self._session.target_rows()
        if not rows or self._session.plane is None or not self._session.curve.complete:
            return False
        signature = self._curve_signature()
        if (
            not force
            and signature == self._preview_signature
            and self._preview is not None
            and bool(getattr(self._preview, "active", False))
        ):
            self._session.preview_pending = False
            self._session.preview_ready = True
            return False
        try:
            member_ids = tuple(row[0] for row in rows)
            replacements: list[tuple[str, Any]] = []
            for member_index, (object_id, _object_index, object_name, source_mesh) in enumerate(rows):
                deformed = deform_mesh(source_mesh, self._session.plane, self._session.curve)
                deformed.mesh_id = str(getattr(source_mesh, "mesh_id", object_id) or object_id)
                if object_name:
                    deformed.name = object_name
                attach_folding_source(
                    deformed,
                    source_mesh=source_mesh,
                    plane=self._session.plane,
                    curve=self._session.curve,
                    group_id=self._session.group_id,
                    group_member_ids=member_ids,
                    group_member_index=member_index,
                )
                replacements.append((object_id, deformed))
            if self._preview is None or not bool(getattr(self._preview, "active", False)):
                self._preview = ctx.preview_session.start(owner_tool=self.id, label="Folding preview")
            self._preview.replace_objects_preview(replacements)
            self._preview_signature = signature
            self._session.last_preview_error = ""
            self._session.preview_pending = False
            self._session.preview_ready = True
            return True
        except Exception as exc:
            self._session.last_preview_error = str(exc)
            self._session.preview_pending = False
            self._session.preview_ready = False
            self._session.status_message = f"Preview failed: {exc}"
            self._workflow_overlay.sync(ctx, can_apply=False)
            ctx.status.error(self._session.status_message)
            return False

    def _on_value_changed(self, ctx: Any, field_id: str, value: Any) -> None:
        curve = self._session.curve
        if field_id == "folding_angle":
            curve.fold_angle_deg = normalized_fold_angle_deg(float(value))
        elif field_id == "folding_fixed_side":
            curve.fixed_side = FoldingFixedSide.END.value if str(value) == FoldingFixedSide.END.value else FoldingFixedSide.START.value
        elif field_id == "folding_deformation_mode":
            curve.deformation_mode = (
                FoldingDeformationMode.UNIFORM.value
                if str(value) == FoldingDeformationMode.UNIFORM.value
                else FoldingDeformationMode.PRESERVE_STRUCTURE.value
            )
        elif field_id == "folding_profile_detail":
            try:
                count = int(value)
            except (TypeError, ValueError):
                count = 3
            curve.shape_angles_deg = resample_shape_angles(curve.normalized_shape_angles(), count)
        elif field_id == "folding_control_1":
            curve.control_1_offset_mm = float(value)
        elif field_id == "folding_control_2":
            curve.control_2_offset_mm = float(value)
        else:
            return
        if self._session.phase is not FoldingPhase.ADJUST_CURVE:
            return
        self._session.dirty = True
        self._renderer.sync_adjustment(ctx)
        self._schedule_preview(ctx)
        self._sync(ctx, self._scheduled_preview_message(), render=False)

    def on_overlay_button_clicked(self, button_id: str, ctx: Any) -> None:
        action = self._workflow_overlay.action_from_button(button_id)
        if action is None:
            return
        if action == "apply":
            owner = getattr(ctx, "owner", None)
            callback = getattr(owner, "apply_preview_and_close_tool", None) if owner is not None else None
            if callable(callback):
                callback()
            else:
                self.on_apply(ctx)
            return
        if action == "cancel":
            owner = getattr(ctx, "owner", None)
            callback = getattr(owner, "discard_preview_and_close_tool", None) if owner is not None else None
            if callable(callback):
                callback()
            else:
                self.on_cancel(ctx)
            return
        self._on_action(ctx, action)

    def _on_action(self, ctx: Any, action_id: str) -> None:
        if action_id == "back":
            self._go_back(ctx)
            return
        if action_id == "restart":
            self._reset_workflow(ctx)
            return
        if self._session.phase is not FoldingPhase.ADJUST_CURVE:
            self._sync(ctx, "Finish defining the hinge first.", render=False)
            return
        curve = self._session.curve
        if action_id == "reset_shape":
            curve.shape_angles_deg = tuple(0.0 for _ in curve.normalized_shape_angles())
        elif action_id == "straighten":
            if curve.is_living_hinge:
                curve.fold_angle_deg = 0.0
                curve.shape_angles_deg = tuple(0.0 for _ in curve.normalized_shape_angles())
            else:
                curve.control_1_offset_mm = 0.0
                curve.control_2_offset_mm = 0.0
        elif action_id == "invert":
            if curve.is_living_hinge:
                curve.fold_angle_deg *= -1.0
                curve.shape_angles_deg = tuple(-float(value) for value in curve.normalized_shape_angles())
            else:
                curve.control_1_offset_mm *= -1.0
                curve.control_2_offset_mm *= -1.0
        elif action_id == "swap_side":
            curve.fixed_side = FoldingFixedSide.END.value if curve.normalized_fixed_side() == FoldingFixedSide.START.value else FoldingFixedSide.START.value
        else:
            return
        self._session.dirty = True
        self._sync_curve_fields(ctx)
        self._renderer.sync_adjustment(ctx)
        self._schedule_preview(ctx)
        self._sync(ctx, self._scheduled_preview_message(), render=False)

    def _reset_workflow(self, ctx: Any) -> None:
        self._preview_debouncer.cancel()
        self._cancel_preview()
        self._preview_signature = None
        self._mesh_hover.hide(ctx, render=False)
        self._session.reset(keep_applied_state=True)
        self._machine = FoldingWorkflowMachine(self._session)
        self._goto_workflow_phase(ctx)
        self._renderer.clear(ctx)
        self._sync(ctx, "Yellow outline: select one or more meshes, then click a highlighted mesh.", render=False)

    def _go_back(self, ctx: Any) -> None:
        self._preview_debouncer.cancel()
        self._session.preview_pending = False
        if self._session.phase is FoldingPhase.SELECT_MESH:
            self._sync(ctx, "Use Cancel to close Folding.", render=False)
            return
        if self._session.phase is FoldingPhase.ADJUST_CURVE:
            self._cancel_preview()
        transition = self._machine.back()
        self._goto_workflow_phase(ctx)
        self._renderer.sync(ctx)
        self._sync(ctx, transition.message, render=False)

    def _cancel_preview(self) -> None:
        self._preview_debouncer.cancel()
        if self._preview is not None and bool(getattr(self._preview, "active", False)):
            try:
                self._preview.cancel()
            except Exception:
                pass
        self._preview = None
        self._preview_signature = None
        self._session.preview_pending = False
        self._session.preview_ready = False

    def _register_workflow(self, ctx: Any) -> None:
        ctx.workflow.clear(self.id)
        ctx.workflow.start(
            self.id,
            (
                ctx.workflow.require_scene_object("mesh", "Select mesh", help="Hover for yellow edges, then click the mesh."),
                ctx.workflow.require_face("face", "Select face", help="Choose the face that contains the living hinge."),
                ctx.workflow.step("start", "Place first limit", requirement="point", help="Place the first boundary of the flexible band."),
                ctx.workflow.step("end", "Place second limit", requirement="point", help="Place the second boundary of the flexible band."),
                ctx.workflow.require_tool_actor("curve", "Adjust fold", help="Drag the purple shape handles or set the terminal angle. The 3D mesh updates after a short idle delay."),
            ),
        )

    def _goto_workflow_phase(self, ctx: Any) -> None:
        try:
            ctx.workflow.goto(_PHASE_WORKFLOW_IDS[self._session.phase])
        except Exception:
            pass

    def _sync_curve_fields(self, ctx: Any) -> None:
        curve = self._session.curve
        ready = self._session.phase is FoldingPhase.ADJUST_CURVE
        living = curve.is_living_hinge
        try:
            ctx.inspector.update_value("folding_angle", float(curve.fold_angle_deg), notify=False)
            ctx.inspector.update_value("folding_fixed_side", curve.normalized_fixed_side(), notify=False)
            ctx.inspector.update_value("folding_deformation_mode", curve.normalized_deformation_mode(), notify=False)
            ctx.inspector.update_value("folding_profile_detail", str(curve.shape_control_count), notify=False)
            ctx.inspector.update_value("folding_control_1", curve.control_1_offset_mm, notify=False)
            ctx.inspector.update_value("folding_control_2", curve.control_2_offset_mm, notify=False)
            ctx.inspector.set_visible("folding_angle", ready and living)
            ctx.inspector.set_visible("folding_fixed_side", ready and living)
            ctx.inspector.set_visible("folding_deformation_mode", ready and living)
            ctx.inspector.set_visible("folding_profile_detail", ready and living)
            ctx.inspector.set_visible("folding_length", ready and living)
            ctx.inspector.set_visible("folding_preview_state", ready)
            ctx.inspector.set_visible("folding_control_1", ready and not living)
            ctx.inspector.set_visible("folding_control_2", ready and not living)
        except Exception:
            pass

    def _sync(self, ctx: Any, message: str, *, render: bool = True) -> None:
        session = self._session
        session.status_message = str(message)
        try:
            self._sync_curve_fields(ctx)
            ready = session.phase is FoldingPhase.ADJUST_CURVE
            living = session.curve.is_living_hinge
            ctx.inspector.set_enabled("folding_angle", ready and living)
            ctx.inspector.set_enabled("folding_fixed_side", ready and living)
            ctx.inspector.set_enabled("folding_deformation_mode", ready and living)
            ctx.inspector.set_enabled("folding_profile_detail", ready and living)
            ctx.inspector.set_enabled("folding_control_1", ready and not living)
            ctx.inspector.set_enabled("folding_control_2", ready and not living)
            if session.plane is not None and session.curve.complete:
                frame = build_folding_frame(session.plane, session.curve)
                ctx.inspector.set_display_value("folding_length", f"{frame.length_mm:.3f} mm")
            else:
                ctx.inspector.set_display_value("folding_length", "Not defined")
            if session.last_preview_error:
                preview_state = "Error"
            elif session.preview_pending:
                preview_state = "Waiting 1.5 s"
            elif session.preview_ready:
                preview_state = "Up to date"
            else:
                preview_state = "Not generated"
            ctx.inspector.set_display_value("folding_preview_state", preview_state)
        except Exception:
            pass
        if render:
            self._sync_pointer_feedback(ctx, render=True)
        self._workflow_overlay.sync(ctx, can_apply=self.can_apply(ctx))
        ctx.status.info(message)


class FoldingTool(CreatorStudioToolAdapter):
    def __init__(self, spec: ToolSpec):
        super().__init__(spec=spec, creator=FoldingCreatorTool())


__all__ = ["FoldingCreatorTool", "FoldingTool"]

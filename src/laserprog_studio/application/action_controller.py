# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from ..app_context import AppContext
from ..services.geometry import bounds_axis_size, translated_mesh_copies
from ..studio_log import log_exception


class WindowController:
    """Small base for application controllers owned by the main window.

    The architecture target is composition: the Qt window owns explicit
    controllers instead of inheriting every behavior through mixins.  The base
    intentionally exposes only the shared AppContext and a few UI helpers so
    future passes can tighten controller dependencies from one place.
    """

    def __init__(self, context: AppContext):
        self.context = context

    @property
    def owner(self) -> Any:
        return self.context.owner

    def ui_log(self, message: str) -> None:
        self.context.ui_log(message)

    def status_message(self, message: str, timeout_ms: int = 1800) -> None:
        try:
            status_bar = self.owner.statusBar()
            if status_bar is not None:
                status_bar.showMessage(message, int(timeout_ms))
        except Exception:
            pass


class HistoryController(WindowController):
    """Undo/redo orchestration kept outside the Qt inheritance chain."""

    def undo_scene(self) -> None:
        """Undo one committed scene action."""
        w = self.owner
        try:
            if w.mesh_store is None:
                return
            if not w._history_tools_available():
                self.status_message("Undo disabled while a tool/preview is active", 2000)
                return
            ok = w.mesh_store.undo(max_redo=int(getattr(w, "_history_limit", 10)))
            if not ok:
                w.ui_log("[UNDO] Nothing to undo")
                w._sync_history_buttons()
                return
            w.selected_indices = []
            w.active_index = None
            w._clear_gizmo_interaction(clear_highlight=True)
            w._clear_gizmo_actors()
            w.rebuild_scene(keep_camera=True)
            w.update_preview_state()
            try:
                from ..project import mark_project_dirty
                mark_project_dirty(w)
            except Exception:
                pass
            w.ui_log("[UNDO] Scene restored to previous action")
        except Exception:
            log_exception("undo_scene")

    def redo_scene(self) -> None:
        """Redo one undone scene action."""
        w = self.owner
        try:
            if w.mesh_store is None:
                return
            if not w._history_tools_available():
                self.status_message("Redo disabled while a tool/preview is active", 2000)
                return
            ok = w.mesh_store.redo(max_undo=int(getattr(w, "_history_limit", 10)))
            if not ok:
                w.ui_log("[REDO] Nothing to redo")
                w._sync_history_buttons()
                return
            w.selected_indices = []
            w.active_index = None
            w._clear_gizmo_interaction(clear_highlight=True)
            w._clear_gizmo_actors()
            w.rebuild_scene(keep_camera=True)
            w.update_preview_state()
            try:
                from ..project import mark_project_dirty
                mark_project_dirty(w)
            except Exception:
                pass
            w.ui_log("[REDO] Scene restored to next action")
        except Exception:
            log_exception("redo_scene")

    def capture_drag_undo_snapshot(self) -> None:
        w = self.owner
        try:
            if w.mesh_store is not None and not w.has_preview():
                w._drag_undo_snapshot = w.mesh_store.snapshot()
            else:
                w._drag_undo_snapshot = None
        except Exception:
            w._drag_undo_snapshot = None

    def commit_drag_undo_snapshot(self, reason: str) -> None:
        w = self.owner
        try:
            snap = getattr(w, "_drag_undo_snapshot", None)
            w._drag_undo_snapshot = None
            if snap is None or w.mesh_store is None:
                return
            meshes, source_path = snap
            pushed = w.mesh_store.push_undo_snapshot(
                meshes,
                source_path,
                max_undo=int(getattr(w, "_history_limit", 10)),
            )
            if pushed:
                try:
                    from ..project import mark_project_dirty
                    mark_project_dirty(w)
                except Exception:
                    pass
                w.ui_log(f"[UNDO] Snapshot stored: {reason}")
            w._sync_history_buttons()
        except Exception:
            log_exception("commit_drag_undo_snapshot")


class ClipboardController(WindowController):
    """Copy/paste/duplicate workflows as a composable application controller."""

    def _clipboard_meshes(self) -> list[Any]:
        """Return the application clipboard meshes, with window fallback."""
        try:
            state = getattr(self.context, "clipboard", None)
            meshes = list(getattr(state, "meshes", []) or []) if state is not None else []
            if meshes:
                return meshes
        except Exception:
            pass
        return list(getattr(self.owner, "_copy_buffer_meshes", []) or [])

    def _set_clipboard_meshes(self, meshes: list[Any]) -> None:
        """Store copied meshes in the scene-independent application clipboard."""
        copies = [copy.deepcopy(mesh) for mesh in meshes]
        try:
            state = getattr(self.context, "clipboard", None)
            if state is not None:
                state.meshes = [copy.deepcopy(mesh) for mesh in copies]
        except Exception:
            pass
        try:
            self.owner._copy_buffer_meshes = [copy.deepcopy(mesh) for mesh in copies]
        except Exception:
            pass

    def blocked_message(self, action_name: str) -> bool:
        w = self.owner
        try:
            active_tool = getattr(w, "active_tool", None)
            tool_none = getattr(w, "TOOL_NONE", None)
            has_preview = bool(w.has_preview())
            blocked = active_tool != tool_none or has_preview
            w.ui_log(
                f"[CLIPBOARD_DIAG] blocked_check action={action_name} "
                f"active_tool={active_tool!r} tool_none={tool_none!r} has_preview={has_preview} blocked={blocked}"
            )
            if blocked:
                w.ui_log(f"[CLIPBOARD] {action_name} blocked during active tool/preview")
                return True
        except Exception:
            log_exception(f"clipboard_blocked_message/{action_name}")
            return True
        return False

    @staticmethod
    def bounds_axis_size(bounds: tuple[float, float, float, float, float, float], axis: str) -> float:
        return bounds_axis_size(bounds, axis)

    def camera_duplicate_delta(self, bounds: tuple[float, float, float, float, float, float]) -> tuple[tuple[float, float, float], str, float]:
        """Return a visible copy offset based on the current camera view."""
        w = self.owner
        try:
            import numpy as np

            right, up_screen, forward = w._camera_basis()
            world_axes = {
                "x": np.asarray((1.0, 0.0, 0.0), dtype=float),
                "y": np.asarray((0.0, 1.0, 0.0), dtype=float),
                "z": np.asarray((0.0, 0.0, 1.0), dtype=float),
            }
            best_axis = "x"
            best_score = -1.0e9
            for key, vec in world_axes.items():
                right_score = abs(float(np.dot(vec, right)))
                up_score = abs(float(np.dot(vec, up_screen))) * 0.12
                depth_penalty = abs(float(np.dot(vec, forward))) * 0.75
                score = right_score + up_score - depth_penalty
                if score > best_score:
                    best_axis = key
                    best_score = score
            vec = world_axes[best_axis]
            sign = float(np.dot(vec, right))
            if abs(sign) < 1.0e-6:
                sign = float(np.dot(vec, up_screen))
            if sign < 0.0:
                vec = -vec
            dist = 2.0 * max(self.bounds_axis_size(bounds, best_axis), 1.0)
            delta = vec * dist
            return (float(delta[0]), float(delta[1]), float(delta[2])), best_axis, float(dist)
        except Exception:
            size = 2.0 * max(self.bounds_axis_size(bounds, "x"), 1.0)
            return (float(size), 0.0, 0.0), "x", float(size)

    def copy_meshes_with_view_offset(self, source_meshes: list[Any]) -> tuple[list[Any], tuple[float, float, float], str, float]:
        w = self.owner
        vertices = [
            (float(x), float(y), float(z))
            for mesh in source_meshes
            for x, y, z in getattr(mesh, "vertices", [])
        ]
        bounds = w._bounds_from_vertices_list(vertices)
        delta, axis, dist = self.camera_duplicate_delta(bounds)
        try:
            w.ui_log(
                f"[CLIPBOARD_DIAG] copy_offset source_meshes={len(source_meshes)} vertices={len(vertices)} "
                f"bounds=({bounds[0]:.3f},{bounds[1]:.3f},{bounds[2]:.3f},{bounds[3]:.3f},{bounds[4]:.3f},{bounds[5]:.3f}) "
                f"axis={axis} dist={float(dist):.3f} delta=({float(delta[0]):.3f},{float(delta[1]):.3f},{float(delta[2]):.3f})"
            )
        except Exception:
            pass
        out = translated_mesh_copies(source_meshes, delta)
        return out, delta, axis, dist

    def copy_selected(self) -> None:
        w = self.owner
        w.ui_log(f"[CLIPBOARD_DIAG] copy_selected begin raw_selected={list(getattr(w, 'selected_indices', []))} active={getattr(w, 'active_index', None)}")
        indices = w._selected_transform_indices()
        if not indices:
            w.ui_log("[CLIPBOARD] Copy: no selected part")
            return
        meshes = w.current_meshes()
        valid = [i for i in indices if 0 <= int(i) < len(meshes)]
        if not valid:
            w.ui_log("[CLIPBOARD] Copy: no valid selected part")
            return
        self._set_clipboard_meshes([meshes[int(i)] for i in valid])
        w.ui_log(f"[CLIPBOARD] Copied {len(valid)} part(s): {valid}")
        w.ui_log(f"[CLIPBOARD_DIAG] copy_selected end buffer={len(self._clipboard_meshes())} names={[getattr(meshes[int(i)], 'name', '?') for i in valid]}")

    def paste_selection(self) -> None:
        w = self.owner
        clipboard_meshes = self._clipboard_meshes()
        w.ui_log(f"[CLIPBOARD_DIAG] paste_selection begin buffer={len(clipboard_meshes)} meshes={len(w.current_meshes())} raw_selected={list(getattr(w, 'selected_indices', []))}")
        if self.blocked_message("Paste"):
            return
        if not clipboard_meshes:
            w.ui_log("[CLIPBOARD] Paste: buffer empty")
            return
        try:
            meshes = [copy.deepcopy(m) for m in w.current_meshes()]
            new_meshes, delta, axis, dist = self.copy_meshes_with_view_offset(clipboard_meshes)
            new_indices: list[int] = []
            for mesh in new_meshes:
                try:
                    from laserprog_studio.domain.work_model import reset_mesh_id

                    reset_mesh_id(mesh)
                except Exception:
                    pass
                base_name = str(getattr(mesh, "name", "part"))
                if not base_name.endswith("_copy"):
                    mesh.name = base_name + "_copy"
                meshes.append(mesh)
                new_indices.append(len(meshes) - 1)
            self._set_clipboard_meshes(new_meshes)
            w.selected_indices = new_indices
            w.active_index = new_indices[-1] if new_indices else None
            w.ui_log(f"[CLIPBOARD_DIAG] paste_selection new_indices={new_indices} meshes_after={len(meshes)}")
            w.push_meshes(meshes, f"Paste {len(new_indices)} part(s), axis={axis}, offset={dist:.3f}, delta={delta}", semantic_operation_type="paste")
        except Exception:
            log_exception("paste_selection")

    def duplicate_selected(self) -> None:
        w = self.owner
        w.ui_log(f"[CLIPBOARD_DIAG] duplicate_selected begin meshes={len(w.current_meshes())} raw_selected={list(getattr(w, 'selected_indices', []))} active={getattr(w, 'active_index', None)}")
        if self.blocked_message("Duplicate"):
            return
        indices = w._selected_transform_indices()
        if not indices:
            w.ui_log("[DUPLICATE] No selected part")
            return
        try:
            meshes = [copy.deepcopy(m) for m in w.current_meshes()]
            valid = [i for i in indices if 0 <= int(i) < len(meshes)]
            if not valid:
                w.ui_log("[DUPLICATE] No valid selected part")
                return
            source = [copy.deepcopy(meshes[int(i)]) for i in valid]
            new_meshes, delta, axis, dist = self.copy_meshes_with_view_offset(source)
            new_indices: list[int] = []
            for mesh in new_meshes:
                try:
                    from laserprog_studio.domain.work_model import reset_mesh_id

                    reset_mesh_id(mesh)
                except Exception:
                    pass
                mesh.name = str(getattr(mesh, "name", "part")) + "_copy"
                meshes.append(mesh)
                new_indices.append(len(meshes) - 1)
            w.selected_indices = new_indices
            w.active_index = new_indices[-1] if new_indices else None
            w.ui_log(f"[CLIPBOARD_DIAG] duplicate_selected valid={valid} new_indices={new_indices} meshes_after={len(meshes)}")
            w.push_meshes(meshes, f"Duplicate selection {valid}, axis={axis}, offset={dist:.3f}, delta={delta}", semantic_operation_type="duplicate")
        except Exception:
            log_exception("duplicate_selected")


class SceneEditController(WindowController):
    """Scene-level edit commands independent from the Qt mixin hierarchy."""

    def clear_transform_drag_state(self) -> bool:
        """Clear transient transform/gizmo state and report whether a drag was active."""
        w = self.owner
        was_dragging = getattr(w, "_drag_axis", None) is not None or getattr(w, "_gizmo_pressed_axis", None) is not None
        w._gizmo_pressed_axis = None
        w._gizmo_press_pos = None
        w._drag_axis = None
        w._drag_transform_mode = None
        w._drag_mesh_index = None
        w._drag_mesh_indices = []
        w._drag_start_qpos = None
        w._drag_start_vertices = None
        w._drag_start_vertices_by_index = {}
        w._drag_start_rotation_state_by_index = {}
        w._drag_axis_origin = None
        w._drag_axis_vector = None
        w._drag_axis_screen = None
        w._drag_rotation_center = None
        w._drag_rotation_last_vector = None
        w._drag_rotation_accum_angle = 0.0
        w._drag_rotation_applied_angle = 0.0
        w._drag_start_rotation_quat = None
        w._drag_start_rotation_euler = None
        w._gizmo_delta_display_signature = None
        w._drag_scale_bounds = None
        w._drag_scale_pivot = None
        w._drag_scale_factor = 1.0
        w._drag_undo_snapshot = None
        return was_dragging

    def delete_selected(self) -> None:
        w = self.owner
        indices = w._selected_transform_indices()
        if not indices:
            w.ui_log("[DELETE] No selected part")
            return
        delete_set = set(indices)
        was_dragging = self.clear_transform_drag_state()
        meshes = [copy.deepcopy(m) for i, m in enumerate(w.current_meshes()) if i not in delete_set]
        w.selected_indices = []
        w.active_index = None
        w.push_meshes(meshes, f"Delete selection {indices}", semantic_operation_type="delete")
        if was_dragging:
            w.ui_log("[TRANSFORM] Deleted dragged selection, kept current transform mode")

    def new_scene(self) -> None:
        """Create a new empty scene inside the current project."""
        w = self.owner
        try:
            from ..project import ensure_project_store, sync_window_to_active_scene

            if callable(getattr(w, "close_active_tool", None)):
                w.close_active_tool(log_it=False, ask_preview=True)
                if getattr(w, "active_tool", getattr(w, "TOOL_NONE", None)) != getattr(w, "TOOL_NONE", None):
                    return
            project = ensure_project_store(w)
            scene = project.create_scene("Scene", meshes=[], make_active=True, mark_dirty=True)
            sync_window_to_active_scene(w)
            w.selected_indices = []
            w.active_index = None
            try:
                w.render_camera_state = None
                w._remove_render_camera_helper(render=False)
            except Exception:
                pass
            w.rebuild_scene(keep_camera=False)
            w._sync_history_buttons()
            try:
                w.sync_scene_tabs()
                w.update_project_title()
            except Exception:
                pass
            w.ui_log(f"[PROJECT] New empty scene '{scene.name}'")
        except Exception:
            log_exception("new_scene")


@dataclass(slots=True)
class StudioActionController:
    """Composition root for first migrated application commands."""

    context: AppContext
    history: HistoryController
    clipboard: ClipboardController
    scene_edit: SceneEditController
    project: Any

    @classmethod
    def create(cls, context: AppContext) -> "StudioActionController":
        from .project_controller import ProjectController

        return cls(
            context=context,
            history=HistoryController(context),
            clipboard=ClipboardController(context),
            scene_edit=SceneEditController(context),
            project=ProjectController.create(context),
        )

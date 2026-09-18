# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from ..app_context import AppContext
from ..geometry_ops import OperationResult
from ..studio_log import log_exception
from .action_controller import WindowController


class PreviewController(WindowController):
    """Own the preview session lifecycle outside the MainWindow mixin chain.

    Geometry tools may still live in controller layers, but they now stage,
    commit and discard preview meshes through this composed controller.  It is
    the future seam for headless tool execution, command history and preview
    validation.
    """

    @classmethod
    def create(cls, context: AppContext) -> "PreviewController":
        return cls(context)

    def ensure_model_store(self) -> Any:
        w = self.owner
        if w.mesh_store is None:
            from laserprog_studio.domain.work_model import ModelStore
            from ..project import replace_active_model_store

            replace_active_model_store(w, ModelStore(), mark_dirty=False)
        return w.mesh_store

    def has_preview(self) -> bool:
        w = self.owner
        return bool(w.mesh_store is not None and w.mesh_store.has_preview)

    def update_state(self) -> None:
        w = self.owner
        active_preview = self.has_preview()
        tool_active = w.active_tool != w.TOOL_NONE
        planar_ready = False
        planar = getattr(w, "planar_tool_controller", None)
        if planar is not None and callable(getattr(planar, "has_applyable_draft", None)):
            try:
                planar_ready = bool(planar.has_applyable_draft())
            except Exception:
                planar_ready = False
        creator_ready = False
        if tool_active and not bool(active_preview or planar_ready):
            try:
                from ..tooling.registry import get_studio_tool

                tool = get_studio_tool(w.active_tool)
                can_apply = getattr(tool, "can_apply", None)
                if callable(can_apply):
                    creator_ready = bool(can_apply(getattr(w, "context", None)))
            except Exception:
                creator_ready = False
        apply_ready = bool(active_preview or planar_ready or creator_ready)
        if tool_active:
            suffix = " - changes ready" if apply_ready else " - no changes"
            w.preview_label.setText(f"{w._tool_display_name()}{suffix}")
        else:
            w.preview_label.setText("")
        w.btn_apply_preview.setVisible(tool_active)
        w.btn_cancel_preview.setVisible(tool_active)
        w.btn_apply_preview.setEnabled(apply_ready)
        w.btn_cancel_preview.setEnabled(tool_active)
        try:
            tool_box = getattr(w, "tool_box", None)
            if tool_box is not None:
                tool_box.setVisible(tool_active)
            idle_panel = getattr(w, "tool_idle_panel", None)
            if idle_panel is not None:
                idle_panel.setVisible(not tool_active)
            w.tool_panel_stack.setVisible(tool_active)
            if not tool_active:
                w.tool_panel_stack.setCurrentIndex(0)
        except Exception:
            pass
        try:
            history_button = getattr(w, "btn_scene_history", None)
            if history_button is not None:
                history_button.setVisible(not tool_active)
                history_button.setEnabled(not tool_active)
        except Exception:
            pass
        help_controller = getattr(w, "tool_help_controller", None)
        if help_controller is not None and callable(getattr(help_controller, "update_button_state", None)):
            help_controller.update_button_state()
        w._sync_transform_buttons()
        w._sync_boolean_buttons()
        w._sync_modifier_buttons()
        w._sync_history_buttons()
        w._schedule_light_transform_overlay_sync("tool/preview state")

    def set_meshes(self, meshes: list[Any], reason: str) -> None:
        w = self.owner
        store = self.ensure_model_store()
        store.set_preview_meshes(meshes, source_path=getattr(store, "source_path", None))
        try:
            self.context.preview.reason = str(reason)
            self.context.tool.preview_reason = str(reason)
        except Exception:
            pass
        w.ui_log(f"[PREVIEW] {reason} | meshes={len(meshes)}")
        w.rebuild_scene(keep_camera=True)
        self.update_state()
        w._sync_history_buttons()

    def set_result(self, result: OperationResult, reason: str) -> bool:
        """Display a geometry operation result through the standard preview path."""
        w = self.owner
        for warning in result.warnings:
            w.ui_log(f"[PREVIEW][WARN] {warning}")
        if not result.ok:
            for error in result.errors:
                w.ui_log(f"[PREVIEW][ERROR] {error}")
            return False
        self.set_meshes(result.meshes, reason)
        return True

    def commit_to_model(self, reason: str, *, rebuild: bool = True, operation_type: str | None = "tool_apply") -> bool:
        w = self.owner
        if w.mesh_store is None or not self.has_preview():
            return False
        ok = w.mesh_store.commit_preview(max_undo=int(getattr(w, "_history_limit", 10)))
        try:
            self.context.preview.clear()
            self.context.tool.preview_reason = None
        except Exception:
            pass
        if ok:
            if operation_type:
                try:
                    project = getattr(w, "project_store", None)
                    scene = getattr(project, "active_scene", None) if project is not None else None
                    if scene is not None:
                        scene.record_modification(str(reason), str(operation_type), capture_snapshot=True)
                except Exception:
                    log_exception("record_preview_semantic_history")
            try:
                from ..project import mark_project_dirty

                mark_project_dirty(w)
            except Exception:
                pass
        w.ui_log(f"[PREVIEW] {reason} -> {ok}")
        if rebuild:
            w.rebuild_scene(keep_camera=True)
            self.update_state()
            w._sync_history_buttons()
        return bool(ok)


    def commit_preview_to_new_scene(self, reason: str, *, scene_name: str | None = None, operation_type: str = "scene_generated") -> bool:
        """Commit the current preview into a new active scene, leaving the source scene intact.

        This is used by tools such as Lay Flat: Apply opens the result in a
        fresh scene instead of replacing the active one, then the scene tabs are
        synchronized to show that new active scene.
        """
        w = self.owner
        if w.mesh_store is None or not self.has_preview():
            return False
        try:
            import copy
            from ..project import ensure_project_store, sync_window_to_active_scene

            project = ensure_project_store(w)
            source_scene = project.active_scene
            preview_meshes = copy.deepcopy(w.mesh_store.preview_meshes or [])
            if not preview_meshes:
                return False
            if str(operation_type) == "layflat":
                try:
                    from ..engraving.roles import apply_default_outline_to_unassigned

                    changed_roles = apply_default_outline_to_unassigned(preview_meshes)
                    if changed_roles:
                        w.ui_log(f"[LAYFLAT] Default outline role assigned at Apply: {changed_roles}")
                except Exception:
                    log_exception("layflat_apply_default_outline")
            name = scene_name or f"{source_scene.name} - result"
            new_scene = project.create_scene(name, meshes=preview_meshes, make_active=True, mark_dirty=True, fresh_mesh_ids=False)
            new_scene.record_modification(reason, operation_type, capture_snapshot=True, metadata={"source_scene_id": source_scene.scene_id})
            # Clear the source preview without modifying its committed meshes.
            source_scene.model_store.discard_preview()
            sync_window_to_active_scene(w)
            try:
                self.context.preview.clear()
                self.context.tool.preview_reason = None
            except Exception:
                pass
            w.selected_indices = []
            w.active_index = None
            w.ui_log(f"[PREVIEW] {reason} -> new scene '{new_scene.name}'")
            w.rebuild_scene(keep_camera=True)
            self.update_state()
            w._sync_history_buttons()
            try:
                w.sync_scene_tabs()
            except Exception:
                pass
            return True
        except Exception:
            log_exception("commit_preview_to_new_scene")
            return False

    def discard_only(self, reason: str) -> None:
        w = self.owner
        if w.mesh_store is not None and w.mesh_store.has_preview:
            ok = w.mesh_store.discard_preview()
            try:
                self.context.preview.clear()
                self.context.tool.preview_reason = None
            except Exception:
                pass
            w.ui_log(f"[PREVIEW] Discarded ({reason}) -> {ok}")
            w.rebuild_scene(keep_camera=True)
            self.update_state()
            w._sync_history_buttons()

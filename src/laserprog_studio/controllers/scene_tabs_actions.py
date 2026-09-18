# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class SceneTabsActionLayer:

    def move_scene_tab_to_index(self, source_scene_id: str, target_index: int) -> None:
            """Move a scene tab to any position in the current tab strip."""
            try:
                project = getattr(self, "project_store", None)
                source_scene_id = str(source_scene_id or "")
                if project is None or not source_scene_id or source_scene_id not in getattr(project, "scenes", {}):
                    return
                # Drag/drop computes insertion indexes in the live strip, before the
                # dragged tab is removed.  Dropping before the source or just after
                # the source keeps the same visual order and must not force a tab
                # strip rebuild, otherwise the dragged tab can appear to disappear.
                if self._scene_tab_live_index_is_noop(source_scene_id, int(target_index)):
                    return
                adjusted_index = int(target_index)
                order = self._scene_order_ids()
                try:
                    source_index = order.index(source_scene_id)
                    if source_index < adjusted_index:
                        adjusted_index -= 1
                except Exception:
                    pass
                project.move_scene_to_index(source_scene_id, adjusted_index)
                try:
                    import time

                    self._last_project_activity_monotonic = time.monotonic()
                    if getattr(self, "_project_dirty_since_monotonic", None) is None:
                        self._project_dirty_since_monotonic = self._last_project_activity_monotonic
                except Exception:
                    pass
                self.sync_scene_tabs()
                try:
                    self.ui_log("[SCENE] Reordered scene tabs")
                except Exception:
                    pass
            except Exception:
                log_exception("move_scene_tab_to_index")
                try:
                    self.sync_scene_tabs()
                except Exception:
                    pass

    def switch_scene_by_id(self, scene_id: str) -> None:
            """Switch active scene from either the hidden QTabBar or visible tab strip."""
            try:
                project = getattr(self, "project_store", None)
                scene_id = str(scene_id or "")
                if project is None or not scene_id or scene_id == str(getattr(project, "active_scene_id", "") or ""):
                    return
                if scene_id not in getattr(project, "scenes", {}):
                    return
                if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_NONE or bool(self.has_preview()):
                    self.close_active_tool(log_it=False, ask_preview=True)
                    if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_NONE or bool(self.has_preview()):
                        self.sync_scene_tabs()
                        return
                from ..project import sync_window_to_active_scene

                project.switch_scene(scene_id)
                sync_window_to_active_scene(self)
                self.selected_indices = []
                self.active_index = None
                self._clear_gizmo_interaction(clear_highlight=True)
                self._clear_gizmo_actors()
                self.rebuild_scene(keep_camera=False)
                self.update_preview_state()
                self._sync_history_buttons()
                self.sync_scene_tabs()
                self.ui_log(f"[SCENE] Switched to '{project.active_scene.name}'")
            except Exception:
                log_exception("switch_scene_by_id")
                try:
                    self.sync_scene_tabs()
                except Exception:
                    pass

    def switch_scene_tab_by_index(self, index: int) -> None:
            """Switch active scene from the hidden synchronization tab bar."""
            try:
                if bool(getattr(self, "_syncing_scene_tabs", False)):
                    return
                bar = getattr(self, "scene_tab_bar", None)
                if bar is None or int(index) < 0 or int(index) >= bar.count():
                    return
                self.switch_scene_by_id(str(bar.tabData(int(index)) or ""))
            except Exception:
                log_exception("switch_scene_tab_by_index")
                try:
                    self.sync_scene_tabs()
                except Exception:
                    pass

    def close_scene_by_id(self, scene_id: str) -> None:
            """Close a scene tab, keeping at least one scene in the project."""
            try:
                project = getattr(self, "project_store", None)
                scene_id = str(scene_id or "")
                if project is None or not scene_id or scene_id not in getattr(project, "scenes", {}):
                    return
                if len(project.scenes) <= 1:
                    try:
                        self.statusBar().showMessage("Cannot close the last scene", 1600)
                    except Exception:
                        pass
                    return
                confirmer = getattr(getattr(self, "action_controller", None), "project", None)
                if confirmer is not None and callable(getattr(confirmer, "confirm_close_scene", None)):
                    if not confirmer.confirm_close_scene(scene_id):
                        self.sync_scene_tabs()
                        return
                if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_NONE or bool(self.has_preview()):
                    self.close_active_tool(log_it=False, ask_preview=True)
                    if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_NONE or bool(self.has_preview()):
                        self.sync_scene_tabs()
                        return
                removed_name = getattr(project.scenes.get(scene_id), "name", "scene")
                project.remove_scene(scene_id)
                from ..project import sync_window_to_active_scene

                sync_window_to_active_scene(self)
                self.selected_indices = []
                self.active_index = None
                self.rebuild_scene(keep_camera=False)
                self.update_preview_state()
                self._sync_history_buttons()
                self.sync_scene_tabs()
                self.ui_log(f"[SCENE] Closed '{removed_name}'")
            except Exception:
                log_exception("close_scene_by_id")
                try:
                    self.sync_scene_tabs()
                except Exception:
                    pass

    def close_scene_tab_by_index(self, index: int) -> None:
            """Close a scene from the hidden synchronization tab bar."""
            try:
                bar = getattr(self, "scene_tab_bar", None)
                if bar is None or int(index) < 0 or int(index) >= bar.count():
                    return
                self.close_scene_by_id(str(bar.tabData(int(index)) or ""))
            except Exception:
                log_exception("close_scene_tab_by_index")
                try:
                    self.sync_scene_tabs()
                except Exception:
                    pass

    def move_scene_tab_before(self, source_scene_id: str, target_scene_id: str | None) -> None:
            """Window-level wrapper: move one scene before another scene."""
            project = getattr(self, "project_store", None)
            target_scene_id = str(target_scene_id or "") if target_scene_id else None
            if target_scene_id:
                target_index = self.scene_tab_insert_index_for_target(target_scene_id, after=False)
            else:
                target_index = len(getattr(project, "scenes", {}) or {}) if project is not None else 0
            self.move_scene_tab_to_index(source_scene_id, target_index)

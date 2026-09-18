# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class SceneTabsDragLayer:

    def begin_scene_tab_drag(self, source_scene_id: str, global_pos=None) -> None:
            """Start a safe scene-tab reorder gesture.

            The tab strip is intentionally *not* rebuilt during mouseMove.  Rebuilding
            while the button is down deletes the source widget and can leave Qt in a
            stuck drag/cursor state.  We only preview the target during movement and
            perform the actual reorder on mouseRelease.  A lightweight ghost follows
            the cursor so the source tab never has to be removed from the layout.
            """
            self._scene_tab_drag_source_id = str(source_scene_id or "")
            self._scene_tab_drag_pending_index = None
            self._scene_tab_drag_active = bool(self._scene_tab_drag_source_id)
            self._set_scene_tab_drag_visuals(self._scene_tab_drag_source_id, None)
            self._create_scene_tab_drag_ghost(self._scene_tab_drag_source_id, global_pos)
            if global_pos is not None:
                self._move_scene_tab_drag_ghost(global_pos)

    def end_scene_tab_drag(self, source_scene_id: str, global_pos=None) -> None:
            """Finish a safe scene-tab reorder gesture."""
            source_scene_id = str(source_scene_id or "")
            target_index = getattr(self, "_scene_tab_drag_pending_index", None)
            try:
                if global_pos is not None:
                    computed = self.scene_tab_insert_index_at_global_pos(global_pos)
                    if computed is not None:
                        target_index = int(computed)
                # Dropping before itself or just after itself is a no-op.  Do not
                # rebuild the tab strip in that case: that rebuild was the last
                # remaining source of intermittent “main tab disappears” flashes
                # when the user only nudged the first tab a little to the right.
                if (
                    source_scene_id
                    and target_index is not None
                    and not self._scene_tab_live_index_is_noop(source_scene_id, int(target_index))
                ):
                    self.move_scene_tab_to_index(source_scene_id, int(target_index))
            except Exception:
                log_exception("end_scene_tab_drag")
                try:
                    self.sync_scene_tabs()
                except Exception:
                    pass
            finally:
                self._clear_scene_tab_drag_visuals()
                self._destroy_scene_tab_drag_ghost()
                self._scene_tab_drag_source_id = None
                self._scene_tab_drag_pending_index = None
                self._scene_tab_drag_active = False

    def update_scene_tab_drag_preview(self, source_scene_id: str, global_pos) -> None:
            """Preview the tab insertion point without rebuilding the strip."""
            try:
                source_scene_id = str(source_scene_id or "")
                if not source_scene_id:
                    return
                project = getattr(self, "project_store", None)
                if project is None or source_scene_id not in getattr(project, "scenes", {}):
                    return
                self._move_scene_tab_drag_ghost(global_pos)
                target_index = self.scene_tab_insert_index_at_global_pos(global_pos)
                if target_index is None:
                    self._scene_tab_drag_pending_index = None
                    self._set_scene_tab_drag_visuals(source_scene_id, None)
                    return
                target_index = int(target_index)
                if self._scene_tab_live_index_is_noop(source_scene_id, target_index):
                    if getattr(self, "_scene_tab_drag_pending_index", None) is not None:
                        self._scene_tab_drag_pending_index = None
                        self._set_scene_tab_drag_visuals(source_scene_id, None)
                    return
                if getattr(self, "_scene_tab_drag_pending_index", None) == target_index:
                    return
                self._scene_tab_drag_pending_index = target_index
                self._set_scene_tab_drag_visuals(source_scene_id, target_index)
            except Exception:
                log_exception("update_scene_tab_drag_preview")

    def update_scene_tab_drag(self, source_scene_id: str, global_pos) -> None:
            """Stable window-level name for the drag preview path.

            Pass63 reordered immediately on mouseMove.  That made the dragged tab
            disappear because sync_scene_tabs() destroyed and rebuilt the widget
            before mouseRelease.  Keep the public method, but make it preview-only.
            """
            self.update_scene_tab_drag_preview(source_scene_id, global_pos)

    def _scene_tab_live_index_is_noop(self, source_scene_id: str, live_insert_index: int) -> bool:
            """Return True when a live insertion index keeps the tab in place.

            The drag preview indexes are computed before the source tab is removed.
            For a source at index N, both inserting before N and after N are the
            same visual order after removal.  Treating both as no-ops prevents a
            needless rebuild when a user slightly drags the first tab to the right.
            """
            try:
                order = self._scene_order_ids()
                source_index = order.index(str(source_scene_id or ""))
                live_insert_index = int(live_insert_index)
                return live_insert_index == source_index or live_insert_index == source_index + 1
            except Exception:
                return False

    def _create_scene_tab_drag_ghost(self, source_scene_id: str, global_pos=None) -> None:
            """Create a non-interactive drag ghost parented to the footer.

            The real tab remains in the layout for the whole gesture.  This avoids
            deleting/reparenting widgets while the mouse is down and gives immediate
            visual feedback similar to a browser tab strip.
            """
            try:
                self._destroy_scene_tab_drag_ghost()
                widgets = getattr(self, "_scene_tab_widgets_by_id", {}) or {}
                source = widgets.get(str(source_scene_id or ""))
                footer = getattr(self, "scene_tabs_footer", None)
                if source is None or footer is None:
                    return
                ghost = QFrame(footer)
                ghost.setObjectName("SceneTabDragGhost")
                try:
                    ghost.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                except Exception:
                    try:
                        ghost.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                    except Exception:
                        pass
                ghost.setFixedSize(source.size())
                ghost_l = QHBoxLayout(ghost)
                ghost_l.setContentsMargins(10, 0, 10, 0)
                ghost_l.setSpacing(0)
                label = QLabel(str(getattr(source, "toolTip", lambda: "Scene")() or "Scene"), ghost)
                label.setObjectName("SceneTabDragGhostLabel")
                try:
                    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                except Exception:
                    pass
                ghost_l.addWidget(label, 1)
                if global_pos is not None:
                    try:
                        self._scene_tab_drag_ghost_offset = source.mapFromGlobal(global_pos)
                    except Exception:
                        self._scene_tab_drag_ghost_offset = source.rect().center()
                else:
                    self._scene_tab_drag_ghost_offset = source.rect().center()
                self._scene_tab_drag_ghost = ghost
                ghost.raise_()
                ghost.show()
            except Exception:
                log_exception("create_scene_tab_drag_ghost")

    def _move_scene_tab_drag_ghost(self, global_pos) -> None:
            try:
                ghost = getattr(self, "_scene_tab_drag_ghost", None)
                footer = getattr(self, "scene_tabs_footer", None)
                if ghost is None or footer is None or global_pos is None:
                    return
                footer_pos = footer.mapFromGlobal(global_pos)
                offset = getattr(self, "_scene_tab_drag_ghost_offset", None)
                if offset is None:
                    offset = ghost.rect().center()
                x = int(footer_pos.x() - offset.x())
                y = int(footer_pos.y() - offset.y())
                try:
                    x = max(0, min(x, max(0, footer.width() - ghost.width())))
                    y = max(0, min(y, max(0, footer.height() - ghost.height())))
                except Exception:
                    pass
                ghost.move(x, y)
                ghost.raise_()
                ghost.show()
            except Exception:
                log_exception("move_scene_tab_drag_ghost")

    def _destroy_scene_tab_drag_ghost(self) -> None:
            try:
                ghost = getattr(self, "_scene_tab_drag_ghost", None)
                if ghost is not None:
                    try:
                        ghost.hide()
                    except Exception:
                        pass
                    ghost.deleteLater()
            except Exception:
                log_exception("destroy_scene_tab_drag_ghost")
            finally:
                self._scene_tab_drag_ghost = None
                self._scene_tab_drag_ghost_offset = None

    def _set_scene_tab_bool_property(self, widget, name: str, value: bool) -> None:
            try:
                widget.setProperty(name, "true" if bool(value) else "false")
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
            except Exception:
                pass

    def _set_scene_tab_drag_visuals(self, source_scene_id: str | None, insert_index: int | None) -> None:
            """Mark the source tab and the current drop target visually."""
            try:
                widgets = getattr(self, "_scene_tab_widgets_by_id", {}) or {}
                order = self._scene_order_ids()
                source_scene_id = str(source_scene_id or "")
                for scene_id, widget in widgets.items():
                    self._set_scene_tab_bool_property(widget, "dragging", scene_id == source_scene_id)
                    self._set_scene_tab_bool_property(widget, "dropTarget", False)
                end_zone = getattr(self, "_scene_tab_end_drop_zone", None)
                if end_zone is not None:
                    self._set_scene_tab_bool_property(end_zone, "dropTarget", False)
                if insert_index is None:
                    return
                insert_index = max(0, min(int(insert_index), len(order)))
                if insert_index >= len(order):
                    if end_zone is not None:
                        self._set_scene_tab_bool_property(end_zone, "dropTarget", True)
                    return
                target_id = order[insert_index]
                target_widget = widgets.get(target_id)
                if target_widget is not None:
                    self._set_scene_tab_bool_property(target_widget, "dropTarget", True)
            except Exception:
                log_exception("set_scene_tab_drag_visuals")

    def _clear_scene_tab_drag_visuals(self) -> None:
            self._set_scene_tab_drag_visuals(None, None)

    def scene_tab_insert_index_at_global_pos(self, global_pos) -> int | None:
            """Return insertion index for a global mouse position in the tab strip."""
            try:
                order = self._scene_order_ids()
                if not order:
                    return None
                widgets = getattr(self, "_scene_tab_widgets_by_id", {}) or {}
                first_left = None
                last_right = None
                for index, scene_id in enumerate(order):
                    widget = widgets.get(scene_id)
                    if widget is None:
                        continue
                    local = widget.mapFromGlobal(global_pos)
                    rect = widget.rect()
                    top_left = widget.mapToGlobal(rect.topLeft())
                    bottom_right = widget.mapToGlobal(rect.bottomRight())
                    if first_left is None or top_left.x() < first_left:
                        first_left = top_left.x()
                    if last_right is None or bottom_right.x() > last_right:
                        last_right = bottom_right.x()
                    if rect.contains(local):
                        return index + (1 if float(local.x()) >= float(max(1, rect.width())) / 2.0 else 0)
                try:
                    x = global_pos.x()
                except Exception:
                    x = 0
                if first_left is not None and x < first_left:
                    return 0
                if last_right is not None and x > last_right:
                    return len(order)
                return None
            except Exception:
                log_exception("scene_tab_insert_index_at_global_pos")
                return None

    def _scene_order_ids(self) -> list[str]:
            project = getattr(self, "project_store", None)
            if project is None:
                return []
            try:
                return list(project.scene_order())
            except Exception:
                return list((getattr(project, "scenes", {}) or {}).keys())

    def scene_tab_insert_index_for_target(self, target_scene_id: str, *, after: bool = False) -> int:
            """Return the live insertion index for a drop on a tab half.

            Dropping on the left half inserts before the target; dropping on the
            right half inserts after it.  The final move method clamps indexes after
            removing the source tab, so this can be computed from the current order.
            """
            order = self._scene_order_ids()
            target_scene_id = str(target_scene_id or "")
            try:
                index = order.index(target_scene_id)
            except ValueError:
                index = len(order)
            return index + (1 if after else 0)

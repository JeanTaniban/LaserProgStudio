# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


_SCENE_TAB_MIME = "application/x-laserprog-scene-id"


class DraggableSceneTabFrame(QFrame):
    """Chrome-like scene tab that can be reordered freely by drag and drop.

    Important Qt detail: the visible text of a tab is a child QToolButton.
    Mouse events on that button do not automatically reach the parent QFrame,
    so dragging the label did nothing in practice.  The label is now made
    transparent to mouse events, letting the parent frame receive normal
    press/move/release events and drive immediate browser-like tab movement.
    The MIME/QDrag path remains as a secondary drag path.
    """

    def __init__(self, owner, scene_id: str, parent=None):
        super().__init__(parent)
        self._owner = owner
        self._scene_id = str(scene_id or "")
        self._drag_start_global_pos = None
        self._dragging_scene_tab = False
        self.setAcceptDrops(True)
        try:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        except Exception:
            try:
                self.setCursor(Qt.OpenHandCursor)
            except Exception:
                pass

    def mousePressEvent(self, event):  # noqa: N802
        self._scene_tab_mouse_press(event)
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._scene_tab_mouse_move(event):
            return
        return super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802
        was_dragging = bool(self._dragging_scene_tab)
        left_release = self._event_is_left_press(event)
        try:
            self._scene_tab_mouse_release(event)
        finally:
            # Never leave a tab with a closed-hand cursor after an aborted or
            # completed drag.  Pass63 rebuilt/deleted the source tab during
            # mouseMove, so release was sometimes lost and the cursor stayed
            # stuck as a closed hand.
            self._dragging_scene_tab = False
            self._drag_start_global_pos = None
            try:
                self.releaseMouse()
            except Exception:
                pass
            try:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            except Exception:
                try:
                    self.setCursor(Qt.OpenHandCursor)
                except Exception:
                    pass
        if was_dragging:
            return
        if left_release and self._scene_id:
            try:
                self._owner.switch_scene_by_id(self._scene_id)
            except Exception:
                log_exception("scene_tab_click_switch")
            return
        return super().mouseReleaseEvent(event)

    def _event_global_pos(self, event):
        try:
            return event.globalPosition().toPoint()
        except Exception:
            try:
                return event.globalPos()
            except Exception:
                return None

    def _event_is_left_press(self, event) -> bool:
        try:
            return event.button() == Qt.MouseButton.LeftButton
        except Exception:
            try:
                return event.button() == Qt.LeftButton
            except Exception:
                return False

    def _event_left_button_down(self, event) -> bool:
        try:
            return bool(event.buttons() & Qt.MouseButton.LeftButton)
        except Exception:
            try:
                return bool(event.buttons() & Qt.LeftButton)
            except Exception:
                return False

    def _scene_tab_mouse_press(self, event) -> None:
        self._dragging_scene_tab = False
        if not self._scene_id:
            self._drag_start_global_pos = None
            return
        if self._event_is_left_press(event):
            self._drag_start_global_pos = self._event_global_pos(event)
        else:
            self._drag_start_global_pos = None

    def _scene_tab_mouse_move(self, event) -> bool:
        if not self._scene_id or self._drag_start_global_pos is None:
            return False
        if not self._event_left_button_down(event):
            return False
        global_pos = self._event_global_pos(event)
        if global_pos is None:
            return False
        try:
            threshold = QApplication.startDragDistance()
        except Exception:
            threshold = 8
        try:
            distance = (global_pos - self._drag_start_global_pos).manhattanLength()
        except Exception:
            distance = threshold
        if not self._dragging_scene_tab:
            if distance < threshold:
                return False
            self._dragging_scene_tab = True
            try:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            except Exception:
                try:
                    self.setCursor(Qt.ClosedHandCursor)
                except Exception:
                    pass
            try:
                self.grabMouse()
            except Exception:
                pass
            try:
                self._owner.begin_scene_tab_drag(self._scene_id, global_pos)
            except Exception:
                log_exception("begin_scene_tab_drag")
        try:
            # Preview only.  Do not rebuild/reorder the tab strip while the
            # mouse button is still down: doing so deletes the source widget
            # mid-drag, making the tab disappear and losing the release event.
            self._owner.update_scene_tab_drag_preview(self._scene_id, global_pos)
        except Exception:
            log_exception("update_scene_tab_drag_preview")
        return True

    def _scene_tab_mouse_release(self, event) -> None:
        try:
            if self._dragging_scene_tab:
                global_pos = self._event_global_pos(event)
                try:
                    self._owner.end_scene_tab_drag(self._scene_id, global_pos)
                except Exception:
                    log_exception("end_scene_tab_drag")
        finally:
            self._dragging_scene_tab = False
            self._drag_start_global_pos = None
            try:
                self.releaseMouse()
            except Exception:
                pass
            try:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            except Exception:
                try:
                    self.setCursor(Qt.OpenHandCursor)
                except Exception:
                    pass

    def _start_scene_drag(self) -> None:
        """Secondary QDrag path used by tests and alternate callers."""
        try:
            from PySide6.QtCore import QMimeData
            from PySide6.QtGui import QDrag

            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(_SCENE_TAB_MIME, self._scene_id.encode("utf-8"))
            drag.setMimeData(mime)
            try:
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            except Exception:
                pass
            drag.exec(Qt.DropAction.MoveAction)
        except Exception:
            log_exception("start_scene_tab_drag")
        finally:
            try:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            except Exception:
                pass

    def dragEnterEvent(self, event):  # noqa: N802
        self._accept_scene_tab_drag(event)

    def dragMoveEvent(self, event):  # noqa: N802
        self._accept_scene_tab_drag(event)

    def _accept_scene_tab_drag(self, event) -> None:
        try:
            mime = event.mimeData()
            if mime is not None and mime.hasFormat(_SCENE_TAB_MIME):
                source_id = bytes(mime.data(_SCENE_TAB_MIME)).decode("utf-8")
                if source_id and source_id != self._scene_id:
                    event.acceptProposedAction()
                    return
        except Exception:
            pass
        event.ignore()

    def _drop_after_target(self, event) -> bool:
        try:
            x = float(event.position().x())
        except Exception:
            try:
                x = float(event.pos().x())
            except Exception:
                x = 0.0
        try:
            width = max(1.0, float(self.width()))
        except Exception:
            width = 1.0
        return x >= width / 2.0

    def dropEvent(self, event):  # noqa: N802
        try:
            source_id = bytes(event.mimeData().data(_SCENE_TAB_MIME)).decode("utf-8")
            if source_id and source_id != self._scene_id:
                target_index = self._owner.scene_tab_insert_index_for_target(
                    self._scene_id,
                    after=self._drop_after_target(event),
                )
                self._owner.move_scene_tab_to_index(source_id, target_index)
                event.acceptProposedAction()
                return
        except Exception:
            log_exception("drop_scene_tab")
        event.ignore()

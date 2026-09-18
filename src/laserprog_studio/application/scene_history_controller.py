# -*- coding: utf-8 -*-
from __future__ import annotations

from functools import partial
from typing import Any

from ..app_context import AppContext
from ..studio_log import log_exception
from .owner_delegating_controller import OwnerDelegatingController


def _qt_widgets() -> tuple[Any, ...]:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QDialog,
        QDialogButtonBox,
        QFrame,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    return Qt, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class SceneHistoryController(OwnerDelegatingController):
    """Floating semantic scene-history window with non-destructive restore."""

    @classmethod
    def create(cls, context: AppContext) -> "SceneHistoryController":
        return cls(context)

    def _active_scene(self):
        project = getattr(self.owner, "project_store", None)
        return getattr(project, "active_scene", None) if project is not None else None

    def restore_history_entry(self, scene_id: str, snapshot_id: str) -> bool:
        """Restore a semantic snapshot into a new scene, leaving source intact."""
        w = self.owner
        try:
            from ..project import ensure_project_store, sync_window_to_active_scene

            project = ensure_project_store(w)
            source = project.scenes[str(scene_id)]
            base_name = f"{source.name} - restored"
            new_scene = project.create_scene_from_snapshot(str(scene_id), str(snapshot_id), name=base_name, make_active=True)
            sync_window_to_active_scene(w)
            w.selected_indices = []
            w.active_index = None
            try:
                w._clear_gizmo_interaction(clear_highlight=True)
                w._clear_gizmo_actors()
            except Exception:
                pass
            w.rebuild_scene(keep_camera=False)
            w.update_preview_state()
            w._sync_history_buttons()
            w.sync_scene_tabs()
            w.ui_log(f"[HISTORY] Restored snapshot into new scene '{new_scene.name}'")
            try:
                dialog = getattr(self, "_last_dialog", None)
                if dialog is not None:
                    dialog.close()
            except Exception:
                pass
            return True
        except Exception:
            log_exception("restore_history_entry")
            return False

    def open_scene_history(self) -> None:
        Qt, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget = _qt_widgets()
        dialog = QDialog(self.owner)
        dialog.setWindowTitle("Scene history")
        dialog.setModal(False)
        dialog.resize(760, 520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        scene = self._active_scene()
        scene_name = getattr(scene, "name", "current scene") if scene is not None else "current scene"
        title = QLabel(f"Scene history — {scene_name}", dialog)
        try:
            title.setObjectName("Title")
        except Exception:
            pass
        layout.addWidget(title)

        help_text = QLabel("Only meaningful scene operations are listed here. Restore creates a new scene and never overwrites the current one.", dialog)
        help_text.setWordWrap(True)
        try:
            help_text.setObjectName("SubTitle")
        except Exception:
            pass
        layout.addWidget(help_text)

        scroll = QScrollArea(dialog)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        rows = QVBoxLayout(content)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(6)

        history = list(getattr(scene, "history", []) or []) if scene is not None else []
        if history:
            header = QWidget(content)
            header_l = QHBoxLayout(header)
            header_l.setContentsMargins(4, 2, 4, 2)
            header_l.setSpacing(8)
            for text, stretch in (("Date / time", 2), ("Modification", 5), ("", 1)):
                label = QLabel(text, header)
                label.setStyleSheet("font-weight: 800;")
                header_l.addWidget(label, stretch)
            rows.addWidget(header)
            for entry in reversed(history):
                row = QWidget(content)
                row_l = QHBoxLayout(row)
                row_l.setContentsMargins(4, 4, 4, 4)
                row_l.setSpacing(8)
                timestamp = str(getattr(entry, "timestamp", "") or "")
                description = str(getattr(entry, "description", "") or "")
                snapshot_id = str(getattr(entry, "snapshot_id", "") or "")
                row_l.addWidget(QLabel(timestamp, row), 2)
                desc = QLabel(description, row)
                desc.setWordWrap(True)
                row_l.addWidget(desc, 5)
                btn = QPushButton("Restore", row)
                btn.setEnabled(bool(snapshot_id))
                if snapshot_id:
                    btn.setToolTip("Create a new scene from this restore point")
                    btn.clicked.connect(partial(self.restore_history_entry, getattr(scene, "scene_id", ""), snapshot_id))
                else:
                    btn.setToolTip("This entry has no stored snapshot")
                row_l.addWidget(btn, 1)
                rows.addWidget(row)
        else:
            store = getattr(self.owner, "mesh_store", None)
            undo_count = len(getattr(store, "_history", []) or []) if store is not None else 0
            redo_count = len(getattr(store, "_redo_history", []) or []) if store is not None else 0
            empty = QLabel(
                "No semantic scene modification has been recorded yet.\n\n"
                "Technical Ctrl+Z remains separate and in RAM only.\n"
                f"Undo states: {undo_count}\nRedo states: {redo_count}",
                content,
            )
            empty.setWordWrap(True)
            rows.addWidget(empty)
        rows.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        try:
            close_button = QDialogButtonBox.StandardButton.Close
        except AttributeError:
            close_button = QDialogButtonBox.Close
        buttons = QDialogButtonBox(close_button, parent=dialog)
        buttons.rejected.connect(dialog.close)
        layout.addWidget(buttons, 0, Qt.AlignRight)

        self._last_dialog = dialog
        dialog.show()
        try:
            dialog.raise_()
            dialog.activateWindow()
        except Exception:
            pass

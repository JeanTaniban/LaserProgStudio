# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .._window_deps import *
from ..app_context import AppContext
from ..studio_log import log_exception
from .action_controller import WindowController
from ..services.toolbar_preferences import load_toolbar_preferences, save_toolbar_preferences
from ..ui.toolbar_icons import toolbar_icon
from ..ui.toolbar_catalog import (
    TOOLBAR_CATEGORY_LABELS,
    TOOLBAR_CATEGORY_ORDER,
    TOOLBAR_MAX_ITEMS,
    TOOLBAR_REGISTRY_VERSION,
    get_toolbar_item_spec,
    iter_toolbar_button_attrs,
    sanitized_toolbar_item_ids,
    search_toolbar_item_specs,
)


TOOLBAR_TRASH_BUTTON_ACTIVE_STYLE = """
QToolButton {
    background-color: #C62828;
    color: #FFFFFF;
    border: 1px solid #8E0000;
    border-radius: 5px;
    font-weight: 700;
}
QToolButton:hover {
    background-color: #B71C1C;
}
"""

TOOLBAR_UNAVAILABLE_ITEM_STYLE = """
QToolButton {
    background-color: #2B3038;
    color: #CBD5E1;
    border: 1px solid #111827;
    border-radius: 5px;
    font-weight: 700;
}
QToolButton:hover {
    background-color: #343B46;
    color: #E5E7EB;
}
QToolButton:pressed {
    background-color: #20252B;
    color: #E5E7EB;
}
"""

TOOLBAR_REMOVABLE_ITEM_STYLE = """
QToolButton {
    background-color: #FDE047;
    color: #111827;
    border: 2px dashed #B45309;
    border-radius: 5px;
    font-weight: 700;
}
QToolButton:hover {
    background-color: #FDBA74;
    color: #111827;
}
QToolButton:pressed {
    background-color: #F59E0B;
    color: #111827;
}
QToolButton:disabled {
    background-color: #FDE047;
    color: #111827;
    border: 2px dashed #B45309;
}
"""

TOOLBAR_MIME_ITEM_ID = "application/x-laserprog-toolbar-item-id"


def _drag_position(event: Any):
    try:
        return event.position().toPoint()
    except Exception:
        try:
            return event.pos()
        except Exception:
            return None


def _toolbar_mime_item_id(event: Any) -> str | None:
    try:
        mime = event.mimeData()
        if mime is not None and mime.hasFormat(TOOLBAR_MIME_ITEM_ID):
            data = bytes(mime.data(TOOLBAR_MIME_ITEM_ID)).decode("utf-8", "ignore")
            return str(data).strip() or None
        if mime is not None and mime.hasText():
            text = str(mime.text()).strip()
            return text if text.startswith(("tool:", "modifier:", "boolean:")) else None
    except Exception:
        pass
    return None


class ToolbarItemDragButton(QToolButton):
    """Toolbar chip with smooth internal drag/reorder support."""

    def __init__(self, controller: "ConfigurableToolbarController", item_id: str, parent: Any = None) -> None:
        super().__init__(parent)
        self._toolbar_controller = controller
        self._toolbar_item_id = str(item_id)
        self._drag_start_pos = None
        self.setAcceptDrops(True)

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        try:
            if event.button() == Qt.LeftButton:
                self._drag_start_pos = _drag_position(event)
        except Exception:
            self._drag_start_pos = None
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt API
        try:
            if not (event.buttons() & Qt.LeftButton) or self._drag_start_pos is None:
                return super().mouseMoveEvent(event)
            pos = _drag_position(event)
            if pos is None:
                return super().mouseMoveEvent(event)
            distance = (pos - self._drag_start_pos).manhattanLength()
            if distance < QApplication.startDragDistance():
                return super().mouseMoveEvent(event)
            from PySide6.QtCore import QMimeData
            from PySide6.QtGui import QDrag

            drag = QDrag(self)
            mime = QMimeData()
            encoded = str(self._toolbar_item_id).encode("utf-8")
            mime.setData(TOOLBAR_MIME_ITEM_ID, encoded)
            mime.setText(str(self._toolbar_item_id))
            drag.setMimeData(mime)
            try:
                pixmap = self.grab()
                drag.setPixmap(pixmap)
                drag.setHotSpot(pos)
            except Exception:
                pass
            drag.exec(Qt.MoveAction)
            event.accept()
            return None
        except Exception:
            return super().mouseMoveEvent(event)

    def dragEnterEvent(self, event):  # noqa: N802 - Qt API
        source_id = _toolbar_mime_item_id(event)
        if self._toolbar_controller.can_accept_toolbar_drop(source_id, target_item_id=self._toolbar_item_id):
            event.setDropAction(Qt.MoveAction)
            event.accept()
            return
        event.ignore()

    def dragMoveEvent(self, event):  # noqa: N802 - Qt API
        source_id = _toolbar_mime_item_id(event)
        if self._toolbar_controller.can_accept_toolbar_drop(source_id, target_item_id=self._toolbar_item_id):
            event.setDropAction(Qt.MoveAction)
            event.accept()
            return
        event.ignore()

    def dropEvent(self, event):  # noqa: N802 - Qt API
        source_id = _toolbar_mime_item_id(event)
        pos = _drag_position(event)
        position = "before"
        try:
            if pos is not None and float(pos.x()) >= float(self.width()) * 0.5:
                position = "after"
        except Exception:
            pass
        if self._toolbar_controller.move_item(source_id, target_item_id=self._toolbar_item_id, position=position):
            event.setDropAction(Qt.MoveAction)
            event.accept()
            return
        event.ignore()


class ToolbarDropEventFilter:
    """Small event-filter object, instantiated as a QObject at runtime.

    The actual QObject base is resolved in ``__new__`` so this module remains
    importable in headless static tests that monkeypatch Qt.
    """

    pass


def _make_toolbar_drop_filter(controller: "ConfigurableToolbarController"):
    from PySide6.QtCore import QObject

    class _Filter(QObject):
        def eventFilter(self, obj, event):  # noqa: N802 - Qt API
            try:
                etype = event.type()
                if etype not in {QEvent.DragEnter, QEvent.DragMove, QEvent.Drop}:
                    return False
                source_id = _toolbar_mime_item_id(event)
                target_kind = str(obj.property("toolbarDropTarget") or "")
                if target_kind == "trash":
                    if source_id and get_toolbar_item_spec(source_id) is not None:
                        if etype == QEvent.Drop:
                            controller.remove_item(source_id)
                        event.setDropAction(Qt.MoveAction)
                        event.accept()
                        return True
                elif target_kind == "category":
                    category = str(obj.property("toolbarCategory") or "")
                    if controller.can_accept_toolbar_drop(source_id, target_category=category):
                        if etype == QEvent.Drop:
                            controller.move_item(source_id, target_category=category, position="end")
                        event.setDropAction(Qt.MoveAction)
                        event.accept()
                        return True
                event.ignore()
                return True
            except Exception:
                return False

    return _Filter(controller.owner)


class ConfigurableToolbarController(WindowController):
    """Own the configurable top-toolbar lifecycle outside MainWindow mixins.

    The UI layer still exposes window-level forwarding methods such as
    ``add_toolbar_item`` and ``_set_toolbar_remove_mode`` because many signals,
    tests and controllers call the window directly.  This controller is
    the real owner of the workflow: sanitising persisted ids, rebuilding dynamic
    buttons, routing clicks, handling trash mode and opening the palette.
    """

    @classmethod
    def create(cls, context: AppContext) -> "ConfigurableToolbarController":
        return cls(context)

    # ------------------------------------------------------------------
    # Setup / shared state
    # ------------------------------------------------------------------
    def setup(self, top_l: QHBoxLayout) -> None:
        """Build the configurable Tools / Modifiers / Booleans section."""
        w = self.owner
        w.toolbar_remove_mode = False
        if not hasattr(w, "tool_group") or w.tool_group is None:
            w.tool_group = QButtonGroup(w)
            w.tool_group.setExclusive(True)
        if not hasattr(w, "modifier_group") or w.modifier_group is None:
            w.modifier_group = QButtonGroup(w)
            w.modifier_group.setExclusive(True)

        w.toolbar_dynamic_buttons = {}
        w.toolbar_category_labels = {}
        w.toolbar_category_layouts = {}
        w.toolbar_category_widgets = {}
        # Dedicated JSON persistence for the configurable toolbar.  The older
        # UI-layout JSON is still read as a fallback so existing installations
        # keep their previous layout after upgrading.
        toolbar_payload = load_toolbar_preferences()
        toolbar_ids = toolbar_payload.get("toolbar_item_ids") if isinstance(toolbar_payload, dict) else None
        registry_version = int(toolbar_payload.get("toolbar_registry_version", 0)) if isinstance(toolbar_payload, dict) else 0
        if registry_version < int(TOOLBAR_REGISTRY_VERSION):
            # A registry-version bump means the production default order changed
            # or entries were retired.  Use the new default once; later user
            # drag/drop edits are persisted with the current version.
            toolbar_ids = None
        if not isinstance(toolbar_ids, list):
            toolbar_ids = getattr(getattr(w, "ui_layout_state", None), "toolbar_item_ids", None)
            try:
                if registry_version < int(TOOLBAR_REGISTRY_VERSION):
                    toolbar_ids = None
            except Exception:
                toolbar_ids = None
        w.toolbar_item_ids = sanitized_toolbar_item_ids(
            toolbar_ids,
            max_items=self.max_items(),
        )
        self._sync_state_to_preferences(registry_version=True)
        self.save_toolbar_preferences_now()

        for category in TOOLBAR_CATEGORY_ORDER:
            label = QLabel(TOOLBAR_CATEGORY_LABELS.get(category, str(category).title()))
            label.setObjectName("ToolbarCategoryLabel")
            top_l.addWidget(label)

            holder = QWidget()
            holder.setObjectName(f"ToolbarCategory_{category}")
            holder.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
            holder.setAcceptDrops(True)
            holder.setProperty("toolbarDropTarget", "category")
            holder.setProperty("toolbarCategory", str(category))
            self._install_toolbar_drop_filter(holder)
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)

            w.toolbar_category_labels[category] = label
            w.toolbar_category_layouts[category] = row
            w.toolbar_category_widgets[category] = holder
            top_l.addWidget(holder)

        self.rebuild(save=False)
        self._ensure_trash_drop_target()
        try:
            orchestrator = getattr(w, "ui_orchestration", None)
            if orchestrator is not None:
                orchestrator.register_dynamic_toolbar_anchors()
        except Exception:
            pass

    def max_items(self) -> int:
        return int(TOOLBAR_MAX_ITEMS)

    def all_button_attrs(self) -> tuple[str, ...]:
        return iter_toolbar_button_attrs()

    def _sync_state_to_preferences(self, *, registry_version: bool = False) -> None:
        w = self.owner
        state = getattr(w, "ui_layout_state", None)
        if state is None:
            return
        try:
            state.toolbar_item_ids = list(getattr(w, "toolbar_item_ids", []) or [])
            if registry_version:
                state.toolbar_registry_version = int(TOOLBAR_REGISTRY_VERSION)
        except Exception:
            pass

    def save_toolbar_preferences_now(self) -> None:
        """Persist the top toolbar immediately to its dedicated JSON file."""
        try:
            save_toolbar_preferences(
                list(getattr(self.owner, "toolbar_item_ids", []) or []),
                registry_version=int(TOOLBAR_REGISTRY_VERSION),
                max_items=self.max_items(),
            )
        except Exception:
            pass

    def _install_toolbar_drop_filter(self, widget: Any) -> None:
        try:
            drop_filter = getattr(self.owner, "_toolbar_drop_event_filter", None)
            if drop_filter is None:
                drop_filter = _make_toolbar_drop_filter(self)
                self.owner._toolbar_drop_event_filter = drop_filter
            widget.installEventFilter(drop_filter)
        except Exception:
            pass

    def _ensure_trash_drop_target(self) -> None:
        w = self.owner
        trash = getattr(w, "btn_toolbar_remove", None)
        if trash is None:
            return
        try:
            trash.setAcceptDrops(True)
            trash.setProperty("toolbarDropTarget", "trash")
            trash.setToolTip("Drop a toolbar item here to remove it, or click to enter remove mode")
            self._install_toolbar_drop_filter(trash)
        except Exception:
            pass

    def _category_for_item(self, item_id: str | None) -> str | None:
        spec = get_toolbar_item_spec(item_id)
        return str(spec.category) if spec is not None else None

    def can_accept_toolbar_drop(
        self,
        source_item_id: str | None,
        *,
        target_item_id: str | None = None,
        target_category: str | None = None,
    ) -> bool:
        source = get_toolbar_item_spec(source_item_id)
        if source is None:
            return False
        if target_item_id is not None:
            target = get_toolbar_item_spec(target_item_id)
            if target is None or target.id == source.id:
                return False
            return str(target.category) == str(source.category)
        if target_category is not None:
            return str(target_category) == str(source.category)
        return False

    # ------------------------------------------------------------------
    # Trash/remove mode
    # ------------------------------------------------------------------
    def set_remove_mode(self, checked: bool) -> None:
        w = self.owner
        w.toolbar_remove_mode = bool(checked)
        try:
            w.btn_toolbar_remove.setStyleSheet(TOOLBAR_TRASH_BUTTON_ACTIVE_STYLE if checked else "")
        except Exception:
            pass
        if checked:
            self.status_message("Toolbar remove mode: click tools to remove, then click the trash icon again to exit", 3500)
        else:
            try:
                w.statusBar().clearMessage()
            except Exception:
                pass
        self.apply_remove_mode_visuals()
        try:
            w._sync_tool_buttons()
        except Exception:
            pass

    def apply_remove_mode_visuals(self) -> None:
        """Make every configurable toolbar entry removable while trash mode is active.

        Normal availability rules intentionally disable some modifiers/booleans
        until a part is selected.  In trash mode the click edits the toolbar
        layout, so those rules must not block the button from receiving it.
        """
        w = self.owner
        remove_mode = bool(getattr(w, "toolbar_remove_mode", False))
        style = TOOLBAR_REMOVABLE_ITEM_STYLE if remove_mode else ""
        try:
            for button in list(getattr(w, "toolbar_dynamic_buttons", {}).values()):
                if button is None:
                    continue
                try:
                    button.setEnabled(True if remove_mode else button.isEnabled())
                    button.setStyleSheet(style)
                except Exception:
                    pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Dynamic rebuild
    # ------------------------------------------------------------------
    def _clear_layout(self, layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                try:
                    # Never detach a visible toolbar widget by calling
                    # setParent(None). In Qt, a QWidget without a parent is an
                    # independent top-level window; during dynamic toolbar
                    # rebuilds that can flash as many tiny windows when a tool
                    # opens. Hiding + deleteLater keeps the widget owned by its
                    # current container until Qt destroys it safely.
                    widget.hide()
                    widget.deleteLater()
                except Exception:
                    pass

    def rebuild(self, *, save: bool = True) -> None:
        w = self.owner
        w.toolbar_item_ids = sanitized_toolbar_item_ids(
            getattr(w, "toolbar_item_ids", None),
            max_items=self.max_items(),
        )

        try:
            for button in list(getattr(w, "toolbar_dynamic_buttons", {}).values()):
                try:
                    if hasattr(w, "tool_group"):
                        w.tool_group.removeButton(button)
                    if hasattr(w, "modifier_group"):
                        w.modifier_group.removeButton(button)
                except Exception:
                    pass
        except Exception:
            pass

        for attr in self.all_button_attrs():
            try:
                setattr(w, attr, None)
            except Exception:
                pass
        w.toolbar_dynamic_buttons = {}

        for category in TOOLBAR_CATEGORY_ORDER:
            layout = getattr(w, "toolbar_category_layouts", {}).get(category)
            if layout is not None:
                self._clear_layout(layout)

        by_category: dict[str, list[Any]] = {category: [] for category in TOOLBAR_CATEGORY_ORDER}
        for item_id in w.toolbar_item_ids:
            spec = get_toolbar_item_spec(item_id)
            if spec is not None and spec.category in by_category:
                by_category[spec.category].append(spec)

        for category in TOOLBAR_CATEGORY_ORDER:
            label = w.toolbar_category_labels.get(category)
            holder = w.toolbar_category_widgets.get(category)
            layout = w.toolbar_category_layouts.get(category)
            visible = bool(by_category.get(category))
            if label is not None:
                label.setVisible(visible)
            if holder is not None:
                holder.setVisible(visible)
            if layout is None:
                continue
            for spec in by_category.get(category, []):
                button = self._item_button(spec, parent=holder)
                layout.addWidget(button)
                w.toolbar_dynamic_buttons[spec.id] = button
                if spec.button_attr:
                    setattr(w, spec.button_attr, button)

        self._sync_state_to_preferences(registry_version=False)
        if save:
            # Save immediately: users often close the app right after changing
            # toolbar tools, so a delayed layout-save timer is not enough.
            self.save_toolbar_preferences_now()
            try:
                w._save_ui_layout_preferences_now()
            except Exception:
                try:
                    w._schedule_ui_layout_preferences_save()
                except Exception:
                    pass
        try:
            w._sync_tool_buttons()
        except Exception:
            pass
        self._ensure_trash_drop_target()
        try:
            orchestrator = getattr(w, "ui_orchestration", None)
            if orchestrator is not None:
                orchestrator.register_dynamic_toolbar_anchors()
        except Exception:
            pass

    def _item_button(self, spec: Any, *, parent: Any = None) -> QToolButton:
        w = self.owner
        button = ToolbarItemDragButton(self, spec.id, parent)
        button.setObjectName(f"ToolbarItem_{spec.id.replace(':', '_')}")
        button.setProperty("toolbarItem", True)
        button.setProperty("toolbarCode", str(spec.code))
        button.setProperty("toolbarName", str(spec.name))
        button.setText(str(spec.code))
        button.setToolTip(f"{spec.name}\n{spec.description}")
        button.setCheckable(spec.kind in {"tool", "modifier"})
        button.setToolButtonStyle(Qt.ToolButtonIconOnly)
        button.setAutoRaise(False)
        button.setProperty("toolbarActionAvailable", True)
        icon = toolbar_icon(spec.id)
        if icon is not None and not icon.isNull():
            button.setIcon(icon)
            button.setIconSize(QSize(46, 46))
        # Larger fixed buttons are required for Qt to actually render the
        # enlarged icon area consistently across tool, modifier and boolean
        # actions.  Keep every category identical so visual weight no longer
        # depends on the original bitmap whitespace.
        button.setFixedSize(68, 68)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        button.setFont(font)
        button.clicked.connect(lambda checked=False, item_id=spec.id: self.activate_item(item_id))
        if spec.kind == "tool":
            w.tool_group.addButton(button)
        elif spec.kind == "modifier":
            w.modifier_group.addButton(button)
        return button

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def activate_item(self, item_id: str) -> None:
        w = self.owner
        spec = get_toolbar_item_spec(item_id)
        if spec is None:
            return
        if bool(getattr(w, "toolbar_remove_mode", False)):
            self.remove_item(item_id)
            return
        button = getattr(getattr(w, "toolbar_dynamic_buttons", {}), "get", lambda _k: None)(spec.id)
        if button is not None and button.property("toolbarActionAvailable") is False:
            self.status_message(f"{spec.name} is not available in the current selection/state", 1600)
            return
        if spec.kind in {"tool", "modifier"} and spec.tool_id:
            w.open_tool(spec.tool_id)
            return
        if spec.kind == "boolean" and spec.callback_name:
            callback = getattr(w, spec.callback_name, None)
            if callable(callback):
                callback()
            else:
                self.status_message(f"Action indisponible : {spec.name}", 1800)

    def add_item(self, item_id: str) -> bool:
        w = self.owner
        spec = get_toolbar_item_spec(item_id)
        if spec is None:
            return False
        ids = list(getattr(w, "toolbar_item_ids", []) or [])
        if spec.id in ids:
            self.status_message(f"{spec.code} is already in the toolbar", 1700)
            return False
        if len(ids) >= self.max_items():
            QMessageBox.information(
                w,
                "Toolbar full",
                f"The toolbar already contains {self.max_items()} tools. Remove one with the trash icon before adding another.",
            )
            return False
        ids.append(spec.id)
        w.toolbar_item_ids = ids
        self.rebuild(save=True)
        self.status_message(f"Added: {spec.code} - {spec.name}", 1800)
        return True

    def remove_item(self, item_id: str) -> bool:
        w = self.owner
        ids = list(getattr(w, "toolbar_item_ids", []) or [])
        if item_id not in ids:
            return False
        spec = get_toolbar_item_spec(item_id)
        ids.remove(item_id)
        w.toolbar_item_ids = ids
        self.rebuild(save=True)
        name = spec.name if spec is not None else item_id
        self.status_message(f"Removed from toolbar: {name}", 1800)
        return True

    def move_item(
        self,
        source_item_id: str | None,
        *,
        target_item_id: str | None = None,
        target_category: str | None = None,
        position: str = "before",
    ) -> bool:
        w = self.owner
        source_id = str(source_item_id or "")
        source = get_toolbar_item_spec(source_id)
        if source is None:
            return False
        ids = list(getattr(w, "toolbar_item_ids", []) or [])
        if source.id not in ids:
            return False
        if target_item_id is not None:
            target = get_toolbar_item_spec(target_item_id)
            if target is None or target.id == source.id:
                return False
            if str(target.category) != str(source.category):
                self.status_message("Cannot mix toolbar families: tools, modifiers and booleans stay separated", 2200)
                return False
            ids.remove(source.id)
            target_index = ids.index(target.id) if target.id in ids else len(ids)
            if str(position) == "after":
                target_index += 1
            ids.insert(max(0, min(target_index, len(ids))), source.id)
        elif target_category is not None:
            if str(target_category) != str(source.category):
                self.status_message("Cannot move this item into another toolbar family", 1800)
                return False
            ids.remove(source.id)
            insert_at = -1
            for i, item_id in enumerate(ids):
                spec = get_toolbar_item_spec(item_id)
                if spec is not None and str(spec.category) == str(source.category):
                    insert_at = i
            ids.insert(insert_at + 1 if insert_at >= 0 else len(ids), source.id)
        else:
            return False
        w.toolbar_item_ids = ids
        self.rebuild(save=True)
        self.status_message(f"Moved: {source.code} - {source.name}", 1100)
        return True

    def match_palette_specs(self, query: str):
        return search_toolbar_item_specs(query)

    def open_palette(self) -> None:
        w = self.owner
        try:
            existing = getattr(w, "toolbar_palette_dialog", None)
            if existing is not None and existing.isVisible():
                existing.close()
                try:
                    w.btn_toolbar_palette.setChecked(False)
                except Exception:
                    pass
                return

            from ..ui.toolbar_palette import create_toolbar_palette_dialog

            dialog = create_toolbar_palette_dialog(w)
            w.toolbar_palette_dialog = dialog

            def _palette_closed(*_args) -> None:
                try:
                    if getattr(w, "toolbar_palette_dialog", None) is dialog:
                        w.toolbar_palette_dialog = None
                except Exception:
                    pass
                try:
                    w.btn_toolbar_palette.setChecked(False)
                except Exception:
                    pass

            try:
                dialog.finished.connect(_palette_closed)
            except Exception:
                pass
            try:
                dialog.destroyed.connect(_palette_closed)
            except Exception:
                pass
            try:
                base = w.btn_toolbar_palette.mapToGlobal(w.btn_toolbar_palette.rect().bottomLeft())
                dialog.move(base)
            except Exception:
                pass
            try:
                w.btn_toolbar_palette.setChecked(True)
            except Exception:
                pass
            dialog.show()
            try:
                dialog.raise_()
                dialog.activateWindow()
            except Exception:
                pass
        except Exception:
            try:
                w.btn_toolbar_palette.setChecked(False)
            except Exception:
                pass
            log_exception("open_toolbar_palette")

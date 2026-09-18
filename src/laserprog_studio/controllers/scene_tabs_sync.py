# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from .scene_tabs_frame import DraggableSceneTabFrame


class SceneTabsSyncLayer:

    def update_project_title(self) -> None:
            """Reflect current project path/dirty state in the main window title."""
            try:
                project = getattr(self, "project_store", None)
                if project is None:
                    self.setWindowTitle("LaserProg Studio V18 - Unified Laser Workshop")
                    return
                path = getattr(project, "project_path", None)
                name = Path(path).name if path is not None else "Untitled project"
                dirty = "*" if bool(getattr(project, "dirty", False)) else ""
                scene = getattr(project, "active_scene", None)
                scene_name = getattr(scene, "name", "main") if scene is not None else "main"
                self.setWindowTitle(f"{dirty}{name} — {scene_name} - LaserProg Studio V18")
            except Exception:
                pass

    def _clear_hidden_scene_tab_bar(self, bar) -> None:
            """Clear a QTabBar without relying on QTabWidget-only APIs.

            QTabBar is the correct widget for a standalone tab strip, but unlike
            QTabWidget it does not provide a portable clear() method.  Calling
            clear() raised on real Qt/PySide builds and stopped sync_scene_tabs()
            before the visible footer strip was rebuilt, which is why only the +
            button could appear.
            """
            try:
                while bar is not None and int(bar.count()) > 0:
                    bar.removeTab(0)
            except Exception:
                log_exception("clear_hidden_scene_tab_bar")

    def sync_scene_tabs(self) -> None:
            """Synchronize the scene tab UI with ProjectStore."""
            try:
                bar = getattr(self, "scene_tab_bar", None)
                project = getattr(self, "project_store", None)
                if project is None:
                    self._sync_visible_scene_tab_strip()
                    self.update_project_title()
                    return

                active_id = str(getattr(project, "active_scene_id", "") or "")
                scene_items = list((getattr(project, "scenes", {}) or {}).values())
                current_index = 0
                dirty = bool(getattr(project, "dirty", False))

                self._syncing_scene_tabs = True
                try:
                    if bar is not None:
                        try:
                            bar.blockSignals(True)
                        except Exception:
                            pass
                        self._clear_hidden_scene_tab_bar(bar)

                        for index, scene in enumerate(scene_items):
                            scene_id = str(getattr(scene, "scene_id", "") or "")
                            label = str(getattr(scene, "name", "Scene") or "Scene")
                            if dirty and scene_id == active_id:
                                label = label + " *"
                            bar.addTab(label)
                            bar.setTabData(index, scene_id)
                            try:
                                bar.setTabToolTip(index, f"Scene: {getattr(scene, 'name', 'Scene')}")
                            except Exception:
                                pass
                            if scene_id == active_id:
                                current_index = index

                        if len(scene_items) <= 1 and bar.count() > 0:
                            try:
                                bar.setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
                            except Exception:
                                pass
                        if bar.count() > 0:
                            bar.setCurrentIndex(current_index)
                except Exception:
                    # The hidden synchronization QTabBar must never prevent the real
                    # footer widgets from being rebuilt.
                    log_exception("sync_hidden_scene_tab_bar")
                finally:
                    if bar is not None:
                        try:
                            bar.blockSignals(False)
                        except Exception:
                            pass
                    self._syncing_scene_tabs = False

                self._sync_visible_scene_tab_strip()
                self.update_project_title()
            except Exception:
                log_exception("sync_scene_tabs")

    def _clear_visible_scene_tab_strip(self) -> None:
            self._scene_tab_end_drop_zone = None
            layout = getattr(self, "scene_tabs_layout", None)
            if layout is None:
                return
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget() if item is not None else None
                if widget is not None:
                    # Do NOT detach a visible QWidget with setParent(None) here.
                    # In Qt, a child widget reparented to None becomes a top-level
                    # window until deleteLater() is processed by the event loop;
                    # this caused a tiny transient window to flash in the center of
                    # the app every time the tab strip was rebuilt after Apply,
                    # Duplicate or Paste. Hiding first keeps the widget non-visible
                    # while Qt schedules its destruction.
                    try:
                        widget.hide()
                    except Exception:
                        pass
                    widget.deleteLater()

    def _make_scene_tab_widget(
            self,
            *,
            text: str,
            scene_id: str | None = None,
            active: bool = False,
            closable: bool = False,
            tooltip: str | None = None,
        ):
            """Create one visible footer tab.

            The widget is deliberately explicit and fixed-height: it must remain
            visible even when the VTK widget above is backed by a native window.
            """
            parent = getattr(self, "scene_tabs_container", None) or getattr(self, "scene_tabs_footer", None)
            tab = DraggableSceneTabFrame(self, str(scene_id or ""), parent)
            tab.setObjectName("SceneTabChrome")
            tab.setProperty("active", "true" if active else "false")
            tab.setMinimumHeight(30)
            tab.setMaximumHeight(34)
            tab.setMinimumWidth(118)
            tab.setMaximumWidth(230)
            tab.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

            tab_l = QHBoxLayout(tab)
            tab_l.setContentsMargins(0, 0, 6 if closable else 8, 0)
            tab_l.setSpacing(0)

            btn = QToolButton(tab)
            btn.setObjectName("SceneTabLabel")
            btn.setText(str(text or "Scene"))
            btn.setToolTip(tooltip or str(text or "Scene"))
            btn.setCheckable(True)
            btn.setChecked(bool(active))
            btn.setAutoRaise(True)
            btn.setMinimumHeight(28)
            btn.setMaximumHeight(30)
            btn.setMinimumWidth(92)
            btn.setMaximumWidth(190)
            btn.clicked.connect(lambda _checked=False, sid=str(scene_id or ""): self.switch_scene_by_id(sid))
            # The label is visual only.  Let the parent frame receive mouse events,
            # otherwise dragging the text/button area never reaches the tab frame.
            try:
                btn.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            except Exception:
                try:
                    btn.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                except Exception:
                    pass
            try:
                btn.setCursor(Qt.CursorShape.OpenHandCursor)
            except Exception:
                try:
                    btn.setCursor(Qt.OpenHandCursor)
                except Exception:
                    pass
            tab_l.addWidget(btn, 1)

            if closable:
                close = QToolButton(tab)
                close.setObjectName("SceneTabClose")
                close.setText("×")
                close.setToolTip("Close scene")
                close.setAutoRaise(True)
                close.setMinimumSize(20, 20)
                close.setMaximumSize(20, 20)
                close.clicked.connect(lambda _checked=False, sid=str(scene_id or ""): self.close_scene_by_id(sid))
                try:
                    close.setCursor(Qt.CursorShape.PointingHandCursor)
                except Exception:
                    try:
                        close.setCursor(Qt.PointingHandCursor)
                    except Exception:
                        pass
                tab_l.addWidget(close, 0)

            try:
                tab.style().unpolish(tab)
                tab.style().polish(tab)
                btn.style().unpolish(btn)
                btn.style().polish(btn)
            except Exception:
                pass
            return tab

    def _make_scene_tab_end_drop_zone(self):
            """Create a flexible drop target after the last visible scene tab."""
            parent = getattr(self, "scene_tabs_container", None) or getattr(self, "scene_tabs_footer", None)
            zone = DraggableSceneTabFrame(self, "", parent)
            zone.setObjectName("SceneTabsEndDropZone")
            zone.setMinimumHeight(30)
            zone.setMinimumWidth(36)
            zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            zone.setToolTip("Drop a scene tab here to move it to the end")
            return zone

    def _sync_visible_scene_tab_strip(self) -> None:
            """Build explicit Chrome-like scene tabs in the footer.

            The strip is rebuilt from the current ProjectStore every time; no test
            or placeholder tab is required when at least one scene exists.
            """
            try:
                layout = getattr(self, "scene_tabs_layout", None)
                project = getattr(self, "project_store", None)
                if layout is None:
                    return
                self._clear_visible_scene_tab_strip()
                self._scene_tab_widgets_by_id = {}

                if project is None:
                    layout.addStretch(1)
                    return

                # Force the ProjectStore invariant.  This also protects against a
                # partially loaded/corrupted project with no active scene.
                try:
                    _active_scene = project.active_scene
                except Exception:
                    _active_scene = None
                active_id = str(getattr(project, "active_scene_id", "") or "")
                dirty = bool(getattr(project, "dirty", False))
                scene_items = list((getattr(project, "scenes", {}) or {}).values())
                scene_count = len(scene_items)

                if not scene_items:
                    fallback = QLabel("No scene", getattr(self, "scene_tabs_container", None))
                    fallback.setObjectName("SceneTabsEmptyLabel")
                    fallback.setMinimumHeight(28)
                    layout.addWidget(fallback, 0)
                    layout.addStretch(1)
                    return

                for scene in scene_items:
                    scene_id = str(getattr(scene, "scene_id", "") or "")
                    is_active = scene_id == active_id
                    label = str(getattr(scene, "name", "Scene") or "Scene")
                    if dirty and is_active:
                        label = label + " *"
                    tab_widget = self._make_scene_tab_widget(
                        text=label,
                        scene_id=scene_id,
                        active=is_active,
                        closable=scene_count > 1,
                        tooltip=f"Scene: {getattr(scene, 'name', 'Scene')} — drag left/right to reorder",
                    )
                    self._scene_tab_widgets_by_id[scene_id] = tab_widget
                    layout.addWidget(tab_widget, 0)
                self._scene_tab_end_drop_zone = self._make_scene_tab_end_drop_zone()
                layout.addWidget(self._scene_tab_end_drop_zone, 1)
                try:
                    container = getattr(self, "scene_tabs_container", None)
                    if container is not None:
                        container.updateGeometry()
                        container.update()
                    footer = getattr(self, "scene_tabs_footer", None)
                    if footer is not None:
                        footer.updateGeometry()
                        footer.update()
                except Exception:
                    pass
            except Exception:
                log_exception("sync_visible_scene_tab_strip")

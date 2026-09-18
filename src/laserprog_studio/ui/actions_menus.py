# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from ..application.creator_global_shortcuts import handle_creator_delete_shortcut, handle_creator_escape_shortcut, handle_creator_redo_shortcut, handle_creator_undo_shortcut


class UIActionsMenusLayer:
    def _apply_stylesheet(self) -> None:
        self.setStyleSheet("""
            QMainWindow {
                background: #14171b;
            }
            QWidget {
                font-size: 9pt;
                color: #e7eaee;
                selection-background-color: #4d6580;
                selection-color: #ffffff;
            }
            QToolTip {
                color: #eef2f6;
                background: #23272d;
                border: 1px solid #3a424c;
                padding: 6px 8px;
                border-radius: 6px;
            }
            QLabel#Title {
                font-size: 14pt;
                font-weight: 900;
                color: #ffffff;
            }
            QLabel#SubTitle {
                color: #98a1ab;
                font-size: 8pt;
            }
            QLabel {
                background: transparent;
            }
            QFrame#TopTools,
            QGroupBox,
            QListWidget,
            QTextEdit,
            QGraphicsView,
            QLineEdit,
            QComboBox,
            QDoubleSpinBox,
            QSpinBox,
            QPlainTextEdit {
                background: #1b1f24;
                border: 1px solid #2d333b;
                border-radius: 10px;
                color: #e7eaee;
            }
            QFrame#TopTools {
                background: #1c2128;
                border: 1px solid #303741;
                border-radius: 12px;
            }
            QFrame#ToolboxBar {
                background: #1a1f26;
                border: 1px solid #303741;
                border-radius: 22px;
            }
            QWidget#ToolboxBarHost,
            QScrollArea#ToolboxScroll,
            QScrollArea#ToolboxScroll > QWidget > QWidget,
            QWidget#SceneTabsContainer {
                background: transparent;
                border: none;
            }
            QLabel#ToolbarCategoryLabel {
                color: #9ca6b1;
                font-size: 7.5pt;
                font-weight: 900;
                padding-left: 5px;
                padding-right: 2px;
                text-transform: uppercase;
            }
            QToolButton#ToolbarPaletteButton {
                background: #2b3139;
                color: #f5f7f9;
                border: 1px solid #596575;
                border-radius: 14px;
                padding: 7px 13px;
                font-weight: 900;
            }
            QToolButton#ToolbarPaletteButton:hover {
                background: #323943;
                border-color: #728399;
            }
            QToolButton#ToolbarTrashButton {
                border-radius: 13px;
            }
            QToolButton[toolbarItem="true"] {
                background: #252b33;
                color: #eff2f5;
                border: 1px solid #47515e;
                border-radius: 15px;
                padding: 7px;
                font-weight: 900;
            }
            QToolButton[toolbarItem="true"]:hover {
                background: #2f3741;
                border-color: #7f93ad;
            }
            QToolButton[toolbarItem="true"]:checked {
                background: #405166;
                border-color: #9aacbf;
                color: #ffffff;
            }
            QFrame#ToolboxSeparator {
                color: #39414b;
                background: #39414b;
                border: none;
                max-width: 1px;
            }
            QFrame#LightTransformOverlay {
                background-color: transparent;
                border: none;
                border-radius: 18px;
            }
            QFrame#LightTransformOverlay:hover {
                background-color: transparent;
                border: none;
            }
            QFrame#LightOverlayFixedLeftCluster {
                background: transparent;
                border: none;
            }
            QFrame#LightOverlaySeparator {
                background: #4b5563;
                border: none;
                max-width: 1px;
            }
            QFrame#LightOverlayLockSlot {
                background: transparent;
                border: none;
            }
            QLabel#LightOverlayAxisLabel, QLabel#LightOverlayUnitLabel {
                color: #f4f7fb;
                font-weight: 900;
                font-size: 10pt;
            }
            QToolButton#LightOverlayCloseButton {
                background: #252d37;
                color: #f6f8fb;
                border: 1px solid #657285;
                border-radius: 12px;
                font-weight: 900;
                padding: 4px;
            }
            QToolButton#LightOverlayCloseButton:hover {
                background: #313b48;
                border-color: #9badc3;
            }
            QToolButton#LightOverlayLockButton {
                background: #202832;
                color: #f6f8fb;
                border: 1px solid #5f7084;
                border-radius: 12px;
                padding: 0px;
            }
            QToolButton#LightOverlayLockButton:hover {
                background: #2b3542;
                border-color: #a4b8d0;
            }
            QToolButton#LightOverlayLockButton:checked {
                background: #3f536a;
                border-color: #bfd0e4;
            }
            QToolButton#LightOverlayLockButton:disabled {
                background: #1c222a;
                border-color: #36404c;
            }
            QFrame#ToolIdlePanel {
                background: transparent;
                border: none;
            }
            QToolButton#LightOverlayExitButton {
                background: #f1f3f6;
                color: #16191d;
                border: 1px solid #b4bcc7;
                border-radius: 12px;
                font-weight: 900;
                padding: 5px 10px;
            }
            QToolButton#LightOverlayExitButton:hover {
                background: #e6ebf0;
                border-color: #8e9bad;
            }
            QToolButton {
                background: #252b33;
                border: 1px solid #3b434d;
                border-radius: 8px;
                padding: 4px;
                min-width: 26px;
                min-height: 24px;
            }
            QToolButton:hover {
                background: #2d353f;
                border-color: #6e7f95;
            }
            QToolButton:checked {
                background: #415163;
                border-color: #889ab0;
                color: #ffffff;
            }
            QToolButton:disabled {
                color: #6f7883;
                background: #1a1e23;
                border-color: #2b3138;
            }
            QToolButton:checked:disabled {
                color: #a8b1bc;
                background: #394654;
                border-color: #596a7d;
            }
            QPushButton {
                background: #2a3038;
                border: 1px solid #3d4651;
                border-radius: 8px;
                padding: 5px 8px;
                color: #f4f6f8;
                min-height: 18px;
                font-weight: 700;
            }
            QPushButton:hover {
                background: #323943;
                border-color: #6f8196;
            }
            QPushButton:pressed {
                background: #242a31;
            }
            QPushButton:disabled {
                color: #737d88;
                background: #1b2026;
                border-color: #2f363f;
            }

            QPushButton#PlanTraceModeButton {
                background: #26303b;
                border: 1px solid #465466;
                border-radius: 9px;
                padding: 5px 7px;
                font-weight: 900;
            }
            QPushButton#PlanTraceModeButton:hover {
                background: #314050;
                border-color: #83a0bf;
            }
            QPushButton#PlanTraceModeButton:checked {
                background: #4a6280;
                border: 1px solid #c5d7ec;
                color: #ffffff;
            }
            QPushButton#PlanTraceSnapButton {
                background: #25303b;
                border: 1px solid #465466;
                border-radius: 9px;
                padding: 5px 8px;
                font-weight: 900;
            }
            QPushButton#PlanTraceSnapButton:hover {
                background: #314050;
                border-color: #83a0bf;
            }
            QPushButton#PlanTraceSnapButton:checked {
                background: #355f4b;
                border: 1px solid #9fe6bf;
                color: #ffffff;
            }
            QPushButton#SceneHistoryButton {
                background: #39485a;
                border-color: #72849b;
                color: #f7f9fb;
                font-weight: 900;
                border-radius: 9px;
                padding: 4px 12px;
            }
            QPushButton#SceneHistoryButton:hover {
                background: #46576b;
                border-color: #8fa1b6;
            }
            QPushButton#ToolHelpButton {
                background: #39485a;
                border-color: #72849b;
                color: #f7f9fb;
                font-weight: 900;
                border-radius: 9px;
                padding: 4px 10px;
            }
            QPushButton#ToolHelpButton:hover {
                background: #46576b;
                border-color: #8fa1b6;
            }
            QGroupBox {
                font-weight: 800;
                margin-top: 8px;
                padding: 6px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
                color: #ffffff;
            }
            QListWidget, QTextEdit, QGraphicsView, QLineEdit, QComboBox {
                min-height: 18px;
                padding: 3px 6px;
            }
            QListWidget::item {
                padding: 4px 5px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: rgba(82, 101, 125, 0.42);
                color: #ffffff;
                border: 1px solid #7d8fa5;
            }
            QListWidget::item:selected:!active {
                background: rgba(82, 101, 125, 0.28);
                color: #ffffff;
                border: 1px solid #65778d;
            }
            QListWidget::item:hover {
                background: rgba(121, 134, 149, 0.12);
            }
            QDoubleSpinBox, QSpinBox {
                padding: 2px 6px;
                min-height: 18px;
            }
            QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus, QListWidget:focus {
                border: 1px solid #7b8ea5;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 22px;
                border-left: 1px solid #343b44;
            }
            QAbstractSpinBox::up-button,
            QAbstractSpinBox::down-button {
                width: 18px;
                border-left: 1px solid #343b44;
                background: #232830;
            }
            QAbstractSpinBox::up-button:hover,
            QAbstractSpinBox::down-button:hover {
                background: #2f3740;
            }
            QCheckBox, QRadioButton {
                spacing: 8px;
            }
            QCheckBox::indicator, QRadioButton::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked, QRadioButton::indicator:unchecked {
                background: #1a1f24;
                border: 1px solid #4c5560;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background: #5e738d;
                border: 1px solid #91a2b6;
                border-radius: 4px;
            }
            QRadioButton::indicator:unchecked {
                border-radius: 8px;
            }
            QRadioButton::indicator:checked {
                background: #5e738d;
                border: 1px solid #91a2b6;
                border-radius: 8px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #252b31;
                border: 1px solid #353d46;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #8b98a8;
                border: 1px solid #b7c0ca;
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::sub-page:horizontal {
                background: #5f7083;
                border-radius: 3px;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #161a1f;
                border: none;
                margin: 2px;
            }
            QScrollBar:vertical {
                width: 12px;
            }
            QScrollBar:horizontal {
                height: 12px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #333942;
                border: 1px solid #4c5560;
                border-radius: 6px;
                min-height: 24px;
                min-width: 24px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
                background: #404852;
                border-color: #7f90a4;
            }
            QScrollBar::add-line, QScrollBar::sub-line,
            QScrollBar::add-page, QScrollBar::sub-page {
                background: none;
                border: none;
            }
            QMenuBar {
                background: #171b20;
                color: #e7eaee;
                border-bottom: 1px solid #2c333b;
            }
            QMenuBar::item {
                padding: 6px 10px;
                background: transparent;
                border-radius: 6px;
            }
            QMenuBar::item:selected {
                background: rgba(124, 139, 157, 0.16);
            }
            QMenu {
                background: #1c2025;
                color: #e7eaee;
                border: 1px solid #313840;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                padding: 7px 26px 7px 10px;
                border-radius: 6px;
            }
            QMenu::item:selected {
                background: rgba(93, 108, 127, 0.25);
            }
            QMenu::separator {
                height: 1px;
                background: #313840;
                margin: 5px 4px;
            }
            QStatusBar {
                background: #171b20;
                color: #9aa4af;
                border-top: 1px solid #2c333b;
            }
            QStatusBar::item {
                border: none;
            }
            QSplitter::handle {
                background: #15191d;
            }
            QSplitter::handle:horizontal {
                width: 8px;
                border-left: 1px solid #232930;
                border-right: 1px solid #232930;
            }
            QSplitter::handle:vertical {
                height: 8px;
                border-top: 1px solid #232930;
                border-bottom: 1px solid #232930;
            }
            QFrame#SceneTabsFooter {
                background: #171b20;
                border-top: 1px solid #2d343d;
                min-height: 38px;
                max-height: 48px;
            }
            QScrollArea#SceneTabsScroll {
                background: transparent;
                border: none;
                min-height: 32px;
            }
            QTabBar#SceneTabBar {
                background: transparent;
                border: none;
                qproperty-drawBase: 0;
            }
            QTabBar#SceneTabBar::tab {
                background: #272d35;
                color: #dbe2e9;
                border: 1px solid #3a424b;
                border-bottom-color: #454f5a;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 7px 28px 7px 14px;
                margin-right: 3px;
                min-width: 96px;
                max-width: 200px;
            }
            QTabBar#SceneTabBar::tab:selected {
                background: #4a5563;
                color: #ffffff;
                border-color: #7e8e9f;
                border-bottom-color: #4a5563;
                font-weight: 900;
            }
            QTabBar#SceneTabBar::tab:hover:!selected {
                background: #313842;
                border-color: #677789;
            }
            QTabBar#SceneTabBar::close-button {
                subcontrol-position: right;
                margin-right: 7px;
            }
            QFrame#SceneTabChrome {
                background: #272d35;
                border: 1px solid #3a424b;
                border-bottom-color: #454f5a;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                min-height: 28px;
                max-height: 32px;
            }
            QFrame#SceneTabChrome[active="true"] {
                background: #4a5563;
                border-color: #7e8e9f;
                border-bottom-color: #4a5563;
            }
            QFrame#SceneTabChrome[dragging="true"] {
                background: #3a434e;
                border: 2px solid #9ba8b6;
            }
            QFrame#SceneTabChrome[dropTarget="true"] {
                border-left: 4px solid #a3afbc;
                border-color: #a3afbc;
            }
            QFrame#SceneTabsEndDropZone[dropTarget="true"] {
                background: rgba(156, 167, 179, 0.12);
                border: 1px dashed #a4afbc;
                border-radius: 8px;
            }
            QFrame#SceneTabDragGhost {
                background: #39424c;
                border: 2px solid #9aa8b7;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
            }
            QLabel#SceneTabDragGhostLabel {
                color: #ffffff;
                background: transparent;
                font-weight: 900;
            }
            QToolButton#SceneTabLabel {
                background: transparent;
                color: #dde4ea;
                border: none;
                border-radius: 0px;
                padding: 3px 8px 3px 10px;
                min-width: 88px;
                max-width: 190px;
                font-weight: 800;
                text-align: left;
            }
            QFrame#SceneTabChrome[active="true"] QToolButton#SceneTabLabel {
                color: #ffffff;
                font-weight: 900;
            }
            QLabel#SceneTabsEmptyLabel {
                color: #9aa4af;
                background: transparent;
                padding: 4px 8px;
                font-weight: 800;
            }
            QToolButton#SceneTabClose {
                background: transparent;
                color: #b5bec8;
                border: none;
                border-radius: 8px;
                padding: 0px;
                min-width: 18px;
                max-width: 18px;
                min-height: 18px;
                max-height: 18px;
                font-weight: 900;
            }
            QToolButton#SceneTabClose:hover {
                background: rgba(255, 255, 255, 0.12);
                color: #ffffff;
            }
            QToolButton#SceneNewTabButton {
                background: #2a3038;
                color: #f8fafc;
                border: 1px solid #464f59;
                border-radius: 13px;
                font-size: 13pt;
                font-weight: 900;
                padding: 0px;
                min-width: 26px;
                min-height: 24px;
            }
            QToolButton#SceneNewTabButton:hover {
                background: #363e47;
                border-color: #738498;
            }
        """)


    def export_application_performance_audit(self) -> None:
        try:
            from laserprog_studio.diagnostics.app_performance_audit import export_application_performance_audit

            path = export_application_performance_audit(reason="manual_menu")
            try:
                self.ui_log(f"[DIAGNOSTICS] Application performance audit exported: {path}")
            except Exception:
                pass
            try:
                self.statusBar().showMessage(f"Performance audit exported: {path}", 3500)
            except Exception:
                pass
        except Exception as exc:
            try:
                self.ui_log(f"[DIAGNOSTICS] Performance audit export failed: {exc}")
            except Exception:
                pass

    def _build_actions(self) -> None:
        self.act_new = QAction("New Project", self)
        self.act_new.setShortcut(QKeySequence("Ctrl+N"))
        self.act_new.triggered.connect(self.new_project)

        self.act_new_scene = QAction("New Scene", self)
        self.act_new_scene.setShortcut(QKeySequence("Ctrl+Alt+N"))
        self.act_new_scene.triggered.connect(self.new_scene)

        self.act_open_project = QAction("Open Project...", self)
        self.act_open_project.setShortcut(QKeySequence("Ctrl+O"))
        self.act_open_project.triggered.connect(self.open_project_dialog)

        self.act_save_project = QAction("Save Project", self)
        self.act_save_project.setShortcut(QKeySequence("Ctrl+S"))
        self.act_save_project.triggered.connect(self.save_project_dialog)

        self.act_save_project_as = QAction("Save Project As...", self)
        self.act_save_project_as.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.act_save_project_as.triggered.connect(self.save_project_as_dialog)

        self.act_open = QAction("Import 3MF...", self)
        self.act_open.triggered.connect(self.open_3mf_dialog)

        self.act_save_3mf = QAction("Export 3MF...", self)
        self.act_save_3mf.triggered.connect(self.export_3mf_dialog)

        self.act_import_2d_mask = QAction("Import 2D mask...", self)
        self.act_import_2d_mask.triggered.connect(self.import_2d_mask_dialog)

        self.act_export_gravure = QAction("Export engraving...", self)
        self.act_export_gravure.setShortcut(QKeySequence("Ctrl+E"))
        self.act_export_gravure.triggered.connect(self.open_engrave_workspace)

        self.act_machine_engraving = QAction("Machine / G-code + USB...", self)
        self.act_machine_engraving.setShortcut(QKeySequence("Ctrl+M"))
        self.act_machine_engraving.triggered.connect(self.open_machine_engraving_dialog)

        self.act_undo = QAction("Undo", self)
        self.act_undo.setShortcut(QKeySequence("Ctrl+Z"))
        self.act_undo.setShortcutContext(Qt.ApplicationShortcut)
        self.act_undo.triggered.connect(lambda _checked=False: handle_creator_undo_shortcut(self))
        self.addAction(self.act_undo)

        self.act_redo = QAction("Redo", self)
        try:
            self.act_redo.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        except Exception:
            self.act_redo.setShortcut(QKeySequence("Ctrl+Y"))
        self.act_redo.setShortcutContext(Qt.ApplicationShortcut)
        self.act_redo.triggered.connect(lambda _checked=False: handle_creator_redo_shortcut(self))
        self.addAction(self.act_redo)

        self.act_select_all = QAction("Select all parts", self)
        self.act_select_all.setShortcut(QKeySequence("Ctrl+A"))
        self.act_select_all.setShortcutContext(Qt.ApplicationShortcut)
        self.act_select_all.triggered.connect(self.select_all_parts)
        self.addAction(self.act_select_all)

        self.act_copy = QAction("Copy", self)
        self.act_copy.setShortcut(QKeySequence("Ctrl+C"))
        self.act_copy.setShortcutContext(Qt.ApplicationShortcut)
        self.act_copy.triggered.connect(self.copy_selected)
        self.addAction(self.act_copy)

        self.act_paste = QAction("Paste", self)
        self.act_paste.setShortcut(QKeySequence("Ctrl+V"))
        self.act_paste.setShortcutContext(Qt.ApplicationShortcut)
        self.act_paste.triggered.connect(self.paste_selection)
        self.addAction(self.act_paste)

        self.act_duplicate = QAction("Duplicate", self)
        self.act_duplicate.setShortcut(QKeySequence("Ctrl+D"))
        self.act_duplicate.setShortcutContext(Qt.ApplicationShortcut)
        self.act_duplicate.triggered.connect(self.duplicate_selected)
        self.addAction(self.act_duplicate)

        self.act_delete = QAction("Delete", self)
        self.act_delete.setShortcut(QKeySequence("Delete"))
        self.act_delete.setShortcutContext(Qt.ApplicationShortcut)
        self.act_delete.triggered.connect(lambda _checked=False: handle_creator_delete_shortcut(self))
        self.addAction(self.act_delete)

        self.act_quit = QAction("Quit", self)
        self.act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_quit.triggered.connect(self.close)

        self.act_iso = QAction("Iso view", self)
        self.act_iso.triggered.connect(self.view_iso)
        self.act_top = QAction("Top view", self)
        self.act_top.triggered.connect(self.view_top)
        self.act_bottom = QAction("Bottom view", self)
        self.act_bottom.triggered.connect(self.view_bottom)
        self.act_front = QAction("Front view", self)
        self.act_front.triggered.connect(self.view_front)
        self.act_back = QAction("Back view", self)
        self.act_back.triggered.connect(self.view_back)
        self.act_left = QAction("Left view", self)
        self.act_left.triggered.connect(self.view_left)
        self.act_right = QAction("Right view", self)
        self.act_right.triggered.connect(self.view_right)
        self.act_reset = QAction("Reset camera", self)
        self.act_reset.triggered.connect(self.reset_camera)

        self.act_perf_optimized = QAction("Optimized mode — diagnostics OFF", self)
        self.act_perf_optimized.setCheckable(True)
        self.act_perf_optimized.triggered.connect(lambda checked=True: self.set_performance_mode("optimized"))
        self.act_perf_debug = QAction("Debug diagnostics mode — ON", self)
        self.act_perf_debug.setCheckable(True)
        self.act_perf_debug.triggered.connect(lambda checked=True: self.set_performance_mode("debug"))
        self.act_export_app_perf_audit = QAction("Export application performance audit (debug)", self)
        self.act_export_app_perf_audit.setShortcut(QKeySequence("Ctrl+Alt+P"))
        self.act_export_app_perf_audit.triggered.connect(lambda _checked=False: self.export_application_performance_audit())
        self.act_preferences = QAction("Preferences", self)
        self.act_preferences.setShortcut(QKeySequence("Ctrl+,"))
        self.act_preferences.triggered.connect(lambda _checked=False: self.open_preferences_dialog())

        self.act_layout_save_current = QAction("Enregistrer la disposition actuelle…", self)
        self.act_layout_save_current.triggered.connect(lambda _checked=False: self.save_current_ui_layout())
        self.act_layout_manage = QAction("Gérer les dispositions…", self)
        self.act_layout_manage.triggered.connect(lambda _checked=False: self.open_ui_layout_manager())
        try:
            self.perf_mode_group = QActionGroup(self)
            self.perf_mode_group.setExclusive(True)
            self.perf_mode_group.addAction(self.act_perf_optimized)
            self.perf_mode_group.addAction(self.act_perf_debug)
            if str(getattr(self, "_performance_mode", "optimized")) == "debug":
                self.act_perf_debug.setChecked(True)
            else:
                self.act_perf_optimized.setChecked(True)
        except Exception:
            pass

        self.act_escape = QAction("Cancel current tool action", self)
        self.act_escape.setShortcut(QKeySequence("Esc"))
        self.act_escape.setShortcutContext(Qt.ApplicationShortcut)
        self.act_escape.triggered.connect(lambda _checked=False: handle_creator_escape_shortcut(self))
        self.addAction(self.act_escape)

    def _build_menus(self) -> None:
        menu_file = self.menuBar().addMenu("File")
        menu_file.addAction(self.act_new)
        menu_file.addAction(self.act_new_scene)
        menu_file.addAction(self.act_open_project)
        menu_file.addAction(self.act_save_project)
        menu_file.addAction(self.act_save_project_as)
        menu_file.addSeparator()
        menu_file.addAction(self.act_open)
        menu_file.addAction(self.act_import_2d_mask)
        menu_file.addSeparator()
        menu_file.addAction(self.act_save_3mf)
        menu_file.addAction(self.act_export_gravure)
        menu_file.addAction(self.act_machine_engraving)
        menu_file.addSeparator()
        menu_file.addAction(self.act_quit)

        menu_edit = self.menuBar().addMenu("Edit")
        menu_edit.addAction(self.act_undo)
        menu_edit.addAction(self.act_redo)
        menu_edit.addSeparator()
        menu_edit.addAction(self.act_select_all)
        menu_edit.addAction(self.act_copy)
        menu_edit.addAction(self.act_paste)
        menu_edit.addAction(self.act_duplicate)
        menu_edit.addAction(self.act_delete)

        menu_tools = self.menuBar().addMenu("Tools")
        try:
            from ..tooling.registry import iter_tool_specs
            for spec in iter_tool_specs(category="tool"):
                menu_tools.addAction(spec.label, lambda _checked=False, tool_id=spec.id: self.open_tool(tool_id))
            menu_tools.addSeparator()
            for spec in iter_tool_specs(category="modifier"):
                menu_tools.addAction(f"Modifier: {spec.label}", lambda _checked=False, tool_id=spec.id: self.open_tool(tool_id))
        except Exception:
            menu_tools.addAction("Primitives", lambda: self.open_tool(self.TOOL_PRIMITIVE))
            menu_tools.addAction("Box generator", lambda: self.open_tool(self.TOOL_BOX))
            menu_tools.addAction("Lay flat", lambda: self.open_tool(self.TOOL_LAYFLAT))
            menu_tools.addAction("Joint builder", lambda: self.open_tool(self.TOOL_JOINT))
            menu_tools.addAction("Engraving role painter", lambda: self.open_tool(self.TOOL_ENGRAVING))
            menu_tools.addAction("Materials", lambda: self.open_tool(self.TOOL_MATERIAL))
            menu_tools.addSeparator()
            menu_tools.addAction("Modifier: split by plane", lambda: self.open_tool(self.TOOL_MOD_SPLIT))
        menu_tools.addSeparator()
        menu_tools.addAction(self.act_escape)

        menu_machine = self.menuBar().addMenu("Machine")
        menu_machine.addAction(self.act_export_gravure)
        menu_machine.addAction(self.act_machine_engraving)

        menu_view = self.menuBar().addMenu("View")
        menu_view.addAction(self.act_iso)
        menu_view.addSeparator()
        for act in [self.act_top, self.act_bottom, self.act_front, self.act_back, self.act_left, self.act_right]:
            menu_view.addAction(act)
        menu_view.addSeparator()
        menu_view.addAction(self.act_reset)
        menu_view.addSeparator()
        self.menu_ui_layouts = menu_view.addMenu("Dispositions de l’interface")
        self.menu_ui_layouts.aboutToShow.connect(self._rebuild_ui_layout_menu)
        self._rebuild_ui_layout_menu()
        menu_view.addSeparator()
        perf_menu = menu_view.addMenu("Performance / Debug")
        perf_menu.addAction(self.act_perf_optimized)
        perf_menu.addAction(self.act_perf_debug)
        perf_menu.addSeparator()
        perf_menu.addAction(self.act_export_app_perf_audit)

        self.menuBar().addAction(self.act_preferences)
        self.ui_log("[UI] Menus created: File / Edit / Tools / Machine / View / Layouts / Preferences")


    def open_preferences_dialog(self) -> None:
        try:
            from .preferences_dialog import open_project_preferences_dialog

            open_project_preferences_dialog(self)
        except Exception:
            log_exception("open_preferences_dialog")

# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class UILayoutPanelsLayer:
    def _build_main_ui(self) -> None:
        root = QSplitter(Qt.Horizontal, self)
        self.main_splitter = root
        self.setCentralWidget(root)
        self.left_panel = self._make_left_panel()
        root.addWidget(self.left_panel)
        self.center_panel = self._make_center_panel()
        root.addWidget(self.center_panel)
        self.right_panel = self._make_right_panel()
        root.addWidget(self.right_panel)
        try:
            root.setStretchFactor(0, 0)
            root.setStretchFactor(1, 1)
            root.setStretchFactor(2, 0)
        except Exception:
            pass
        try:
            from ..services.ui_preferences import load_ui_layout_preferences
            state = getattr(self, "ui_layout_state", None)
            if state is not None and hasattr(state, "apply_preferences"):
                state.apply_preferences(load_ui_layout_preferences())
                root.setSizes(state.preferred_full_sizes())
            else:
                root.setSizes([220, 1120, 260])
        except Exception:
            root.setSizes([220, 1120, 260])
        # Light UI is a true compact workspace: both side panes can collapse.
        # The center viewport remains non-collapsible.
        root.setCollapsible(0, True)
        root.setCollapsible(1, False)
        root.setCollapsible(2, True)
        try:
            root.splitterMoved.connect(self._on_main_splitter_moved)
        except Exception:
            pass
        self.ui_log("[UI] Studio V18 UI created")

    def _make_title(self, text: str, subtitle: bool = False) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("SubTitle" if subtitle else "Title")
        return lbl

    def _make_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(160)
        panel.setMaximumWidth(16777215)
        panel.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        # The left pane now contains more controls (final render + render camera).
        # Without a scroll area, Qt compresses the Parts list first when the app
        # height is limited.  Keep the pane usable by scrolling the whole left
        # content, like the inspector on the right side.
        outer_layout = QVBoxLayout(panel)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        self.left_scroll_area = QScrollArea(panel)
        self.left_scroll_area.setWidgetResizable(True)
        self.left_scroll_area.setFrameShape(QFrame.NoFrame)
        self.left_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.left_scroll_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer_layout.addWidget(self.left_scroll_area, 1)

        left_content = QWidget()
        left_content.setMinimumWidth(0)
        left_content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.MinimumExpanding)
        self.left_scroll_area.setWidget(left_content)
        layout = QVBoxLayout(left_content)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(8)
        layout.addWidget(self._make_title("LaserProg"))
        layout.addWidget(self._make_title("Laser modeling studio", subtitle=True))

        project_box = QGroupBox("Project")
        p = QVBoxLayout(project_box)
        for text, fn in [("New project", self.new_project), ("Open project", self.open_project_dialog), ("Save project", self.save_project_dialog), ("Import 3MF", self.open_3mf_dialog), ("Export 3MF", self.export_3mf_dialog)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            p.addWidget(b)

        history_label = QLabel("History")
        history_label.setObjectName("SubTitle")
        p.addWidget(history_label)
        hist_row = QHBoxLayout()
        hist_row.setSpacing(4)
        self.btn_project_undo = QPushButton("Undo")
        self.btn_project_redo = QPushButton("Redo")
        self.btn_project_undo.setToolTip("Undo last scene action (Ctrl+Z)")
        self.btn_project_redo.setToolTip("Redo undone scene action (Ctrl+Y)")
        self.btn_project_undo.setMinimumWidth(0)
        self.btn_project_redo.setMinimumWidth(0)
        self.btn_project_undo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_project_redo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_project_undo.clicked.connect(self.undo_scene)
        self.btn_project_redo.clicked.connect(self.redo_scene)
        hist_row.addWidget(self.btn_project_undo)
        hist_row.addWidget(self.btn_project_redo)
        p.addLayout(hist_row)
        # Stable names used by history sync/tests.  The history
        # actions live in the left Project pane now; the top 3D toolbar no
        # longer creates duplicate Undo/Redo buttons.
        self.btn_undo = self.btn_project_undo
        self.btn_redo = self.btn_project_redo
        layout.addWidget(project_box)

        list_box = QGroupBox("Parts")
        # Keep roughly ten parts visible before the left pane scrolls.  The
        # previous 130 px list height only showed about three rows on Windows
        # once the extra render/view controls compressed the scroll content.
        visible_part_rows = 10
        part_row_height = 24
        parts_list_height = visible_part_rows * part_row_height + 14
        list_box.setMinimumHeight(parts_list_height + 86)
        list_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        l = QVBoxLayout(list_box)
        self.mesh_list = QListWidget()
        self.mesh_list.setMinimumHeight(parts_list_height)
        self.mesh_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.mesh_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.mesh_list.itemClicked.connect(self.on_list_clicked)
        l.addWidget(self.mesh_list, 1)
        actions_col = QVBoxLayout()
        actions_col.setSpacing(4)
        b_dup = QPushButton("Duplicate")
        b_del = QPushButton("Delete")
        b_dup.setMinimumWidth(0)
        b_del.setMinimumWidth(0)
        b_dup.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b_del.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        b_dup.clicked.connect(self.duplicate_selected)
        b_del.clicked.connect(self.delete_selected)
        actions_col.addWidget(b_dup)
        actions_col.addWidget(b_del)
        l.addLayout(actions_col)
        layout.addWidget(list_box, 1)

        view_box = QGroupBox("View")
        v = QVBoxLayout(view_box)
        b_iso = QPushButton("Iso / free orbit")
        b_iso.clicked.connect(self.view_iso)
        v.addWidget(b_iso)

        net_title = QLabel("Orthographic view net")
        net_title.setObjectName("SubTitle")
        v.addWidget(net_title)
        net = QGridLayout()
        net.setSpacing(4)
        view_buttons = [
            ("Top", self.view_top, 0, 1),
            ("Left", self.view_left, 1, 0),
            ("Front", self.view_front, 1, 1),
            ("Right", self.view_right, 1, 2),
            ("Back", self.view_back, 2, 0),
            ("Bottom", self.view_bottom, 2, 1),
        ]
        for text, fn, row_i, col_i in view_buttons:
            b = QPushButton(text)
            b.clicked.connect(fn)
            b.setMinimumWidth(0)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            net.addWidget(b, row_i, col_i)
        v.addLayout(net)

        b_reset = QPushButton("Reset camera")
        b_reset.clicked.connect(self.reset_camera)
        v.addWidget(b_reset)

        workspace_title = QLabel("Workspace")
        workspace_title.setObjectName("SubTitle")
        v.addWidget(workspace_title)
        workspace_row = QHBoxLayout()
        workspace_row.setSpacing(4)
        self.btn_floor_grid = QToolButton()
        self.btn_floor_grid.setText("Grid")
        self.btn_floor_grid.setToolTip("Show or hide the 10 mm floor grid")
        self.btn_floor_grid.setCheckable(True)
        self.btn_floor_grid.setMinimumSize(0, 30)
        self.btn_floor_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid_font = QFont()
        grid_font.setPointSize(9)
        grid_font.setBold(True)
        self.btn_floor_grid.setFont(grid_font)
        self.btn_floor_grid.setChecked(bool(self.show_floor_grid))
        self.btn_floor_grid.toggled.connect(self.set_floor_grid_visible)
        workspace_row.addWidget(self.btn_floor_grid)

        self.btn_light_ui_toggle = QToolButton()
        self.btn_light_ui_toggle.setText("Light UI")
        self.btn_light_ui_toggle.setToolTip("Toggle the compact light transform UI")
        self.btn_light_ui_toggle.setCheckable(True)
        self.btn_light_ui_toggle.setMinimumSize(0, 30)
        self.btn_light_ui_toggle.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        ui_font = QFont()
        ui_font.setPointSize(9)
        ui_font.setBold(True)
        self.btn_light_ui_toggle.setFont(ui_font)
        self.btn_light_ui_toggle.toggled.connect(self._on_light_ui_button_toggled)
        workspace_row.addWidget(self.btn_light_ui_toggle)
        v.addLayout(workspace_row)

        render_row = QVBoxLayout()
        render_row.setSpacing(2)
        render_row.addWidget(QLabel("Render"))
        self.display_mode_combo = QComboBox()
        self.display_mode_combo.addItem("Wireframe", "wireframe")
        self.display_mode_combo.addItem("Solid", "solid")
        self.display_mode_combo.addItem("Materials", "material")
        self.display_mode_combo.setMinimumWidth(0)
        self.display_mode_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.display_mode_combo.currentIndexChanged.connect(lambda _index=0: self.on_display_mode_changed())
        render_row.addWidget(self.display_mode_combo)
        v.addLayout(render_row)

        self.edges_check = QCheckBox("Show edges")
        self.edges_check.setChecked(True)
        self.edges_check.stateChanged.connect(self.toggle_edges)
        self.ghost_check = QCheckBox("Dim inactive selection")
        self.ghost_check.stateChanged.connect(self.toggle_ghost)
        v.addWidget(self.edges_check)
        v.addWidget(self.ghost_check)

        self.material_render_box = QGroupBox("Material render")
        mr = QGridLayout(self.material_render_box)
        mr.setContentsMargins(4, 7, 4, 4)
        mr.setSpacing(3)
        state = getattr(self, "render_state", None)
        self.material_render_light_intensity = self._spin(0.0, 4.0, float(getattr(state, "material_light_intensity", 1.4)), 0.1)
        self.material_render_ambient = self._spin(0.0, 1.0, float(getattr(state, "material_ambient", 0.18)), 0.05)
        self.material_render_specular = self._spin(0.0, 1.0, float(getattr(state, "material_specular", 0.55)), 0.05)
        self.material_render_azimuth = self._spin(-180.0, 180.0, float(getattr(state, "material_light_azimuth", -45.0)), 5.0)
        self.material_render_elevation = self._spin(0.0, 90.0, float(getattr(state, "material_light_elevation", 45.0)), 5.0)
        render_rows = [
            ("Intensity", self.material_render_light_intensity),
            ("Ambient", self.material_render_ambient),
            ("Highlights", self.material_render_specular),
            ("Azimuth", self.material_render_azimuth),
            ("Elevation", self.material_render_elevation),
        ]
        for row_i, (label, widget) in enumerate(render_rows):
            mr.addWidget(QLabel(label), row_i, 0)
            mr.addWidget(widget, row_i, 1)
        self.material_render_shadows = QCheckBox("Real shadows")
        self.material_render_shadows.setChecked(False)
        self.material_render_shadows.setVisible(False)
        mr.addWidget(self.material_render_shadows, len(render_rows), 0, 1, 2)
        for widget in (
            self.material_render_light_intensity,
            self.material_render_ambient,
            self.material_render_specular,
            self.material_render_azimuth,
            self.material_render_elevation,
        ):
            try:
                signal = widget.toggled if hasattr(widget, "toggled") else widget.valueChanged
                signal.connect(self._on_material_render_params_changed)
            except Exception:
                pass
        v.addWidget(self.material_render_box)
        self.material_render_box.setVisible(False)

        final_render_box = QGroupBox("Final render")
        fr = QVBoxLayout(final_render_box)
        render_info = QLabel("The render camera is stored separately. Shadows appear only in the render window.")
        render_info.setWordWrap(True)
        fr.addWidget(render_info)
        cam_row = QVBoxLayout()
        cam_row.setSpacing(4)
        self.btn_render_camera = QPushButton("Camera")
        self.btn_render_camera.setMinimumWidth(0)
        self.btn_render_camera.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_render_camera.setToolTip("Save the current editor camera as the render camera")
        self.btn_render_camera.clicked.connect(self.capture_render_camera_from_editor)
        self.btn_open_render = QPushButton("Render")
        self.btn_open_render.setMinimumWidth(0)
        self.btn_open_render.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_open_render.setToolTip("Open a separate square render window with shadows")
        self.btn_open_render.clicked.connect(self.open_render_preview_window)
        cam_row.addWidget(self.btn_render_camera)
        cam_row.addWidget(self.btn_open_render)
        fr.addLayout(cam_row)
        v.addWidget(final_render_box)

        layout.addWidget(view_box)
        layout.addStretch(1)
        return panel

    def _make_center_panel(self) -> QWidget:
        """Center area: 3D workspace page + engraving export page.

        Engraving export replaces the 3D view in the center area.
        """
        outer = QWidget()
        outer.setMinimumWidth(0)
        outer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        self.center_stack = QStackedWidget()
        self.center_stack.setMinimumWidth(0)
        self.center_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        outer_layout.addWidget(self.center_stack)
        self.page_3d = self._make_3d_workspace()
        self.page_engrave = self._make_engrave_workspace()
        self.center_stack.addWidget(self.page_3d)
        self.center_stack.addWidget(self.page_engrave)
        return outer

    def _make_3d_workspace(self) -> QWidget:
        from pyvistaqt import QtInteractor
        panel = QWidget()
        panel.setMinimumWidth(0)
        panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        top = QFrame()
        top.setObjectName("ToolboxBar")
        top.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        top_l = QHBoxLayout(top)
        top_l.setContentsMargins(14, 9, 14, 9)
        top_l.setSpacing(9)
        self.btn_toolbar_palette = QToolButton()
        self.btn_toolbar_palette.setObjectName("ToolbarPaletteButton")
        self.btn_toolbar_palette.setText("+ Tools")
        self.btn_toolbar_palette.setToolTip("Open/close the tool palette and add an item to the toolbar")
        self.btn_toolbar_palette.setCheckable(True)
        self.btn_toolbar_palette.setMinimumSize(96, 44)
        self.btn_toolbar_palette.setMaximumSize(124, 50)
        palette_font = QFont()
        palette_font.setPointSize(9)
        palette_font.setBold(True)
        self.btn_toolbar_palette.setFont(palette_font)
        self.btn_toolbar_palette.clicked.connect(self.open_toolbar_palette)
        top_l.addWidget(self.btn_toolbar_palette)

        sep_palette = QFrame()
        sep_palette.setObjectName("ToolboxSeparator")
        sep_palette.setFrameShape(QFrame.VLine)
        sep_palette.setFrameShadow(QFrame.Sunken)
        sep_palette.setFixedHeight(28)
        top_l.addWidget(sep_palette)

        # The center toolbar is now a real toolbox: only tool entries and
        # toolbar-management actions live here.  Transform modes, Grid, Light UI
        # and Apply/Cancel live in side panels where they do not inflate the
        # viewport minimum width.  The dynamic setup still creates window attrs
        # such as self.btn_tool_material for older controllers/tests.
        self._setup_configurable_toolbar(top_l)

        sep_tools = QFrame()
        sep_tools.setObjectName("ToolboxSeparator")
        sep_tools.setFrameShape(QFrame.VLine)
        sep_tools.setFrameShadow(QFrame.Sunken)
        sep_tools.setFixedHeight(28)
        top_l.addWidget(sep_tools)

        self.btn_toolbar_remove = QToolButton()
        self.btn_toolbar_remove.setObjectName("ToolbarTrashButton")
        self.btn_toolbar_remove.setText("🗑")
        self.btn_toolbar_remove.setToolTip("Remove mode: click a toolbar item to remove it")
        self.btn_toolbar_remove.setCheckable(True)
        self.btn_toolbar_remove.setMinimumSize(48, 48)
        self.btn_toolbar_remove.setMaximumSize(56, 54)
        self.btn_toolbar_remove.toggled.connect(self._set_toolbar_remove_mode)
        top_l.addWidget(self.btn_toolbar_remove)

        # The toolbar contains fixed-size tool chips.  It should look centred
        # when there is room, but it must not become the minimum width of the whole 3D viewport
        # when many tools are present.  A resizable host centers the
        # capsule; the scroll area only appears when the capsule is wider than
        # the viewport.
        self.top_toolbar_host = QWidget(panel)
        self.top_toolbar_host.setObjectName("ToolboxBarHost")
        self.top_toolbar_host.setMinimumWidth(0)
        self.top_toolbar_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        host_l = QHBoxLayout(self.top_toolbar_host)
        host_l.setContentsMargins(0, 0, 0, 0)
        host_l.setSpacing(0)
        host_l.addStretch(1)
        host_l.addWidget(top, 0, Qt.AlignCenter)
        host_l.addStretch(1)

        self.top_toolbar_scroll = QScrollArea(panel)
        self.top_toolbar_scroll.setObjectName("ToolboxScroll")
        self.top_toolbar_scroll.setWidgetResizable(True)
        self.top_toolbar_scroll.setFrameShape(QFrame.NoFrame)
        self.top_toolbar_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.top_toolbar_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.top_toolbar_scroll.setMinimumWidth(0)
        self.top_toolbar_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.top_toolbar_scroll.setWidget(self.top_toolbar_host)
        try:
            self.top_toolbar_scroll.setMinimumHeight(max(int(top.sizeHint().height()) + 12, 82))
            self.top_toolbar_scroll.setMaximumHeight(max(int(top.sizeHint().height()) + 26, 104))
        except Exception:
            pass
        layout.addWidget(self.top_toolbar_scroll)

        self.plotter_area = QFrame(panel)
        self.plotter_area.setMinimumWidth(0)
        self.plotter_area.setFrameShape(QFrame.NoFrame)
        self.plotter_area.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        plotter_area_layout = QVBoxLayout(self.plotter_area)
        plotter_area_layout.setContentsMargins(0, 0, 0, 0)
        plotter_area_layout.setSpacing(0)

        self.plotter = QtInteractor(self.plotter_area, auto_update=False)
        self.plotter.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        try:
            self.plotter.set_background("#F3F6FA")
        except Exception:
            pass
        try:
            self.plotter.ren_win.SetMultiSamples(0)
            log("[VTK] RenderWindow MultiSamples=0")
        except Exception:
            log_exception("SetMultiSamples")
        try:
            self.plotter.enable_anti_aliasing("none")
            log("[PYVISTA] Anti aliasing none")
        except Exception:
            log("[PYVISTA] Anti aliasing none ignore/non disponible")
        plotter_area_layout.addWidget(self.plotter)
        try:
            from laserprog_studio.rendering.render_scheduler import install_central_render_scheduler
            install_central_render_scheduler(self, self.plotter, coalesce_delay_ms=0)
            log("[RENDER] Central render scheduler installed")
        except Exception:
            log_exception("install_central_render_scheduler")
        # Parent the light transform overlay directly to the VTK/Qt viewport.
        # As a child of the wrapper area it could be hidden behind the native
        # render widget on some Qt/VTK builds.
        self.light_transform_overlay = self._make_light_transform_overlay(self.plotter)
        self.light_transform_overlay.hide()
        layout.addWidget(self.plotter_area, 1)

        self.scene_tabs_footer = QFrame(panel)
        self.scene_tabs_footer.setObjectName("SceneTabsFooter")
        self.scene_tabs_footer.setMinimumHeight(40)
        self.scene_tabs_footer.setMaximumHeight(48)
        self.scene_tabs_footer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        footer_l = QHBoxLayout(self.scene_tabs_footer)
        footer_l.setContentsMargins(6, 3, 6, 2)
        footer_l.setSpacing(6)

        # Hidden QTabBar kept as a hidden synchronization model for existing
        # controller/tests.  The visible strip below uses explicit widgets because
        # native QTabBar rendering is unreliable when embedded under VTK on some
        # Windows/PyVista builds: the + button remained visible while tab shapes
        # were clipped or not painted.
        self.scene_tab_bar = QTabBar(self.scene_tabs_footer)
        self.scene_tab_bar.setObjectName("SceneTabBar")
        self.scene_tab_bar.setExpanding(False)
        self.scene_tab_bar.setMovable(False)
        self.scene_tab_bar.setTabsClosable(True)
        self.scene_tab_bar.setDrawBase(False)
        self.scene_tab_bar.setUsesScrollButtons(True)
        try:
            self.scene_tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        except Exception:
            try:
                self.scene_tab_bar.setElideMode(Qt.ElideRight)
            except Exception:
                pass
        try:
            self.scene_tab_bar.setShape(QTabBar.Shape.RoundedNorth)
        except Exception:
            try:
                self.scene_tab_bar.setShape(QTabBar.RoundedNorth)
            except Exception:
                pass
        self.scene_tab_bar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.scene_tab_bar.currentChanged.connect(self.switch_scene_tab_by_index)
        self.scene_tab_bar.tabCloseRequested.connect(self.close_scene_tab_by_index)
        self.scene_tab_bar.setVisible(False)
        footer_l.addWidget(self.scene_tab_bar, 0)

        # Visible scene tabs are inserted directly in the footer layout.  The
        # previous QScrollArea-based host could stay visually empty on some
        # Qt/VTK combinations even though the + button was visible, because the
        # scroll viewport compressed/clipped the child tab widgets.  Direct
        # footer children make the first tab visible unconditionally.
        self.scene_tabs_container = self.scene_tabs_footer
        self.scene_tabs_layout = QHBoxLayout()
        self.scene_tabs_layout.setContentsMargins(0, 0, 0, 0)
        self.scene_tabs_layout.setSpacing(3)
        footer_l.addLayout(self.scene_tabs_layout, 1)

        self.btn_new_scene_tab = QToolButton(self.scene_tabs_footer)
        self.btn_new_scene_tab.setObjectName("SceneNewTabButton")
        self.btn_new_scene_tab.setText("+")
        self.btn_new_scene_tab.setToolTip("New scene")
        self.btn_new_scene_tab.setFixedSize(30, 26)
        self.btn_new_scene_tab.clicked.connect(self.new_scene)
        footer_l.addWidget(self.btn_new_scene_tab, 0, Qt.AlignBottom)
        layout.addWidget(self.scene_tabs_footer)
        try:
            self.sync_scene_tabs()
        except Exception:
            pass

        self._setup_vtk_interaction()
        return panel


    def _make_engrave_workspace(self) -> QWidget:
        panel = QWidget()
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 6, 6, 6)

        header = QFrame()
        header.setObjectName("TopTools")
        h = QHBoxLayout(header)
        h.setContentsMargins(10, 8, 10, 8)
        title = QLabel("Engraving export")
        title.setObjectName("Title")
        h.addWidget(title)
        h.addStretch(1)
        b_back = QPushButton("Back to 3D")
        b_back.clicked.connect(self.close_engrave_workspace)
        h.addWidget(b_back)
        root.addWidget(header)

        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        left = QWidget()
        left.setMinimumWidth(250)
        left.setMaximumWidth(340)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 6, 0)

        file_box = QGroupBox("Source")
        fv = QVBoxLayout(file_box)
        self.engrave_source_label = QLabel("Source: current model")
        self.engrave_source_label.setWordWrap(True)
        fv.addWidget(self.engrave_source_label)
        self.engrave_status = QLabel("Open this view via File > Export engraving.")
        self.engrave_status.setWordWrap(True)
        fv.addWidget(self.engrave_status)
        lv.addWidget(file_box)

        params = QGroupBox("Parameters")
        pv_l = QGridLayout(params)
        self.eng_dpi = QSpinBox(); self.eng_dpi.setRange(50, 600); self.eng_dpi.setValue(220)
        self.eng_contour_width = self._spin(0.01, 2.0, 0.12, 0.01)
        self.eng_contour_margin = self._spin(-2.0, 2.0, 0.0, 0.01)
        self.eng_fill_margin = self._spin(-2.0, 2.0, 0.0, 0.01)
        self.eng_fill_edge = self._spin(0.0, 1.0, 0.02, 0.01)
        self.eng_normal_z = self._spin(0.0, 1.0, 0.5, 0.01)
        self.eng_page_margin = self._spin(0.0, 0.30, 0.08, 0.005)
        self.eng_label_px = QSpinBox(); self.eng_label_px.setRange(8, 80); self.eng_label_px.setValue(22)
        self.eng_min_px = QSpinBox(); self.eng_min_px.setRange(300, 2000); self.eng_min_px.setValue(700)
        rows = [
            ("DPI", self.eng_dpi),
            ("Contour width", self.eng_contour_width),
            ("Contour margin", self.eng_contour_margin),
            ("Fill margin", self.eng_fill_margin),
            ("Fill edge", self.eng_fill_edge),
            ("Normal Z threshold", self.eng_normal_z),
            ("Page margin", self.eng_page_margin),
            ("Thickness text", self.eng_label_px),
            ("Min size", self.eng_min_px),
        ]
        for r, (label, widget) in enumerate(rows):
            pv_l.addWidget(QLabel(label), r, 0)
            pv_l.addWidget(widget, r, 1)
        self.eng_grid = QCheckBox("10 mm on-screen grid")
        pv_l.addWidget(self.eng_grid, len(rows), 0, 1, 2)
        lv.addWidget(params)

        actions = QGroupBox("Actions")
        av = QVBoxLayout(actions)
        b_render = QPushButton("Recompute")
        b_render.clicked.connect(self.render_engrave_current)
        av.addWidget(b_render)
        b_save_all = QPushButton("Export images + Falcon SVG")
        b_save_all.clicked.connect(self.save_engrave_all)
        av.addWidget(b_save_all)
        b_svg = QPushButton("Export Falcon SVG only")
        b_svg.clicked.connect(self.save_engrave_falcon_svg)
        av.addWidget(b_svg)
        b_machine = QPushButton("Machine / G-code + USB")
        b_machine.clicked.connect(self.open_machine_engraving_dialog)
        av.addWidget(b_machine)
        b_dim = QPushButton("Export dimensions JSON")
        b_dim.clicked.connect(self.save_engrave_dimensions_json)
        av.addWidget(b_dim)
        lv.addWidget(actions)

        legend = QLabel("Rule: green -> outline/cut vector; red -> filled engraving vector. TEX Engrave exports raster; TEX Cut exports traced vector contours. 04 shows a texture preview.")
        legend.setWordWrap(True)
        lv.addWidget(legend)
        lv.addStretch(1)
        split.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(6, 0, 0, 0)
        self.engrave_laser_view = Image2DViewer()
        self.engrave_top_view = Image2DViewer()
        self.engrave_thick_view = Image2DViewer()
        self.engrave_texture_view = Image2DViewer()
        laser_box = QGroupBox("01 - Mesh laser layer (B/W)")
        lz = QVBoxLayout(laser_box); lz.addWidget(self.engrave_laser_view)
        rv.addWidget(laser_box, 3)
        bottom = QHBoxLayout()
        top_box = QGroupBox("02 - Top-down preview")
        tb = QVBoxLayout(top_box); tb.addWidget(self.engrave_top_view)
        thick_box = QGroupBox("03 - Thickness")
        thb = QVBoxLayout(thick_box); thb.addWidget(self.engrave_thick_view)
        texture_box = QGroupBox("04 - Texture layer")
        txb = QVBoxLayout(texture_box); txb.addWidget(self.engrave_texture_view)
        bottom.addWidget(top_box)
        bottom.addWidget(thick_box)
        bottom.addWidget(texture_box)
        rv.addLayout(bottom, 2)
        split.addWidget(right)
        split.setSizes([300, 920])
        return panel

    def _history_button(self, text: str, tooltip: str, callback) -> QToolButton:
        b = QToolButton()
        b.setText(text)
        b.setToolTip(tooltip)
        b.setCheckable(False)
        b.setMinimumSize(54, 34)
        b.setMaximumSize(72, 38)
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        b.setFont(font)
        b.clicked.connect(callback)
        return b

    def _tool_button(self, icon_text: str, tooltip: str, tool_id: str) -> QToolButton:
        b = QToolButton()
        b.setText(icon_text)
        b.setToolTip(tooltip)
        b.setCheckable(True)
        b.setMinimumSize(38, 34)
        b.setMaximumSize(44, 38)
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        b.setFont(font)
        b.clicked.connect(lambda checked=False, t=tool_id: self.open_tool(t))
        self.tool_group.addButton(b)
        return b

    def _boolean_button(self, icon_text: str, tooltip: str, callback) -> QToolButton:
        b = QToolButton()
        b.setText(icon_text)
        b.setToolTip(tooltip)
        b.setCheckable(False)
        b.setMinimumSize(44, 34)
        b.setMaximumSize(58, 38)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        b.setFont(font)
        b.clicked.connect(callback)
        return b

    def _modifier_button(self, icon_text: str, tooltip: str, tool_id: str) -> QToolButton:
        b = QToolButton()
        b.setText(icon_text)
        b.setToolTip(tooltip)
        b.setCheckable(True)
        b.setMinimumSize(44, 34)
        b.setMaximumSize(58, 38)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        b.setFont(font)
        b.clicked.connect(lambda checked=False, t=tool_id: self.open_tool(t))
        self.modifier_group.addButton(b)
        return b

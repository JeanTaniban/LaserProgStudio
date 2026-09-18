# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from .tool_panel_factory import ToolPanelFactory


class UIToolPanelsLayer:
    # layout test marker: outer.setMinimumWidth(220)
    def _make_right_panel(self) -> QWidget:
        outer = QWidget()
        outer.setMinimumWidth(200)
        outer.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        outer_layout = QVBoxLayout(outer)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content.setMinimumWidth(0)
        content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)
        layout.addWidget(self._make_title("Inspector"))

        sel_box = QGroupBox("Selection")
        s = QVBoxLayout(sel_box)
        s.setContentsMargins(4, 7, 4, 4); s.setSpacing(2)
        self.selection_label = QLabel("No selection")
        self.bounds_label = QLabel("Dimensions : -")
        self.selection_label.setWordWrap(True)
        self.bounds_label.setWordWrap(True)
        s.addWidget(self.selection_label)
        s.addWidget(self.bounds_label)
        layout.addWidget(sel_box)

        self.transform_box = QGroupBox("Transformation")
        g = QVBoxLayout(self.transform_box)
        g.setContentsMargins(3, 7, 3, 3); g.setSpacing(3)

        mode_row = QHBoxLayout(); mode_row.setSpacing(4)
        mode_label = QLabel("Mode"); mode_label.setFixedWidth(50); mode_row.addWidget(mode_label)
        self.transform_group = QButtonGroup(self); self.transform_group.setExclusive(True)
        self.btn_tf_none = self._transform_button("N", "None", self.TRANSFORM_NONE)
        self.btn_tf_translate = self._transform_button("T", "Translate", self.TRANSFORM_TRANSLATE)
        self.btn_tf_rotate = self._transform_button("R", "Rotate", self.TRANSFORM_ROTATE)
        self.btn_tf_scale = self._transform_button("S", "Scale", self.TRANSFORM_SCALE)
        for b in [self.btn_tf_none, self.btn_tf_translate, self.btn_tf_rotate, self.btn_tf_scale]:
            b.setMinimumSize(30, 30); b.setMaximumSize(16777215, 34); b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            mode_row.addWidget(b)
        g.addLayout(mode_row)
        self._sync_transform_buttons()

        self.pos_x = self._spin(-100000, 100000, 0, 1)
        self.pos_y = self._spin(-100000, 100000, 0, 1)
        self.pos_z = self._spin(-100000, 100000, 0, 1)
        self.rot_x = self._spin(-360, 360, 0, 5)
        self.rot_y = self._spin(-360, 360, 0, 5)
        self.rot_z = self._spin(-360, 360, 0, 5)
        self.scale_x = self._spin(0.0, 100000, 1, 1)
        self.scale_y = self._spin(0.0, 100000, 1, 1)
        self.scale_z = self._spin(0.0, 100000, 1, 1)
        g.addLayout(self._triple_row("Position", self.pos_x, self.pos_y, self.pos_z, "mm"))
        g.addLayout(self._triple_row("Rotation", self.rot_x, self.rot_y, self.rot_z, "deg"))
        g.addLayout(self._triple_row("Size", self.scale_x, self.scale_y, self.scale_z, "mm"))
        self.scale_ratio_lock_check = QCheckBox("Lock size ratio")
        self.scale_ratio_lock_check.setToolTip("When enabled, editing one size axis scales the other axes proportionally. It also makes scale gizmo drags uniform.")
        self.scale_ratio_lock_check.setChecked(bool(getattr(self, "scale_ratio_locked", False)))
        self.scale_ratio_lock_check.toggled.connect(self._on_scale_ratio_lock_changed)
        g.addWidget(self.scale_ratio_lock_check)
        for spin in (
            self.pos_x, self.pos_y, self.pos_z,
            self.rot_x, self.rot_y, self.rot_z,
            self.scale_x, self.scale_y, self.scale_z,
        ):
            spin.valueChanged.connect(self._on_transform_field_changed)

        snap_box = QGroupBox("Transform snap")
        snap_l = QGridLayout(snap_box)
        snap_l.setContentsMargins(4, 7, 4, 4)
        snap_l.setSpacing(3)
        self.grid_snap_check = QCheckBox("Grid snap")
        self.smart_snap_check = QCheckBox("Smart snap")
        self.rotation_snap_check = QCheckBox("Rotation snap")
        self.grid_snap_check.setChecked(bool(self.grid_snap_enabled))
        self.smart_snap_check.setChecked(bool(self.smart_snap_enabled))
        self.rotation_snap_check.setChecked(bool(self.rotation_snap_enabled))
        self.grid_snap_step_spin = self._spin(0.01, 100000, self.grid_snap_step, 1.0)
        self.smart_snap_tol_spin = self._spin(0.01, 100000, self.smart_snap_tolerance, 0.5)
        self.rotation_snap_step_spin = self._spin(1.0, 180.0, self.rotation_snap_step_deg, 5.0)
        self.rotation_snap_tol_spin = self._spin(0.1, 90.0, self.rotation_snap_tolerance_deg, 1.0)
        self.grid_snap_step_spin.setSuffix(" mm")
        self.smart_snap_tol_spin.setSuffix(" mm")
        self.rotation_snap_step_spin.setSuffix(" deg")
        self.rotation_snap_tol_spin.setSuffix(" deg")
        self.snap_status_label = QLabel(self._snap_idle_status_text())
        self.snap_status_label.setWordWrap(True)
        self.grid_snap_check.stateChanged.connect(self._on_snap_settings_changed)
        self.smart_snap_check.stateChanged.connect(self._on_snap_settings_changed)
        self.rotation_snap_check.stateChanged.connect(self._on_snap_settings_changed)
        self.grid_snap_step_spin.valueChanged.connect(self._on_snap_settings_changed)
        self.smart_snap_tol_spin.valueChanged.connect(self._on_snap_settings_changed)
        self.rotation_snap_step_spin.valueChanged.connect(self._on_snap_settings_changed)
        self.rotation_snap_tol_spin.valueChanged.connect(self._on_snap_settings_changed)
        snap_l.addWidget(self.grid_snap_check, 0, 0, 1, 2)
        snap_l.addWidget(self.smart_snap_check, 1, 0, 1, 2)
        snap_l.addWidget(QLabel("Grid step"), 2, 0)
        snap_l.addWidget(self.grid_snap_step_spin, 2, 1)
        snap_l.addWidget(QLabel("Smart tolerance"), 3, 0)
        snap_l.addWidget(self.smart_snap_tol_spin, 3, 1)
        snap_l.addWidget(self.rotation_snap_check, 4, 0, 1, 2)
        snap_l.addWidget(QLabel("Angle step"), 5, 0)
        snap_l.addWidget(self.rotation_snap_step_spin, 5, 1)
        snap_l.addWidget(QLabel("Angle tolerance"), 6, 0)
        snap_l.addWidget(self.rotation_snap_tol_spin, 6, 1)
        snap_l.addWidget(self.snap_status_label, 7, 0, 1, 2)
        g.addWidget(snap_box)

        row = QHBoxLayout()
        live_label = QLabel("Live edit: values are applied immediately.")
        live_label.setWordWrap(True)
        b_reset = QPushButton("Reload")
        b_reset.clicked.connect(self.reset_transform_fields)
        row.addWidget(live_label, 1)
        row.addWidget(b_reset, 0)
        g.addLayout(row)
        layout.addWidget(self.transform_box)

        self.tool_idle_panel = QFrame(); self.tool_idle_panel.setObjectName("ToolIdlePanel"); self.tool_idle_panel.setFrameShape(QFrame.NoFrame)
        idle_layout = QHBoxLayout(self.tool_idle_panel); idle_layout.setContentsMargins(0, 2, 0, 2); idle_layout.setSpacing(0); idle_layout.addStretch(1)
        self.btn_scene_history = QPushButton("History")
        self.btn_scene_history.setObjectName("SceneHistoryButton")
        self.btn_scene_history.setMinimumWidth(86)
        self.btn_scene_history.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_scene_history.setToolTip("Open the current scene modification history.")
        self.btn_scene_history.clicked.connect(lambda: self.scene_history_controller.open_scene_history())
        idle_layout.addWidget(self.btn_scene_history, 0, Qt.AlignRight)
        layout.addWidget(self.tool_idle_panel)

        self.tool_box = QGroupBox("Tool")
        tool_layout = QVBoxLayout(self.tool_box)
        tool_layout.setContentsMargins(4, 7, 4, 4)
        tool_layout.setSpacing(4)
        tool_header = QHBoxLayout(); tool_header.setSpacing(4)
        self.preview_label = QLabel(""); self.preview_label.setObjectName("SubTitle"); self.preview_label.setWordWrap(True)
        self.btn_tool_help = QPushButton("Help"); self.btn_tool_help.setObjectName("ToolHelpButton")
        self.btn_tool_help.setEnabled(False); self.btn_tool_help.setVisible(False); self.btn_tool_help.setMinimumWidth(58)
        self.btn_tool_help.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.btn_tool_help.setToolTip("Open documentation for the active tool.")
        self.btn_tool_help.clicked.connect(lambda: self.tool_help_controller.open_active_tool_help())
        tool_header.addWidget(self.preview_label, 1); tool_header.addWidget(self.btn_tool_help, 0)
        tool_layout.addLayout(tool_header)
        tool_actions = QHBoxLayout(); tool_actions.setSpacing(4)
        self.btn_apply_preview = QPushButton("Apply")
        self.btn_cancel_preview = QPushButton("Cancel")
        self.btn_apply_preview.clicked.connect(self.apply_preview_and_close_tool)
        self.btn_cancel_preview.clicked.connect(self.discard_preview_and_close_tool)
        for button in (self.btn_apply_preview, self.btn_cancel_preview):
            button.setEnabled(False); button.setVisible(False); button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tool_actions.addWidget(self.btn_apply_preview)
        tool_actions.addWidget(self.btn_cancel_preview)
        tool_layout.addLayout(tool_actions)
        self.tool_panel_stack = self._tool_panel_factory().build_stack()
        self.tool_panel_stack.setVisible(False)
        tool_layout.addWidget(self.tool_panel_stack, 0, Qt.AlignTop)
        self.tool_box.setVisible(False)
        layout.addWidget(self.tool_box)

        logs_box = QGroupBox("Logs")
        lo = QVBoxLayout(logs_box)
        lo.setContentsMargins(4, 7, 4, 4); lo.setSpacing(2)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(70)
        self.log_text.setLineWrapMode(QTextEdit.WidgetWidth)
        try:
            self.log_text.document().setMaximumBlockCount(int(getattr(self, "_ui_log_max_blocks", 900)))
        except Exception:
            pass
        lo.addWidget(self.log_text)
        layout.addWidget(logs_box)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer_layout.addWidget(scroll)
        return outer

    def _triple_row(self, title: str, x: QDoubleSpinBox, y: QDoubleSpinBox, z: QDoubleSpinBox, unit: str) -> QGridLayout:
        """Responsive, aligned Transform row.

        V16 made X/Y/Z fields fluid, but each row label had a different implicit width.
        Result: X for Position/Rotation/Size was not aligned.

        V18 uses a short shared label column width, and lets only numeric fields stretch.
        X/Y/Z keep the same position from one row to another, without horizontal scrolling.
        """
        row = QGridLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setHorizontalSpacing(3)
        row.setVerticalSpacing(0)

        label = QLabel(f"{title}:")
        label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label.setFixedWidth(50)
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        row.addWidget(label, 0, 0)

        widgets = [("X", x, 1, 2), ("Y", y, 3, 4), ("Z", z, 5, 6)]
        for axis, sp, axis_col, value_col in widgets:
            axis_lbl = QLabel(axis)
            axis_lbl.setAlignment(Qt.AlignCenter)
            axis_lbl.setFixedWidth(10)
            axis_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            row.addWidget(axis_lbl, 0, axis_col)

            sp.setButtonSymbols(QAbstractSpinBox.NoButtons)
            sp.setMinimumWidth(34)
            sp.setMaximumWidth(16777215)
            sp.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row.addWidget(sp, 0, value_col)

        row.setColumnMinimumWidth(0, 50)
        row.setColumnMinimumWidth(1, 10)
        row.setColumnMinimumWidth(3, 10)
        row.setColumnMinimumWidth(5, 10)
        row.setColumnStretch(0, 0)
        row.setColumnStretch(1, 0)
        row.setColumnStretch(2, 1)
        row.setColumnStretch(3, 0)
        row.setColumnStretch(4, 1)
        row.setColumnStretch(5, 0)
        row.setColumnStretch(6, 1)
        return row

    def _compact_triple_row(self, title: str, x: QDoubleSpinBox, y: QDoubleSpinBox, z: QDoubleSpinBox, unit: str = "") -> QHBoxLayout:
        return self._triple_row(title, x, y, z, unit)

    def _combo(self, values: list[str], current: str | None = None) -> QComboBox:
        cb = QComboBox()
        cb.addItems(values)
        if current and current in values:
            cb.setCurrentText(current)
        try:
            cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(8)
        except Exception:
            pass
        cb.setMinimumWidth(0)
        cb.setMaximumWidth(170)
        cb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        return cb

    def _compact_group_layout(self, box: QGroupBox) -> QVBoxLayout:
        box.setMinimumWidth(0)
        box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(4, 7, 4, 4)
        layout.setSpacing(3)
        return layout

    def _param_row(self, label_text: str, widget: QWidget, unit: str = "") -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        label = QLabel(label_text)
        label.setWordWrap(False)
        label.setMinimumWidth(0)
        label.setFixedWidth(76)
        label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        row.addWidget(label, 0)
        try:
            widget.setMinimumWidth(44)
            widget.setMaximumWidth(64)
            widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        except Exception:
            pass
        row.addWidget(widget, 0)
        if unit:
            unit_lbl = QLabel(unit)
            unit_lbl.setFixedWidth(22)
            unit_lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            row.addWidget(unit_lbl, 0)
        row.addStretch(1)
        return row

    def _tool_panel_factory(self) -> ToolPanelFactory:
        factory = getattr(self, "tool_panel_factory", None)
        if factory is None or getattr(factory, "owner", None) is not self:
            factory = ToolPanelFactory(self)
            self.tool_panel_factory = factory
        return factory

    def _panel_no_tool(self) -> QWidget:
        return self._tool_panel_factory().panel_no_tool()



    def _panel_layflat_tool(self) -> QWidget:
        return self._tool_panel_factory().panel_layflat_tool()

    def _panel_joint_tool(self) -> QWidget:
        return self._tool_panel_factory().panel_joint_tool()

    def _panel_texture_projection_tool(self) -> QWidget:
        return self._tool_panel_factory().panel_texture_projection_tool()

    def _panel_relief_modifier(self) -> QWidget:
        return self._tool_panel_factory().panel_relief_modifier()

    def _panel_extrude_down_modifier(self) -> QWidget:
        return self._tool_panel_factory().panel_extrude_down_modifier()

    def _panel_split_modifier(self) -> QWidget:
        return self._tool_panel_factory().panel_split_modifier()



    def _spin(self, mn: float, mx: float, value: float, step: float) -> QDoubleSpinBox:
        sp = QDoubleSpinBox()
        sp.setRange(mn, mx)
        sp.setValue(value)
        sp.setSingleStep(step)
        sp.setDecimals(3)
        sp.setButtonSymbols(QAbstractSpinBox.NoButtons)
        sp.setKeyboardTracking(False)
        sp.setAlignment(Qt.AlignRight)
        sp.setMinimumWidth(44)
        sp.setMaximumWidth(64)
        sp.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._install_value_field_select_all(sp)
        return sp

# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .._window_deps import *
from .tool_panel_catalog import get_tool_panel_spec, iter_tool_panel_specs
from .tool_panel_widgets import top_aligned_tool_page


class ToolPanelFactory:
    """Builds the right-inspector tool panels for a window-like owner.

    The owner still receives the Qt widget attributes used by
    existing controllers, but the panel construction order
    and builders are now centralized outside ``UIToolPanelsLayer``.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def build_stack(self) -> QStackedWidget:
        owner = self.owner
        stack = QStackedWidget()
        stack.setMinimumWidth(0)
        stack.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        widgets_by_key: dict[str, QWidget] = {}
        # Sparse-safe replacement for the old contiguous loop: for spec in iter_tool_panel_specs()
        specs = tuple(iter_tool_panel_specs())
        specs_by_index = {int(spec.panel_index): spec for spec in specs}
        max_index = max(specs_by_index.keys(), default=0)
        for index in range(max_index + 1):
            spec = specs_by_index.get(index)
            if spec is None:
                stack.addWidget(self.panel_reserved_slot(index))
                continue
            widget = self.build_panel(spec.key)
            stack.addWidget(top_aligned_tool_page(widget))
            widgets_by_key[spec.key] = widget
        owner.tool_panel_widgets_by_key = widgets_by_key
        owner.tool_panel_index_by_key = {spec.key: int(spec.panel_index) for spec in specs}
        return stack

    def panel_reserved_slot(self, index: int) -> QWidget:
        w = QWidget()
        w.setObjectName(f"ReservedToolPanel{int(index)}")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        return w

    def build_panel(self, key: str) -> QWidget:
        spec = get_tool_panel_spec(key)
        if spec is None:
            raise KeyError(f"Unknown tool panel key: {key!r}")
        builder = getattr(self, spec.builder)
        return builder()


    def panel_declarative_creator_tool(self) -> QWidget:
        from .declarative_tool_panel_host import LiveDeclarativeToolPanelWidget

        def _ctx():
            context = getattr(self.owner, "context", None)
            return getattr(context, "tool_context", None) or getattr(self.owner, "tool_context", None)

        return LiveDeclarativeToolPanelWidget(_ctx)

    def panel_no_tool(self) -> QWidget:
        # Slot 0 is intentionally empty.  When no tool is active, the whole Tool
        # group is hidden and the right inspector only exposes the standalone
        # History button.
        w = QWidget()
        w.setObjectName("NoToolReservedPanel")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        return w

    def panel_layflat_tool(self) -> QWidget:
        owner = self.owner
        w = QGroupBox("Lay flat")
        v = owner._compact_group_layout(w)
        v.addWidget(QLabel("Flatten and pack the current scene."))
        owner.lay_spacing = owner._spin(0, 1000, 5, 1)
        owner.lay_min_overlap = owner._spin(0, 10, 0.01, 0.01)
        owner.lay_touch_tol = owner._spin(0, 10, 0.05, 0.01)
        owner.lay_max_length = owner._spin(1, 10000, 300, 10)
        owner.lay_max_depth = owner._spin(1, 10000, 200, 10)
        owner.lay_fusion_combo = owner._combo(["overlap - overlap only", "none - no merge", "touch - contact/tolerance"], "overlap - overlap only")
        owner.lay_pack_combo = owner._combo(["Max length X", "Max depth Y", "Free - no constraint"], "Max length X")
        owner.lay_allow_rot = QCheckBox("Allow XY 90 deg rotation")
        owner.lay_allow_rot.setChecked(True)
        for label, sp in [("Spacing", owner.lay_spacing), ("Overlap", owner.lay_min_overlap), ("Contact tol", owner.lay_touch_tol), ("Max X", owner.lay_max_length), ("Max Y", owner.lay_max_depth)]:
            v.addLayout(owner._param_row(label, sp, "mm"))
        v.addWidget(QLabel("Merging")); v.addWidget(owner.lay_fusion_combo)
        v.addWidget(QLabel("Packing constraint")); v.addWidget(owner.lay_pack_combo)
        v.addWidget(owner.lay_allow_rot)
        b_prev = QPushButton("Preview lay flat")
        b_prev.clicked.connect(owner.generate_layflat_preview)
        v.addWidget(b_prev)
        owner.lay_report = QLabel("No computation started.")
        owner.lay_report.setWordWrap(True)
        v.addWidget(owner.lay_report)
        return w

    def panel_joint_tool(self) -> QWidget:
        owner = self.owner
        w = QGroupBox("Joint builder")
        v = owner._compact_group_layout(w)
        info = QLabel("Pick two parts: A then B.")
        info.setWordWrap(True)
        info.setMaximumHeight(20)
        v.addWidget(info)
        owner.joint_info = QLabel("A/B: — · Preview: no")
        owner.joint_info.setObjectName("SubTitle")
        owner.joint_info.setWordWrap(False)
        owner.joint_info.setMaximumHeight(22)
        v.addWidget(owner.joint_info)
        owner.joint_touch_tol = owner._spin(0.001, 100, 0.20, 0.05)
        owner.joint_clearance = owner._spin(-100, 100, 0.15, 0.05)
        owner.joint_clearance.setToolTip("Positive = loose slot. Negative = tighter slot / interference fit.")
        owner.joint_size = owner._spin(0.1, 1000, 10.0, 1.0)
        owner.joint_count = owner._spin(1, 100, 1, 1)
        owner.joint_edge_margin = owner._spin(0, 1000, 2.0, 0.5)
        owner.joint_count.setDecimals(0)
        owner.joint_single_probe = QCheckBox("Fast depth")
        owner.joint_single_probe.setChecked(True)
        owner.joint_debug = QCheckBox("Debug log")
        for label, sp, unit in [("Contact tol", owner.joint_touch_tol, "mm"), ("Clearance", owner.joint_clearance, "mm"), ("Size", owner.joint_size, "mm"), ("Count", owner.joint_count, ""), ("Edge margin", owner.joint_edge_margin, "mm")]:
            v.addLayout(owner._param_row(label, sp, unit))
        v.addWidget(owner.joint_single_probe)
        v.addWidget(owner.joint_debug)
        b_prev = QPushButton("Add joint to preview")
        b_prev.clicked.connect(owner.generate_joint_preview)
        v.addWidget(b_prev)
        return w

    def panel_texture_projection_tool(self) -> QWidget:
        owner = self.owner
        w = QGroupBox("Texture projection")
        v = owner._compact_group_layout(w)
        info = QLabel("Project an image onto selected parts or a clicked face.")
        info.setWordWrap(True)
        v.addWidget(info)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        owner.texture_projection_path = QLineEdit("")
        owner.texture_projection_path.setPlaceholderText("PNG/JPG texture…")
        browse = QPushButton("...")
        browse.setMaximumWidth(30)
        browse.clicked.connect(owner._choose_texture_projection_file)
        row.addWidget(owner.texture_projection_path, 1)
        row.addWidget(browse, 0)
        v.addWidget(QLabel("Image"))
        v.addLayout(row)

        owner.texture_projection_mode = QComboBox()
        for label, data in [("Planar XY", "planar"), ("Box", "box"), ("Cylindrical", "cylindrical"), ("Spherical", "spherical")]:
            owner.texture_projection_mode.addItem(label, data)
        v.addWidget(QLabel("Projection"))
        v.addWidget(owner.texture_projection_mode)

        owner.texture_projection_usage = QComboBox()
        for label, data in [("Engrave", "engrave"), ("Visual only", "visual"), ("Cut outline", "cut")]:
            owner.texture_projection_usage.addItem(label, data)
        v.addWidget(QLabel("Usage"))
        v.addWidget(owner.texture_projection_usage)

        owner.texture_projection_scale = owner._spin(0.001, 100000, 1.0, 0.1)
        owner.texture_projection_rotation = owner._spin(-360, 360, 0.0, 5.0)
        owner.texture_projection_offset_u = owner._spin(-1000, 1000, 0.0, 0.05)
        owner.texture_projection_offset_v = owner._spin(-1000, 1000, 0.0, 0.05)
        owner.texture_projection_coverage = owner._spin(0, 180, 20.0, 5.0)
        v.addLayout(owner._param_row("Scale", owner.texture_projection_scale, ""))
        v.addLayout(owner._param_row("Rotation", owner.texture_projection_rotation, "°"))
        v.addLayout(owner._param_row("Offset U", owner.texture_projection_offset_u, ""))
        v.addLayout(owner._param_row("Offset V", owner.texture_projection_offset_v, ""))
        v.addLayout(owner._param_row("Coverage", owner.texture_projection_coverage, "°"))

        owner.texture_projection_repeat = QCheckBox("Repeat texture")
        owner.texture_projection_repeat.setToolTip("Allow UV coordinates outside 0..1 for repeated texture patterns.")
        v.addWidget(owner.texture_projection_repeat)
        owner.texture_projection_attach_to_mesh = QCheckBox("Attach to mesh")
        owner.texture_projection_attach_to_mesh.setToolTip("Attach the texture to the selected mesh instead of creating a decal.")
        v.addWidget(owner.texture_projection_attach_to_mesh)
        owner.texture_projection_preserve_aspect = QCheckBox("Keep image ratio")
        owner.texture_projection_preserve_aspect.setChecked(True)
        owner.texture_projection_preserve_aspect.setToolTip("Keep the original image ratio.")
        v.addWidget(owner.texture_projection_preserve_aspect)

        b_preview = QPushButton("Preview selected")
        b_preview.clicked.connect(owner.generate_texture_projection_preview)
        v.addWidget(b_preview)
        b_clear = QPushButton("Clear selected texture")
        b_clear.clicked.connect(owner.clear_texture_projection_selected)
        v.addWidget(b_clear)

        owner.texture_projection_report = QLabel("Select parts, choose an image, then preview.")
        owner.texture_projection_report.setWordWrap(True)
        v.addWidget(owner.texture_projection_report)

        for widget in (
            owner.texture_projection_path,
            owner.texture_projection_mode,
            owner.texture_projection_usage,
            owner.texture_projection_scale,
            owner.texture_projection_rotation,
            owner.texture_projection_offset_u,
            owner.texture_projection_offset_v,
            owner.texture_projection_coverage,
            owner.texture_projection_repeat,
            owner.texture_projection_attach_to_mesh,
            owner.texture_projection_preserve_aspect,
        ):
            try:
                signal = widget.textChanged if hasattr(widget, "textChanged") else (widget.currentIndexChanged if hasattr(widget, "currentIndexChanged") else (widget.toggled if hasattr(widget, "toggled") else widget.valueChanged))
                signal.connect(lambda *_args: owner._update_texture_projection_report())
            except Exception:
                pass
        return w

    def _planar_mode_buttons(self, owner: Any, *, prefix: str) -> QButtonGroup:
        group = QButtonGroup(owner)
        group.setExclusive(True)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(3)
        for label in ("ADD", "MOD", "SUPP", "RST"):
            btn = QPushButton(label)
            btn.setCheckable(True)
            if label == "ADD":
                btn.setChecked(True)
            row.addWidget(btn)
            group.addButton(btn)
            setattr(owner, f"{prefix}_mode_{label.lower()}", btn)
            btn.clicked.connect(lambda _checked=False, value=label: owner.planar_tool_controller.set_payload_mode(value))
        setattr(owner, f"{prefix}_mode_group", group)
        setattr(owner, f"{prefix}_mode_row", row)
        return group



    def panel_relief_modifier(self) -> QWidget:
        owner = self.owner
        w = QGroupBox("Modifier - Relief")
        v = owner._compact_group_layout(w)
        info = QLabel("Click a face to place text relief.")
        info.setWordWrap(True)
        v.addWidget(info)

        v.addWidget(QLabel("Text"))
        owner.relief_text = QLineEdit("Text")
        owner.relief_text.setPlaceholderText("Text to place")
        v.addWidget(owner.relief_text)

        v.addWidget(QLabel("Font"))
        owner.relief_font_combo = QFontComboBox()
        owner.relief_font_combo.setMaximumWidth(170)
        owner.relief_font_combo.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        v.addWidget(owner.relief_font_combo)

        owner.relief_size = owner._spin(0.1, 10000, 12, 1)
        owner.relief_depth = owner._spin(0.01, 10000, 1.5, 0.25)
        owner.relief_rotation = owner._spin(-360, 360, 0, 5)
        v.addLayout(owner._param_row("Size", owner.relief_size, "mm"))
        v.addLayout(owner._param_row("Depth", owner.relief_depth, "mm"))
        v.addLayout(owner._param_row("Rotation", owner.relief_rotation, "deg"))

        v.addWidget(QLabel("Mode"))
        owner.relief_mode_combo = owner._combo(["Raised", "Subtract"], "Raised")
        v.addWidget(owner.relief_mode_combo)

        v.addWidget(QLabel("Alignment"))
        owner.relief_align_combo = owner._combo(["Center", "Left", "Right"], "Center")
        v.addWidget(owner.relief_align_combo)

        owner.relief_report = QLabel("Select a target, then click a face.")
        owner.relief_report.setWordWrap(True)
        v.addWidget(owner.relief_report)

        for widget in (owner.relief_text, owner.relief_font_combo, owner.relief_size, owner.relief_depth, owner.relief_rotation, owner.relief_mode_combo, owner.relief_align_combo):
            try:
                if hasattr(widget, "textChanged"):
                    widget.textChanged.connect(owner._on_relief_params_changed)
                elif hasattr(widget, "currentIndexChanged"):
                    widget.currentIndexChanged.connect(owner._on_relief_params_changed)
                elif hasattr(widget, "valueChanged"):
                    widget.valueChanged.connect(owner._on_relief_params_changed)
            except Exception:
                pass
        return w

    def panel_extrude_down_modifier(self) -> QWidget:
        owner = self.owner
        w = QGroupBox("Modifier - Extrude down")
        v = owner._compact_group_layout(w)
        info = QLabel("Extend selected meshes down to Z=0.")
        info.setWordWrap(True)
        v.addWidget(info)

        owner.extrude_down_z = owner._spin(-100000, 100000, 0, 1)
        owner.extrude_down_size = owner._spin(1, 100000, 120, 10)
        owner.extrude_down_tol = owner._spin(0.0001, 10, 0.001, 0.001)
        v.addLayout(owner._param_row("Plane Z", owner.extrude_down_z, "mm"))
        v.addLayout(owner._param_row("Plane size", owner.extrude_down_size, "mm"))
        v.addLayout(owner._param_row("Tolerance", owner.extrude_down_tol, "mm"))

        b_preview = QPushButton("Preview now")
        b_preview.clicked.connect(owner.generate_extrude_down_modifier_preview)
        v.addWidget(b_preview)

        owner.extrude_down_report = QLabel("Select parts, then move the yellow plane.")
        owner.extrude_down_report.setWordWrap(True)
        v.addWidget(owner.extrude_down_report)

        for sp in (owner.extrude_down_z, owner.extrude_down_size, owner.extrude_down_tol):
            sp.valueChanged.connect(owner._on_extrude_down_params_changed)
        return w

    def panel_split_modifier(self) -> QWidget:
        owner = self.owner
        w = QGroupBox("Modifier - Split plane")
        v = owner._compact_group_layout(w)
        info = QLabel("Cut selected parts with an editable plane.")
        info.setWordWrap(True)
        v.addWidget(info)

        owner.split_offset = owner._spin(-100000, 100000, 0, 1)
        owner.split_rx = owner._spin(-360, 360, 0, 5)
        owner.split_ry = owner._spin(-360, 360, 0, 5)
        owner.split_rz = owner._spin(-360, 360, 0, 5)
        owner.split_size = owner._spin(1, 100000, 120, 10)
        owner.split_tol = owner._spin(0.0001, 10, 0.001, 0.001)
        v.addLayout(owner._param_row("Forward offset", owner.split_offset, "mm"))
        v.addLayout(owner._compact_triple_row("Rotation", owner.split_rx, owner.split_ry, owner.split_rz, "deg"))
        v.addLayout(owner._param_row("Plane size", owner.split_size, "mm"))
        v.addLayout(owner._param_row("Tolerance", owner.split_tol, "mm"))

        for sp in (owner.split_offset, owner.split_rx, owner.split_ry, owner.split_rz, owner.split_size):
            sp.valueChanged.connect(owner._on_split_plane_params_changed)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        b_center = QPushButton("Reset offset")
        b_center.clicked.connect(owner._set_split_plane_to_selection_center)
        b_camera = QPushButton("Face camera")
        b_camera.clicked.connect(owner._orient_split_plane_to_camera)
        row.addWidget(b_center)
        row.addWidget(b_camera)
        v.addLayout(row)

        b_preview = QPushButton("Preview split")
        b_preview.clicked.connect(owner.generate_split_modifier_preview)
        v.addWidget(b_preview)

        owner.split_report = QLabel("Move the plane, then preview.")
        owner.split_report.setWordWrap(True)
        v.addWidget(owner.split_report)
        return w

# -*- coding: utf-8 -*-
from __future__ import annotations

from .laser_3mf_core import *  # type: ignore  # noqa: F401,F403
from .image_panel import ImagePanel  # type: ignore  # noqa: F401

class Laser3MFAppUILayer:
    def _build_ui(self):
        # Main layout: controls on the left, renders on the right.
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)

        left = ttk.Frame(self.root)
        left.grid(row=0, column=0, sticky="ns", padx=10, pady=10)
        left.columnconfigure(0, weight=1)

        right = ttk.Frame(self.root)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=10)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(0, weight=3)
        right.rowconfigure(1, weight=1)

        # ---- File ----
        file_frame = ttk.LabelFrame(left, text="File")
        file_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        file_frame.columnconfigure(0, weight=1)

        ttk.Button(file_frame, text="Select a 3MF file", command=self.choose_3mf).grid(
            row=0, column=0, sticky="ew", padx=8, pady=6
        )
        ttk.Entry(file_frame, textvariable=self.input_var, width=42).grid(row=1, column=0, sticky="ew", padx=8, pady=4)

        ttk.Label(file_frame, text="Output root folder:").grid(row=2, column=0, sticky="w", padx=8, pady=(8, 2))
        ttk.Entry(file_frame, textvariable=self.output_root_var, width=42).grid(row=3, column=0, sticky="ew", padx=8, pady=4)
        ttk.Button(file_frame, text="Choose folder", command=self.choose_output_root).grid(
            row=4, column=0, sticky="ew", padx=8, pady=(4, 8)
        )

        # ---- JSON presets ----
        presets = ttk.LabelFrame(left, text="JSON presets")
        presets.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        presets.columnconfigure(0, weight=1)
        presets.columnconfigure(1, weight=0)
        presets.columnconfigure(2, weight=0)
        presets.columnconfigure(3, weight=0)

        ttk.Label(presets, text=f"Folder: ./{PRESET_DIR_NAME}").grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=(6, 2)
        )
        self.preset_combo = ttk.Combobox(presets, textvariable=self.preset_var, values=[], state="readonly")
        self.preset_combo.grid(row=1, column=0, columnspan=4, sticky="ew", padx=8, pady=4)
        self.preset_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_selected_preset())

        ttk.Button(presets, text="Load", command=self.load_selected_preset).grid(
            row=2, column=0, sticky="ew", padx=(8, 3), pady=(4, 8)
        )
        ttk.Button(presets, text="Save", command=self.save_selected_preset).grid(
            row=2, column=1, sticky="ew", padx=3, pady=(4, 8)
        )
        ttk.Button(presets, text="+", width=4, command=self.create_new_preset).grid(
            row=2, column=2, sticky="ew", padx=3, pady=(4, 8)
        )
        ttk.Button(presets, text="-", width=4, command=self.delete_selected_preset).grid(
            row=2, column=3, sticky="ew", padx=(3, 8), pady=(4, 8)
        )

        # ---- Parameters ----
        params = ttk.LabelFrame(left, text="Live parameters")
        params.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        params.columnconfigure(1, weight=1)

        self._add_param(params, 0, "DPI", self.dpi_var, "PNG resolution", 50, 600, 1, "int")
        self._add_param(params, 1, "Outline stroke (mm)", self.contour_width_var, "Black laser stroke", 0.01, 2.0, 0.01, "float")
        self._add_param(params, 2, "Outline offset (mm)", self.contour_margin_var, "+ expands / - shrinks", -2.0, 2.0, 0.01, "float")
        self._add_param(params, 3, "Fill offset (mm)", self.fill_margin_var, "+ expands / - shrinks", -2.0, 2.0, 0.01, "float")
        self._add_param(params, 4, "Fill edge (mm)", self.fill_edge_width_var, "Black fill edge", 0.0, 1.0, 0.01, "float")
        self._add_param(params, 5, "Z normal threshold", self.normal_threshold_var, "Top faces", 0.0, 1.0, 0.01, "float")
        self._add_param(params, 6, "Page margin", self.page_margin_var, "Model border ratio", 0.0, 0.30, 0.005, "float")
        self._add_param(params, 7, "Thickness text (px)", self.label_size_var, "Label size", 8, 80, 1, "int")
        self._add_param(params, 8, "Min image size (px)", self.min_px_var, "Avoid tiny previews", 300, 2000, 10, "int")

        grid_frame = ttk.Frame(params)
        grid_frame.grid(row=9, column=0, columnspan=4, sticky="ew", padx=8, pady=(8, 6))
        ttk.Checkbutton(
            grid_frame,
            text="Show 10 mm grid",
            variable=self.grid_var,
            command=self.on_grid_toggle,
        ).pack(anchor="w")

        # ---- Actions ----
        actions = ttk.LabelFrame(left, text="Actions")
        actions.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        actions.columnconfigure(0, weight=1)
        ttk.Button(actions, text="Recompute now", command=self.render_current).grid(row=0, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(actions, text="Save images + Falcon SVG", command=self.save_all).grid(row=1, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(actions, text="Export Falcon SVG", command=self.export_falcon_svg_file).grid(row=2, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(actions, text="Export dimensions JSON", command=self.export_dimensions_json).grid(row=3, column=0, sticky="ew", padx=8, pady=6)
        ttk.Button(actions, text="Open export folder", command=self.open_export_folder).grid(row=4, column=0, sticky="ew", padx=8, pady=6)

        # ---- Legend ----
        legend = ttk.LabelFrame(left, text="Current convention")
        legend.grid(row=4, column=0, sticky="ew")
        legend_text = (
            "Dominant green -> outline/cut vector\n"
            "Dominant red -> filled engraving vector\n"
            "Top-down preview -> union by color\n"
            "Laser PNG -> union of outlines + union of fills\n"
            "Falcon SVG -> real-size editable vector paths\n"
            "10 mm grid -> display-only overlay (not exported)\n"
            "Settings update as soon as you change an entry or a slider."
        )
        ttk.Label(legend, text=legend_text, justify="left", wraplength=330).grid(row=0, column=0, sticky="w", padx=8, pady=8)

        # ---- Integrated renders ----
        # The laser B/W view is the primary render: large and alone on top.
        # The other two views are control helpers, so smaller at the bottom.
        self.panels: Dict[str, ImagePanel] = {}

        self.panels["laser"] = ImagePanel(right, self, "01 - Laser cut B/W", "laser", "01_laser_black_white.png")
        self.panels["laser"].grid(row=0, column=0, sticky="nsew")

        bottom_row = ttk.Frame(right)
        bottom_row.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        bottom_row.columnconfigure(0, weight=1)
        bottom_row.columnconfigure(1, weight=1)
        bottom_row.rowconfigure(0, weight=1)

        self.panels["top"] = ImagePanel(bottom_row, self, "02 - Top-down preview", "top", "02_top_down_union.png")
        self.panels["top"].grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        self.panels["thickness"] = ImagePanel(bottom_row, self, "03 - Thickness labels", "thickness", "03_thickness_labels_bw.png")
        self.panels["thickness"].grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # Status bar at the bottom of the single window.
        status_bar = ttk.Frame(self.root)
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 8))
        status_bar.columnconfigure(0, weight=1)
        ttk.Label(status_bar, textvariable=self.status_var, anchor="w").grid(row=0, column=0, sticky="ew")

        # Refresh thumbnails when the window is resized.
        self.root.bind("<Configure>", self._on_resize)

    def _format_param_value(self, value: float, kind: str, step: float) -> str:
        """Format a value coming from a slider."""
        if kind == "int":
            return str(int(round(value)))
        # Number of decimals based on the slider step.
        if step >= 0.1:
            decimals = 1
        elif step >= 0.01:
            decimals = 2
        else:
            decimals = 3
        text = f"{value:.{decimals}f}"
        # Keep at least one decimal when needed, but avoid trailing zeros.
        return text.rstrip("0").rstrip(".") if "." in text else text

    def _add_param(
        self,
        parent,
        row: int,
        label: str,
        var: tk.StringVar,
        hint: str,
        minimum: float,
        maximum: float,
        step: float,
        kind: str,
    ):
        """Add one parameter row: label, numeric entry, slider, and help text."""
        ttk.Label(parent, text=label + " :").grid(row=row, column=0, sticky="w", padx=8, pady=5)

        entry = ttk.Entry(parent, textvariable=var, width=9)
        entry.grid(row=row, column=1, sticky="ew", padx=(4, 6), pady=5)

        scale_var = tk.DoubleVar(value=float(var.get()))
        slider = ttk.Scale(parent, from_=minimum, to=maximum, orient="horizontal", variable=scale_var)
        slider.grid(row=row, column=2, sticky="ew", padx=(0, 6), pady=5)

        ttk.Label(parent, text=hint, foreground="#555", wraplength=110).grid(row=row, column=3, sticky="w", padx=4, pady=5)

        parent.columnconfigure(2, weight=1)

        def slider_changed(_value=None, *, v=var, sv=scale_var, k=kind, st=step):
            if self._updating_from_entry:
                return
            self._updating_from_slider = True
            try:
                raw = sv.get()
                if st > 0:
                    raw = round(raw / st) * st
                v.set(self._format_param_value(raw, k, st))
            finally:
                self._updating_from_slider = False
            self.schedule_render(immediate=True)

        def entry_changed(*_, v=var, sv=scale_var, mn=minimum, mx=maximum):
            if self._loading_preset:
                return
            # The numeric entry remains the priority. If it is temporarily invalid
            # while typing, simply wait for the next valid value.
            if self._updating_from_slider:
                return
            try:
                value = float(v.get().strip().replace(",", "."))
            except ValueError:
                self.schedule_render(immediate=True)
                return
            clamped = max(mn, min(mx, value))
            self._updating_from_entry = True
            try:
                sv.set(clamped)
            finally:
                self._updating_from_entry = False
            self.schedule_render(immediate=True)

        slider.configure(command=slider_changed)
        var.trace_add("write", entry_changed)
        self.param_widgets[str(var)] = {
            "entry": entry,
            "slider": slider,
            "scale_var": scale_var,
            "min": minimum,
            "max": maximum,
            "step": step,
            "kind": kind,
        }

    def _bind_live_updates(self):
        # Traces are installed directly by _add_param to synchronize
        # each entry cleanly with its slider.
        pass

    def _on_resize(self, event=None):
        # No geometry recompute: only refresh thumbnails.
        if event is not None and event.widget is not self.root:
            return
        if not self.images:
            return
        if getattr(self, "resize_after_id", None):
            self.root.after_cancel(self.resize_after_id)
        self.resize_after_id = self.root.after(250, self.refresh_panels)

    def refresh_panels(self):
        for key, img in self.images.items():
            self.panels[key].set_image(img)

    def on_grid_toggle(self):
        # The grid is a display overlay: no need to recompute geometries.
        for panel in getattr(self, "panels", {}).values():
            panel.redraw()
        self.status_var.set("Grille affichee." if self.grid_var.get() else "Grille masquee.")

# -*- coding: utf-8 -*-
"""Stable wrapper for the layflat_arranger tool UI.

The computational core lives in `layflat_core.py`; this module keeps the
public imports used by LaserProg Studio and the toolbox.
"""
from __future__ import annotations

from .layflat_core import *  # type: ignore  # noqa: F401,F403


class ToolFrame(ttk.Frame):
    def __init__(self, parent: tk.Widget, app_context) -> None:
        super().__init__(parent)
        self.context = app_context
        self.settings = AutoSaveSettings(self.context.settings_dir / f"{TOOL_ID}.json", DEFAULT_SETTINGS)
        if not self.settings.data.get("output_dir"):
            self.settings.data["output_dir"] = str(self.context.exports_dir)
            self.settings.save()
        self._save_after_id: str | None = None
        self.vars: dict[str, tk.Variable] = {}
        self._last_pieces: list[PieceGroup] | None = None
        self._build_ui()
        self._load_vars_from_settings()
        self._update_input_mode()
        self._connect_autosave()
        self._update_preview()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        left = ttk.Frame(self, padding=(0, 0, 12, 0))
        left.grid(row=0, column=0, sticky="nsw")
        right = ttk.Frame(self, padding=(12, 0, 0, 0))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(left, text="Lay flat / packing", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 12))
        self.vars = {
            "input_path": tk.StringVar(),
            "use_loaded_model": tk.BooleanVar(),
            "output_name": tk.StringVar(),
            "output_dir": tk.StringVar(),
            "spacing_mm": tk.StringVar(),
            "fusion_mode": tk.StringVar(),
            "minimum_overlap_mm": tk.StringVar(),
            "touch_tolerance_mm": tk.StringVar(),
            "packing_constraint": tk.StringVar(),
            "max_length_mm": tk.StringVar(),
            "max_depth_mm": tk.StringVar(),
            "allow_xy_rotation": tk.BooleanVar(),
        }
        row = 1
        ttk.Label(left, text="Source 3MF").grid(row=row, column=0, sticky="w", pady=4)
        self.input_entry = ttk.Entry(left, textvariable=self.vars["input_path"], width=30)
        self.input_entry.grid(row=row, column=1, sticky="ew", pady=4)
        self.input_button = ttk.Button(left, text="...", width=4, command=self._choose_input)
        self.input_button.grid(row=row, column=2, sticky="e", padx=(4, 0), pady=4)
        row += 1
        ttk.Checkbutton(
            left,
            text="Use loaded model ('Load 3MF' button)",
            variable=self.vars["use_loaded_model"],
            command=self._update_input_mode,
        ).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 8))
        row += 1
        row = self._add_float_field(left, row, "Spacing", "spacing_mm", "mm")
        ttk.Label(left, text="Merging").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(left, textvariable=self.vars["fusion_mode"], state="readonly", width=26, values=list(FUSION_LABELS.values())).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        row += 1
        row = self._add_float_field(left, row, "Min overlap", "minimum_overlap_mm", "mm")
        row = self._add_float_field(left, row, "Touch tolerance", "touch_tolerance_mm", "mm")

        ttk.Separator(left).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        ttk.Label(left, text="Packing", font=("Segoe UI", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 4))
        row += 1
        ttk.Label(left, text="Constraint").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Combobox(left, textvariable=self.vars["packing_constraint"], state="readonly", width=26, values=list(PACKING_LABELS.values())).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        row += 1
        row = self._add_float_field(left, row, "Max length X", "max_length_mm", "mm")
        row = self._add_float_field(left, row, "Max depth Y", "max_depth_mm", "mm")
        ttk.Checkbutton(left, text="Allow 90deg XY rotation", variable=self.vars["allow_xy_rotation"]).grid(row=row, column=0, columnspan=3, sticky="w", pady=4)
        row += 1

        ttk.Separator(left).grid(row=row, column=0, columnspan=3, sticky="ew", pady=12)
        row += 1
        ttk.Label(left, text="File name").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(left, textvariable=self.vars["output_name"], width=28).grid(row=row, column=1, columnspan=2, sticky="ew", pady=4)
        row += 1
        ttk.Label(left, text="Output folder").grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(left, textvariable=self.vars["output_dir"], width=28).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(left, text="...", width=4, command=self._choose_output_dir).grid(row=row, column=2, sticky="e", padx=(4, 0), pady=4)
        row += 1
        self.generate_button = ttk.Button(left, text="Generate lay-flat 3MF", command=self._generate_3mf)
        self.generate_button.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(16, 6))
        row += 1
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(left, textvariable=self.status_var, wraplength=330, foreground="#444").grid(row=row, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        row += 1
        ttk.Label(
            left,
            text="Default: touch-only does NOT merge. Choose 'touch' only if you want to merge touching parts.",
            wraplength=330,
            foreground="#555",
        ).grid(row=row, column=0, columnspan=3, sticky="ew", pady=(14, 0))

        ttk.Label(right, text="Analysis / text preview", font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        self.info_text = tk.Text(right, height=18, wrap="word", state="disabled")
        self.info_text.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(right, orient="vertical", command=self.info_text.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.info_text.configure(yscrollcommand=scrollbar.set)

    def _add_float_field(self, parent: tk.Widget, row: int, label: str, key: str, unit: str) -> int:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.vars[key], width=12).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(parent, text=unit).grid(row=row, column=2, sticky="w", padx=(4, 0), pady=4)
        return row + 1

    def _load_vars_from_settings(self) -> None:
        for key, var in self.vars.items():
            value = self.settings.data.get(key, DEFAULT_SETTINGS.get(key, ""))
            if key == "fusion_mode":
                value = FUSION_LABELS.get(str(value), FUSION_LABELS["overlap"])
            elif key == "packing_constraint":
                value = PACKING_LABELS.get(str(value), PACKING_LABELS["max_length"])
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                var.set(str(value))

    def _connect_autosave(self) -> None:
        for var in self.vars.values():
            var.trace_add("write", self._on_any_change)

    def _on_any_change(self, *_args) -> None:
        self._schedule_autosave()
        self._update_preview()

    def _schedule_autosave(self) -> None:
        if self._save_after_id is not None:
            self.after_cancel(self._save_after_id)
        self._save_after_id = self.after(180, self._save_settings_now)

    def _fusion_mode_code(self) -> str:
        raw = self.vars["fusion_mode"].get().strip()
        if raw.startswith("none"):
            return "none"
        if raw.startswith("touch"):
            return "touch"
        return "overlap"

    def _packing_constraint_code(self) -> str:
        raw = self.vars["packing_constraint"].get().strip()
        for code, label in PACKING_LABELS.items():
            if raw == label:
                return code
        if raw.startswith("Max depth"):
            return "max_depth"
        if raw.startswith("Free"):
            return "none"
        return "max_length"

    def _save_settings_now(self) -> None:
        self._save_after_id = None
        for key, var in self.vars.items():
            raw = var.get()
            if key == "fusion_mode":
                self.settings.data[key] = self._fusion_mode_code()
            elif key == "packing_constraint":
                self.settings.data[key] = self._packing_constraint_code()
            elif isinstance(var, tk.BooleanVar):
                self.settings.data[key] = bool(var.get())
            elif key.endswith("_mm"):
                try:
                    self.settings.data[key] = float(raw.replace(",", "."))
                except ValueError:
                    continue
            else:
                self.settings.data[key] = raw
        self.settings.save()

    def _read_float(self, key: str) -> float:
        return float(self.vars[key].get().strip().replace(",", "."))

    def _choose_input(self) -> None:
        if bool(self.vars.get("use_loaded_model", tk.BooleanVar()).get()):
            return
        initial = str(Path(self.vars["input_path"].get()).parent) if self.vars["input_path"].get() else str(self.context.exports_dir)
        selected = filedialog.askopenfilename(initialdir=initial, title="Choose a 3MF file", filetypes=[("3MF", "*.3mf"), ("All files", "*.*")])
        if selected:
            self.vars["input_path"].set(selected)
            if not self.vars["output_name"].get().strip():
                self.vars["output_name"].set(Path(selected).stem + "_layflat")

    def _update_input_mode(self) -> None:
        use_loaded = bool(self.vars.get("use_loaded_model", tk.BooleanVar()).get())
        if use_loaded:
            src = getattr(self.context, "model_store", None).source_path if getattr(self.context, "model_store", None) else None
            self.vars["input_path"].set(str(src) if src is not None else "")
            self.input_entry.configure(state="disabled")
            self.input_button.configure(state="disabled")
        else:
            self.input_entry.configure(state="normal")
            self.input_button.configure(state="normal")

    def _choose_output_dir(self) -> None:
        initial = self.vars["output_dir"].get() or str(self.context.exports_dir)
        selected = filedialog.askdirectory(initialdir=initial, title="Choose output folder")
        if selected:
            self.vars["output_dir"].set(selected)

    def _set_text(self, content: str) -> None:
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", content)
        self.info_text.configure(state="disabled")

    def _update_preview(self) -> None:
        use_loaded = bool(self.vars.get("use_loaded_model", tk.BooleanVar()).get())
        if use_loaded:
            src = self.context.model_store.source_path
            if src is None:
                self._last_pieces = None
                self._set_text(
                    "Enabled: Use loaded model.\n\n"
                    "First load a file using the 'Load 3MF' button (top bar)."
                )
                self.status_var.set("No model loaded.")
                self.generate_button.configure(state="disabled")
                return
            input_path = src
        else:
            input_raw = self.vars.get("input_path", tk.StringVar()).get().strip()
            if not input_raw:
                self._last_pieces = None
                self._set_text(
                    "Choose a source 3MF file.\n\n"
                    "The tool will orient parts flat, then place them on the ground using the requested spacing and packing constraint."
                )
                self.status_var.set("No source 3MF selected.")
                self.generate_button.configure(state="disabled")
                return
            input_path = Path(input_raw)
        try:
            if not input_path.exists():
                raise ValueError("Source file does not exist.")
            pieces, info = process_3mf(
                input_path,
                self._read_float("spacing_mm"),
                self._read_float("touch_tolerance_mm"),
                self._fusion_mode_code(),
                self._read_float("minimum_overlap_mm"),
                self._packing_constraint_code(),
                self._read_float("max_length_mm"),
                self._read_float("max_depth_mm"),
                bool(self.vars["allow_xy_rotation"].get()),
            )
            self._last_pieces = pieces
            self._set_text(info)
            self.status_var.set("Valid parameters. Ready to generate.")
            self.generate_button.configure(state="normal")

            # Auto-apply: update the work model.
            meshes: list[WorkMesh] = []
            for p in pieces:
                meshes.append(WorkMesh(name=p.name, vertices=p.vertices, triangles=p.triangles, color=p.color))
            # Keep the original path so we can re-run the process and derive export naming.
            self.context.model_store.set_preview_meshes(meshes, source_path=input_path)
        except Exception as exc:
            self._last_pieces = None
            self._set_text(f"Invalid parameters or incompatible file:\n\n{exc}")
            self.status_var.set("Fix parameters before generating.")
            self.generate_button.configure(state="disabled")

    def _generate_3mf(self) -> None:
        try:
            self._save_settings_now()
            input_path = Path(self.vars["input_path"].get().strip())
            pieces, _info = process_3mf(
                input_path,
                self._read_float("spacing_mm"),
                self._read_float("touch_tolerance_mm"),
                self._fusion_mode_code(),
                self._read_float("minimum_overlap_mm"),
                self._packing_constraint_code(),
                self._read_float("max_length_mm"),
                self._read_float("max_depth_mm"),
                bool(self.vars["allow_xy_rotation"].get()),
            )
            output_dir = Path(self.vars["output_dir"].get() or self.context.exports_dir)
            name = safe_filename(self.vars["output_name"].get())
            path = output_dir / f"{name}.3mf"
            write_3mf(path, pieces)
            self.status_var.set(f"Lay-flat 3MF generated: {path}")
            messagebox.showinfo("3MF generated", f"File created:\n{path}")
        except Exception as exc:
            messagebox.showerror("Generation error", str(exc))
            self.status_var.set("Error during generation.")


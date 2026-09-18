# -*- coding: utf-8 -*-
from __future__ import annotations

from .laser_3mf_core import *  # type: ignore  # noqa: F401,F403
from .image_panel import ImagePanel  # type: ignore  # noqa: F401

class Laser3MFAppPresetsLayer:
    def choose_3mf(self):
        path = filedialog.askopenfilename(
            title="Select a 3MF file",
            filetypes=[("3MF files", "*.3mf"), ("All files", "*.*")],
        )
        if not path:
            return
        self.input_path = Path(path)
        self.input_var.set(str(self.input_path))
        self.output_root_var.set(str(self.input_path.parent))
        self.render_current()

    def choose_output_root(self):
        path = filedialog.askdirectory(title="Choose the export root folder")
        if path:
            self.output_root_var.set(path)

    def read_config_from_ui(self) -> RenderConfig:
        def f(var: tk.StringVar) -> float:
            return float(var.get().strip().replace(",", "."))

        cfg = RenderConfig(
            dpi=int(f(self.dpi_var)),
            contour_width_mm=f(self.contour_width_var),
            contour_margin_mm=f(self.contour_margin_var),
            fill_margin_mm=f(self.fill_margin_var),
            fill_edge_width_mm=f(self.fill_edge_width_var),
            normal_z_threshold=f(self.normal_threshold_var),
            page_margin_ratio=f(self.page_margin_var),
            label_font_size_px=int(f(self.label_size_var)),
            min_output_px=int(f(self.min_px_var)),
        )
        if cfg.dpi <= 0:
            raise ValueError("DPI must be positive.")
        if cfg.min_output_px < 100:
            raise ValueError("The minimum size must be at least 100 px.")
        if not 0 <= cfg.normal_z_threshold <= 1:
            raise ValueError("The normal Z threshold must be between 0 and 1.")
        return cfg

    def app_root(self) -> Path:
        """Application root folder: the folder containing this script."""
        try:
            return Path(__file__).resolve().parent
        except NameError:
            return Path.cwd()

    def presets_dir(self) -> Path:
        """All presets are loaded from ./presets next to the script."""
        folder = self.app_root() / PRESET_DIR_NAME
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def sanitize_preset_name(self, name: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in name.strip())
        cleaned = "_".join(cleaned.split())
        return cleaned.strip("._-")

    def preset_path(self, name: str) -> Path:
        safe = self.sanitize_preset_name(name)
        if not safe:
            raise ValueError("Nom de preset vide.")
        return self.presets_dir() / f"{safe}{PRESET_FILE_SUFFIX}"

    def refresh_preset_list(self):
        folder = self.presets_dir()
        self.available_presets = sorted(p.stem for p in folder.glob(f"*{PRESET_FILE_SUFFIX}") if p.is_file())
        if hasattr(self, "preset_combo"):
            self.preset_combo.configure(values=self.available_presets)

        current = self.preset_var.get().strip()
        if self.available_presets:
            if current not in self.available_presets:
                self.preset_var.set(DEFAULT_PRESET_NAME if DEFAULT_PRESET_NAME in self.available_presets else self.available_presets[0])
        else:
            self.preset_var.set("")

    def ensure_default_preset(self):
        """Cree ./presets/default.json s'il n'existe pas encore."""
        path = self.preset_path(DEFAULT_PRESET_NAME)
        if not path.exists():
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.preset_data(DEFAULT_PRESET_NAME), f, ensure_ascii=False, indent=2)
        return path

    def load_startup_preset(self):
        """Automatically load the default preset at application startup."""
        try:
            self.ensure_default_preset()
            self.refresh_preset_list()
            self.preset_var.set(DEFAULT_PRESET_NAME)
            path = self.preset_path(DEFAULT_PRESET_NAME)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.apply_preset_data(data)
            self.status_var.set(f"Preset par defaut charge : ./{PRESET_DIR_NAME}/{DEFAULT_PRESET_NAME}{PRESET_FILE_SUFFIX}")
        except Exception as exc:
            self.status_var.set(f"Default preset not loaded: {exc}")

    def preset_data(self, name: str = "") -> dict:
        """Return the current parameters as JSON-serializable data."""
        cfg = self.read_config_from_ui()
        return {
            "preset_type": PRESET_TYPE,
            "version": PRESET_VERSION,
            "name": name,
            "parameters": {
                "dpi": cfg.dpi,
                "contour_width_mm": cfg.contour_width_mm,
                "contour_margin_mm": cfg.contour_margin_mm,
                "fill_margin_mm": cfg.fill_margin_mm,
                "fill_edge_width_mm": cfg.fill_edge_width_mm,
                "normal_z_threshold": cfg.normal_z_threshold,
                "page_margin_ratio": cfg.page_margin_ratio,
                "label_font_size_px": cfg.label_font_size_px,
                "min_output_px": cfg.min_output_px,
                "show_grid": bool(self.grid_var.get()) if hasattr(self, "grid_var") else False,
            },
        }

    def apply_preset_data(self, data: dict):
        """Apply a JSON preset and recompute only once at the end."""
        params = data.get("parameters", data)
        mapping = {
            "dpi": self.dpi_var,
            "contour_width_mm": self.contour_width_var,
            "contour_margin_mm": self.contour_margin_var,
            "fill_margin_mm": self.fill_margin_var,
            "fill_edge_width_mm": self.fill_edge_width_var,
            "normal_z_threshold": self.normal_threshold_var,
            "page_margin_ratio": self.page_margin_var,
            "label_font_size_px": self.label_size_var,
            "min_output_px": self.min_px_var,
        }
        missing = [key for key in mapping if key not in params]
        if missing:
            raise ValueError("Preset incomplet, cle(s) manquante(s) : " + ", ".join(missing))

        self._loading_preset = True
        try:
            for key, var in mapping.items():
                var.set(str(params[key]))
                widget_info = self.param_widgets.get(str(var))
                if widget_info:
                    try:
                        value = float(str(params[key]).replace(",", "."))
                        value = max(widget_info["min"], min(widget_info["max"], value))
                        widget_info["scale_var"].set(value)
                    except Exception:
                        pass
            if "show_grid" in params and hasattr(self, "grid_var"):
                self.grid_var.set(bool(params.get("show_grid")))
        finally:
            self._loading_preset = False

        self.config = self.read_config_from_ui()
        self.status_var.set("Preset loaded: automatic recompute...")
        self.schedule_render(immediate=True)

    def save_preset_file(self, name: str):
        safe = self.sanitize_preset_name(name)
        if not safe:
            raise ValueError("The preset name is empty or invalid.")
        path = self.preset_path(safe)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.preset_data(safe), f, ensure_ascii=False, indent=2)
        self.refresh_preset_list()
        self.preset_var.set(safe)
        return path

    def create_new_preset(self):
        name = simpledialog.askstring("New preset", "New preset name:", parent=self.root)
        if name is None:
            return
        safe = self.sanitize_preset_name(name)
        if not safe:
            messagebox.showwarning("Invalid name", "Enter a non-empty preset name.")
            return
        path = self.preset_path(safe)
        if path.exists():
            if not messagebox.askyesno("Existing preset", f"Preset '{safe}' already exists. Replace it?"):
                return
        try:
            self.save_preset_file(safe)
        except Exception as exc:
            messagebox.showerror("Preset error", str(exc))

    def save_selected_preset(self):
        name = self.preset_var.get().strip()
        if not name:
            self.create_new_preset()
            return
        try:
            self.save_preset_file(name)
        except Exception as exc:
            messagebox.showerror("Preset error", str(exc))

    def delete_selected_preset(self):
        name = self.preset_var.get().strip()
        if not name:
            messagebox.showwarning("No preset", "No preset selected for deletion ")
            return

        safe = self.sanitize_preset_name(name)
        if safe == DEFAULT_PRESET_NAME:
            messagebox.showwarning(
                "Preset protege",
                "The default preset cannot be deleted. You can modify it and save it ",
            )
            return

        path = self.preset_path(safe)
        if not path.exists():
            self.refresh_preset_list()
            return

        if not messagebox.askyesno("Delete preset", f"Permanently delete preset '{safe}' ?"):
            return

        try:
            path.unlink()
            self.refresh_preset_list()
            if self.available_presets:
                next_name = DEFAULT_PRESET_NAME if DEFAULT_PRESET_NAME in self.available_presets else self.available_presets[0]
                self.preset_var.set(next_name)
                self.load_selected_preset()
            else:
                self.ensure_default_preset()
                self.refresh_preset_list()
                self.preset_var.set(DEFAULT_PRESET_NAME)
                self.load_selected_preset()
        except Exception as exc:
            messagebox.showerror("Preset error", f"Cannot delete preset:\n{exc}")

    def load_selected_preset(self):
        name = self.preset_var.get().strip()
        if not name:
            messagebox.showwarning("No preset", f"No preset found in folder ./{PRESET_DIR_NAME}.")
            return
        path = self.preset_path(name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.apply_preset_data(data)
            self.status_var.set(f"Preset charge : {path}")
        except Exception as exc:
            messagebox.showerror("Preset error", f"Cannot load preset:\n{exc}")

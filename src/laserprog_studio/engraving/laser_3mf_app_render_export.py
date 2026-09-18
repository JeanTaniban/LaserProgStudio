# -*- coding: utf-8 -*-
from __future__ import annotations

from .laser_3mf_core import *  # type: ignore  # noqa: F401,F403
from .image_panel import ImagePanel  # type: ignore  # noqa: F401

class Laser3MFAppRenderExportLayer:
    def schedule_render(self, immediate: bool = False):
        if not self.input_path and not self.input_var.get().strip():
            return
        if self.render_after_id is not None:
            self.root.after_cancel(self.render_after_id)
        # Fast automatic recompute. Keep a very small delay to avoid
        # stacking 30 renders during a slider drag, while the interface
        # updates as soon as the change is stable.
        delay_ms = 70 if immediate else 180
        self.render_after_id = self.root.after(delay_ms, self.render_current)
        self.status_var.set("Setting changed: automatic recompute...")

    def render_current(self):
        if self.is_rendering:
            return
        self.render_after_id = None
        try:
            raw = self.input_var.get().strip()
            if raw:
                self.input_path = Path(raw)
            if self.input_path is None or not self.input_path.exists():
                self.status_var.set("Select a .3mf file first.")
                return

            self.config = self.read_config_from_ui()
            self.is_rendering = True
            self.status_var.set("Calcul en cours...")
            self.root.update_idletasks()

            instances = load_instances(self.input_path, self.config)
            self.last_instances = instances
            if not instances:
                raise RuntimeError("No top surface detected in the 3MF.")

            self.images = {
                "top": render_top_down(instances, self.config),
                "laser": render_laser_bw(instances, self.config),
                "thickness": render_thickness(instances, self.config),
            }
            self.refresh_panels()

            outline_union = union_by_operation(instances, "outline")
            fill_union = union_by_operation(instances, "fill")
            n_outline = sum(1 for _ in iter_polygons(outline_union)) if outline_union else 0
            n_fill = sum(1 for _ in iter_polygons(fill_union)) if fill_union else 0
            self.last_instances_count = len(instances)
            self.status_var.set(
                f"OK  {len(instances)} area(s) detected. "
                f"Green outlines after union: {n_outline}. Red fills after union: {n_fill}."
            )
        except ValueError as exc:
            # During live input, avoid an aggressive popup.
            self.status_var.set(f"Invalid parameter: {exc}")
        except Exception as exc:
            self.status_var.set("Error during computation.")
            messagebox.showerror("Error", str(exc))
        finally:
            self.is_rendering = False

    def export_folder(self) -> Path:
        root = Path(self.output_root_var.get()).expanduser()
        stem = self.input_path.stem if self.input_path else "3mf"
        return root / f"{stem}_laser_exports"

    def current_dimension_metadata(self) -> Dict:
        """Dimension metadata used to preserve the real scale of PNG exports."""
        if not self.last_instances:
            return {}

        minx, miny, maxx, maxy = global_bounds(self.last_instances)
        tr = CanvasTransform((minx, miny, maxx, maxy), self.config)
        effective_dpi = float(tr.scale * 25.4)

        return {
            "metadata_type": "laser_3mf_dimensions",
            "version": 1,
            "source_file": str(self.input_path) if self.input_path else None,
            "unit": "mm",
            "model_bounds_mm": {
                "min_x": float(minx),
                "min_y": float(miny),
                "max_x": float(maxx),
                "max_y": float(maxy),
                "width": float(maxx - minx),
                "height": float(maxy - miny),
            },
            "image_canvas_mm": {
                "min_x": float(tr.minx),
                "min_y": float(tr.miny),
                "max_x": float(tr.maxx),
                "max_y": float(tr.maxy),
                "width": float(tr.maxx - tr.minx),
                "height": float(tr.maxy - tr.miny),
            },
            "image_pixels": {
                "width": int(tr.width),
                "height": int(tr.height),
            },
            "pixels_per_mm": float(tr.scale),
            "effective_dpi": effective_dpi,
            "note": "The PNG also contains this DPI. Some software ignores PNG DPI; in that case, use the *_dimensions.json file.",
        }

    def save_png_with_dimensions(self, img: Image.Image, out: Path):
        """Save PNG + DPI + text metadata + sidecar JSON."""
        from PIL import PngImagePlugin

        metadata = self.current_dimension_metadata()
        dpi = float(metadata.get("effective_dpi", self.config.dpi))

        pnginfo = PngImagePlugin.PngInfo()
        if metadata:
            pnginfo.add_text("laser_3mf_dimensions_json", json.dumps(metadata, ensure_ascii=False))
            pnginfo.add_text("unit", "mm")
            pnginfo.add_text("effective_dpi", f"{dpi:.6f}")
            pnginfo.add_text("pixels_per_mm", f"{metadata.get('pixels_per_mm', 0):.9f}")

        img.save(out, dpi=(dpi, dpi), pnginfo=pnginfo)

    def save_image(self, key: str, filename: str):
        if key not in self.images:
            messagebox.showwarning("No image", "No image has been generated yet.")
            return
        try:
            folder = self.export_folder()
            folder.mkdir(parents=True, exist_ok=True)
            out = folder / filename
            self.save_png_with_dimensions(self.images[key], out)
            self.status_var.set(f"Image saved: {out}")
            messagebox.showinfo("Save complete", f"Image saved:\n{out}")
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))

    def save_all(self):
        if not self.images:
            messagebox.showwarning("No image", "No image has been generated yet.")
            return
        try:
            folder = self.export_folder()
            folder.mkdir(parents=True, exist_ok=True)
            mapping = {
                "laser": "01_laser_black_white.png",
                "top": "02_top_down_union.png",
                "thickness": "03_thickness_labels_bw.png",
            }
            for key, filename in mapping.items():
                self.save_png_with_dimensions(self.images[key], folder / filename)

            svg_path = export_falcon_svg(self.last_instances, self.config, folder / "04_falcon_design_space.svg")

            if self.input_path and self.input_path.exists():
                shutil.copy2(self.input_path, folder / self.input_path.name)
            self.status_var.set(f"Images + Falcon SVG saved in: {folder}")
            messagebox.showinfo("Save complete", f"Images and Falcon SVG saved in:\n{folder}\n\nSVG: {svg_path.name}")
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))

    def export_falcon_svg_file(self):
        """Generate a Falcon Design Space compatible SVG manually."""
        if not self.last_instances:
            messagebox.showwarning("No data", "No model has been computed yet.")
            return
        try:
            folder = self.export_folder()
            folder.mkdir(parents=True, exist_ok=True)
            out = export_falcon_svg(self.last_instances, self.config, folder / "04_falcon_design_space.svg")
            self.status_var.set(f"Falcon SVG generated: {out}")
            messagebox.showinfo("SVG generated", f"Falcon-compatible SVG generated:\n{out}")
        except Exception as exc:
            messagebox.showerror("SVG error", str(exc))

    def export_dimensions_json(self):
        """Generate a dimensions/parameters JSON manually in the export folder."""
        if not self.last_instances:
            messagebox.showwarning("No data", "No model has been computed yet.")
            return
        try:
            folder = self.export_folder()
            folder.mkdir(parents=True, exist_ok=True)
            data = {
                "metadata_type": "laser_3mf_export_report",
                "version": 1,
                "preset": self.preset_var.get(),
                "parameters": self.preset_data().get("parameters", {}),
                "dimensions": self.current_dimension_metadata(),
            }
            out = folder / "dimensions_export.json"
            with open(out, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.status_var.set(f"Dimensions JSON generated: {out}")
            messagebox.showinfo("JSON generated", f"Dimensions JSON generated:\n{out}")
        except Exception as exc:
            messagebox.showerror("JSON error", str(exc))

    def open_export_folder(self):
        folder = self.export_folder()
        folder.mkdir(parents=True, exist_ok=True)
        try:
            import os
            import subprocess
            import sys
            if sys.platform.startswith("win"):
                os.startfile(folder)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Error", f"Cannot open folder:\n{exc}")

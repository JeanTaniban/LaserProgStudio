# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from pathlib import Path

from ..app_context import AppContext
from ..bootstrap import compute_paths
from ..studio_log import log_exception
from .action_controller import WindowController


class _LazyQtSymbol:
    """Import a Qt symbol only when a UI operation actually needs it.

    Architecture tests import application controllers in environments where Qt
    may be unavailable.  Runtime calls still resolve the real PySide6 objects.
    """

    def __init__(self, module_name: str, symbol_name: str):
        self.module_name = module_name
        self.symbol_name = symbol_name

    def _resolve(self):
        module = __import__(self.module_name, fromlist=[self.symbol_name])
        return getattr(module, self.symbol_name)

    def __getattr__(self, name: str):
        return getattr(self._resolve(), name)

    def __call__(self, *args, **kwargs):
        return self._resolve()(*args, **kwargs)


QFileDialog = _LazyQtSymbol("PySide6.QtWidgets", "QFileDialog")
QMessageBox = _LazyQtSymbol("PySide6.QtWidgets", "QMessageBox")
QTimer = _LazyQtSymbol("PySide6.QtCore", "QTimer")


_STUDIO_PATHS = compute_paths()
ROOT = _STUDIO_PATHS.root
EXAMPLES_DIR = _STUDIO_PATHS.examples_dir
EXPORTS_DIR = _STUDIO_PATHS.exports_dir
DIAG_DIR = _STUDIO_PATHS.diagnostics_dir


class _ExportOperations:
    def _polydata_to_workmesh(self, poly, name: str, color: str):
        from laserprog_studio.domain.work_model import WorkMesh
        import numpy as np
        pdata = poly.triangulate().clean()
        points = [(float(x), float(y), float(z)) for x, y, z in np.asarray(pdata.points)]
        faces = np.asarray(pdata.faces, dtype=int)
        tris = []
        i = 0
        while i < len(faces):
            n = int(faces[i])
            if n == 3:
                tris.append((int(faces[i+1]), int(faces[i+2]), int(faces[i+3])))
            i += n + 1
        return WorkMesh(name=name, vertices=points, triangles=tris, color=color)

    def _make_manual_workmesh(self, name: str, vertices: list[tuple[float, float, float]], triangles: list[tuple[int, int, int]], color: str):
        from laserprog_studio.domain.work_model import WorkMesh
        return WorkMesh(name=name, vertices=vertices, triangles=triangles, color=color)



    def export_3mf_dialog(self) -> None:
        if self.mesh_store is None or not self.current_meshes():
            self.ui_log("[EXPORT] No model to export"); return
        path, _ = QFileDialog.getSaveFileName(self, "Export 3MF model", str(ROOT / "laserprog_studio_export.3mf"), "3MF (*.3mf)")
        if not path: return
        try:
            from laserprog_studio.domain.work_model import build_3mf_model_xml, write_3mf_container
            export_meshes = [copy.deepcopy(m) for m in self.current_meshes() if not self._is_scene_helper_mesh(m)]
            xml = build_3mf_model_xml(export_meshes, application_name="LaserProg Studio V18")
            write_3mf_container(Path(path), xml)
            self.ui_log(f"[EXPORT] 3MF exported: {path}")
        except Exception:
            log_exception("export_3mf_dialog"); self.ui_log("[EXPORT] ERROR exporting 3MF (see log)")

    def open_engrave_workspace(self) -> None:
        """Open the engraving export workspace instead of the 3D view."""
        try:
            if self.mesh_store is None or not self.current_meshes():
                QMessageBox.information(self, "Engraving export", "The scene is empty. Create or open a model first.")
                return
            if not self.confirm_preview_before_tool_change("export engraving"):
                return
            self.close_active_tool(log_it=False, ask_preview=False)
            self.center_stack.setCurrentIndex(1)
            self._sync_light_transform_overlay()
            self.engrave_status.setText("Rendering laser views...")
            self.ui_log("[ENGRAVE] Export workspace opened")
            QTimer.singleShot(50, self.render_engrave_current)
        except Exception:
            log_exception("open_engrave_workspace")

    def close_engrave_workspace(self) -> None:
        try:
            self.center_stack.setCurrentIndex(0)
            self._sync_light_transform_overlay()
            self.ui_log("[ENGRAVE] Back to 3D view")
        except Exception:
            log_exception("close_engrave_workspace")

    def _engrave_config_from_ui(self):
        from laserprog_studio.engraving.export_2d import RenderConfig
        cfg = RenderConfig()
        cfg.dpi = int(self.eng_dpi.value())
        cfg.contour_width_mm = float(self.eng_contour_width.value())
        cfg.contour_margin_mm = float(self.eng_contour_margin.value())
        cfg.fill_margin_mm = float(self.eng_fill_margin.value())
        cfg.fill_edge_width_mm = float(self.eng_fill_edge.value())
        cfg.normal_z_threshold = float(self.eng_normal_z.value())
        cfg.page_margin_ratio = float(self.eng_page_margin.value())
        cfg.label_font_size_px = int(self.eng_label_px.value())
        cfg.min_output_px = int(self.eng_min_px.value())
        return cfg

    def _render_current_model_to_engrave_images(self):
        from laserprog_studio.engraving.export_2d import load_instances, render_top_down, render_laser_bw, render_thickness, global_bounds
        tmp_dir = DIAG_DIR / "engrave_current"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        tmp_3mf = tmp_dir / "_laserprog_engraving_source.3mf"
        cfg = self._engrave_config_from_ui()

        # TEX face decals are viewport/export overlays, not physical mesh parts.
        # If they are included in the temporary 3MF, the normal mesh layer can be
        # hidden or polluted by white "ignore" faces.  Filter them out for the
        # geometry layer, then render them separately as a texture raster layer.
        current_meshes = [copy.deepcopy(m) for m in self.current_meshes() if not self._is_scene_helper_mesh(m)]
        geometry_meshes = [m for m in current_meshes if not bool(getattr(m, "is_texture_decal", False))]
        if not geometry_meshes:
            geometry_meshes = current_meshes
        from laserprog_studio.domain.work_model import build_3mf_model_xml, write_3mf_container

        xml = build_3mf_model_xml(geometry_meshes, application_name="LaserProg Studio V18 - Engraving")
        write_3mf_container(tmp_3mf, xml)
        instances = load_instances(tmp_3mf, cfg)
        if not instances:
            raise RuntimeError("No top surface detected in the 3MF.")
        bounds = global_bounds(instances)
        from laserprog_studio.engraving.texture_layer import render_texture_layer_from_meshes, render_texture_cut_outline_mask

        texture_engrave = render_texture_layer_from_meshes(
            current_meshes,
            texture_assets_by_id=getattr(self, "texture_assets_by_id", {}),
            bounds=bounds,
            cfg=cfg,
            usage_filter="engrave",
        )
        # Cut outline uses two texture images:
        # - a filled binary mask for vector tracing;
        # - a boundary-only mask for the UI/PNG preview layer.
        texture_cut_fill = render_texture_layer_from_meshes(
            current_meshes,
            texture_assets_by_id=getattr(self, "texture_assets_by_id", {}),
            bounds=bounds,
            cfg=cfg,
            usage_filter="cut",
            source_mode="binary_fill",
        )
        texture_cut = render_texture_layer_from_meshes(
            current_meshes,
            texture_assets_by_id=getattr(self, "texture_assets_by_id", {}),
            bounds=bounds,
            cfg=cfg,
            usage_filter="cut",
            source_mode="binary_boundary",
        )
        # UI preview: when TEX usage is Cut, the pure engraving texture layer is
        # intentionally white.  Showing only that layer made the user think TEX
        # export was empty.  The preview layer combines engrave and cut masks,
        # while the manufacturing exports below still use the separate pure
        # engrave/cut images.
        try:
            from PIL import ImageChops
            from laserprog_studio.engraving.texture_layer import texture_layer_has_marks
            if texture_layer_has_marks(texture_engrave) and texture_layer_has_marks(texture_cut):
                texture_preview = ImageChops.darker(texture_engrave.convert("RGB"), texture_cut.convert("RGB"))
            elif texture_layer_has_marks(texture_cut):
                texture_preview = texture_cut.convert("RGB")
            else:
                texture_preview = texture_engrave.convert("RGB")
        except Exception:
            texture_preview = texture_engrave
        images = {
            "laser": render_laser_bw(instances, cfg),
            "top": render_top_down(instances, cfg),
            "thickness": render_thickness(instances, cfg),
            "texture": texture_engrave,
            "texture_cut": texture_cut,
            "texture_cut_fill": texture_cut_fill,
            "texture_preview": texture_preview,
        }
        return tmp_3mf, cfg, instances, images

    def render_engrave_current(self) -> None:
        try:
            if self.mesh_store is None or not self.current_meshes():
                self.engrave_status.setText("No model to convert.")
                return
            tmp_3mf, cfg, instances, images = self._render_current_model_to_engrave_images()
            self._engrave_source_path = tmp_3mf
            self._engrave_config = cfg
            self._engrave_instances = instances
            self._engrave_images = images
            tmp_dir = DIAG_DIR / "engrave_current"
            paths = {
                "laser": tmp_dir / "01_laser_black_white.png",
                "top": tmp_dir / "02_top_down_union.png",
                "thickness": tmp_dir / "03_thickness_labels_bw.png",
                "texture_preview": tmp_dir / "04_texture_layer.png",
                "texture_cut": tmp_dir / "04b_texture_cut_mask.png",
            }
            images["laser"].save(paths["laser"])
            images["top"].save(paths["top"])
            images["thickness"].save(paths["thickness"])
            images.get("texture_preview", images.get("texture", images["laser"])).save(paths["texture_preview"])
            images.get("texture_cut", images["laser"]).save(paths["texture_cut"])
            self.engrave_laser_view.load_image(paths["laser"])
            self.engrave_top_view.load_image(paths["top"])
            self.engrave_thick_view.load_image(paths["thickness"])
            if hasattr(self, "engrave_texture_view"):
                self.engrave_texture_view.load_image(paths["texture_preview"])
            self.engrave_source_label.setText(f"Temporary source: {tmp_3mf.name}")
            self.engrave_status.setText(f"OK: {len(instances)} area(s) detected.")
            self.ui_log(f"[ENGRAVE] Render OK: instances={len(instances)}")
        except Exception as exc:
            log_exception("render_engrave_current")
            self.engrave_status.setText(f"Error: {exc}")
            QMessageBox.warning(self, "Engraving export", str(exc))

    def _engrave_dimension_metadata(self) -> dict:
        try:
            from laserprog_studio.engraving.export_2d import global_bounds, CanvasTransform
            if not getattr(self, "_engrave_instances", None):
                return {}
            cfg = getattr(self, "_engrave_config", self._engrave_config_from_ui())
            minx, miny, maxx, maxy = global_bounds(self._engrave_instances)
            tr = CanvasTransform((minx, miny, maxx, maxy), cfg)
            effective_dpi = float(tr.scale * 25.4)
            return {
                "metadata_type": "laser_3mf_dimensions",
                "version": 1,
                "source_file": str(self._engrave_source_path) if self._engrave_source_path else None,
                "unit": "mm",
                "model_bounds_mm": {"min_x": float(minx), "min_y": float(miny), "max_x": float(maxx), "max_y": float(maxy), "width": float(maxx-minx), "height": float(maxy-miny)},
                "image_canvas_mm": {"min_x": float(tr.minx), "min_y": float(tr.miny), "max_x": float(tr.maxx), "max_y": float(tr.maxy), "width": float(tr.maxx-tr.minx), "height": float(tr.maxy-tr.miny)},
                "image_pixels": {"width": int(tr.width), "height": int(tr.height)},
                "pixels_per_mm": float(tr.scale),
                "effective_dpi": effective_dpi,
            }
        except Exception:
            log_exception("engrave_dimension_metadata")
            return {}

    def _save_png_with_dimensions(self, img, out: Path) -> None:
        try:
            import json
            from PIL import PngImagePlugin
            metadata = self._engrave_dimension_metadata()
            dpi = float(metadata.get("effective_dpi", int(self.eng_dpi.value())))
            pnginfo = PngImagePlugin.PngInfo()
            if metadata:
                pnginfo.add_text("laser_3mf_dimensions_json", json.dumps(metadata, ensure_ascii=False))
                pnginfo.add_text("unit", "mm")
                pnginfo.add_text("effective_dpi", f"{dpi:.6f}")
                pnginfo.add_text("pixels_per_mm", f"{metadata.get('pixels_per_mm', 0):.9f}")
            img.save(out, dpi=(dpi, dpi), pnginfo=pnginfo)
        except Exception:
            img.save(out)

    def save_engrave_all(self) -> None:
        if not self._engrave_images:
            self.render_engrave_current()
            if not self._engrave_images:
                return
        folder = QFileDialog.getExistingDirectory(self, "Choose engraving export folder", str(EXPORTS_DIR / "engraving"))
        if not folder:
            return
        try:
            out_dir = Path(folder)
            out_dir.mkdir(parents=True, exist_ok=True)
            mapping = {
                "laser": "01_laser_black_white.png",
                "top": "02_top_down_union.png",
                "thickness": "03_thickness_labels_bw.png",
                # 04 is the user-visible texture preview layer.  Pure manufacturing
                # images remain available in memory as "texture" and "texture_cut"
                # for SVG generation below.
                "texture_preview": "04_texture_layer.png",
                "texture_cut": "04b_texture_cut_mask.png",
            }
            for key, filename in mapping.items():
                if key in self._engrave_images:
                    self._save_png_with_dimensions(self._engrave_images[key], out_dir / filename)
            from laserprog_studio.engraving.export_2d import export_falcon_svg, global_bounds
            cfg = getattr(self, "_engrave_config", self._engrave_config_from_ui())
            svg_path = export_falcon_svg(
                self._engrave_instances,
                cfg,
                out_dir / "05_falcon_geometry.svg",
            )
            texture_svg_path = None
            texture_cut_svg_path = None
            from laserprog_studio.engraving.texture_layer import export_texture_layer_svg, export_texture_cut_contours_svg, texture_layer_has_marks
            export_bounds = global_bounds(self._engrave_instances)
            if "texture" in self._engrave_images and texture_layer_has_marks(self._engrave_images["texture"]):
                texture_svg_path = export_texture_layer_svg(
                    self._engrave_images["texture"],
                    bounds=export_bounds,
                    cfg=cfg,
                    out=out_dir / "06_falcon_texture_engrave.svg",
                )
            cut_source = self._engrave_images.get("texture_cut_fill", self._engrave_images.get("texture_cut"))
            if cut_source is not None and texture_layer_has_marks(cut_source):
                texture_cut_svg_path = export_texture_cut_contours_svg(
                    cut_source,
                    bounds=export_bounds,
                    cfg=cfg,
                    out=out_dir / "07_falcon_texture_cut.svg",
                )
            import json
            meta = self._engrave_dimension_metadata()
            if meta:
                (out_dir / "engraving_dimensions.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            self.ui_log(f"[ENGRAVE] Images + Falcon SVG exported: {out_dir}")
            extras = []
            if texture_svg_path is not None:
                extras.append(f"Texture engrave SVG: {texture_svg_path.name}")
            if texture_cut_svg_path is not None:
                extras.append(f"Texture cut SVG: {texture_cut_svg_path.name}")
            extra = ("\n" + "\n".join(extras)) if extras else ""
            QMessageBox.information(self, "Engraving export", f"Images and Falcon SVG exported:\n{out_dir}\n\nGeometry SVG: {svg_path.name}{extra}")
        except Exception as exc:
            log_exception("save_engrave_all")
            QMessageBox.warning(self, "Engraving export", str(exc))

    def save_engrave_falcon_svg(self) -> None:
        if not self._engrave_images:
            self.render_engrave_current()
            if not self._engrave_images:
                return
        if not getattr(self, "_engrave_instances", None):
            QMessageBox.warning(self, "Falcon SVG export", "No vector geometry to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Falcon Design Space SVG",
            str(ROOT / "04_falcon_design_space.svg"),
            "SVG (*.svg)",
        )
        if not path:
            return
        try:
            from laserprog_studio.engraving.export_2d import export_falcon_svg, global_bounds
            cfg = getattr(self, "_engrave_config", self._engrave_config_from_ui())
            out = export_falcon_svg(
                self._engrave_instances,
                cfg,
                Path(path),
            )
            texture_out = None
            texture_cut_out = None
            from laserprog_studio.engraving.texture_layer import export_texture_layer_svg, export_texture_cut_contours_svg, texture_layer_has_marks
            export_bounds = global_bounds(self._engrave_instances)
            if "texture" in self._engrave_images and texture_layer_has_marks(self._engrave_images["texture"]):
                texture_out = export_texture_layer_svg(
                    self._engrave_images["texture"],
                    bounds=export_bounds,
                    cfg=cfg,
                    out=Path(path).with_name(Path(path).stem + "_texture_engrave.svg"),
                )
            cut_source = self._engrave_images.get("texture_cut_fill", self._engrave_images.get("texture_cut"))
            if cut_source is not None and texture_layer_has_marks(cut_source):
                texture_cut_out = export_texture_cut_contours_svg(
                    cut_source,
                    bounds=export_bounds,
                    cfg=cfg,
                    out=Path(path).with_name(Path(path).stem + "_texture_cut.svg"),
                )
            self.ui_log(f"[ENGRAVE] Falcon SVG exported: {out}")
            msg = f"Falcon-ready geometry SVG exported:\n{out}"
            if texture_out is not None:
                msg += f"\n\nTexture engrave SVG exported:\n{texture_out}"
            if texture_cut_out is not None:
                msg += f"\n\nTexture cut SVG exported:\n{texture_cut_out}"
            QMessageBox.information(self, "Falcon SVG export", msg)
        except Exception as exc:
            log_exception("save_engrave_falcon_svg")
            QMessageBox.warning(self, "Falcon SVG export", str(exc))

    def save_engrave_dimensions_json(self) -> None:
        if not self._engrave_images:
            self.render_engrave_current()
        meta = self._engrave_dimension_metadata()
        if not meta:
            QMessageBox.warning(self, "Export dimensions", "No metadata to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export dimensions JSON", str(ROOT / "engraving_dimensions.json"), "JSON (*.json)")
        if not path:
            return
        try:
            import json
            Path(path).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            self.ui_log(f"[ENGRAVE] Dimensions JSON exported: {path}")
        except Exception as exc:
            log_exception("save_engrave_dimensions_json")
            QMessageBox.warning(self, "Export dimensions", str(exc))

    def export_gravure_dialog(self) -> None:
        # Open the dedicated workspace through the current window bridge.
        self.open_engrave_workspace()

    def open_3mf_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a 3MF file", str(ROOT / "Documents"), "3MF (*.3mf);;All files (*.*)")
        if path: self.load_3d_model(Path(path))

    def load_default_2d_preview(self) -> None:
        path = EXAMPLES_DIR / "layflat_parts_laser_exports" / "01_laser_black_white.png"
        if path.exists(): self.load_2d_image(path)

    def load_2d_image(self, path: Path) -> None:
        # Engraving export is an output tool, not a separate workspace shown by default.
        self.ui_log(f"[2D] Example image available: {path}")



class ExportController(WindowController):
    """Composable owner for 3MF, primitive and engraving export workflows.

    ``ExportingLayer`` is a thin Qt-window adapter. Keeping the real
    behavior here makes export features discoverable without adding more
    behavior to ``MainWindow``'s inheritance chain.
    """

    @classmethod
    def create(cls, context: AppContext) -> "ExportController":
        return cls(context)

    def _polydata_to_workmesh(self, *args, **kwargs):
        return _ExportOperations._polydata_to_workmesh(self.owner, *args, **kwargs)

    def _make_manual_workmesh(self, *args, **kwargs):
        return _ExportOperations._make_manual_workmesh(self.owner, *args, **kwargs)



    def export_3mf_dialog(self, *args, **kwargs):
        return _ExportOperations.export_3mf_dialog(self.owner, *args, **kwargs)

    def open_engrave_workspace(self, *args, **kwargs):
        return _ExportOperations.open_engrave_workspace(self.owner, *args, **kwargs)

    def close_engrave_workspace(self, *args, **kwargs):
        return _ExportOperations.close_engrave_workspace(self.owner, *args, **kwargs)

    def _engrave_config_from_ui(self, *args, **kwargs):
        return _ExportOperations._engrave_config_from_ui(self.owner, *args, **kwargs)

    def _render_current_model_to_engrave_images(self, *args, **kwargs):
        return _ExportOperations._render_current_model_to_engrave_images(self.owner, *args, **kwargs)

    def render_engrave_current(self, *args, **kwargs):
        return _ExportOperations.render_engrave_current(self.owner, *args, **kwargs)

    def _engrave_dimension_metadata(self, *args, **kwargs):
        return _ExportOperations._engrave_dimension_metadata(self.owner, *args, **kwargs)

    def _save_png_with_dimensions(self, *args, **kwargs):
        return _ExportOperations._save_png_with_dimensions(self.owner, *args, **kwargs)

    def save_engrave_all(self, *args, **kwargs):
        return _ExportOperations.save_engrave_all(self.owner, *args, **kwargs)

    def save_engrave_falcon_svg(self, *args, **kwargs):
        return _ExportOperations.save_engrave_falcon_svg(self.owner, *args, **kwargs)

    def save_engrave_dimensions_json(self, *args, **kwargs):
        return _ExportOperations.save_engrave_dimensions_json(self.owner, *args, **kwargs)

    def export_gravure_dialog(self, *args, **kwargs):
        return _ExportOperations.export_gravure_dialog(self.owner, *args, **kwargs)

    def open_3mf_dialog(self, *args, **kwargs):
        return _ExportOperations.open_3mf_dialog(self.owner, *args, **kwargs)

    def load_default_2d_preview(self, *args, **kwargs):
        return _ExportOperations.load_default_2d_preview(self.owner, *args, **kwargs)

    def load_2d_image(self, *args, **kwargs):
        return _ExportOperations.load_2d_image(self.owner, *args, **kwargs)

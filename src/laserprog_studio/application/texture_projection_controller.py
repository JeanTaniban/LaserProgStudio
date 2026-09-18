# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from ..app_context import AppContext
from ..bootstrap import compute_paths
from ..studio_log import log_exception
from .owner_delegating_controller import OwnerDelegatingController

ROOT = compute_paths().root


def _qfiledialog() -> Any:
    from PySide6.QtWidgets import QFileDialog

    return QFileDialog


class TextureProjectionController(OwnerDelegatingController):
    """Own texture projection file/anchor/preview workflows outside MainWindow.

    This is the first TEX migration slice.  It extracts the non-gizmo
    workflows from the old mixin while keeping delegated access to the
    window during the transition.  Later passes can split the remaining gizmo
    code into smaller interaction services.
    """

    @classmethod
    def create(cls, context: AppContext) -> "TextureProjectionController":
        return cls(context)

    def _texture_projection_selected_indices(self) -> list[int]:
        try:
            return self._selected_transform_indices()
        except Exception:
            return [int(i) for i in getattr(self, "selected_indices", [])]

    def _clear_texture_projection_tool_state(self) -> None:
        try:
            self._texture_projection_last_anchor = None
            if hasattr(self, "texture_projection_report"):
                self.texture_projection_report.setText("Click a face or select a part, choose an image, then Preview selected.")
        except Exception:
            pass

    def _initialize_texture_projection_tool(self, render: bool | None = None) -> None:
        try:
            if not hasattr(self, "_texture_projection_last_anchor"):
                self._texture_projection_last_anchor = None
            self._update_texture_projection_report()
        except Exception:
            log_exception("initialize_texture_projection_tool")

    def _choose_texture_projection_file(self) -> None:
        try:
            # QFileDialog expects a QWidget parent.  After the migration this
            # method lives on a controller, not on QMainWindow, so passing
            # ``self`` makes the TEX file picker fail on PySide.
            parent = self.owner if hasattr(self, "owner") else None
            path, _ = _qfiledialog().getOpenFileName(
                parent,
                "Select projected texture",
                str(ROOT),
                "Images (*.png *.jpg *.jpeg *.bmp);;All files (*.*)",
            )
            if path and hasattr(self, "texture_projection_path"):
                self.texture_projection_path.setText(path)
                self._register_texture_asset(Path(path))
                self._update_texture_projection_report()
        except Exception:
            log_exception("choose_texture_projection_file")

    def _register_texture_asset(self, path: Path):
        try:
            from ..domain.texture_asset import TextureAsset

            p = Path(path).expanduser()
            texture_id = "tex_" + uuid5(NAMESPACE_URL, str(p.resolve() if p.exists() else p)).hex[:12]
            width = height = None
            try:
                from PIL import Image

                with Image.open(p) as img:
                    width, height = img.size
            except Exception:
                pass
            asset = TextureAsset(id=texture_id, path=p, usage="visual", width=width, height=height)
            if not hasattr(self, "texture_assets_by_id"):
                self.texture_assets_by_id = {}
            self.texture_assets_by_id[texture_id] = asset
            try:
                store = getattr(self, "recent_texture_store", None)
                if store is not None:
                    store.add(p)
            except Exception:
                pass
            return asset
        except Exception:
            log_exception("register_texture_asset")
            return None

    def _texture_projection_params_from_ui(
        self,
        *,
        target_index: int | None = None,
        seed_face_index: int | None = None,
        projection_origin: tuple[float, float, float] | None = None,
        projection_normal: tuple[float, float, float] | None = None,
    ):
        from laserprog_studio.geometry_ops.texture_projection import TextureProjectionParams

        path = Path(str(self.texture_projection_path.text()).strip()).expanduser() if hasattr(self, "texture_projection_path") else Path("")
        if not path.exists():
            raise FileNotFoundError("Select a valid texture image.")
        asset = self._register_texture_asset(path)
        texture_id = getattr(asset, "id", "") or ("tex_" + uuid5(NAMESPACE_URL, str(path)).hex[:12])
        mode = self.texture_projection_mode.currentData() if hasattr(self, "texture_projection_mode") else "planar"
        usage = self.texture_projection_usage.currentData() if hasattr(self, "texture_projection_usage") else "visual"
        scale = float(self.texture_projection_scale.value()) if hasattr(self, "texture_projection_scale") else 1.0
        rotation = float(self.texture_projection_rotation.value()) if hasattr(self, "texture_projection_rotation") else 0.0
        offset_u = float(self.texture_projection_offset_u.value()) if hasattr(self, "texture_projection_offset_u") else 0.0
        offset_v = float(self.texture_projection_offset_v.value()) if hasattr(self, "texture_projection_offset_v") else 0.0
        coverage = float(self.texture_projection_coverage.value()) if hasattr(self, "texture_projection_coverage") else 20.0
        repeat = bool(self.texture_projection_repeat.isChecked()) if hasattr(self, "texture_projection_repeat") else False
        attach_to_mesh = bool(self.texture_projection_attach_to_mesh.isChecked()) if hasattr(self, "texture_projection_attach_to_mesh") else False
        preserve_aspect = bool(self.texture_projection_preserve_aspect.isChecked()) if hasattr(self, "texture_projection_preserve_aspect") else True
        # Reuse the last clicked face if Preview selected is pressed afterwards.
        anchor = getattr(self, "_texture_projection_last_anchor", None)
        if seed_face_index is None and anchor is not None:
            try:
                if target_index is None or int(anchor.get("index", -1)) == int(target_index):
                    seed_face_index = int(anchor.get("cell_id"))
                    projection_origin = tuple(float(v) for v in anchor.get("point"))
                    projection_normal = tuple(float(v) for v in anchor.get("normal"))
            except Exception:
                pass
        return TextureProjectionParams(
            texture_id=str(texture_id),
            texture_path=path,
            projection_mode=str(mode or "planar"),
            usage=str(usage or "visual"),
            coverage_angle_deg=coverage,
            scale=max(scale, 1e-6),
            rotation_deg=rotation,
            offset_u=offset_u,
            offset_v=offset_v,
            repeat=repeat,
            attach_to_mesh=attach_to_mesh,
            preserve_aspect=preserve_aspect,
            image_width=getattr(asset, "width", None),
            image_height=getattr(asset, "height", None),
            seed_face_index=seed_face_index,
            projection_origin=projection_origin,
            projection_normal=projection_normal,
        )

    def _update_texture_projection_report(self, *, preview_meshes=None, error: str | None = None) -> None:
        if not hasattr(self, "texture_projection_report"):
            return
        if error:
            self.texture_projection_report.setText(error)
            return
        idxs = self._texture_projection_selected_indices()
        path_text = ""
        try:
            path_text = str(self.texture_projection_path.text()).strip()
        except Exception:
            pass
        detail = f"Selected parts: {len(idxs)}"
        if path_text:
            detail += f"\nTexture : {Path(path_text).name}"
        anchor = getattr(self, "_texture_projection_last_anchor", None)
        if anchor is not None:
            try:
                detail += f"\nTarget face: part {int(anchor.get('index')):02d}, triangle {int(anchor.get('cell_id'))}"
            except Exception:
                detail += "\nTarget face: saved"
        if preview_meshes is not None:
            detail += "\nPreview ready. Apply keeps it, Cancel discards it."
        else:
            detail += "\nClick a face to place the texture, or Preview selected."
        self.texture_projection_report.setText(detail)

    def _texture_projection_anchor_from_pick(self, idx: int, point, normal, cell_id: int) -> dict[str, object]:
        return {
            "index": int(idx),
            "point": (float(point[0]), float(point[1]), float(point[2])),
            "normal": (float(normal[0]), float(normal[1]), float(normal[2])),
            "cell_id": int(cell_id),
        }

    def _mesh_triangle_normal(self, mesh, cell_id: int) -> tuple[float, float, float] | None:
        try:
            import numpy as np

            tri = getattr(mesh, "triangles", [])[int(cell_id)]
            verts = getattr(mesh, "vertices", [])
            p0 = np.asarray(verts[int(tri[0])], dtype=float)
            p1 = np.asarray(verts[int(tri[1])], dtype=float)
            p2 = np.asarray(verts[int(tri[2])], dtype=float)
            n = np.cross(p1 - p0, p2 - p0)
            length = float(np.linalg.norm(n))
            if length <= 1e-12:
                return None
            n = n / length
            return (float(n[0]), float(n[1]), float(n[2]))
        except Exception:
            return None

    def _pick_texture_projection_anchor_at(self, x: int, y: int):
        """Pick a mesh triangle for TEX so planar UVs follow the clicked face."""
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                return None
            import vtk

            picker = vtk.vtkCellPicker()
            picker.SetTolerance(0.0008)
            try:
                from laserprog_studio.geometry_ops.texture_projection_decal import _is_texture_decal

                picker.PickFromListOn()
                meshes_for_pick = list(self.current_meshes())
                added = False
                for raw_idx, actor in sorted(getattr(self, "actors_by_index", {}).items()):
                    try:
                        idx = int(raw_idx)
                    except Exception:
                        idx = -1
                    if 0 <= idx < len(meshes_for_pick) and _is_texture_decal(meshes_for_pick[idx]):
                        # Decals sit slightly above the source mesh.  If they are
                        # pickable here, a second click on the same painted face can
                        # resolve to the preview decal index instead of the real
                        # source mesh.  Pick through decals so same-face click means
                        # “move/reload placement at this hit point”.
                        continue
                    picker.AddPickList(actor)
                    added = True
                if not added:
                    for actor in self.actors_by_index.values():
                        picker.AddPickList(actor)
            except Exception:
                try:
                    picker.PickFromListOn()
                    for actor in self.actors_by_index.values():
                        picker.AddPickList(actor)
                except Exception:
                    pass
            picker.Pick(int(x), int(y), 0, self.plotter.renderer)
            picked_actor = picker.GetActor() or picker.GetViewProp()
            resolved = self._resolve_picked_actor(picked_actor)
            if not resolved or resolved[0] != "mesh":
                return None
            idx = int(resolved[1])
            cell_id = int(picker.GetCellId())
            if cell_id < 0:
                return None
            meshes = self.current_meshes()
            if not (0 <= idx < len(meshes)):
                return None
            normal = self._mesh_triangle_normal(meshes[idx], cell_id)
            if normal is None:
                try:
                    normal = tuple(float(v) for v in picker.GetPickNormal())
                except Exception:
                    normal = (0.0, 0.0, 1.0)
            point = picker.GetPickPosition()
            return idx, point, normal, cell_id
        except Exception:
            log_exception("pick_texture_projection_anchor_at")
            return None

    def _pick_texture_projection_anchor_from_qt_pos(self, qx: float, qy: float):
        try:
            for vx, vy, label in self._qt_to_vtk_candidates(qx, qy):
                anchor = self._pick_texture_projection_anchor_at(vx, vy)
                if anchor is not None:
                    idx, _point, _normal, cell_id = anchor
                    self.ui_log(f"[TEXTURE] Face pick OK mesh={idx} triangle={cell_id} via {label} vtk=({vx},{vy})")
                    return anchor
        except Exception:
            log_exception("pick_texture_projection_anchor_from_qt_pos")
        return None

    def generate_texture_projection_preview(
        self,
        *,
        target_index: int | None = None,
        seed_face_index: int | None = None,
        projection_origin: tuple[float, float, float] | None = None,
        projection_normal: tuple[float, float, float] | None = None,
    ) -> None:
        try:
            from laserprog_studio.geometry_ops.texture_projection import apply_texture_projection

            idxs = [int(target_index)] if target_index is not None else self._texture_projection_selected_indices()
            if not idxs:
                self._update_texture_projection_report(error="Select at least one part to texture.")
                return
            params = self._texture_projection_params_from_ui(
                target_index=idxs[-1] if idxs else None,
                seed_face_index=seed_face_index,
                projection_origin=projection_origin,
                projection_normal=projection_normal,
            )
            base = [copy.deepcopy(m) for m in self.committed_meshes()]
            preview = apply_texture_projection(base, idxs, params)
            self.set_preview_meshes(preview, "Texture projection preview")
            self.selected_indices = [i for i in idxs if 0 <= int(i) < len(preview)]
            self.active_index = self.selected_indices[-1] if self.selected_indices else None
            try:
                self.display_mode_combo.setCurrentIndex(self.display_mode_combo.findData("material"))
            except Exception:
                pass
            try:
                self.render_state.display_mode = "material"
            except Exception:
                pass
            self.refresh_actor_styles(render=False)
            self.update_inspector()
            self.update_gizmo(render=False)
            self.update_texture_rotation_gizmo(render=False)
            try:
                self.plotter.render()
            except Exception:
                pass
            self._update_texture_projection_report(preview_meshes=preview)
            face_txt = f" face={params.seed_face_index}" if params.seed_face_index is not None else ""
            ratio_txt = " keep_ratio" if params.preserve_aspect else " stretch"
            attach_txt = " attached" if bool(getattr(params, "attach_to_mesh", False)) else " decal"
            self.ui_log(
                f"[TEXTURE] Preview indices={idxs} texture={Path(params.texture_path).name} mode={params.projection_mode}{face_txt} "
                f"scale={params.scale:g}{ratio_txt}{attach_txt} repeat={int(params.repeat)} size={params.image_width}x{params.image_height}"
            )
        except Exception as exc:
            log_exception("generate_texture_projection_preview")
            self._update_texture_projection_report(error=str(exc))

    def apply_texture_projection_to_index(
        self,
        idx: int,
        *,
        seed_face_index: int | None = None,
        projection_origin: tuple[float, float, float] | None = None,
        projection_normal: tuple[float, float, float] | None = None,
    ) -> None:
        try:
            self.selected_indices = [int(idx)]
            self.active_index = int(idx)
            self.generate_texture_projection_preview(
                target_index=int(idx),
                seed_face_index=seed_face_index,
                projection_origin=projection_origin,
                projection_normal=projection_normal,
            )
        except Exception:
            log_exception("apply_texture_projection_to_index")

    def apply_texture_projection_from_pick(self, idx: int, point, normal, cell_id: int) -> None:
        try:
            anchor = self._texture_projection_anchor_from_pick(idx, point, normal, cell_id)
            self._texture_projection_last_anchor = anchor
            self.apply_texture_projection_to_index(
                int(idx),
                seed_face_index=int(cell_id),
                projection_origin=anchor["point"],  # type: ignore[arg-type]
                projection_normal=anchor["normal"],  # type: ignore[arg-type]
            )
        except Exception:
            log_exception("apply_texture_projection_from_pick")

    def clear_texture_projection_selected(self) -> None:
        try:
            from laserprog_studio.geometry_ops.texture_projection import clear_texture_projection

            idxs = self._texture_projection_selected_indices()
            if not idxs:
                self._update_texture_projection_report(error="Select at least one part to clear.")
                return
            base = [copy.deepcopy(m) for m in self.committed_meshes()]
            preview = clear_texture_projection(base, idxs)
            self._texture_projection_last_anchor = None
            self.set_preview_meshes(preview, "Clear projected texture preview")
            self.selected_indices = [i for i in idxs if 0 <= int(i) < len(preview)]
            self.active_index = self.selected_indices[-1] if self.selected_indices else None
            self.refresh_actor_styles(render=False)
            self.update_inspector()
            self.update_gizmo(render=False)
            try:
                self._clear_gizmo_actors()
            except Exception:
                pass
            try:
                self.plotter.render()
            except Exception:
                pass
            self._update_texture_projection_report(preview_meshes=preview)
            self.ui_log(f"[TEXTURE] Clear preview indices={idxs}")
        except Exception as exc:
            log_exception("clear_texture_projection_selected")
            self._update_texture_projection_report(error=str(exc))


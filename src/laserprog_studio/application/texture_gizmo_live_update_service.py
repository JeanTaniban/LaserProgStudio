# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from ..studio_log import log_exception
from .owner_delegating_controller import OwnerDelegatingController


class TextureGizmoLiveUpdateService(OwnerDelegatingController):
    """Migrated TEX gizmo responsibility extracted from TextureGizmoController."""

    def _texture_projection_set_mesh_projection_values(self, mesh, params, *, origin=None, repeat_override=None) -> None:
        """Keep texture projection metadata in sync without rebuilding the scene."""
        try:
            projections = list(getattr(mesh, "texture_projections", []) or [])
            if not projections:
                return
            proj = projections[0]
            for name, value in (
                ("scale", float(params.scale)),
                ("rotation_deg", float(params.rotation_deg)),
                ("offset_u", float(params.offset_u)),
                ("offset_v", float(params.offset_v)),
                ("repeat", bool(params.repeat) if repeat_override is None else bool(repeat_override)),
                ("coverage_angle_deg", float(params.coverage_angle_deg)),
                ("seed_face_index", params.seed_face_index),
                ("projection_mode", params.projection_mode),
            ):
                try:
                    setattr(proj, name, value)
                except Exception:
                    pass
            try:
                proj.placement = "mesh" if bool(getattr(params, "attach_to_mesh", False)) else "decal"
            except Exception:
                pass
            try:
                mesh.texture_projections = projections
            except Exception:
                pass
            if origin is not None:
                try:
                    setattr(mesh, "texture_decal_origin", tuple(float(v) for v in origin))
                except Exception:
                    pass
        except Exception:
            log_exception("texture_projection_set_mesh_projection_values")

    def _texture_projection_set_actor_uvs_fast(self, idx: int, mesh) -> bool:
        """Update only VTK texture coordinates for one actor.

        This avoids the old full preview rebuild during TEX drags, which caused
        the texture to disappear/reappear and made interaction feel laggy.
        """
        try:
            uvs = getattr(mesh, "uvs", None)
            if uvs is None:
                return False
            actor = getattr(self, "actors_by_index", {}).get(int(idx))
            if actor is None:
                return False
            mapper = actor.GetMapper() if hasattr(actor, "GetMapper") else None
            dataset = None
            if mapper is not None and hasattr(mapper, "GetInput"):
                dataset = mapper.GetInput()
            if dataset is None:
                dataset = getattr(self, "polydata_by_index", {}).get(int(idx))
            if dataset is None:
                return False
            n_points = int(dataset.GetNumberOfPoints()) if hasattr(dataset, "GetNumberOfPoints") else len(getattr(mesh, "vertices", []))
            if len(uvs) != n_points:
                return False
            from vtkmodules.vtkCommonCore import vtkFloatArray

            tcoords = vtkFloatArray()
            tcoords.SetName("Texture Coordinates")
            tcoords.SetNumberOfComponents(2)
            tcoords.SetNumberOfTuples(int(n_points))
            for i, (u, v) in enumerate(uvs):
                tcoords.SetTuple2(int(i), float(u), float(v))
            dataset.GetPointData().SetTCoords(tcoords)
            try:
                dataset.point_data["Texture Coordinates"] = uvs  # pyvista wrapper path
            except Exception:
                pass
            try:
                dataset.Modified()
            except Exception:
                pass
            try:
                if mapper is not None:
                    mapper.Modified()
            except Exception:
                pass
            try:
                from ..rendering.textures import actor_has_texture, apply_texture_to_actor, configure_actor_for_texture_visibility

                if actor_has_texture(actor):
                    configure_actor_for_texture_visibility(actor)
                else:
                    apply_texture_to_actor(self, actor, mesh, reason="tex_live_drag")
            except Exception:
                pass
            return True
        except Exception:
            log_exception("texture_projection_set_actor_uvs_fast")
            return False

    def _texture_projection_update_decal_live(self, idx: int, mesh, params, *, origin=None) -> bool:
        """Recompute decal UVs in place from its stored editable frame."""
        try:
            from laserprog_studio.geometry_ops.texture_projection_vector import _dot, _sub, _uv_from_plane_coords

            if origin is None:
                origin = getattr(mesh, "texture_decal_origin", None)
            if origin is None:
                return False
            origin = tuple(float(v) for v in origin)
            u_axis = tuple(float(v) for v in getattr(mesh, "texture_decal_u_axis"))
            v_axis = tuple(float(v) for v in getattr(mesh, "texture_decal_v_axis"))
            tile_w = float(getattr(mesh, "texture_decal_tile_width", 1.0) or 1.0)
            tile_h = float(getattr(mesh, "texture_decal_tile_height", 1.0) or 1.0)
            vertices = [tuple(float(x) for x in p) for p in getattr(mesh, "vertices", [])]
            uvs = []
            for p in vertices:
                rel = _sub(p, origin)
                uvs.append(
                    _uv_from_plane_coords(
                        _dot(rel, u_axis),
                        _dot(rel, v_axis),
                        tile_w=tile_w,
                        tile_h=tile_h,
                        scale=float(params.scale),
                        rotation_deg=float(params.rotation_deg),
                        offset_u=float(params.offset_u),
                        offset_v=float(params.offset_v),
                    )
                )
            mesh.uvs = uvs
            setattr(mesh, "texture_decal_origin", origin)
            self._texture_projection_set_mesh_projection_values(mesh, params, origin=origin)
            return self._texture_projection_set_actor_uvs_fast(int(idx), mesh)
        except Exception:
            log_exception("texture_projection_update_decal_live")
            return False

    def _texture_projection_update_attached_mesh_live(self, idx: int, mesh, params, *, origin=None) -> bool:
        """Recompute attached-mesh UVs in place without rebuilding actors.

        Face-anchored attached projections must keep uncovered faces on the
        saved pre-texture colour.  Reusing the generic full-mesh UV projector here
        makes every face sample the bitmap during TEX drags, which looks like the
        rest of the model becomes transparent/painted.
        """
        try:
            from laserprog_studio.geometry_ops.texture_projection_faces import _store_texture_edit_frame
            from laserprog_studio.geometry_ops.texture_projection_operations import compute_anchor_attached_coverage_uvs
            from laserprog_studio.geometry_ops.texture_projection_uv import compute_projected_uvs

            projection_origin = tuple(float(v) for v in origin) if origin is not None else params.projection_origin
            repeat_override = None
            if getattr(params, "seed_face_index", None) is not None:
                masked_uvs = compute_anchor_attached_coverage_uvs(
                    mesh,
                    params,
                    projection_origin=projection_origin,
                    scale=float(params.scale),
                    rotation_deg=float(params.rotation_deg),
                    offset_u=float(params.offset_u),
                    offset_v=float(params.offset_v),
                    stretch_u=float(getattr(params, "stretch_u", 1.0)),
                    stretch_v=float(getattr(params, "stretch_v", 1.0)),
                )
                if masked_uvs is not None:
                    mesh.uvs = masked_uvs
                    # A repeated texture cannot have a stable neutral colour for
                    # uncovered faces, so match the apply path and force the
                    # projection texture to the saved-colour padded mode.
                    repeat_override = False
                else:
                    mesh.uvs = compute_projected_uvs(
                        mesh,
                        projection_mode=params.projection_mode,
                        scale=float(params.scale),
                        rotation_deg=float(params.rotation_deg),
                        offset_u=float(params.offset_u),
                        offset_v=float(params.offset_v),
                        preserve_aspect=bool(params.preserve_aspect),
                        image_width=params.image_width,
                        image_height=params.image_height,
                        seed_face_index=params.seed_face_index,
                        projection_origin=projection_origin,
                        projection_normal=params.projection_normal,
                        coverage_angle_deg=float(params.coverage_angle_deg),
                    )
            else:
                mesh.uvs = compute_projected_uvs(
                    mesh,
                    projection_mode=params.projection_mode,
                    scale=float(params.scale),
                    rotation_deg=float(params.rotation_deg),
                    offset_u=float(params.offset_u),
                    offset_v=float(params.offset_v),
                    preserve_aspect=bool(params.preserve_aspect),
                    image_width=params.image_width,
                    image_height=params.image_height,
                    seed_face_index=params.seed_face_index,
                    projection_origin=projection_origin,
                    projection_normal=params.projection_normal,
                    coverage_angle_deg=float(params.coverage_angle_deg),
                )
            self._texture_projection_set_mesh_projection_values(mesh, params, origin=projection_origin, repeat_override=repeat_override)
            try:
                _store_texture_edit_frame(mesh, params)
                if projection_origin is not None:
                    setattr(mesh, "texture_decal_origin", tuple(float(v) for v in projection_origin))
            except Exception:
                pass
            return self._texture_projection_set_actor_uvs_fast(int(idx), mesh)
        except Exception:
            log_exception("texture_projection_update_attached_mesh_live")
            return False

    def _texture_projection_live_update_current_target(self, *, origin=None, source: str = "drag", refresh_gizmo: bool = False) -> bool:
        """Live TEX update used while dragging rotation/scale/move handles.

        The previous path called ``generate_texture_projection_preview`` for every
        mouse event, which deep-copied meshes, rebuilt the whole PyVista scene and
        recreated actors.  This path mutates only the active preview mesh UVs and
        its existing actor's TCoords.  A full rebuild is still available as a
        fallback if the fast path cannot resolve a target.
        """
        try:
            target_idx = getattr(self, "_texture_rotation_gizmo_target_index", None)
            target = self._texture_rotation_target() if target_idx is None else None
            if target_idx is None and target is not None:
                target_idx = int(target[0])
            if target_idx is None:
                return False
            meshes = self.current_meshes()
            if not (0 <= int(target_idx) < len(meshes)):
                return False
            mesh = meshes[int(target_idx)]
            from laserprog_studio.geometry_ops.texture_projection_decal import _is_texture_decal

            seed_face = None
            projection_normal = None
            source_index = getattr(self, "_texture_move_gizmo_source_index", None)
            try:
                projections = list(getattr(mesh, "texture_projections", []) or [])
                if projections and getattr(projections[0], "seed_face_index", None) is not None:
                    seed_face = int(getattr(projections[0], "seed_face_index"))
            except Exception:
                pass
            try:
                if seed_face is None and getattr(mesh, "texture_decal_source_face", None) is not None:
                    seed_face = int(getattr(mesh, "texture_decal_source_face"))
            except Exception:
                pass
            try:
                if seed_face is None and getattr(mesh, "texture_attached_source_face", None) is not None:
                    seed_face = int(getattr(mesh, "texture_attached_source_face"))
            except Exception:
                pass
            try:
                projection_normal = tuple(float(v) for v in getattr(mesh, "texture_decal_normal"))
            except Exception:
                projection_normal = getattr(self, "_texture_rotation_gizmo_normal", None)
            if origin is None:
                try:
                    origin = tuple(float(v) for v in getattr(mesh, "texture_decal_origin"))
                except Exception:
                    origin = getattr(self, "_texture_move_gizmo_current_origin", None)
            if source_index is None:
                source_index = self._texture_move_source_index_for_target(int(target_idx), mesh)
            params = self._texture_projection_params_from_ui(
                target_index=int(source_index) if source_index is not None else int(target_idx),
                seed_face_index=seed_face,
                projection_origin=tuple(float(v) for v in origin) if origin is not None else None,
                projection_normal=tuple(float(v) for v in projection_normal) if projection_normal is not None else None,
            )
            if _is_texture_decal(mesh):
                ok = self._texture_projection_update_decal_live(int(target_idx), mesh, params, origin=origin)
            else:
                ok = self._texture_projection_update_attached_mesh_live(int(target_idx), mesh, params, origin=origin)
            if not ok:
                return False
            if origin is not None:
                origin_tuple = tuple(float(v) for v in origin)
                try:
                    anchor = getattr(self, "_texture_projection_last_anchor", None) or {}
                    anchor["point"] = origin_tuple
                    if source_index is not None:
                        anchor["index"] = int(source_index)
                    if seed_face is not None:
                        anchor["cell_id"] = int(seed_face)
                    if projection_normal is not None:
                        anchor["normal"] = tuple(float(v) for v in projection_normal)
                    self._texture_projection_last_anchor = anchor
                except Exception:
                    pass
                self._texture_rotation_gizmo_center = origin_tuple
                self._texture_move_gizmo_current_origin = origin_tuple
                self._texture_rotation_gizmo_center_qt = self._texture_rotation_project_qt(origin_tuple)
            if refresh_gizmo:
                import time

                now = time.monotonic()
                last = float(getattr(self, "_texture_live_gizmo_refresh_time", 0.0) or 0.0)
                if now - last >= 0.035:
                    self._texture_live_gizmo_refresh_time = now
                    self.update_texture_rotation_gizmo(render=False)
            try:
                self.plotter.render()
            except Exception:
                pass
            if bool(getattr(self, "_diagnostic_verbose", False)):
                self.ui_log(f"[TEXTURE_GIZMO] live update ok source={source} target={target_idx} origin={origin}")
            return True
        except Exception:
            log_exception("texture_projection_live_update_current_target")
            return False


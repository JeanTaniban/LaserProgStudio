# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from ..studio_log import log_exception
from .owner_delegating_controller import OwnerDelegatingController


class TextureGizmoTargetService(OwnerDelegatingController):
    """Migrated TEX gizmo responsibility extracted from TextureGizmoController."""

    def _texture_rotation_target(self):
        """Return the active TEX editable target.

        Earlier versions only looked for separate decal meshes.  When
        ``Attach to mesh`` is enabled there is no decal actor anymore, but the
        texture still has a face anchor, UVs and projection metadata.  The TEX
        gizmo must therefore target either:

        * the selected/active texture decal, or
        * the selected/active real mesh carrying an attached texture projection.
        """
        try:
            from laserprog_studio.geometry_ops.texture_projection_decal import _is_texture_decal

            meshes = self.current_meshes()
            if not meshes:
                return None
            selected = [int(i) for i in list(getattr(self, "selected_indices", []) or []) if 0 <= int(i) < len(meshes)]
            active = getattr(self, "active_index", None)
            preferred_sources = set()
            for idx in selected:
                preferred_sources.add(str(getattr(meshes[int(idx)], "name", "") or ""))
            candidates = []
            for idx, mesh in enumerate(meshes):
                if _is_texture_decal(mesh):
                    src = str(getattr(mesh, "texture_decal_for", "") or "")
                    rank = 0 if src in preferred_sources else 2
                    if int(idx) in selected:
                        rank = -1
                    candidates.append((rank, idx, mesh, "decal"))
            for idx, mesh in enumerate(meshes):
                if _is_texture_decal(mesh):
                    continue
                projections = list(getattr(mesh, "texture_projections", []) or [])
                has_attached_projection = any(str(getattr(p, "placement", "mesh") or "mesh") == "mesh" for p in projections)
                if not has_attached_projection and getattr(mesh, "uvs", None) is None:
                    continue
                rank = 1
                if int(idx) in selected:
                    rank = 0
                if active is not None and int(idx) == int(active):
                    rank -= 1
                candidates.append((rank, idx, mesh, "mesh"))
            if not candidates:
                return None
            _rank, idx, mesh, _kind = sorted(candidates, key=lambda item: (item[0], -item[1]))[0]
            vertices = [tuple(float(v) for v in p) for p in getattr(mesh, "vertices", [])]
            if not vertices:
                return None
            try:
                origin = tuple(float(v) for v in getattr(mesh, "texture_decal_origin"))
            except Exception:
                origin = None
            try:
                normal = tuple(float(v) for v in getattr(mesh, "texture_decal_normal"))
            except Exception:
                normal = None
            if origin is None or normal is None:
                anchor = getattr(self, "_texture_projection_last_anchor", None)
                try:
                    if anchor is not None and int(anchor.get("index", -999)) == int(idx):
                        if origin is None and anchor.get("point") is not None:
                            origin = tuple(float(v) for v in anchor.get("point"))
                        if normal is None and anchor.get("normal") is not None:
                            normal = tuple(float(v) for v in anchor.get("normal"))
                except Exception:
                    pass
            if origin is None:
                xs = [p[0] for p in vertices]
                ys = [p[1] for p in vertices]
                zs = [p[2] for p in vertices]
                origin = ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5)
            if normal is None:
                normal = (0.0, 0.0, 1.0)
            ln = math.sqrt(sum(float(v) * float(v) for v in normal)) or 1.0
            normal = (normal[0] / ln, normal[1] / ln, normal[2] / ln)
            return int(idx), mesh, origin, normal
        except Exception:
            log_exception("texture_rotation_target")
            return None

    def _texture_rotation_ring_basis(self, normal):
        """Stable in-plane basis for the single TEX rotation ring."""
        import numpy as np

        n = np.asarray(normal, dtype=float)
        norm = float(np.linalg.norm(n))
        if norm <= 1e-12:
            n = np.asarray((0.0, 0.0, 1.0), dtype=float)
        else:
            n = n / norm
        ref = np.asarray((1.0, 0.0, 0.0), dtype=float)
        if abs(float(np.dot(ref, n))) > 0.85:
            ref = np.asarray((0.0, 1.0, 0.0), dtype=float)
        u = np.cross(n, ref)
        u = u / (float(np.linalg.norm(u)) or 1.0)
        v = np.cross(n, u)
        v = v / (float(np.linalg.norm(v)) or 1.0)
        return n, u, v

    def _texture_rotation_world_radius_for_screen(self, center, radius_px: float = 72.0) -> float:
        """Convert a desired on-screen ring radius to a world-space radius.

        The previous TEX gizmo reused the transform-gizmo length and could grow or
        shrink whenever the preview rebuilt.  TEX now keeps a nearly constant
        screen size, which makes it much easier to grab.
        """
        try:
            visible_height = float(self._camera_visible_height_at(tuple(float(v) for v in center)))
            viewport_h = max(float(self.plotter.height()), 1.0)
            return max(visible_height * float(radius_px) / viewport_h, self._gizmo_visible_epsilon())
        except Exception:
            return max(float(radius_px) * 0.01, 0.5)

    def _texture_rotation_project_qt(self, point) -> tuple[float, float] | None:
        try:
            sx, sy_vtk, _sz = self._world_to_display(tuple(float(v) for v in point))
            return (float(sx), float(self.plotter.height()) - float(sy_vtk))
        except Exception:
            return None

    @staticmethod
    def _texture_rotation_point_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
        abx = float(bx) - float(ax)
        aby = float(by) - float(ay)
        apx = float(px) - float(ax)
        apy = float(py) - float(ay)
        denom = abx * abx + aby * aby
        if denom <= 1e-12:
            return math.hypot(apx, apy)
        t = max(0.0, min(1.0, (apx * abx + apy * aby) / denom))
        cx = float(ax) + t * abx
        cy = float(ay) + t * aby
        return math.hypot(float(px) - cx, float(py) - cy)

    def _pick_texture_rotation_gizmo_from_qt_pos(self, qx: float, qy: float):
        """Forgiving screen-space picker for the TEX ring and center handle.

        VTK prop picking is too strict for a thin torus, especially because the
        TEX tool also has normal mesh picking active.  This picker projects the
        rotation circle to screen space and accepts clicks within a practical
        pixel tolerance around the ring.  The center sphere is picked first and
        acts as a 2D translation handle constrained to the decal face.
        """
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                return None
            if not self.has_preview():
                return None
            target = self._texture_rotation_target()
            if target is None:
                return None
            _idx, _mesh, center, normal = target
            center_qt = self._texture_rotation_project_qt(center)
            if center_qt is not None:
                center_dist = math.hypot(float(qx) - float(center_qt[0]), float(qy) - float(center_qt[1]))
                center_threshold = float(getattr(self, "_texture_move_gizmo_pick_radius_px", 22.0) or 22.0)
                if center_dist <= max(12.0, center_threshold):
                    try:
                        self.ui_log(
                            f"[TEXTURE_GIZMO] center-pick HIT dist={center_dist:.1f}px "
                            f"threshold={center_threshold:.1f}px"
                        )
                    except Exception:
                        pass
                    return ("gizmo", "texmove")
            radius = float(getattr(self, "_texture_rotation_gizmo_radius_world", 0.0) or 0.0)
            if radius <= 1e-12:
                radius = self._texture_rotation_world_radius_for_screen(center)
            _n, u, v = self._texture_rotation_ring_basis(normal)
            import numpy as np

            c = np.asarray(center, dtype=float)
            samples = 80
            pts_qt: list[tuple[float, float]] = []
            for i in range(samples):
                t = 2.0 * math.pi * float(i) / float(samples)
                p = c + math.cos(t) * radius * u + math.sin(t) * radius * v
                pq = self._texture_rotation_project_qt(p)
                if pq is not None:
                    pts_qt.append(pq)
            if len(pts_qt) < 8:
                return None
            min_dist = 1e18
            for a, b in zip(pts_qt, pts_qt[1:] + pts_qt[:1]):
                min_dist = min(min_dist, self._texture_rotation_point_segment_distance(float(qx), float(qy), a[0], a[1], b[0], b[1]))
            threshold = float(getattr(self, "_texture_rotation_gizmo_pick_radius_px", 18.0) or 18.0)
            if min_dist <= max(12.0, threshold):
                try:
                    self.ui_log(f"[TEXTURE_GIZMO] screen-pick HIT dist={min_dist:.1f}px threshold={threshold:.1f}px")
                except Exception:
                    pass
                return ("gizmo", "texrot")
            try:
                self.ui_log(f"[TEXTURE_GIZMO] screen-pick miss dist={min_dist:.1f}px threshold={threshold:.1f}px")
            except Exception:
                pass
            return None
        except Exception:
            log_exception("pick_texture_rotation_gizmo_from_qt_pos")
            return None

    def _texture_move_source_index_for_target(self, target_idx: int, decal_mesh) -> int | None:
        """Resolve the committed source mesh index for the active texture decal."""
        try:
            anchor = getattr(self, "_texture_projection_last_anchor", None)
            if anchor is not None:
                try:
                    idx = int(anchor.get("index"))
                    committed = self.committed_meshes()
                    if 0 <= idx < len(committed):
                        return idx
                except Exception:
                    pass
            source_name = str(getattr(decal_mesh, "texture_decal_for", "") or "")
            if source_name:
                for idx, mesh in enumerate(self.committed_meshes()):
                    if str(getattr(mesh, "name", "") or "") == source_name:
                        return int(idx)
            selected = [int(i) for i in list(getattr(self, "selected_indices", []) or [])]
            committed = self.committed_meshes()
            for idx in selected:
                if 0 <= idx < len(committed):
                    return int(idx)
        except Exception:
            log_exception("texture_move_source_index_for_target")
        return None

    @staticmethod
    def _texture_vec3_add(a, b):
        return (float(a[0]) + float(b[0]), float(a[1]) + float(b[1]), float(a[2]) + float(b[2]))

    @staticmethod
    def _texture_vec3_scale(v, s: float):
        return (float(v[0]) * float(s), float(v[1]) * float(s), float(v[2]) * float(s))

    def _texture_move_basis_from_target(self, mesh, normal):
        """Return the in-plane U/V axes used by the decal, with safe fallbacks."""
        try:
            u_axis = tuple(float(v) for v in getattr(mesh, "texture_decal_u_axis"))
            v_axis = tuple(float(v) for v in getattr(mesh, "texture_decal_v_axis"))
            return u_axis, v_axis
        except Exception:
            try:
                _n, u, v = self._texture_rotation_ring_basis(normal)
                return (float(u[0]), float(u[1]), float(u[2])), (float(v[0]), float(v[1]), float(v[2]))
            except Exception:
                return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)

    def _texture_move_screen_matrix(self, center, u_axis, v_axis):
        """Matrix mapping in-plane world movement to Qt pixel movement."""
        try:
            import numpy as np

            c = tuple(float(x) for x in center)
            radius = float(getattr(self, "_texture_rotation_gizmo_radius_world", 0.0) or 0.0)
            step = max(radius * 0.35, self._texture_rotation_world_radius_for_screen(c, radius_px=28.0), 1e-6)
            p0 = self._texture_rotation_project_qt(c)
            pu = self._texture_rotation_project_qt(
                (c[0] + float(u_axis[0]) * step, c[1] + float(u_axis[1]) * step, c[2] + float(u_axis[2]) * step)
            )
            pv = self._texture_rotation_project_qt(
                (c[0] + float(v_axis[0]) * step, c[1] + float(v_axis[1]) * step, c[2] + float(v_axis[2]) * step)
            )
            if p0 is None or pu is None or pv is None:
                return None
            su = ((float(pu[0]) - float(p0[0])) / step, (float(pu[1]) - float(p0[1])) / step)
            sv = ((float(pv[0]) - float(p0[0])) / step, (float(pv[1]) - float(p0[1])) / step)
            mat = np.asarray([[su[0], sv[0]], [su[1], sv[1]]], dtype=float)
            det = float(np.linalg.det(mat))
            if not np.isfinite(det) or abs(det) < 1e-9:
                return None
            return mat
        except Exception:
            log_exception("texture_move_screen_matrix")
            return None

    def _texture_move_delta_from_screen(self, dx: float, dy: float) -> tuple[float, float] | None:
        try:
            import numpy as np

            mat = getattr(self, "_texture_move_gizmo_screen_matrix", None)
            if mat is None:
                return None
            vec = np.asarray([float(dx), float(dy)], dtype=float)
            sol = np.linalg.solve(mat, vec)
            if not np.all(np.isfinite(sol)):
                return None
            return (float(sol[0]), float(sol[1]))
        except Exception:
            return None

    def _texture_move_apply_origin(self, origin, *, source: str = "move") -> None:
        """Apply a new decal center by updating the remembered face anchor."""
        try:
            origin = (float(origin[0]), float(origin[1]), float(origin[2]))
            anchor = getattr(self, "_texture_projection_last_anchor", None)
            source_index = getattr(self, "_texture_move_gizmo_source_index", None)
            if anchor is None:
                anchor = {}
            anchor["point"] = origin
            if source_index is not None:
                anchor["index"] = int(source_index)
            normal = getattr(self, "_texture_rotation_gizmo_normal", None)
            if normal is not None:
                anchor["normal"] = tuple(float(v) for v in normal)
            self._texture_projection_last_anchor = anchor
            # Fast live update: mutate UVs/TCoords only. If anything is missing,
            # fall back to the old preview rebuild so the tool remains safe.
            ok = self._texture_projection_live_update_current_target(origin=origin, source=source, refresh_gizmo=False)
            if not ok:
                # Never rebuild the whole preview inside a mouse-drag event.  A
                # full generate_texture_projection_preview() here removes and
                # recreates actors/gizmos, which is exactly the flicker reported
                # by the user.  Keep the drag responsive and perform one safe
                # rebuild at drag end only if the fast path failed.
                self._texture_live_update_failed = True
                if bool(getattr(self, "_diagnostic_verbose", False)):
                    self.ui_log(f"[TEXTURE_GIZMO_MOVE] live update failed during drag origin={origin}")
                return
            # Keep drag state centered on the updated texture frame.
            self._texture_rotation_gizmo_center = origin
            self._texture_move_gizmo_current_origin = origin
            self._texture_rotation_gizmo_center_qt = self._texture_rotation_project_qt(origin)
            u_axis = getattr(self, "_texture_move_gizmo_u_axis", None)
            v_axis = getattr(self, "_texture_move_gizmo_v_axis", None)
            if u_axis is not None and v_axis is not None:
                self._texture_move_gizmo_screen_matrix = self._texture_move_screen_matrix(origin, u_axis, v_axis)
            if bool(getattr(self, "_diagnostic_verbose", False)):
                self.ui_log(
                    f"[TEXTURE_GIZMO_MOVE] apply source={source} target={source_index} fast={ok} "
                    f"origin=({origin[0]:.4f},{origin[1]:.4f},{origin[2]:.4f})"
                )
        except Exception:
            log_exception("texture_move_apply_origin")


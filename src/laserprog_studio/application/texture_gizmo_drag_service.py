# -*- coding: utf-8 -*-
from __future__ import annotations

import math

from ..studio_log import log_exception
from .owner_delegating_controller import OwnerDelegatingController


class TextureGizmoDragService(OwnerDelegatingController):
    """Migrated TEX gizmo responsibility extracted from TextureGizmoController."""

    def _texture_rotation_screen_angle(self, qx: float, qy: float, center_qt=None) -> float | None:
        """Angle of the pointer around the projected TEX gizmo centre.

        Using screen-space angles is more robust than ray/plane intersection for
        the TEX decal ring because the ring is already a screen-stable control.
        """
        try:
            if center_qt is None:
                center_qt = getattr(self, "_texture_rotation_gizmo_center_qt", None)
            if center_qt is None:
                return None
            cx, cy = float(center_qt[0]), float(center_qt[1])
            dx = float(qx) - cx
            dy = float(qy) - cy
            if abs(dx) + abs(dy) < 1e-6:
                return None
            return math.atan2(dy, dx)
        except Exception:
            return None

    def _start_texture_rotation_gizmo_drag(self, qx: float, qy: float, *, kind: str = "texrot") -> None:
        try:
            target = self._texture_rotation_target()
            if target is None:
                return
            idx, mesh, center, normal = target
            kind = "texmove" if str(kind).lower() == "texmove" else "texrot"
            self._texture_rotation_gizmo_drag_active = True
            self._texture_rotation_gizmo_drag_kind = kind
            self._texture_rotation_gizmo_target_index = int(idx)
            self._texture_rotation_gizmo_start_qpos = (float(qx), float(qy))
            self._texture_rotation_gizmo_update_count = 0
            self._texture_rotation_gizmo_event_seq = 0
            self._texture_live_update_failed = False
            self._texture_rotation_gizmo_center = center
            self._texture_rotation_gizmo_normal = normal
            u_axis, v_axis = self._texture_move_basis_from_target(mesh, normal)
            self._texture_move_gizmo_u_axis = u_axis
            self._texture_move_gizmo_v_axis = v_axis
            self._texture_move_gizmo_screen_matrix = self._texture_move_screen_matrix(center, u_axis, v_axis)
            self._texture_move_gizmo_start_origin = tuple(float(v) for v in center)
            self._texture_move_gizmo_current_origin = tuple(float(v) for v in center)
            self._texture_move_gizmo_source_index = self._texture_move_source_index_for_target(int(idx), mesh)
            self._texture_rotation_gizmo_start_value = float(self.texture_projection_rotation.value()) if hasattr(self, "texture_projection_rotation") else 0.0
            self._texture_rotation_gizmo_current_value = float(self._texture_rotation_gizmo_start_value)
            self._texture_rotation_gizmo_start_scale = float(self.texture_projection_scale.value()) if hasattr(self, "texture_projection_scale") else 1.0
            self._texture_rotation_gizmo_current_scale = float(self._texture_rotation_gizmo_start_scale)
            self._texture_rotation_gizmo_last_qpos = (float(qx), float(qy))
            try:
                self._texture_rotation_gizmo_center_qt = self._texture_rotation_project_qt(center)
            except Exception:
                self._texture_rotation_gizmo_center_qt = None
            self._texture_rotation_gizmo_start_screen_angle = self._texture_rotation_screen_angle(qx, qy, getattr(self, "_texture_rotation_gizmo_center_qt", None))
            try:
                self._texture_rotation_gizmo_start_vector = self._rotation_vector_from_qt(qx, qy, center, normal)
            except Exception:
                self._texture_rotation_gizmo_start_vector = None
            self._install_texture_rotation_global_event_filter()
            self._install_texture_rotation_vtk_observers()
            self._texture_rotation_gizmo_last_poll_qpos = (float(qx), float(qy))
            self._texture_rotation_gizmo_poll_count = 0
            self._start_texture_rotation_poll_timer()
            self.ui_log(
                f"[TEXTURE_GIZMO] start kind={kind} value={self._texture_rotation_gizmo_start_value:.2f} "
                f"scale={self._texture_rotation_gizmo_start_scale:.4f} "
                f"start_q=({float(qx):.1f},{float(qy):.1f}) center_qt={getattr(self, '_texture_rotation_gizmo_center_qt', None)} "
                f"start_angle={self._texture_rotation_gizmo_start_screen_angle} target={idx} "
                f"source={getattr(self, '_texture_move_gizmo_source_index', None)} "
                f"origin={self._texture_move_gizmo_start_origin}"
            )
        except Exception:
            log_exception("start_texture_rotation_gizmo_drag")

    def _update_texture_rotation_gizmo_drag(self, qx: float, qy: float, *, source: str = "direct") -> None:
        """Apply TEX polar gizmo movement: tangent = rotation, radius = scale.

        This behaves like a real transform handle in screen space.  For each mouse
        sample, the previous pointer vector around the decal centre is compared to
        the current vector:

        * angular delta updates the texture rotation;
        * radial ratio updates the texture scale/size.

        Moving away from the centre grows the decal; moving toward the centre
        shrinks it.  Both operations are accumulated incrementally, which keeps the
        control stable even when events arrive through QWindow/global filters.
        """
        try:
            if getattr(self, "_texture_rotation_gizmo_drag_kind", "texrot") == "texmove":
                self._update_texture_move_gizmo_drag(qx, qy, source=source)
                return
            if not bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                self.ui_log(f"[TEXTURE_GIZMO] polar ignored inactive source={source} q=({float(qx):.1f},{float(qy):.1f})")
                return

            qx = float(qx)
            qy = float(qy)
            center_qt = getattr(self, "_texture_rotation_gizmo_center_qt", None)
            last_qpos = getattr(self, "_texture_rotation_gizmo_last_qpos", None)
            if last_qpos is None:
                last_qpos = getattr(self, "_texture_rotation_gizmo_start_qpos", None)
            if last_qpos is None:
                self._texture_rotation_gizmo_last_qpos = (qx, qy)
                self.ui_log(f"[TEXTURE_GIZMO] polar seed source={source} q=({qx:.1f},{qy:.1f}) no-last")
                return

            lx, ly = float(last_qpos[0]), float(last_qpos[1])
            dx = qx - lx
            dy = qy - ly
            move_px = math.hypot(dx, dy)
            if move_px < float(getattr(self, "_texture_drag_min_px", 1.0)):
                if bool(getattr(self, "_diagnostic_verbose", False)):
                    self.ui_log(
                        f"[TEXTURE_GIZMO] polar ignored tiny source={source} "
                        f"q=({qx:.1f},{qy:.1f}) last=({lx:.1f},{ly:.1f}) move={move_px:.3f}px"
                    )
                return

            delta_deg = None
            scale_ratio = 1.0
            scale_method = "radial-none"
            method = ""
            r0 = r1 = None
            if center_qt is not None:
                try:
                    cx, cy = float(center_qt[0]), float(center_qt[1])
                    v0x = lx - cx
                    v0y = ly - cy
                    v1x = qx - cx
                    v1y = qy - cy
                    r0 = math.hypot(v0x, v0y)
                    r1 = math.hypot(v1x, v1y)
                    # The cursor must be far enough from the center to define an angle.
                    # When the user drags through the center, use a linear fallback.
                    if r0 >= 8.0 and r1 >= 8.0:
                        a0 = math.atan2(v0y, v0x)
                        a1 = math.atan2(v1y, v1x)
                        da = a1 - a0
                        while da > math.pi:
                            da -= 2.0 * math.pi
                        while da < -math.pi:
                            da += 2.0 * math.pi
                        # Qt Y points downward. Invert the screen-space delta so the
                        # TEX decal follows the visual rotation direction of the
                        # transform rotation gizmos.
                        delta_deg = -math.degrees(da)
                        method = "incremental-angle-inverted"
                    if r0 is not None and r1 is not None and r0 >= 8.0 and r1 >= 1.0:
                        # Radial polar component: larger screen radius means larger
                        # texture scale.  Clamp per-sample to avoid violent jumps if
                        # the cursor crosses the centre or the window focus jumps.
                        raw_ratio = float(r1) / max(float(r0), 1e-6)
                        scale_ratio = max(0.70, min(1.45, raw_ratio))
                        scale_method = "radial-ratio"
                except Exception:
                    delta_deg = None
                    scale_ratio = 1.0
                    scale_method = "radial-error"

            if delta_deg is None:
                # Fallback close to the center: use tangential screen movement.
                # This is intentionally simple and stable: horizontal movement rotates,
                # vertical movement contributes in the opposite direction.
                delta_deg = -(dx - dy) * 0.35
                method = "linear-fallback-inverted"

            if not math.isfinite(float(delta_deg)) or not math.isfinite(float(scale_ratio)):
                self.ui_log(
                    f"[TEXTURE_GIZMO] polar skipped nonfinite source={source} "
                    f"q=({qx:.1f},{qy:.1f}) last=({lx:.1f},{ly:.1f}) delta={delta_deg} ratio={scale_ratio}"
                )
                self._texture_rotation_gizmo_last_qpos = (qx, qy)
                return

            current_value = getattr(self, "_texture_rotation_gizmo_current_value", None)
            if current_value is None:
                current_value = float(getattr(self, "_texture_rotation_gizmo_start_value", 0.0))
            current_value = float(current_value)
            target_value = current_value + float(delta_deg)
            while target_value > 360.0:
                target_value -= 720.0
            while target_value < -360.0:
                target_value += 720.0

            current_scale = getattr(self, "_texture_rotation_gizmo_current_scale", None)
            if current_scale is None:
                current_scale = float(getattr(self, "_texture_rotation_gizmo_start_scale", 1.0))
            current_scale = max(float(current_scale), 1e-6)
            target_scale = current_scale * float(scale_ratio)
            if hasattr(self, "texture_projection_scale"):
                try:
                    target_scale = max(float(self.texture_projection_scale.minimum()), min(float(self.texture_projection_scale.maximum()), target_scale))
                except Exception:
                    target_scale = max(0.001, min(100000.0, target_scale))
            else:
                target_scale = max(0.001, min(100000.0, target_scale))

            scale_changed = abs(float(target_scale) - float(current_scale)) > max(1e-6, abs(float(current_scale)) * 1e-5)
            rotation_changed = abs(float(delta_deg)) > 1e-4
            if not (scale_changed or rotation_changed):
                self._texture_rotation_gizmo_last_qpos = (qx, qy)
                if bool(getattr(self, "_diagnostic_verbose", False)):
                    self.ui_log(
                        f"[TEXTURE_GIZMO] polar skipped no-change source={source} "
                        f"delta={delta_deg:.6f} ratio={scale_ratio:.6f} scale={current_scale:.6f}"
                    )
                return

            self._texture_rotation_gizmo_last_qpos = (qx, qy)
            self._texture_rotation_gizmo_current_value = float(target_value)
            self._texture_rotation_gizmo_current_scale = float(target_scale)
            self._texture_rotation_gizmo_last_applied = float(target_value)
            self._texture_rotation_gizmo_last_scale_applied = float(target_scale)
            self._texture_rotation_gizmo_update_count = int(getattr(self, "_texture_rotation_gizmo_update_count", 0) or 0) + 1

            if hasattr(self, "texture_projection_rotation"):
                self.texture_projection_rotation.blockSignals(True)
                self.texture_projection_rotation.setValue(float(target_value))
                self.texture_projection_rotation.blockSignals(False)
            if hasattr(self, "texture_projection_scale"):
                self.texture_projection_scale.blockSignals(True)
                self.texture_projection_scale.setValue(float(target_scale))
                self.texture_projection_scale.blockSignals(False)

            if bool(getattr(self, "_diagnostic_verbose", False)):
                self.ui_log(
                    f"[TEXTURE_GIZMO] polar update#{self._texture_rotation_gizmo_update_count} source={source} "
                    f"rot_method={method} scale_method={scale_method} q=({qx:.1f},{qy:.1f}) last=({lx:.1f},{ly:.1f}) "
                    f"dx={dx:.2f} dy={dy:.2f} move={move_px:.2f}px r0={r0} r1={r1} "
                    f"delta={delta_deg:.3f} rotation={target_value:.3f} ratio={scale_ratio:.5f} "
                    f"scale={current_scale:.5f}->{target_scale:.5f} center_qt={center_qt}"
                )

            # Live-update only UVs/texture coordinates. Full scene rebuilds during
            # mouse drag caused visible texture flashes and heavy lag. Never call
            # generate_texture_projection_preview() from here: it rebuilds the
            # whole scene and makes the texture/gizmo blink on every event.
            if not self._texture_projection_live_update_current_target(source=source, refresh_gizmo=False):
                self._texture_live_update_failed = True
                if bool(getattr(self, "_diagnostic_verbose", False)):
                    self.ui_log(f"[TEXTURE_GIZMO] live update failed during polar drag source={source}")
        except Exception:
            log_exception("update_texture_rotation_gizmo_drag")

    def _update_texture_move_gizmo_drag(self, qx: float, qy: float, *, source: str = "direct") -> None:
        """Translate the TEX decal center inside the clicked face plane.

        The center sphere behaves like a 2D transform handle.  Mouse movement is
        converted into movement along the decal's in-plane U/V axes by solving the
        projected screen-space axis matrix.  The remembered TEX anchor is then
        moved and the preview decal is regenerated immediately.
        """
        try:
            if not bool(getattr(self, "_texture_rotation_gizmo_drag_active", False)):
                self.ui_log(f"[TEXTURE_GIZMO_MOVE] ignored inactive source={source} q=({float(qx):.1f},{float(qy):.1f})")
                return
            qx = float(qx)
            qy = float(qy)
            last_qpos = getattr(self, "_texture_rotation_gizmo_last_qpos", None)
            if last_qpos is None:
                last_qpos = getattr(self, "_texture_rotation_gizmo_start_qpos", None)
            if last_qpos is None:
                self._texture_rotation_gizmo_last_qpos = (qx, qy)
                self.ui_log(f"[TEXTURE_GIZMO_MOVE] seed source={source} q=({qx:.1f},{qy:.1f}) no-last")
                return
            lx, ly = float(last_qpos[0]), float(last_qpos[1])
            dx = qx - lx
            dy = qy - ly
            move_px = math.hypot(dx, dy)
            if move_px < float(getattr(self, "_texture_drag_min_px", 1.0)):
                if bool(getattr(self, "_diagnostic_verbose", False)):
                    self.ui_log(
                        f"[TEXTURE_GIZMO_MOVE] ignored tiny source={source} "
                        f"q=({qx:.1f},{qy:.1f}) last=({lx:.1f},{ly:.1f}) move={move_px:.3f}px"
                    )
                return

            u_axis = getattr(self, "_texture_move_gizmo_u_axis", None)
            v_axis = getattr(self, "_texture_move_gizmo_v_axis", None)
            current_origin = getattr(self, "_texture_move_gizmo_current_origin", None)
            if u_axis is None or v_axis is None or current_origin is None:
                self.ui_log(
                    f"[TEXTURE_GIZMO_MOVE] skipped missing-state source={source} "
                    f"u={u_axis is not None} v={v_axis is not None} origin={current_origin}"
                )
                self._texture_rotation_gizmo_last_qpos = (qx, qy)
                return

            uv_delta = self._texture_move_delta_from_screen(dx, dy)
            method = "screen-matrix"
            if uv_delta is None:
                # Fallback: use camera basis projected into the decal plane.  This
                # is less exact than the matrix solve but still provides a useful
                # movement instead of silently doing nothing.
                try:
                    import numpy as np

                    normal = getattr(self, "_texture_rotation_gizmo_normal", (0.0, 0.0, 1.0))
                    n = np.asarray(normal, dtype=float)
                    n = n / (float(np.linalg.norm(n)) or 1.0)
                    right, up_screen, _forward = self._camera_basis()
                    right = right - n * float(np.dot(right, n))
                    up_screen = up_screen - n * float(np.dot(up_screen, n))
                    if float(np.linalg.norm(right)) > 1e-9:
                        right = right / float(np.linalg.norm(right))
                    if float(np.linalg.norm(up_screen)) > 1e-9:
                        up_screen = up_screen / float(np.linalg.norm(up_screen))
                    world_per_px = self._texture_rotation_world_radius_for_screen(current_origin, radius_px=1.0)
                    delta_vec_np = (right * float(dx) + up_screen * float(dy)) * float(world_per_px)
                    u = np.asarray(u_axis, dtype=float)
                    v = np.asarray(v_axis, dtype=float)
                    uv_delta = (float(np.dot(delta_vec_np, u)), float(np.dot(delta_vec_np, v)))
                    method = "camera-plane-fallback"
                except Exception:
                    uv_delta = None
            if uv_delta is None:
                self.ui_log(
                    f"[TEXTURE_GIZMO_MOVE] skipped no-delta source={source} "
                    f"dx={dx:.2f} dy={dy:.2f} matrix={getattr(self, '_texture_move_gizmo_screen_matrix', None)}"
                )
                self._texture_rotation_gizmo_last_qpos = (qx, qy)
                return

            du, dv = float(uv_delta[0]), float(uv_delta[1])
            if not (math.isfinite(du) and math.isfinite(dv)):
                self.ui_log(f"[TEXTURE_GIZMO_MOVE] skipped nonfinite source={source} du={du} dv={dv}")
                self._texture_rotation_gizmo_last_qpos = (qx, qy)
                return
            delta_world = self._texture_vec3_add(self._texture_vec3_scale(u_axis, du), self._texture_vec3_scale(v_axis, dv))
            new_origin = self._texture_vec3_add(current_origin, delta_world)
            self._texture_rotation_gizmo_last_qpos = (qx, qy)
            self._texture_move_gizmo_current_origin = new_origin
            self._texture_rotation_gizmo_update_count = int(getattr(self, "_texture_rotation_gizmo_update_count", 0) or 0) + 1
            if bool(getattr(self, "_diagnostic_verbose", False)):
                self.ui_log(
                    f"[TEXTURE_GIZMO_MOVE] update#{self._texture_rotation_gizmo_update_count} source={source} method={method} "
                    f"q=({qx:.1f},{qy:.1f}) last=({lx:.1f},{ly:.1f}) dx={dx:.2f} dy={dy:.2f} "
                    f"du={du:.5f} dv={dv:.5f} "
                    f"origin=({float(current_origin[0]):.4f},{float(current_origin[1]):.4f},{float(current_origin[2]):.4f})->"
                    f"({new_origin[0]:.4f},{new_origin[1]:.4f},{new_origin[2]:.4f})"
                )
            self._texture_move_apply_origin(new_origin, source=source)
        except Exception:
            log_exception("update_texture_move_gizmo_drag")

    def _finish_texture_rotation_gizmo_drag(self) -> None:
        try:
            was_active = bool(getattr(self, "_texture_rotation_gizmo_drag_active", False))
            if was_active:
                kind = getattr(self, "_texture_rotation_gizmo_drag_kind", "texrot")
                if kind == "texmove":
                    self.ui_log(
                        f"[TEXTURE_GIZMO_MOVE] end updates={int(getattr(self, '_texture_rotation_gizmo_update_count', 0) or 0)} "
                        f"origin={getattr(self, '_texture_move_gizmo_current_origin', None)}"
                    )
                else:
                    self.ui_log(
                        f"[TEXTURE_GIZMO] end polar updates={int(getattr(self, '_texture_rotation_gizmo_update_count', 0) or 0)} "
                        f"last_rotation={getattr(self, '_texture_rotation_gizmo_last_applied', None)} "
                        f"last_scale={getattr(self, '_texture_rotation_gizmo_last_scale_applied', None)}"
                    )
            self._stop_texture_rotation_poll_timer()
            self._remove_texture_rotation_vtk_observers()
            self._remove_texture_rotation_global_event_filter()
            try:
                self.plotter.releaseMouse()
            except Exception:
                pass
            self._texture_rotation_gizmo_pressed = False
            self._texture_rotation_gizmo_press_pos = None
            self._texture_rotation_gizmo_drag_active = False
            self._texture_rotation_gizmo_drag_kind = None
            self._texture_rotation_gizmo_start_qpos = None
            self._texture_rotation_gizmo_start_vector = None
            self._texture_rotation_gizmo_center = None
            self._texture_rotation_gizmo_normal = None
            self._texture_rotation_gizmo_center_qt = None
            self._texture_rotation_gizmo_start_screen_angle = None
            self._texture_rotation_gizmo_last_applied = None
            self._texture_rotation_gizmo_current_value = None
            self._texture_rotation_gizmo_current_scale = None
            self._texture_rotation_gizmo_start_scale = None
            self._texture_rotation_gizmo_last_qpos = None
            self._texture_rotation_gizmo_last_poll_qpos = None
            self._texture_rotation_gizmo_poll_count = 0
            self._texture_move_gizmo_start_origin = None
            self._texture_move_gizmo_current_origin = None
            self._texture_move_gizmo_source_index = None
            self._texture_move_gizmo_u_axis = None
            self._texture_move_gizmo_v_axis = None
            self._texture_move_gizmo_screen_matrix = None
            # If a fast live update failed, rebuild the TEX preview once at the
            # end of the drag instead of on every mouse event. This preserves the
            # safety fallback without causing repeated flicker while dragging.
            if bool(getattr(self, "_texture_live_update_failed", False)):
                try:
                    source_index = getattr(self, "_texture_move_gizmo_source_index", None)
                    anchor = getattr(self, "_texture_projection_last_anchor", None) or {}
                    if source_index is not None:
                        self.generate_texture_projection_preview(
                            target_index=int(source_index),
                            seed_face_index=int(anchor.get("cell_id")) if anchor.get("cell_id") is not None else None,
                            projection_origin=tuple(float(v) for v in anchor.get("point")) if anchor.get("point") is not None else None,
                            projection_normal=tuple(float(v) for v in anchor.get("normal")) if anchor.get("normal") is not None else None,
                        )
                    else:
                        self.generate_texture_projection_preview()
                except Exception:
                    log_exception("texture_live_failed_end_rebuild")
                finally:
                    self._texture_live_update_failed = False
            # Keep ring metadata available for screen-space picking after the drag;
            # update_texture_rotation_gizmo will replace it with the latest camera scale.
            self.update_texture_rotation_gizmo(render=True)
        except Exception:
            log_exception("finish_texture_rotation_gizmo_drag")


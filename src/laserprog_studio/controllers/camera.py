# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class CameraNavigationLayer:
    def _camera_forward_vector(self):
        """Return normalized camera forward vector, from camera position to focal point."""
        import numpy as np
        cam = self.plotter.camera
        pos = np.array(cam.GetPosition(), dtype=float)
        foc = np.array(cam.GetFocalPoint(), dtype=float)
        forward = foc - pos
        n = float(np.linalg.norm(forward))
        if not np.isfinite(n) or n < 1e-9:
            return np.array((0.0, 0.0, -1.0), dtype=float)
        return forward / n

    def _fixed_view_names(self) -> set[str]:
        return {"top", "bottom", "front", "back", "left", "right", "plan_trace_surface"}

    def _is_fixed_camera_mode(self) -> bool:
        """True for locked orthographic face views.

        In these views the VTK orbit interactor must not receive left-drag events.
        Navigation is intentionally limited to right-drag pan and wheel zoom.
        """
        try:
            mode = str(getattr(self, "_camera_view_mode", "free"))
            return mode in self._fixed_view_names()
        except Exception:
            return False

    def _is_top_camera_mode(self) -> bool:
        """Return whether the active fixed view is the top face."""
        try:
            return str(getattr(self, "_camera_view_mode", "free")) == "top"
        except Exception:
            return False

    def _fixed_view_specs(self) -> dict[str, tuple[tuple[float, float, float], tuple[float, float, float], str, str]]:
        """Return camera-from vector, view-up vector, horizontal span axis, vertical span axis."""
        return {
            "top": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), "x", "y"),
            "bottom": ((0.0, 0.0, -1.0), (0.0, -1.0, 0.0), "x", "y"),
            "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0), "x", "z"),
            "back": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), "x", "z"),
            "left": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0), "y", "z"),
            "right": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), "y", "z"),
        }

    def _apply_fixed_camera_orientation(self) -> None:
        """Re-apply the orientation contract of the current fixed view without moving its pan center."""
        try:
            mode = str(getattr(self, "_camera_view_mode", "free"))
            spec = self._fixed_view_specs().get(mode)
            if spec is None:
                return
            import numpy as np
            from_vec, up_vec, _h_axis, _v_axis = spec
            cam = self.plotter.camera
            foc = np.array(cam.GetFocalPoint(), dtype=float)
            pos = np.array(cam.GetPosition(), dtype=float)
            current_dist = float(np.linalg.norm(pos - foc))
            if not np.isfinite(current_dist) or current_dist < 1e-6:
                current_dist = max(bounds_size(scene_bounds(self.current_meshes())) * 3.0, 50.0)
            from_arr = np.array(from_vec, dtype=float)
            from_arr = from_arr / (float(np.linalg.norm(from_arr)) or 1.0)
            new_pos = foc + from_arr * current_dist
            cam.SetPosition(float(new_pos[0]), float(new_pos[1]), float(new_pos[2]))
            cam.SetViewUp(float(up_vec[0]), float(up_vec[1]), float(up_vec[2]))
            try:
                cam.SetParallelProjection(True)
                cam.OrthogonalizeViewUp()
            except Exception:
                pass
        except Exception:
            log_exception("apply_fixed_camera_orientation")

    def _stabilize_camera_up(self) -> None:
        """Repair camera up after programmatic changes only."""
        try:
            cam = self.plotter.camera
            if self._is_fixed_camera_mode():
                self._apply_fixed_camera_orientation()
            else:
                cam.SetViewUp(0.0, 0.0, 1.0)
            self.plotter.renderer.ResetCameraClippingRange()
        except Exception:
            log_exception("stabilize_camera_up")

    def _camera_basis(self):
        """Return normalized camera right/up/forward vectors.

        The basis follows the current camera ViewUp. It does not silently replace it
        with a synthetic up vector because that was the source of the orbit-roll
        regression after panning.
        """
        import numpy as np
        cam = self.plotter.camera
        pos = np.array(cam.GetPosition(), dtype=float)
        foc = np.array(cam.GetFocalPoint(), dtype=float)
        up = np.array(cam.GetViewUp(), dtype=float)

        forward = foc - pos
        n = float(np.linalg.norm(forward))
        if not np.isfinite(n) or n < 1e-9:
            forward = np.array((0.0, 0.0, -1.0), dtype=float)
        else:
            forward = forward / n

        upn = up / (float(np.linalg.norm(up)) or 1.0)
        if not np.all(np.isfinite(upn)) or abs(float(np.dot(forward, upn))) > 0.995:
            upn = np.array((0.0, 1.0, 0.0), dtype=float) if abs(float(forward[2])) > 0.985 else np.array((0.0, 0.0, 1.0), dtype=float)

        right = np.cross(forward, upn)
        rn = float(np.linalg.norm(right))
        if not np.isfinite(rn) or rn < 1e-9:
            right = np.array((1.0, 0.0, 0.0), dtype=float)
        else:
            right = right / rn

        up_screen = np.cross(right, forward)
        un = float(np.linalg.norm(up_screen))
        if not np.isfinite(un) or un < 1e-9:
            up_screen = upn
        else:
            up_screen = up_screen / un
        return right, up_screen, forward

    def _display_to_world_at_depth(self, x: float, y: float, z_depth: float):
        ren = self.plotter.renderer
        ren.SetDisplayPoint(float(x), float(y), float(z_depth))
        ren.DisplayToWorld()
        wx, wy, wz, ww = ren.GetWorldPoint()
        if not ww:
            ww = 1.0
        return (float(wx) / float(ww), float(wy) / float(ww), float(wz) / float(ww))

    def _pan_camera_from_qt(self, old_qx: float, old_qy: float, new_qx: float, new_qy: float) -> None:
        """Right-drag pan.

        Free camera uses the original focal-depth projection. Fixed orthographic
        face views use a separate screen-plane pan and never receive orbit events.
        """
        try:
            if self._is_fixed_camera_mode():
                self._pan_fixed_camera_by_pixels(float(new_qx) - float(old_qx), float(new_qy) - float(old_qy))
            else:
                self._pan_free_camera_at_focal_depth(old_qx, old_qy, new_qx, new_qy)
        except Exception:
            log_exception("pan_camera_from_qt")

    def _pan_free_camera_at_focal_depth(self, old_qx: float, old_qy: float, new_qx: float, new_qy: float) -> None:
        """Original stable free-camera pan path used by the Terrain orbit."""
        try:
            import numpy as np
            cam = self.plotter.camera
            ren = self.plotter.renderer
            h = float(self.plotter.height())
            foc = np.array(cam.GetFocalPoint(), dtype=float)
            ren.SetWorldPoint(float(foc[0]), float(foc[1]), float(foc[2]), 1.0)
            ren.WorldToDisplay()
            _, _, focal_depth = ren.GetDisplayPoint()

            old_vtk = (float(old_qx), h - float(old_qy))
            new_vtk = (float(new_qx), h - float(new_qy))
            old_world = np.array(self._display_to_world_at_depth(old_vtk[0], old_vtk[1], focal_depth), dtype=float)
            new_world = np.array(self._display_to_world_at_depth(new_vtk[0], new_vtk[1], focal_depth), dtype=float)

            shift = (old_world - new_world) * float(getattr(self, "_pan_sensitivity", 1.08))
            if not np.all(np.isfinite(shift)):
                return
            pos = np.array(cam.GetPosition(), dtype=float)
            cam.SetPosition(*(pos + shift))
            cam.SetFocalPoint(*(foc + shift))
            # Keep the old free-view contract: Terrain orbit remains Z-up from the start,
            # not by snapping the camera after an orbit.
            cam.SetViewUp(0.0, 0.0, 1.0)
            self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()
        except Exception:
            log_exception("pan_free_camera_at_focal_depth")

    def _pan_fixed_camera_by_pixels(self, dx: float, dy: float) -> None:
        """Pan a locked orthographic face view in its screen plane."""
        try:
            cam = self.plotter.camera
            plan_trace_fast = str(getattr(self, "active_tool", "")) == "plan_trace"
            if not plan_trace_fast:
                self._apply_fixed_camera_orientation()
            if plan_trace_fast:
                # Plan Tracer locks camera orientation for the lifetime of the
                # sketch. Rebuilding NumPy camera vectors and re-applying that
                # same orientation on every raw mouse event is pure overhead.
                pos_tuple = tuple(float(value) for value in cam.GetPosition())
                foc_tuple = tuple(float(value) for value in cam.GetFocalPoint())
                up_tuple = tuple(float(value) for value in cam.GetViewUp())
                view_vector = tuple(foc_tuple[i] - pos_tuple[i] for i in range(3))
                basis_key = tuple(round(value, 12) for value in (*view_vector, *up_tuple))
                cached_basis = getattr(self, "_plan_trace_pan_basis_cache", None)
                if cached_basis is not None and cached_basis[0] == basis_key:
                    right, up_screen = cached_basis[1], cached_basis[2]
                else:

                    def _normal(value):
                        length = math.sqrt(sum(float(component) * float(component) for component in value))
                        if not math.isfinite(length) or length <= 1.0e-30:
                            return (0.0, 0.0, 0.0)
                        return tuple(float(component) / length for component in value)

                    forward = _normal(view_vector)
                    up = _normal(up_tuple)
                    right = _normal(
                        (
                            forward[1] * up[2] - forward[2] * up[1],
                            forward[2] * up[0] - forward[0] * up[2],
                            forward[0] * up[1] - forward[1] * up[0],
                        )
                    )
                    up_screen = _normal(
                        (
                            right[1] * forward[2] - right[2] * forward[1],
                            right[2] * forward[0] - right[0] * forward[2],
                            right[0] * forward[1] - right[1] * forward[0],
                        )
                    )
                    self._plan_trace_pan_basis_cache = (basis_key, right, up_screen)
            else:
                right, up_screen, _forward = self._camera_basis()
            height_px = max(float(self.plotter.height()), 1.0)
            world_per_pixel = (2.0 * max(float(cam.GetParallelScale()), 1e-6)) / height_px
            world_per_pixel *= float(getattr(self, "_pan_sensitivity", 1.08))
            shift = tuple(
                (-float(right[i]) * float(dx) + float(up_screen[i]) * float(dy)) * world_per_pixel
                for i in range(3)
            )
            if not all(math.isfinite(value) for value in shift):
                return
            pos = tuple(float(value) for value in cam.GetPosition())
            foc = tuple(float(value) for value in cam.GetFocalPoint())
            cam.SetPosition(*(pos[i] + shift[i] for i in range(3)))
            cam.SetFocalPoint(*(foc[i] + shift[i] for i in range(3)))
            if not plan_trace_fast:
                self._apply_fixed_camera_orientation()
                self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()
        except Exception:
            log_exception("pan_fixed_camera_by_pixels")

    def _pan_top_camera_by_pixels(self, dx: float, dy: float) -> None:
        """Top-view pan helper used by fixed-view navigation."""
        self._pan_fixed_camera_by_pixels(dx, dy)

    def _zoom_fixed_camera_from_wheel(self, event) -> None:
        """Wheel zoom for locked orthographic views.

        This keeps the view parallel and avoids handing the wheel to an interactor that
        may internally switch camera state.
        """
        try:
            cam = self.plotter.camera
            delta_y = 0.0
            try:
                delta_y = float(event.angleDelta().y())
            except Exception:
                try:
                    delta_y = float(event.delta())
                except Exception:
                    delta_y = 0.0
            steps = delta_y / 120.0 if abs(delta_y) > 1e-6 else 0.0
            if abs(steps) < 1e-6:
                return
            factor = math.pow(0.88, steps)
            new_scale = max(min(float(cam.GetParallelScale()) * factor, 1.0e9), 1.0e-4)
            cam.SetParallelScale(float(new_scale))
            plan_trace_fast = str(getattr(self, "active_tool", "")) == "plan_trace"
            if not plan_trace_fast:
                self._apply_fixed_camera_orientation()
                self.plotter.renderer.ResetCameraClippingRange()
            self._mark_camera_zoom_interaction()
            if not plan_trace_fast:
                self._refresh_camera_scaled_overlays(render=False, fast_transform_resize=True)
            request = getattr(self, "request_render", None)
            if callable(request):
                request(reason="camera.zoom.fixed")
            else:
                self.plotter.render()
            if not plan_trace_fast:
                self._schedule_gizmo_wheel_refresh()
        except Exception:
            log_exception("zoom_fixed_camera_from_wheel")

    def _pan_camera_by_pixels(self, dx: float, dy: float) -> None:
        """Top-view pan helper used by fixed-view navigation."""
        try:
            if self._is_fixed_camera_mode():
                self._pan_fixed_camera_by_pixels(dx, dy)
                return
            import numpy as np
            cam = self.plotter.camera
            right, up_screen, _forward = self._camera_basis()
            height_px = max(float(self.plotter.height()), 1.0)
            pos = np.array(cam.GetPosition(), dtype=float)
            foc = np.array(cam.GetFocalPoint(), dtype=float)
            if bool(cam.GetParallelProjection()):
                world_per_pixel = (2.0 * max(float(cam.GetParallelScale()), 1e-6)) / height_px
            else:
                dist = float(np.linalg.norm(foc - pos))
                if not np.isfinite(dist) or dist < 1e-6:
                    dist = max(bounds_size(scene_bounds(self.current_meshes())) * 2.0, 20.0)
                view_angle = math.radians(float(cam.GetViewAngle() or 30.0))
                world_per_pixel = (2.0 * dist * math.tan(view_angle / 2.0)) / height_px
            world_per_pixel *= float(getattr(self, "_pan_sensitivity", 1.08))
            shift = (-right * float(dx) + up_screen * float(dy)) * world_per_pixel
            if not np.all(np.isfinite(shift)):
                return
            cam.SetPosition(*(pos + shift))
            cam.SetFocalPoint(*(foc + shift))
            cam.SetViewUp(0.0, 0.0, 1.0)
            self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()
        except Exception:
            log_exception("pan_camera_by_pixels")

    def focus_camera_on_bounds(self, bounds: tuple[float, float, float, float, float, float], label: str = "zone") -> None:
        """Center the orbit pivot and zoom with a comfortable margin.

        Distance keeps a wide framing: the targeted area occupies at most about half the view,
        to remain readable and comfortable.
        """
        try:
            import numpy as np
            cx, cy, cz = ((bounds[0]+bounds[1])/2, (bounds[2]+bounds[3])/2, (bounds[4]+bounds[5])/2)
            size = bounds_size(bounds)
            dist = max(size * 4.2, 20.0)
            direction = np.array((1.0, -1.0, 0.75), dtype=float)
            direction = direction / (np.linalg.norm(direction) or 1.0)
            pos = np.array((cx, cy, cz), dtype=float) + direction * dist
            self._camera_view_mode = "free"
            cam = self.plotter.camera
            cam.SetFocalPoint(float(cx), float(cy), float(cz))
            cam.SetPosition(float(pos[0]), float(pos[1]), float(pos[2]))
            cam.SetViewUp(0, 0, 1)
            try:
                cam.SetParallelProjection(False)
            except Exception:
                pass
            try:
                cam.SetViewAngle(30.0)
            except Exception:
                pass
            self.plotter.renderer.ResetCameraClippingRange()
            # Camera focus changes the visible height used by adaptive gizmos.
            # Rebuild the transform gizmo / split handle before rendering so a
            # double-click focus immediately resizes the overlays.
            try:
                self._refresh_camera_scaled_overlays(render=False)
            except Exception:
                try:
                    self.update_gizmo(render=False)
                except Exception:
                    pass
            self.plotter.render()
            self.ui_log(f"[CAMERA] Focus {label} | center=({cx:.3f},{cy:.3f},{cz:.3f}) size={size:.3f}")
        except Exception:
            log_exception("focus_camera_on_bounds")

    def focus_camera_on_index(self, idx: int) -> None:
        try:
            meshes = self.current_meshes()
            if 0 <= idx < len(meshes):
                self.focus_camera_on_bounds(mesh_bounds(meshes[idx]), f"part {idx:02d}")
        except Exception:
            log_exception("focus_camera_on_index")

    def view_iso(self) -> None:
        self.ui_log("[ACTION] Iso / free orbit view")
        self._camera_view_mode = "free"
        self.set_stable_iso_camera(reset=True)
        self.plotter.render()

    def align_camera_to_plan_surface(self, *, origin, normal, up_axis=None, focus_bounds=None) -> None:
        """Lock the viewport camera perpendicular to an arbitrary picked surface.

        Plan Tracer uses this when the user selects a scene face as drawing
        support.  It intentionally behaves like a locked orthographic view for
        pan/zoom, but it is not one of the six global axis views.
        """
        try:
            import numpy as np

            origin_arr = np.array(tuple(float(v) for v in origin), dtype=float)
            normal_arr = np.array(tuple(float(v) for v in normal), dtype=float)
            n = float(np.linalg.norm(normal_arr))
            if not np.isfinite(n) or n < 1.0e-9:
                return
            normal_arr = normal_arr / n
            if up_axis is None:
                up_arr = np.array((0.0, 0.0, 1.0), dtype=float)
            else:
                up_arr = np.array(tuple(float(v) for v in up_axis), dtype=float)
            up_arr = up_arr - normal_arr * float(np.dot(up_arr, normal_arr))
            un = float(np.linalg.norm(up_arr))
            if not np.isfinite(un) or un < 1.0e-9:
                up_arr = np.array((0.0, 1.0, 0.0), dtype=float) if abs(float(normal_arr[2])) > 0.95 else np.array((0.0, 0.0, 1.0), dtype=float)
                up_arr = up_arr - normal_arr * float(np.dot(up_arr, normal_arr))
                un = float(np.linalg.norm(up_arr)) or 1.0
            up_arr = up_arr / un

            cam = self.plotter.camera
            try:
                current_dist = float(np.linalg.norm(np.array(cam.GetPosition(), dtype=float) - np.array(cam.GetFocalPoint(), dtype=float)))
            except Exception:
                current_dist = 0.0
            if not np.isfinite(current_dist) or current_dist < 1.0e-6:
                current_dist = max(bounds_size(scene_bounds(self.current_meshes())) * 3.0, 50.0)

            focal_arr = origin_arr
            parallel_scale = None
            if focus_bounds is not None:
                try:
                    b = tuple(float(v) for v in focus_bounds)
                    focal_arr = np.array(((b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5, (b[4] + b[5]) * 0.5), dtype=float)
                    corners = np.array([(x, y, z) for x in (b[0], b[1]) for y in (b[2], b[3]) for z in (b[4], b[5])], dtype=float)
                    right_arr = np.cross(up_arr, normal_arr)
                    rn = float(np.linalg.norm(right_arr))
                    if np.isfinite(rn) and rn > 1.0e-9:
                        right_arr = right_arr / rn
                    else:
                        right_arr = np.array((1.0, 0.0, 0.0), dtype=float)
                    rel = corners - focal_arr
                    h = rel @ right_arr
                    v = rel @ up_arr
                    viewport_w = float(self.plotter.width()) if callable(getattr(self.plotter, "width", None)) else 1.0
                    viewport_h = float(self.plotter.height()) if callable(getattr(self.plotter, "height", None)) else 1.0
                    aspect = max(viewport_w / max(viewport_h, 1.0), 0.1)
                    half_h = max((float(np.max(h)) - float(np.min(h))) * 0.5, 0.5)
                    half_v = max((float(np.max(v)) - float(np.min(v))) * 0.5, 0.5)
                    parallel_scale = max(half_v, half_h / aspect, 1.0) * 1.18
                    current_dist = max(current_dist, bounds_size(b) * 3.0, 50.0)
                except Exception:
                    focal_arr = origin_arr
                    parallel_scale = None

            pos = focal_arr + normal_arr * current_dist
            self._camera_view_mode = "plan_trace_surface"
            cam.SetFocalPoint(float(focal_arr[0]), float(focal_arr[1]), float(focal_arr[2]))
            cam.SetPosition(float(pos[0]), float(pos[1]), float(pos[2]))
            cam.SetViewUp(float(up_arr[0]), float(up_arr[1]), float(up_arr[2]))
            try:
                cam.SetParallelProjection(True)
                if parallel_scale is not None and np.isfinite(float(parallel_scale)):
                    cam.SetParallelScale(float(parallel_scale))
                cam.OrthogonalizeViewUp()
            except Exception:
                pass
            self.plotter.renderer.ResetCameraClippingRange()
            self.update_gizmo(render=False)
            self.plotter.render()
            self.ui_log("[CAMERA] Plan tracer aligned to selected surface normal")
        except Exception:
            log_exception("align_camera_to_plan_surface")

    def _set_fixed_orthographic_view(self, mode: str) -> None:
        """Set one face of the unfolded view net as a locked parallel camera.

        Fixed views intentionally disable left-drag orbit. They are meant for precise
        top/front/side work: right-drag pans, wheel zooms, click selects.
        """
        try:
            import numpy as np
            mode = str(mode).lower().strip()
            specs = self._fixed_view_specs()
            if mode not in specs:
                return
            self.ui_log(f"[ACTION] {mode.capitalize()} orthographic view")
            b = scene_bounds(self.current_meshes())
            cx, cy, cz = ((b[0]+b[1])/2, (b[2]+b[3])/2, (b[4]+b[5])/2)
            center = np.array((cx, cy, cz), dtype=float)
            size = max(bounds_size(b), 10.0)
            dist = max(size * 3.0, 50.0)
            from_vec, up_vec, h_axis, v_axis = specs[mode]
            from_arr = np.array(from_vec, dtype=float)
            from_arr = from_arr / (float(np.linalg.norm(from_arr)) or 1.0)
            pos = center + from_arr * dist

            axis_span = {
                "x": max(float(b[1] - b[0]), 1.0),
                "y": max(float(b[3] - b[2]), 1.0),
                "z": max(float(b[5] - b[4]), 1.0),
            }
            viewport_w = max(float(self.plotter.width()), 1.0)
            viewport_h = max(float(self.plotter.height()), 1.0)
            aspect = max(viewport_w / viewport_h, 0.1)
            h_span = axis_span.get(h_axis, size)
            v_span = axis_span.get(v_axis, size)
            parallel_scale = max(v_span * 0.62, (h_span / aspect) * 0.62, 10.0)

            self._camera_view_mode = mode
            cam = self.plotter.camera
            cam.SetFocalPoint(float(center[0]), float(center[1]), float(center[2]))
            cam.SetPosition(float(pos[0]), float(pos[1]), float(pos[2]))
            cam.SetViewUp(float(up_vec[0]), float(up_vec[1]), float(up_vec[2]))
            try:
                cam.SetParallelProjection(True)
                cam.SetParallelScale(float(parallel_scale))
                cam.OrthogonalizeViewUp()
            except Exception:
                pass
            self.plotter.renderer.ResetCameraClippingRange()
            self.update_gizmo(render=False)
            self.plotter.render()
        except Exception:
            log_exception(f"set_fixed_orthographic_view_{mode}")

    def view_top(self) -> None:
        self._set_fixed_orthographic_view("top")

    def view_bottom(self) -> None:
        self._set_fixed_orthographic_view("bottom")

    def view_front(self) -> None:
        self._set_fixed_orthographic_view("front")

    def view_back(self) -> None:
        self._set_fixed_orthographic_view("back")

    def view_left(self) -> None:
        self._set_fixed_orthographic_view("left")

    def view_right(self) -> None:
        self._set_fixed_orthographic_view("right")

    def reset_camera(self) -> None:
        self.ui_log("[ACTION] Reset camera")
        self.focus_camera_on_bounds(scene_bounds(self.current_meshes()), "full scene")

    def closeEvent(self, event) -> None:  # noqa: N802
        try:
            confirmer = getattr(getattr(self, "action_controller", None), "project", None)
            if confirmer is not None and callable(getattr(confirmer, "confirm_discard_if_dirty", None)):
                if not confirmer.confirm_discard_if_dirty("Quit"):
                    try:
                        event.ignore()
                    except Exception:
                        pass
                    self.ui_log("[CLOSE] Quit cancelled: unsaved project")
                    return
        except Exception:
            log_exception("confirm_close_unsaved_project")
            try:
                event.ignore()
            except Exception:
                pass
            return
        self.ui_log("[CLOSE] Closing LaserProg Studio V18")
        try:
            toolbar_controller = getattr(self, "toolbar_controller", None)
            if toolbar_controller is not None and callable(getattr(toolbar_controller, "save_toolbar_preferences_now", None)):
                toolbar_controller.save_toolbar_preferences_now()
            if callable(getattr(self, "_save_ui_layout_preferences_now", None)):
                self._save_ui_layout_preferences_now()
        except Exception:
            log_exception("close save preferences")
        try:
            manager = getattr(self, "background_task_manager", None)
            if manager is not None and callable(getattr(manager, "shutdown", None)):
                manager.shutdown()
                self.ui_log("[CLOSE] Background workers stopped")
        except Exception:
            log_exception("close background workers")
        try:
            orchestrator = getattr(self, "ui_orchestration", None)
            if orchestrator is not None and callable(getattr(orchestrator, "shutdown", None)):
                orchestrator.shutdown()
        except Exception:
            log_exception("close ui orchestration")
        try:
            self.plotter.close(); self.ui_log("[CLOSE] Plotter closed")
        except Exception:
            log_exception("close plotter")
        QMainWindow.closeEvent(self, event)

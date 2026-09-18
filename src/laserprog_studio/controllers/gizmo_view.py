# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class GizmoViewLayer:
    def _log_gizmo_state_once(self, event: str, **state: Any) -> None:
        try:
            items = tuple(sorted((str(k), repr(v)) for k, v in state.items()))
            signature = (str(event), items)
            if getattr(self, "_last_gizmo_visibility_state", None) == signature:
                return
            self._last_gizmo_visibility_state = signature
            detail = " ".join(f"{k}={v}" for k, v in state.items())
            self.ui_log(f"[GIZMO] {event} {detail}".rstrip())
        except Exception:
            pass

    def update_gizmo(self, render: bool = True) -> None:
        try:
            self._gizmo_update_serial = int(getattr(self, "_gizmo_update_serial", 0)) + 1
            serial = int(self._gizmo_update_serial)
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            available = bool(self._transform_tools_available())
            mode_ok = self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}
            try:
                from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event
                record_transform_gizmo_event(
                    self,
                    "view.update_begin",
                    extra={
                        "serial": serial,
                        "render": bool(render),
                        "mode": self.transform_mode,
                        "available": available,
                        "mode_ok": mode_ok,
                        "indices": list(indices),
                    },
                )
            except Exception:
                pass
            try:
                self.ui_log(
                    f"[GIZMO_TRACE] update#{serial} begin render={bool(render)} "
                    f"mode={self.transform_mode} mode_ok={mode_ok} available={available} "
                    f"active_tool={self.active_tool} preview={self.has_preview()} "
                    f"selected_raw={list(getattr(self, 'selected_indices', []))} selected_valid={list(indices)} "
                    f"active={self.active_index} meshes={len(meshes)}"
                )
            except Exception:
                pass
            try:
                self._preserve_native_transform_gizmo = True
                self._clear_gizmo_actors()
            finally:
                self._preserve_native_transform_gizmo = False

            # Logic gate for the transform gizmo:
            # - N hides it; T/R/S show it;
            # - at least one selected mesh is required;
            # - modal tools/previews own the scene and temporarily hide transforms.
            # Do not depend solely on active_index here: the selection list is the
            # source of truth after the refactor, and active_index is only focus.
            if not mode_ok or not available or not indices:
                reasons = []
                if not mode_ok:
                    reasons.append("mode")
                if not available:
                    reasons.append("tool_or_preview")
                if not indices:
                    reasons.append("selection")
                self._log_gizmo_state_once(
                    "hidden",
                    hidden_reason="+".join(reasons) or "unknown",
                    mode=self.transform_mode,
                    active_tool=self.active_tool,
                    preview=self.has_preview(),
                    selected=list(getattr(self, "selected_indices", [])),
                    active=self.active_index,
                )
                try:
                    self.ui_log(f"[GIZMO_TRACE] update#{serial} hidden reasons={reasons} mode={self.transform_mode} selected={indices}")
                except Exception:
                    pass
                try:
                    from laserprog_studio.application.transform_gizmo_api import clear_native_transform_gizmo
                    from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event

                    record_transform_gizmo_event(self, "view.hidden", extra={"serial": serial, "reasons": reasons}, ui_log=True)
                    clear_native_transform_gizmo(self, render=False)
                except Exception:
                    pass
                if render:
                    self.plotter.render()
                return

            import pyvista as pv
            bounds = self._selection_world_bounds(indices, meshes)
            c = self._bounds_center_tuple(bounds)
            length = self._gizmo_length_at(c, meshes)
            axes = self._gizmo_axis_definitions()
            eps = self._gizmo_visible_epsilon()
            center_radius = max(length * 0.060, eps)
            try:
                self.ui_log(
                    f"[GIZMO_TRACE] update#{serial} build bounds=({bounds[0]:.3f},{bounds[1]:.3f},{bounds[2]:.3f},{bounds[3]:.3f},{bounds[4]:.3f},{bounds[5]:.3f}) "
                    f"center=({c[0]:.3f},{c[1]:.3f},{c[2]:.3f}) length={float(length):.3f} eps={float(eps):.6f} "
                    f"axes={list(axes.keys())}"
                )
            except Exception:
                pass

            if self.transform_mode == self.TRANSFORM_TRANSLATE:
                try:
                    from laserprog_studio.application.transform_gizmo_api import sync_native_translate_gizmo

                    if sync_native_translate_gizmo(self, center=c, length=length, axes=axes, render=bool(render)):
                        self._log_gizmo_state_once(
                            "visible_native",
                            mode=self.transform_mode,
                            actors="api_persistent",
                            selected=list(indices),
                            active=self.active_index,
                            center=tuple(round(float(v), 3) for v in c),
                            length=round(float(length), 3),
                        )
                        try:
                            self.ui_log(f"[GIZMO_TRACE] update#{serial} branch=translate_native_api")
                        except Exception:
                            pass
                        return
                except Exception as exc:
                    try:
                        from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event
                        record_transform_gizmo_event(self, "view.native_sync_exception", extra={"mode": "translate", "serial": serial}, error=exc, ui_log=True)
                    except Exception:
                        pass
                try:
                    from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event
                    record_transform_gizmo_event(self, "view.native_sync_failed", extra={"mode": "translate", "serial": serial}, ui_log=True)
                    from laserprog_studio.application.transform_gizmo_api import clear_native_transform_gizmo

                    clear_native_transform_gizmo(self, render=False)
                except Exception:
                    pass
                try:
                    self.ui_log(f"[GIZMO_TRACE] update#{serial} branch=translate_legacy")
                except Exception:
                    pass
                shaft_length = max(length * 0.78, eps)
                tip_length = max(length * 0.22, eps)
                shaft_radius = max(length * 0.030, eps)
                tip_radius = max(length * 0.090, eps)

                # Thick primitive axes: cylinder shaft + cone tip. They are rendered
                # in a foreground VTK layer so they stay visible over the selected mesh.
                for axis, (vec, color) in axes.items():
                    vx, vy, vz = vec
                    shaft_center = (
                        c[0] + vx * shaft_length * 0.5,
                        c[1] + vy * shaft_length * 0.5,
                        c[2] + vz * shaft_length * 0.5,
                    )
                    try:
                        shaft = pv.Cylinder(
                            center=shaft_center,
                            direction=vec,
                            radius=shaft_radius,
                            height=shaft_length,
                            resolution=28,
                        )
                    except TypeError:
                        shaft = pv.Cylinder(center=shaft_center, direction=vec, radius=shaft_radius, height=shaft_length)
                    self._add_overlay_mesh_actor(shaft, key=f"{axis}_shaft", axis=axis, color=color, pickable=True)

                    cone_center = (
                        c[0] + vx * (shaft_length + tip_length * 0.5),
                        c[1] + vy * (shaft_length + tip_length * 0.5),
                        c[2] + vz * (shaft_length + tip_length * 0.5),
                    )
                    try:
                        tip = pv.Cone(
                            center=cone_center,
                            direction=vec,
                            height=tip_length,
                            radius=tip_radius,
                            resolution=32,
                        )
                    except TypeError:
                        tip = pv.Cone(center=cone_center, direction=vec, height=tip_length, radius=tip_radius)
                    self._add_overlay_mesh_actor(tip, key=f"{axis}_tip", axis=axis, color=color, pickable=True)
                    self._add_gizmo_label(axis, c, vec, length, color)

            elif self.transform_mode == self.TRANSFORM_ROTATE:
                try:
                    from laserprog_studio.application.transform_gizmo_api import sync_native_rotate_gizmo

                    if sync_native_rotate_gizmo(self, center=c, length=length, axes=axes, render=bool(render)):
                        self._log_gizmo_state_once(
                            "visible_native",
                            mode=self.transform_mode,
                            actors="api_persistent",
                            selected=list(indices),
                            active=self.active_index,
                            center=tuple(round(float(v), 3) for v in c),
                            length=round(float(length), 3),
                        )
                        try:
                            self.ui_log(f"[GIZMO_TRACE] update#{serial} branch=rotate_native_api")
                        except Exception:
                            pass
                        return
                except Exception as exc:
                    try:
                        from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event
                        record_transform_gizmo_event(self, "view.native_sync_exception", extra={"mode": "rotate", "serial": serial}, error=exc, ui_log=True)
                    except Exception:
                        pass
                try:
                    from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event
                    record_transform_gizmo_event(self, "view.native_sync_failed", extra={"mode": "rotate", "serial": serial}, ui_log=True)
                    from laserprog_studio.application.transform_gizmo_api import clear_native_transform_gizmo

                    clear_native_transform_gizmo(self, render=False)
                except Exception:
                    pass
                try:
                    self.ui_log(f"[GIZMO_TRACE] update#{serial} branch=rotate_legacy")
                except Exception:
                    pass
                ring_radius = max(length * 0.92, eps)
                ring_tube_radius = max(length * 0.020, eps)
                for axis, (vec, color) in axes.items():
                    ring = self._make_rotation_ring_mesh(c, axis, ring_radius, ring_tube_radius)
                    self._add_overlay_mesh_actor(ring, key=f"rotate_{axis}_ring", axis=axis, color=color, pickable=True)
                    # Put labels outside the rings along their corresponding world axes.
                    self._add_gizmo_label(axis, c, vec, ring_radius * 1.05, color)

            elif self.transform_mode == self.TRANSFORM_SCALE:
                local_bounds, c, axes = self._oriented_bounds_for_selection(indices, meshes)
                length = self._gizmo_length_at(c, meshes)
                center_radius = max(length * 0.060, eps)
                try:
                    from laserprog_studio.application.transform_gizmo_api import sync_native_scale_gizmo

                    frame_specs = self._scale_frame_specs_to_world(self._adaptive_scale_frame_specs(local_bounds, axes, length), axes)
                    if sync_native_scale_gizmo(self, center=c, length=length, axes=axes, frame_specs=frame_specs, render=bool(render)):
                        self._log_gizmo_state_once(
                            "visible_native",
                            mode=self.transform_mode,
                            actors="api_persistent",
                            selected=list(indices),
                            active=self.active_index,
                            center=tuple(round(float(v), 3) for v in c),
                            length=round(float(length), 3),
                        )
                        try:
                            self.ui_log(f"[GIZMO_TRACE] update#{serial} branch=scale_native_api")
                        except Exception:
                            pass
                        return
                except Exception as exc:
                    try:
                        from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event
                        record_transform_gizmo_event(self, "view.native_sync_exception", extra={"mode": "scale", "serial": serial}, error=exc, ui_log=True)
                    except Exception:
                        pass
                try:
                    from laserprog_studio.application.transform_gizmo_diagnostics import record_transform_gizmo_event
                    record_transform_gizmo_event(self, "view.native_sync_failed", extra={"mode": "scale", "serial": serial}, ui_log=True)
                    from laserprog_studio.application.transform_gizmo_api import clear_native_transform_gizmo

                    clear_native_transform_gizmo(self, render=False)
                except Exception:
                    pass
                try:
                    self.ui_log(f"[GIZMO_TRACE] update#{serial} branch=scale_legacy")
                except Exception:
                    pass
                shaft_length = max(length * 0.74, eps)
                shaft_radius = max(length * 0.020, eps)
                handle_size = max(length * 0.135, eps)

                for axis, (vec, color) in axes.items():
                    vx, vy, vz = vec
                    shaft_center = (
                        c[0] + vx * shaft_length * 0.5,
                        c[1] + vy * shaft_length * 0.5,
                        c[2] + vz * shaft_length * 0.5,
                    )
                    try:
                        shaft = pv.Cylinder(center=shaft_center, direction=vec, radius=shaft_radius, height=shaft_length, resolution=20)
                    except TypeError:
                        shaft = pv.Cylinder(center=shaft_center, direction=vec, radius=shaft_radius, height=shaft_length)
                    self._add_overlay_mesh_actor(shaft, key=f"scale_{axis}_shaft", axis=axis, color=color, pickable=True)

                    handle_center = (
                        c[0] + vx * shaft_length,
                        c[1] + vy * shaft_length,
                        c[2] + vz * shaft_length,
                    )
                    cube = self._make_scale_box_handle(handle_center, handle_size)
                    self._add_overlay_mesh_actor(cube, key=f"scale_{axis}_handle", axis=axis, color=color, pickable=True)
                    self._add_gizmo_label(axis, c, vec, length, color)

                # Adaptive local bounds frame. It chooses the local face that is
                # most visible from the current camera direction, so the frame does
                # not become edge-on when looking at the part from the side.
                frame_radius = max(length * 0.018, eps)
                frame_specs = self._scale_frame_specs_to_world(self._adaptive_scale_frame_specs(local_bounds, axes, length), axes)
                for handle, p0, p1, color in frame_specs:
                    edge = self._make_tube_line_mesh(p0, p1, frame_radius)
                    self._add_overlay_mesh_actor(edge, key=f"scale_edge_{handle}", axis=handle, color=color, pickable=True)

            try:
                center_ball = pv.Sphere(radius=center_radius, center=c, theta_resolution=24, phi_resolution=12)
                self._add_overlay_mesh_actor(center_ball, key="center", axis=None, color="#f2f4f8", pickable=False)
            except Exception:
                pass

            actor_count = len(getattr(self, "gizmo_actors", {}))
            try:
                overlay = getattr(self, "gizmo_overlay_renderer", None)
                main_renderer = getattr(self.plotter, "renderer", None)
                ren_win = getattr(self.plotter, "ren_win", None) or getattr(self.plotter, "render_window", None)
                if callable(ren_win):
                    ren_win = ren_win()
                layers = int(ren_win.GetNumberOfLayers()) if ren_win is not None else -1
                keys = list(getattr(self, "gizmo_actors", {}).keys())
                self.ui_log(
                    f"[GIZMO_TRACE] update#{serial} actors={actor_count} keys={keys} "
                    f"overlay_props={self._vtk_prop_count(overlay) if overlay is not None else 'none'} "
                    f"main_props={self._vtk_prop_count(main_renderer) if main_renderer is not None else 'none'} layers={layers}"
                )
            except Exception:
                pass
            self._log_gizmo_state_once(
                "visible" if actor_count else "no_actors_created",
                mode=self.transform_mode,
                actors=actor_count,
                selected=list(indices),
                active=self.active_index,
                center=tuple(round(float(v), 3) for v in c),
                length=round(float(length), 3),
            )
            self._apply_highlighted_transform_axis()
            if render:
                try:
                    self.ui_log(f"[GIZMO_TRACE] update#{serial} render requested")
                except Exception:
                    pass
                self.plotter.render()
            try:
                self.ui_log(f"[GIZMO_TRACE] update#{serial} end ok")
            except Exception:
                pass
        except Exception:
            try:
                self.ui_log(
                    f"[GIZMO_TRACE] update#{getattr(self, '_gizmo_update_serial', '?')} exception "
                    f"mode={getattr(self, 'transform_mode', '?')} selected={getattr(self, 'selected_indices', '?')} "
                    f"active={getattr(self, 'active_index', '?')}"
                )
            except Exception:
                pass
            log_exception("update_gizmo")

    def on_display_mode_changed(self) -> None:
        try:
            combo = getattr(self, "display_mode_combo", None)
            mode = str(combo.currentData() if combo is not None else "wireframe")
            applied = self.scene_renderer.set_display_mode(mode, render=False)
            if applied == "wireframe":
                self.show_edges = True
            render_state = getattr(self, "render_state", None)
            if render_state is not None:
                render_state.display_mode = applied
                render_state.show_edges_overlay = bool(self.show_edges)
            self.ui_log(f"[DISPLAY] mode={applied} edges={self.show_edges}")
            textured = any(getattr(m, "uvs", None) is not None and getattr(m, "texture_projections", None) for m in self.current_meshes())
            if textured:
                # Texture actors need to be recreated when entering/leaving material mode.
                self.rebuild_scene(keep_camera=True)
                return
            getattr(self, "_sync_material_scene_rendering", lambda **_kwargs: None)(render=False)
            self.refresh_actor_styles()
        except Exception:
            log_exception("on_display_mode_changed")

    def toggle_edges(self) -> None:
        self.show_edges = self.edges_check.isChecked()
        try:
            if getattr(self, "render_state", None) is not None:
                self.render_state.show_edges_overlay = bool(self.show_edges)
        except Exception:
            pass
        self.ui_log(f"[DISPLAY] edges={self.show_edges}")
        self.refresh_actor_styles()

    def toggle_ghost(self) -> None:
        self.show_ghost = self.ghost_check.isChecked(); self.ui_log(f"[DISPLAY] dim_inactive={self.show_ghost}"); self.refresh_actor_styles()

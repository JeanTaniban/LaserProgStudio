# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *


class GizmoOverlayLayer:
    def _gizmo_diag_enabled(self) -> bool:
        try:
            return bool(getattr(self, "_diagnostic_verbose", True))
        except Exception:
            return True

    def _gizmo_diag(self, message: str) -> None:
        if not self._gizmo_diag_enabled():
            return
        try:
            self.ui_log(f"[GIZMO_DIAG] {message}")
        except Exception:
            pass

    @staticmethod
    def _vtk_prop_count(renderer: Any) -> int | str:
        try:
            props = renderer.GetViewProps()
            return int(props.GetNumberOfItems())
        except Exception:
            return "?"

    @staticmethod
    def _vtk_actor_addr(actor: Any) -> str:
        try:
            return str(actor.GetAddressAsString(""))
        except Exception:
            return hex(id(actor))

    def _gizmo_poly_summary(self, mesh: Any) -> str:
        try:
            n_points = int(mesh.GetNumberOfPoints())
        except Exception:
            try:
                n_points = int(mesh.n_points)
            except Exception:
                n_points = -1
        try:
            n_cells = int(mesh.GetNumberOfCells())
        except Exception:
            try:
                n_cells = int(mesh.n_cells)
            except Exception:
                n_cells = -1
        try:
            b = mesh.GetBounds()
            bounds = f"({float(b[0]):.3f},{float(b[1]):.3f},{float(b[2]):.3f},{float(b[3]):.3f},{float(b[4]):.3f},{float(b[5]):.3f})"
        except Exception:
            bounds = "(?)"
        return f"points={n_points} cells={n_cells} bounds={bounds}"

    def _ensure_gizmo_overlay_renderer(self):
        """Return the foreground VTK renderer dedicated to transform gizmos.

        The transform gizmo is a VTK overlay, not a Qt overlay. The renderer
        must be attached as a real layer-1 renderer sharing the main camera.
        This method is intentionally verbose in diagnostics because most gizmo
        visibility bugs are caused by renderer/layer/camera state.
        """
        try:
            import vtk

            ren_win = getattr(self.plotter, "ren_win", None) or getattr(self.plotter, "render_window", None)
            if callable(ren_win):
                ren_win = ren_win()
            if ren_win is None:
                self._gizmo_diag("ensure_overlay failed: no render window")
                return None

            base_renderer = self.plotter.renderer
            overlay = self.gizmo_overlay_renderer
            created = False
            reattached = False
            if overlay is None:
                overlay = vtk.vtkRenderer()
                created = True
                try:
                    overlay.SetLayer(1)
                except Exception:
                    pass
                try:
                    overlay.SetInteractive(False)
                except Exception:
                    pass
                try:
                    overlay.SetBackgroundAlpha(0.0)
                except Exception:
                    pass
                try:
                    overlay.SetPreserveDepthBuffer(False)
                except Exception:
                    pass
                try:
                    ren_win.AddRenderer(overlay)
                    reattached = True
                except Exception:
                    log_exception("gizmo overlay AddRenderer")
                try:
                    ren_win.SetNumberOfLayers(max(2, int(ren_win.GetNumberOfLayers())))
                except Exception:
                    try:
                        ren_win.SetNumberOfLayers(2)
                    except Exception:
                        pass
                self.gizmo_overlay_renderer = overlay
            else:
                try:
                    has_renderer = bool(ren_win.HasRenderer(overlay))
                except Exception:
                    has_renderer = True
                if not has_renderer:
                    try:
                        ren_win.AddRenderer(overlay)
                        reattached = True
                    except Exception:
                        log_exception("gizmo overlay re-AddRenderer")
                    try:
                        ren_win.SetNumberOfLayers(max(2, int(ren_win.GetNumberOfLayers())))
                    except Exception:
                        pass

            try:
                overlay.SetLayer(1)
            except Exception:
                pass
            try:
                overlay.SetViewport(base_renderer.GetViewport())
            except Exception:
                pass
            try:
                overlay.SetActiveCamera(base_renderer.GetActiveCamera())
            except Exception:
                pass

            if created or reattached or getattr(self, "_gizmo_overlay_last_diag", None) is None:
                try:
                    layers = int(ren_win.GetNumberOfLayers())
                except Exception:
                    layers = -1
                try:
                    viewport = tuple(round(float(v), 3) for v in overlay.GetViewport())
                except Exception:
                    viewport = ("?",)
                signature = (id(overlay), layers, viewport, self._vtk_prop_count(overlay))
                self._gizmo_overlay_last_diag = signature
                self._gizmo_diag(
                    "ensure_overlay "
                    f"created={created} reattached={reattached} layers={layers} "
                    f"overlay_props={self._vtk_prop_count(overlay)} main_props={self._vtk_prop_count(base_renderer)} "
                    f"viewport={viewport} overlay_addr={self._vtk_actor_addr(overlay)}"
                )
            return overlay
        except Exception:
            log_exception("ensure_gizmo_overlay_renderer")
            return None

    def _make_gizmo_actor(self, mesh: Any, *, color: str, pickable: bool) -> Any | None:
        """Create a standalone VTK actor for one gizmo mesh."""
        try:
            import vtk

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(mesh)
            try:
                mapper.Update()
            except Exception:
                pass

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            r, g, b = parse_hex_color(color)
            prop = actor.GetProperty()
            prop.SetColor(float(r), float(g), float(b))
            prop.SetAmbient(1.0)
            prop.SetDiffuse(0.0)
            prop.SetSpecular(0.0)
            prop.SetOpacity(1.0)
            try:
                prop.LightingOff()
            except Exception:
                pass
            # Keep bounds enabled. A renderer containing only UseBoundsOff actors
            # can compute invalid clipping and hide the gizmo.
            try:
                actor.SetUseBounds(True)
            except Exception:
                pass
            try:
                actor.SetPickable(bool(pickable))
            except Exception:
                if pickable:
                    actor.PickableOn()
                else:
                    actor.PickableOff()
            self._gizmo_diag(
                f"make_actor color={color} pickable={bool(pickable)} "
                f"addr={self._vtk_actor_addr(actor)} {self._gizmo_poly_summary(mesh)}"
            )
            return actor
        except Exception:
            log_exception("make_gizmo_actor")
            return None

    def _register_gizmo_actor(self, key: str, actor: Any, axis: str | None = None) -> None:
        self.gizmo_actors[key] = actor
        if axis is not None:
            self.gizmo_actor_ids[id(actor)] = axis
            try:
                self.gizmo_key_by_addr[actor.GetAddressAsString("")] = axis
            except Exception:
                pass
        self._gizmo_diag(f"register_actor key={key} axis={axis} addr={self._vtk_actor_addr(actor)}")

    def _add_actor_to_main_renderer(self, actor: Any, *, key: str, pickable: bool) -> bool:
        try:
            add_actor = getattr(self.plotter, "add_actor", None)
            if callable(add_actor):
                try:
                    added = add_actor(
                        actor,
                        reset_camera=False,
                        name=f"gizmo_{key}__main",
                        pickable=bool(pickable),
                        render=False,
                        remove_existing_actor=True,
                    )
                except TypeError:
                    added = add_actor(actor, reset_camera=False, name=f"gizmo_{key}__main", pickable=bool(pickable), render=False)
                ok = added is not None
                if ok:
                    try:
                        self._gizmo_main_actor_names.add(f"gizmo_{key}__main")
                    except Exception:
                        pass
                self._gizmo_diag(f"main_add via plotter.add_actor key={key} pickable={pickable} ok={ok} addr={self._vtk_actor_addr(actor)}")
                return ok
            self.plotter.renderer.AddActor(actor)
            try:
                self._gizmo_main_actor_names.add(f"gizmo_{key}__main")
            except Exception:
                pass
            self._gizmo_diag(f"main_add via renderer.AddActor key={key} pickable={pickable} ok=True addr={self._vtk_actor_addr(actor)}")
            return True
        except Exception:
            log_exception(f"gizmo main add_actor key={key}")
            try:
                self.plotter.renderer.AddActor(actor)
                try:
                    self._gizmo_main_actor_names.add(f"gizmo_{key}__main")
                except Exception:
                    pass
                self._gizmo_diag(f"main_add fallback renderer.AddActor key={key} ok=True addr={self._vtk_actor_addr(actor)}")
                return True
            except Exception:
                log_exception(f"gizmo main fallback AddActor key={key}")
                return False

    def _add_overlay_mesh_actor(self, mesh: Any, *, key: str, axis: str | None, color: str, pickable: bool) -> Any | None:
        """Add one transform-gizmo mesh to the VTK overlay, with a safe fallback."""
        try:
            self._gizmo_diag(f"add_mesh_actor begin key={key} axis={axis} color={color} pickable={pickable} {self._gizmo_poly_summary(mesh)}")
            overlay = self._ensure_gizmo_overlay_renderer()
            added_any = False
            first_actor = None
            overlay_added = False
            main_added = False

            overlay_actor = self._make_gizmo_actor(mesh, color=color, pickable=pickable)
            if overlay is not None and overlay_actor is not None:
                try:
                    overlay.AddActor(overlay_actor)
                    overlay_added = True
                    self._register_gizmo_actor(f"{key}__overlay", overlay_actor, axis if pickable else None)
                    r, g, b = parse_hex_color(color)
                    self._gizmo_actor_base_colors[id(overlay_actor)] = (float(r), float(g), float(b))
                    first_actor = overlay_actor
                    added_any = True
                except Exception:
                    log_exception(f"gizmo overlay AddActor key={key}")

            main_actor = self._make_gizmo_actor(mesh, color=color, pickable=pickable)
            if main_actor is not None and self._add_actor_to_main_renderer(main_actor, key=key, pickable=pickable):
                main_added = True
                self._register_gizmo_actor(f"{key}__main", main_actor, axis if pickable else None)
                r, g, b = parse_hex_color(color)
                self._gizmo_actor_base_colors[id(main_actor)] = (float(r), float(g), float(b))
                if first_actor is None:
                    first_actor = main_actor
                added_any = True

            if added_any:
                try:
                    if overlay is not None:
                        overlay.ResetCameraClippingRange()
                except Exception:
                    log_exception(f"gizmo overlay ResetCameraClippingRange key={key}")
                try:
                    self.plotter.renderer.ResetCameraClippingRange()
                except Exception:
                    log_exception(f"gizmo main ResetCameraClippingRange key={key}")
                self._gizmo_diag(
                    f"add_mesh_actor end key={key} overlay_added={overlay_added} main_added={main_added} "
                    f"overlay_props={self._vtk_prop_count(overlay) if overlay is not None else 'none'} "
                    f"main_props={self._vtk_prop_count(getattr(self.plotter, 'renderer', None))} "
                    f"registered={len(getattr(self, 'gizmo_actors', {}))}"
                )
                return first_actor
            self._gizmo_diag(f"add_mesh_actor FAILED key={key} overlay_actor={overlay_actor is not None} overlay_exists={overlay is not None} main_actor={main_actor is not None}")
            return None
        except Exception:
            log_exception("add_overlay_mesh_actor")
            return None

    def _clear_gizmo_actors(self) -> None:
        """Remove all transform gizmo actors from overlay and fallback renderers."""
        try:
            overlay = self.gizmo_overlay_renderer
            main_renderer = getattr(self.plotter, "renderer", None)
            actors = list(self.gizmo_actors.items())
            self._gizmo_diag(
                f"clear_actors begin count={len(actors)} overlay_props={self._vtk_prop_count(overlay) if overlay is not None else 'none'} "
                f"main_props={self._vtk_prop_count(main_renderer) if main_renderer is not None else 'none'}"
            )
            for key, actor in actors:
                try:
                    if overlay is not None:
                        overlay.RemoveActor(actor)
                except Exception:
                    log_exception(f"gizmo overlay RemoveActor key={key}")
                try:
                    self.plotter.remove_actor(actor, render=False)
                except Exception:
                    try:
                        if main_renderer is not None:
                            main_renderer.RemoveActor(actor)
                    except Exception:
                        log_exception(f"gizmo main RemoveActor key={key}")
            try:
                for actor_name in list(getattr(self, "_gizmo_main_actor_names", set()) or set()):
                    try:
                        self.plotter.remove_actor(actor_name, render=False)
                    except Exception:
                        pass
                self._gizmo_main_actor_names.clear()
            except Exception:
                pass
            self.gizmo_actors.clear()
            self.gizmo_actor_ids.clear()
            self.gizmo_key_by_addr.clear()
            self._gizmo_actor_base_colors.clear()
            if not bool(getattr(self, "_preserve_native_transform_gizmo", False)):
                try:
                    from laserprog_studio.application.transform_gizmo_api import clear_native_transform_gizmo

                    clear_native_transform_gizmo(self, render=False)
                except Exception:
                    pass
            self._gizmo_diag(
                f"clear_actors end overlay_props={self._vtk_prop_count(overlay) if overlay is not None else 'none'} "
                f"main_props={self._vtk_prop_count(main_renderer) if main_renderer is not None else 'none'}"
            )
        except Exception:
            log_exception("clear_gizmo_actors")

    def _iter_gizmo_pick_actors(self):
        count = 0
        for key, actor in self.gizmo_actors.items():
            logical_key = key.split("__", 1)[0]
            if logical_key.startswith("label_") or logical_key == "center":
                continue
            if actor is not None:
                count += 1
                yield actor
        try:
            self._last_iter_gizmo_pick_count = count
        except Exception:
            pass

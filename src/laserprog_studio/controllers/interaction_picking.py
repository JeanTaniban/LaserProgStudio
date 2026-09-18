# -*- coding: utf-8 -*-
from __future__ import annotations

from .._window_deps import *
from ..tooling.registry import get_studio_tool


class InteractionPickingLayer:
    def _select_from_qt_click(self, qx: float, qy: float, additive: bool = False) -> None:
        try:
            picked = self._pick_from_qt_pos(qx, qy)
            if self.active_tool == self.TOOL_MOD_RELIEF:
                anchor = self._pick_relief_anchor_from_qt_pos(qx, qy)
                if anchor is not None:
                    idx, point, normal, cell_id = anchor
                    self._set_relief_anchor_from_pick(idx, point, normal)
                    self.ui_log(f"[RELIEF] Face picked: object={idx} triangle={cell_id}")
                    return
            if picked and picked[0] == "mesh":
                idx = int(picked[1])
                if self.active_tool == self.TOOL_ENGRAVING:
                    tool = get_studio_tool(self.TOOL_ENGRAVING)
                    handler = getattr(tool, "assign_index", None)
                    if callable(handler):
                        handler(self.context, idx)
                elif self.active_tool == getattr(self, "TOOL_MATERIAL", "material"):
                    self.apply_material_to_index(idx)
                elif self.active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                    anchor = self._pick_texture_projection_anchor_from_qt_pos(qx, qy)
                    if anchor is not None:
                        a_idx, point, normal, cell_id = anchor
                        self.apply_texture_projection_from_pick(int(a_idx), point, normal, int(cell_id))
                    else:
                        self.apply_texture_projection_to_index(idx)
                else:
                    self.select_index(idx, toggle=additive)
            elif picked and picked[0] == "gizmo":
                if self.transform_mode == self.TRANSFORM_ROTATE:
                    self.ui_log("[GIZMO] Click a rotation ring, then drag to rotate the part.")
                elif self.transform_mode == self.TRANSFORM_SCALE:
                    self.ui_log("[GIZMO] Click a scale axis or a bounds-frame edge, then drag to resize the part.")
                else:
                    self.ui_log("[GIZMO] Click an axis, then drag to move the part.")
            else:
                self.clear_selection(reason=f"empty click q=({qx:.1f},{qy:.1f})")
        except Exception:
            log_exception("select_from_qt_click")

    def _qt_to_vtk_candidates(self, qx: float, qy: float) -> list[tuple[int, int, str]]:
        """Convert a Qt top-left position into VTK bottom-left coordinates.

        Depending on Qt/PyVista versions and Windows DPI, devicePixelRatioF may already
        be applied by the interactor. We try a couple of close conversions and keep the
        one that successfully picks an actor.
        """
        try:
            h = float(self.plotter.height())
            dpr = float(self.plotter.devicePixelRatioF()) if hasattr(self.plotter, "devicePixelRatioF") else 1.0
        except Exception:
            h, dpr = 0.0, 1.0
        base = []
        base.append((int(round(qx)), int(round(h - qy)), "qt_no_dpr"))
        if abs(dpr - 1.0) > 0.01:
            base.append((int(round(qx * dpr)), int(round((h - qy) * dpr)), f"qt_dpr_{dpr:.2f}"))
        # Small tolerance: useful if the click falls on an edge or empty pixel.
        out = []
        for x, y, label in base:
            for dx, dy in [(0, 0), (3, 0), (-3, 0), (0, 3), (0, -3), (5, 5), (-5, -5)]:
                out.append((max(0, x + dx), max(0, y + dy), label))
        return out

    def _pick_from_qt_pos(self, qx: float, qy: float):
        for vx, vy, label in self._qt_to_vtk_candidates(qx, qy):
            result = self._pick_at(vx, vy)
            if result is not None:
                self.ui_log(f"[PICKING] OK {result} via {label} vtk=({vx},{vy})")
                return result
        return None

    def _on_left_press_select_probe(self, obj, event) -> None:
        """Remember click start without taking control of the camera."""
        try:
            import time
            x, y = self.plotter.iren.interactor.GetEventPosition()
            self._left_down_pos = (int(x), int(y))
            self._last_mouse_pos = self._left_down_pos
            self._left_down_time = time.monotonic()
        except Exception:
            log_exception("left_press_select_probe")

    def _on_mouse_move_select_probe(self, obj, event) -> None:
        """Track mouse position only. No manual camera state."""
        try:
            x, y = self.plotter.iren.interactor.GetEventPosition()
            self._last_mouse_pos = (int(x), int(y))
        except Exception:
            log_exception("mouse_move_select_probe")

    def _on_left_release_select_probe(self, obj, event) -> None:
        """Select only if it was a short click, not an orbit.

        This method does not block the Terrain style: VTK keeps control of the camera.
        """
        try:
            import time
            x, y = self.plotter.iren.interactor.GetEventPosition()
            x, y = int(x), int(y)
            was_click = False
            if self._left_down_pos is not None:
                ox, oy = self._left_down_pos
                moved = max(abs(x - ox), abs(y - oy))
                elapsed = time.monotonic() - self._left_down_time
                was_click = moved <= 5 and elapsed <= 0.55
            self._left_down_pos = None
            self._last_mouse_pos = None
            if not was_click:
                self._stabilize_camera_up()
                return
            if self.active_tool == self.TOOL_MOD_RELIEF:
                anchor = self._pick_relief_anchor_at(x, y)
                if anchor is not None:
                    idx, point, normal, cell_id = anchor
                    self._set_relief_anchor_from_pick(idx, point, normal)
                    self.ui_log(f"[RELIEF] Face picked: object={idx} triangle={cell_id}")
                    return
                self.ui_log("[RELIEF] Pick a face on the selected part.")
                return
            picked = self._pick_at(x, y)
            if picked and picked[0] == "mesh":
                if self.active_tool == self.TOOL_ENGRAVING:
                    tool = get_studio_tool(self.TOOL_ENGRAVING)
                    handler = getattr(tool, "assign_index", None)
                    if callable(handler):
                        handler(self.context, int(picked[1]))
                elif self.active_tool == getattr(self, "TOOL_MATERIAL", "material"):
                    self.apply_material_to_index(int(picked[1]))
                elif self.active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                    anchor = self._pick_texture_projection_anchor_at(x, y)
                    if anchor is not None:
                        idx, point, normal, cell_id = anchor
                        self.apply_texture_projection_from_pick(int(idx), point, normal, int(cell_id))
                    else:
                        self.apply_texture_projection_to_index(int(picked[1]))
                else:
                    self.select_index(int(picked[1]), toggle=False)
            elif picked and picked[0] == "gizmo":
                if self.transform_mode == self.TRANSFORM_ROTATE:
                    self.ui_log("[GIZMO] Click-drag an X/Y/Z ring to rotate the part.")
                elif self.transform_mode == self.TRANSFORM_SCALE:
                    self.ui_log("[GIZMO] Click-drag a scale handle or frame edge to resize the part.")
                else:
                    self.ui_log("[GIZMO] Click-drag an X/Y/Z arrow to move the part.")
        except Exception:
            log_exception("left_release_select_probe")

    def _actor_address(self, actor) -> str | None:
        try:
            return actor.GetAddressAsString("")
        except Exception:
            return None

    def _resolve_picked_actor(self, actor):
        if actor is None:
            return None
        actor_id = id(actor)
        if actor_id in self.gizmo_actor_ids:
            return ("gizmo", self.gizmo_actor_ids[actor_id])
        if actor_id in self.actor_key_by_vtk:
            return ("mesh", self.actor_key_by_vtk[actor_id])
        addr = self._actor_address(actor)
        if addr:
            if addr in self.gizmo_key_by_addr:
                return ("gizmo", self.gizmo_key_by_addr[addr])
            if addr in self.actor_key_by_addr:
                return ("mesh", self.actor_key_by_addr[addr])
        # Fallback: direct VTK comparison.
        for idx, act in self.actors_by_index.items():
            try:
                if act == actor or self._actor_address(act) == addr:
                    return ("mesh", idx)
            except Exception:
                pass
        for key, act in self.gizmo_actors.items():
            try:
                if act == actor or self._actor_address(act) == addr:
                    # Fallback if id/address registration did not match exactly.
                    # Keep returning only the logical axis expected by the drag code.
                    if key.startswith("rotate_") and key.endswith("_ring"):
                        return ("gizmo", key.split("_")[1])
                    if key.startswith("scale_edge_"):
                        return ("gizmo", key.replace("scale_edge_", "", 1))
                    if key.startswith("scale_") and key.endswith("_handle"):
                        return ("gizmo", key.split("_")[1])
                    if key[:1] in {"x", "y", "z"}:
                        return ("gizmo", key[:1])
                    return ("gizmo", key)
            except Exception:
                pass
        return None

    def _pick_relief_anchor_at(self, x: int, y: int):
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) != self.TOOL_MOD_RELIEF:
                return None
            target = None
            try:
                target = self._relief_target_index()
            except Exception:
                target = getattr(self, "active_index", None)
            if target is None or int(target) not in self.actors_by_index:
                return None
            import vtk
            actor = self.actors_by_index[int(target)]
            picker = vtk.vtkCellPicker()
            picker.SetTolerance(0.0008)
            picker.PickFromListOn()
            picker.AddPickList(actor)
            picker.Pick(int(x), int(y), 0, self.plotter.renderer)
            picked_actor = picker.GetActor() or picker.GetViewProp()
            if not (picked_actor is actor or picked_actor == actor):
                return None
            cell_id = int(picker.GetCellId())
            if cell_id < 0:
                return None
            point = picker.GetPickPosition()
            meshes = self.current_meshes()
            if not (0 <= int(target) < len(meshes)):
                return None
            from laserprog_studio.geometry_ops.text_relief import triangle_normal
            normal = triangle_normal(meshes[int(target)], cell_id)
            return (int(target), (float(point[0]), float(point[1]), float(point[2])), normal, cell_id)
        except Exception:
            log_exception("pick_relief_anchor_at")
            return None

    def _pick_relief_anchor_from_qt_pos(self, qx: float, qy: float):
        try:
            for vx, vy, _label in self._qt_to_vtk_candidates(qx, qy):
                result = self._pick_relief_anchor_at(vx, vy)
                if result is not None:
                    return result
            return None
        except Exception:
            return None

    def _pick_split_plane_handle_at(self, x: int, y: int) -> bool:
        try:
            actor = getattr(self, "split_plane_handle_actor", None)
            if actor is None or getattr(self, "active_tool", self.TOOL_NONE) not in {self.TOOL_MOD_SPLIT, getattr(self, "TOOL_MOD_EXTRUDE_DOWN", "modifier_extrude_down")}:
                return False
            import vtk
            picker = vtk.vtkPropPicker()
            picker.PickFromListOn()
            picker.AddPickList(actor)
            renderer = self.gizmo_overlay_renderer or self.plotter.renderer
            picker.Pick(int(x), int(y), 0, renderer)
            picked = picker.GetActor() or picker.GetViewProp()
            if picked is actor or picked == actor:
                return True
            try:
                return bool(self._actor_address(picked) and self._actor_address(picked) == self._actor_address(actor))
            except Exception:
                return False
        except Exception:
            return False

    def _pick_split_plane_handle_from_qt_pos(self, qx: float, qy: float) -> bool:
        try:
            for vx, vy, _label in self._qt_to_vtk_candidates(qx, qy):
                if self._pick_split_plane_handle_at(vx, vy):
                    return True
            return False
        except Exception:
            return False

    def _pick_gizmo_at(self, x: int, y: int):
        try:
            texture_gizmo_mode = self.active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection")
            transform_gizmo_mode = self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}
            if not self.gizmo_actors or not (transform_gizmo_mode or texture_gizmo_mode):
                try:
                    self.ui_log(f"[PICKING_DIAG] gizmo_pick_at skipped x={x} y={y} actors={len(getattr(self, 'gizmo_actors', {}))} mode={self.transform_mode} active_tool={self.active_tool}")
                except Exception:
                    pass
                return None
            import vtk

            actors = list(self._iter_gizmo_pick_actors())
            if not actors:
                try:
                    self.ui_log(f"[PICKING_DIAG] gizmo_pick_at no_pick_actors registered={len(getattr(self, 'gizmo_actors', {}))}")
                except Exception:
                    pass
                return None

            renderers = []
            overlay = getattr(self, "gizmo_overlay_renderer", None)
            main_renderer = getattr(self.plotter, "renderer", None)
            if overlay is not None:
                renderers.append(overlay)
            if main_renderer is not None and main_renderer is not overlay:
                renderers.append(main_renderer)

            for renderer in renderers:
                try:
                    picker = vtk.vtkPropPicker()
                    picker.PickFromListOn()
                    for actor in actors:
                        picker.AddPickList(actor)
                    picker.Pick(int(x), int(y), 0, renderer)
                    actor = picker.GetActor() or picker.GetViewProp()
                    resolved = self._resolve_picked_actor(actor)
                    if resolved is not None and resolved[0] == "gizmo":
                        try:
                            self.ui_log(f"[PICKING_DIAG] gizmo_pick_at HIT x={x} y={y} renderer_props={self._vtk_prop_count(renderer)} resolved={resolved}")
                        except Exception:
                            pass
                        return resolved
                except Exception:
                    pass
            try:
                self.ui_log(f"[PICKING_DIAG] gizmo_pick_at miss x={x} y={y} actors={len(actors)} renderers={len(renderers)}")
            except Exception:
                pass
            return None
        except Exception:
            log_exception("pick_gizmo_at")
            return None

    def _pick_gizmo_from_qt_pos(self, qx: float, qy: float):
        try:
            for vx, vy, _label in self._qt_to_vtk_candidates(qx, qy):
                result = self._pick_gizmo_at(vx, vy)
                if result is not None:
                    return result
            return None
        except Exception:
            return None

    def _qt_to_vtk_primary_candidates(self, qx: float, qy: float) -> list[tuple[int, int, str]]:
        """Convert Qt coordinates to one or two primary VTK coordinates only.

        This is used for transform-gizmo probing at the start of an orbit. The
        previous code tried seven tolerance offsets and then fell through to mesh
        picking, which made the first orbit frame pause whenever a gizmo was
        visible. For a drag handle, the exact primary pixel is enough because the
        handles are already thick.
        """
        try:
            h = float(self.plotter.height())
            dpr = float(self.plotter.devicePixelRatioF()) if hasattr(self.plotter, "devicePixelRatioF") else 1.0
        except Exception:
            h, dpr = 0.0, 1.0
        out = [(int(round(qx)), int(round(h - qy)), "qt_no_dpr_primary")]
        if abs(dpr - 1.0) > 0.01:
            out.append((int(round(qx * dpr)), int(round((h - qy) * dpr)), f"qt_dpr_{dpr:.2f}_primary"))
        return out

    def _fast_selection_bounds_for_gizmo(self, indices: list[int], meshes: list[Any]) -> tuple[float, float, float, float, float, float]:
        """Return selected bounds without scanning all vertices when actors exist."""
        try:
            bounds_list = []
            for raw in indices:
                idx = int(raw)
                b = None
                actor = self.actors_by_index.get(idx)
                if actor is not None:
                    try:
                        b = actor.GetBounds()
                    except Exception:
                        b = None
                if b is None:
                    poly = self.polydata_by_index.get(idx)
                    if poly is not None:
                        try:
                            b = poly.GetBounds()
                        except Exception:
                            b = None
                if b is None and 0 <= idx < len(meshes):
                    b = mesh_bounds(meshes[idx])
                if b is not None:
                    bounds_list.append(tuple(float(v) for v in b))
            if not bounds_list:
                return self._selection_world_bounds(indices, meshes)
            return (
                min(b[0] for b in bounds_list), max(b[1] for b in bounds_list),
                min(b[2] for b in bounds_list), max(b[3] for b in bounds_list),
                min(b[4] for b in bounds_list), max(b[5] for b in bounds_list),
            )
        except Exception:
            return self._selection_world_bounds(indices, meshes)

    def _qt_pos_near_transform_gizmo(self, qx: float, qy: float) -> bool:
        """Cheap screen-space guard before doing any VTK gizmo pick.

        Left mouse press is also the start of free orbit. When a transform gizmo
        was visible, the old path did a full VTK pick immediately, even if the
        click was far away from the gizmo. That caused a noticeable pause before
        orbiting. This guard only allows the VTK gizmo picker to run when the
        cursor is inside a generous projected area around the current gizmo.
        """
        try:
            try:
                from laserprog_studio.application.transform_gizmo_api import native_transform_gizmo_near

                if bool(getattr(self, "_native_transform_gizmo_active", False)):
                    return bool(native_transform_gizmo_near(self, qx, qy))
            except Exception:
                pass
            if not self.gizmo_actors:
                return False
            if self.active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                # TEX owns a single face-normal rotation ring.  It is already a
                # small pickable overlay, so let the VTK picker decide directly.
                return True
            if self.active_index is None or not self._transform_tools_available():
                return False
            if self.transform_mode not in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}:
                return False
            meshes = self.current_meshes()
            indices = self._selected_transform_indices()
            if not indices:
                return False

            b_fast = self._fast_selection_bounds_for_gizmo(indices, meshes)
            c = self._bounds_center_tuple(b_fast)
            length = self._gizmo_length_at(c, meshes)
            axes = self._scale_axes_for_selection(indices, meshes) if self.transform_mode == self.TRANSFORM_SCALE else self._gizmo_axis_definitions()

            samples = [c]
            for vec, _color in axes.values():
                samples.append((c[0] + vec[0] * length * 1.35, c[1] + vec[1] * length * 1.35, c[2] + vec[2] * length * 1.35))
                samples.append((c[0] - vec[0] * length * 1.10, c[1] - vec[1] * length * 1.10, c[2] - vec[2] * length * 1.10))

            # Include the selected bounds so scale-frame edges remain pickable
            # even when the frame is wider than the axis handles.
            try:
                xmin, xmax, ymin, ymax, zmin, zmax = [float(v) for v in b_fast]
                samples.extend([
                    (xmin, ymin, zmin), (xmax, ymin, zmin), (xmin, ymax, zmin), (xmax, ymax, zmin),
                    (xmin, ymin, zmax), (xmax, ymin, zmax), (xmin, ymax, zmax), (xmax, ymax, zmax),
                ])
            except Exception:
                pass

            h = float(self.plotter.height())
            cx, cy_vtk, _cz = self._world_to_display(c)
            cx_qt = float(cx)
            cy_qt = h - float(cy_vtk)
            max_r = 0.0
            for p in samples:
                try:
                    sx, sy_vtk, _sz = self._world_to_display(p)
                    sy_qt = h - float(sy_vtk)
                    max_r = max(max_r, math.hypot(float(sx) - cx_qt, sy_qt - cy_qt))
                except Exception:
                    pass
            radius_px = max(42.0, min(max_r + 34.0, max(float(self.plotter.width()), float(self.plotter.height())) * 0.75))
            return math.hypot(float(qx) - cx_qt, float(qy) - cy_qt) <= radius_px
        except Exception:
            # If the guard fails, keep the UI responsive: do not force a pick.
            return False

    def _pick_gizmo_from_qt_pos_fast(self, qx: float, qy: float):
        """Fast gizmo-only pick for mouse press/hover.

        It avoids mesh picking and avoids the tolerance-candidate loop. This keeps
        free orbit startup smooth when a transform gizmo is displayed.
        """
        try:
            try:
                from laserprog_studio.application.transform_gizmo_api import pick_native_transform_gizmo

                native_hit = pick_native_transform_gizmo(self, qx, qy)
                if bool(getattr(self, "_native_transform_gizmo_active", False)):
                    # The native line/point renderer and its screen-space picker
                    # are one coherent system. Falling through to legacy VTK
                    # actors would reintroduce invisible/stale hit targets and
                    # can grab a different axis than the one under the cursor.
                    return native_hit
                if native_hit is not None:
                    return native_hit
            except Exception:
                pass
            if self.active_tool == getattr(self, "TOOL_TEXTURE_PROJECTION", "texture_projection"):
                try:
                    tex_hit = self._pick_texture_rotation_gizmo_from_qt_pos(qx, qy)
                    if tex_hit is not None:
                        return tex_hit
                except Exception:
                    pass
            if not self._qt_pos_near_transform_gizmo(qx, qy):
                return None
            for vx, vy, _label in self._qt_to_vtk_primary_candidates(qx, qy):
                result = self._pick_gizmo_at(vx, vy)
                if result is not None:
                    return result
            return None
        except Exception:
            return None

    def _pick_at(self, x: int, y: int):
        try:
            renderer = self.plotter.renderer

            # First try the three gizmo axes only. This keeps mesh surfaces from
            # stealing clicks and prevents an X arrow click from resolving as Y due
            # to another actor behind it. It runs only on click/drag start.
            try:
                if self.gizmo_actors and self.transform_mode in {self.TRANSFORM_TRANSLATE, self.TRANSFORM_ROTATE, self.TRANSFORM_SCALE}:
                    import vtk
                    gizmo_picker = vtk.vtkPropPicker()
                    gizmo_picker.PickFromListOn()
                    for actor in self._iter_gizmo_pick_actors():
                        gizmo_picker.AddPickList(actor)
                    gizmo_renderers = []
                    if self.gizmo_overlay_renderer is not None:
                        gizmo_renderers.append(self.gizmo_overlay_renderer)
                    gizmo_renderers.append(renderer)
                    for gizmo_renderer in gizmo_renderers:
                        try:
                            gizmo_picker.Pick(int(x), int(y), 0, gizmo_renderer)
                            actor = gizmo_picker.GetActor() or gizmo_picker.GetViewProp()
                            resolved = self._resolve_picked_actor(actor)
                            if resolved is not None and resolved[0] == "gizmo":
                                return resolved
                        except Exception:
                            pass
            except Exception:
                pass

            # PropPicker: fast and sufficient for actors with pickable=True.
            self._picker.Pick(int(x), int(y), 0, renderer)
            actor = self._picker.GetActor() or self._picker.GetViewProp()
            resolved = self._resolve_picked_actor(actor)
            if resolved is not None:
                return resolved

            # Fallback CellPicker: sometimes more robust with some VTK/Qt styles.
            try:
                import vtk
                cell_picker = vtk.vtkCellPicker()
                cell_picker.SetTolerance(0.0008)
                cell_picker.Pick(int(x), int(y), 0, renderer)
                actor = cell_picker.GetActor() or cell_picker.GetViewProp()
                resolved = self._resolve_picked_actor(actor)
                if resolved is not None:
                    return resolved
            except Exception:
                pass
            return None
        except Exception:
            log_exception("pick_at")
            return None

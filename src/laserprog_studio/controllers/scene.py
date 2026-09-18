# -*- coding: utf-8 -*-
from __future__ import annotations
from .._window_deps import *
from ..engraving.roles import role_from_color_hint_or_ignore
from ..services.geometry import bounds_from_vertices_list
from ..rendering.textures import pyvista_texture_for_mesh, apply_texture_to_actor
from ..rendering.incremental_scene import rebuild_scene_optimized
import time
try:
    from laserprog_studio.diagnostics.app_performance_audit import GLOBAL_APP_PERFORMANCE_AUDIT as _APP_AUDIT
except Exception:  # pragma: no cover
    _APP_AUDIT = None
class SceneStateLayer:

    def load_default_3d_model(self) -> None:
        path = EXAMPLES_DIR / "box.3mf"
        if path.exists():
            self.load_3d_model(path)
        else:
            self.ui_log(f"[3D] Example missing: {path}")

    def load_3d_model(self, path: Path) -> None:
        self.ui_log(f"[3D] Loading 3MF: {path}")
        try:
            from laserprog_studio.domain.work_model import ModelStore
            from ..project import replace_active_model_store

            store = ModelStore()
            store.load_3mf(path)
            replace_active_model_store(self, store, mark_dirty=True)
            try:
                project = getattr(self, "project_store", None)
                scene = getattr(project, "active_scene", None) if project is not None else None
                if scene is not None:
                    scene.record_modification(f"Imported 3MF {Path(path).name}", "import", capture_snapshot=True)
            except Exception:
                log_exception("record_import_history")
            try:
                self.ui_log(f"[SELECTION_DIAG] clear_selection begin reason=load_3d_model selected_before={list(getattr(self, 'selected_indices', []))} active_before={getattr(self, 'active_index', None)} mode={getattr(self, 'transform_mode', None)}")
            except Exception:
                pass
            self.selected_indices = []
            self.active_index = None
            self.close_active_tool(log_it=False)
            self.ui_log(f"[3D] 3MF loaded: meshes={len(self.mesh_store.meshes)}")
            self.rebuild_scene()
            self._sync_history_buttons()
            self.sync_scene_tabs()
        except Exception:
            log_exception("load_3d_model")
            self.ui_log("[3D] ERROR loading 3MF (see log file)")

    def current_meshes(self):
        return [] if self.mesh_store is None else self.mesh_store.meshes

    def committed_meshes(self):
        return [] if self.mesh_store is None else self.mesh_store.committed_meshes

    def _selected_transform_indices(self) -> list[int]:
        """Valid selected mesh indices used by transform gizmos.

        The last selected mesh remains the active mesh for inspector focus and for
        local scale orientation, but transforms are applied to every selected mesh.
        """
        try:
            meshes = self.current_meshes()
            seen: set[int] = set()
            out: list[int] = []
            for raw in self.selected_indices:
                idx = int(raw)
                if 0 <= idx < len(meshes) and idx not in seen:
                    out.append(idx)
                    seen.add(idx)
            if not out and self.active_index is not None:
                idx = int(self.active_index)
                if 0 <= idx < len(meshes):
                    out.append(idx)
            return out
        except Exception:
            return []

    @staticmethod
    def _bounds_from_vertices_list(vertices: list[tuple[float, float, float]]) -> tuple[float, float, float, float, float, float]:
        return bounds_from_vertices_list(vertices)

    def _vertices_for_indices(self, indices: list[int], meshes: list[Any] | None = None) -> list[tuple[float, float, float]]:
        meshes = self.current_meshes() if meshes is None else meshes
        out: list[tuple[float, float, float]] = []
        for idx in indices:
            if 0 <= int(idx) < len(meshes):
                out.extend([(float(x), float(y), float(z)) for x, y, z in getattr(meshes[int(idx)], "vertices", [])])
        return out

    def _selection_world_bounds(self, indices: list[int] | None = None, meshes: list[Any] | None = None) -> tuple[float, float, float, float, float, float]:
        idxs = self._selected_transform_indices() if indices is None else list(indices)
        verts = self._vertices_for_indices(idxs, meshes)
        bounds = self._bounds_from_vertices_list(verts)
        try:
            if getattr(self, "_diagnostic_verbose", True):
                self.ui_log(
                    f"[BOUNDS] selection indices={list(idxs)} vertices={len(verts)} "
                    f"bounds=({bounds[0]:.3f},{bounds[1]:.3f},{bounds[2]:.3f},{bounds[3]:.3f},{bounds[4]:.3f},{bounds[5]:.3f})"
                )
        except Exception:
            pass
        return bounds

    def _bounds_center_tuple(self, bounds: tuple[float, float, float, float, float, float]) -> tuple[float, float, float]:
        return ((float(bounds[0]) + float(bounds[1])) * 0.5, (float(bounds[2]) + float(bounds[3])) * 0.5, (float(bounds[4]) + float(bounds[5])) * 0.5)

    def _selection_center(self, indices: list[int] | None = None, meshes: list[Any] | None = None) -> tuple[float, float, float]:
        return self._bounds_center_tuple(self._selection_world_bounds(indices, meshes))

    def _active_or_first_selected_index(self, indices: list[int] | None = None) -> int | None:
        idxs = self._selected_transform_indices() if indices is None else list(indices)
        if self.active_index in idxs:
            return int(self.active_index)  # type: ignore[arg-type]
        return idxs[-1] if idxs else None

    def _scale_axes_for_selection(self, indices: list[int] | None = None, meshes: list[Any] | None = None) -> dict[str, tuple[tuple[float, float, float], str]]:
        meshes = self.current_meshes() if meshes is None else meshes
        idx = self._active_or_first_selected_index(indices)
        if idx is not None and 0 <= idx < len(meshes):
            return self._local_scale_axis_definitions_for_mesh(meshes[idx])
        return self._gizmo_axis_definitions()

    def _oriented_bounds_for_selection(self, indices: list[int] | None = None, meshes: list[Any] | None = None) -> tuple[tuple[float, float, float, float, float, float], tuple[float, float, float], dict[str, tuple[tuple[float, float, float], str]]]:
        try:
            import numpy as np
            meshes = self.current_meshes() if meshes is None else meshes
            idxs = self._selected_transform_indices() if indices is None else list(indices)
            if len(idxs) == 1 and 0 <= idxs[0] < len(meshes):
                return self._oriented_bounds_for_mesh(meshes[idxs[0]])
            axes = self._scale_axes_for_selection(idxs, meshes)
            pts = np.asarray(self._vertices_for_indices(idxs, meshes), dtype=float)
            if pts.size == 0:
                b = self._selection_world_bounds(idxs, meshes)
                return b, self._bounds_center_tuple(b), axes
            ax = np.asarray(axes["x"][0], dtype=float)
            ay = np.asarray(axes["y"][0], dtype=float)
            az = np.asarray(axes["z"][0], dtype=float)
            coords = np.column_stack((pts @ ax, pts @ ay, pts @ az))
            mins = coords.min(axis=0)
            maxs = coords.max(axis=0)
            mids = (mins + maxs) * 0.5
            center = ax * mids[0] + ay * mids[1] + az * mids[2]
            bounds = (float(mins[0]), float(maxs[0]), float(mins[1]), float(maxs[1]), float(mins[2]), float(maxs[2]))
            return bounds, (float(center[0]), float(center[1]), float(center[2])), axes
        except Exception:
            b = self._selection_world_bounds(indices, meshes)
            return b, self._bounds_center_tuple(b), self._gizmo_axis_definitions()
    def push_meshes(self, meshes, reason: str, *, semantic_operation_type: str | None = None) -> None:
        if self.mesh_store is None:
            from laserprog_studio.domain.work_model import ModelStore
            from ..project import replace_active_model_store

            replace_active_model_store(self, ModelStore(), mark_dirty=False)
        self.mesh_store.set_meshes(
            meshes,
            source_path=getattr(self.mesh_store, "source_path", None),
            push_undo=True,
            max_undo=int(getattr(self, "_history_limit", 10)),
        )
        if semantic_operation_type:
            try:
                project = getattr(self, "project_store", None)
                scene = getattr(project, "active_scene", None) if project is not None else None
                if scene is not None:
                    scene.record_modification(str(reason), str(semantic_operation_type), capture_snapshot=True)
            except Exception:
                log_exception("record_scene_semantic_history")
        try:
            from ..project import mark_project_dirty

            mark_project_dirty(self)
        except Exception:
            pass
        self.ui_log(f"[MODEL] {reason} | meshes={len(meshes)}")
        self.rebuild_scene(keep_camera=True)
        self._sync_history_buttons()
        self.sync_scene_tabs()
    def rebuild_scene(self, keep_camera: bool = False) -> None:
        start = time.perf_counter()
        try:
            rebuild_scene_optimized(self, keep_camera=keep_camera)
        finally:
            if _APP_AUDIT is not None:
                try:
                    _APP_AUDIT.record_timing("scene.rebuild", (time.perf_counter() - start) * 1000.0, details={"keep_camera": keep_camera, "mesh_count": len(self.current_meshes()) if callable(getattr(self, "current_meshes", None)) else "?"})
                except Exception:
                    pass

    def set_stable_iso_camera(self, reset: bool = False) -> None:
        try:
            meshes = self.current_meshes()
            b = scene_bounds(meshes)
            cx, cy, cz = ((b[0]+b[1])/2, (b[2]+b[3])/2, (b[4]+b[5])/2)
            import numpy as np
            size = bounds_size(b)
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
        except Exception:
            log_exception("set_stable_iso_camera")

    def refresh_actor_styles(self, render: bool = True) -> None:
        try:
            from ..rendering.materials import actor_style_for_mesh, apply_actor_style
            meshes = self.current_meshes()
            render_state = getattr(self, "render_state", None)
            mode = getattr(render_state, "display_mode", "wireframe")
            edge_toggle = bool(getattr(render_state, "show_edges_overlay", getattr(self, "show_edges", True)))
            for i, actor in self.actors_by_index.items():
                prop = actor.GetProperty()
                mesh = meshes[i] if i < len(meshes) else None
                if mesh is not None:
                    apply_actor_style(actor, actor_style_for_mesh(mesh, mode, show_edges=edge_toggle))
                    if str(mode) == "material": apply_texture_to_actor(self, actor, mesh, reason="refresh_actor_styles")
                    getattr(self, "_apply_material_lighting_to_actor", lambda _actor: None)(actor)
                    base = parse_hex_color(getattr(mesh, "color", "#B8B8B8"))
                else:
                    base = (0.72, 0.72, 0.72)
                if self.has_preview() and mesh is not None:
                    current_color = prop.GetColor() if hasattr(prop, "GetColor") else base
                    prop.SetColor(min(float(current_color[0]) + 0.10, 1), min(float(current_color[1]) + 0.10, 1), min(float(current_color[2]) + 0.18, 1))
                if i in self.selected_indices:
                    prop.SetEdgeVisibility(True); prop.SetLineWidth(4); prop.SetOpacity(1.0)
                    if self.active_tool == self.TOOL_ENGRAVING:
                        prop.SetColor(*base)
                    elif str(mode) == "material": pass  # keep material color; selection uses thick edges
                    elif i == self.active_index:
                        prop.SetColor(1.0, 0.58, 0.05)
                    else:
                        prop.SetColor(0.05, 0.70, 1.0)
                else:
                    prop.SetEdgeVisibility(bool(edge_toggle)); prop.SetLineWidth(1); prop.SetOpacity(0.35 if self.show_ghost and self.selected_indices else (prop.GetOpacity() if hasattr(prop, "GetOpacity") else 1.0))
            getattr(self, "_sync_material_scene_rendering", lambda **_kwargs: None)(render=False)
            if render:
                self.plotter.render()
        except Exception:
            log_exception("refresh_actor_styles")
    def _sync_mesh_list_selection(self) -> None:
        """Mirror the 3D selection in the left Parts list."""
        try:
            widget = getattr(self, "mesh_list", None)
            if widget is None:
                return
            selected = {int(i) for i in getattr(self, "selected_indices", [])}
            active = getattr(self, "active_index", None)
            widget.blockSignals(True)
            widget.clearSelection()
            for row in range(widget.count()):
                item = widget.item(row)
                if item is None:
                    continue
                mesh_index = item.data(Qt.UserRole)
                try:
                    mesh_index = int(mesh_index)
                except Exception:
                    mesh_index = row
                item.setSelected(mesh_index in selected)
            if isinstance(active, int) and 0 <= active < widget.count():
                widget.setCurrentRow(int(active), QItemSelectionModel.NoUpdate)
            else:
                widget.setCurrentRow(-1, QItemSelectionModel.NoUpdate)
            widget.blockSignals(False)
        except Exception:
            try:
                widget.blockSignals(False)
            except Exception:
                pass
            log_exception("sync_mesh_list_selection")


    def set_selection_indices(self, indices: list[int], *, reason: str = "selection") -> None:
        """Set a complete multi-selection in one update pass.

        This is used by Ctrl+A and rectangle selection. It avoids calling
        select_index repeatedly, which would rebuild styles/gizmos once per
        part and becomes expensive on large scenes.
        """
        try:
            valid_actor_indices = set(int(i) for i in self.actors_by_index.keys())
            cleaned: list[int] = []
            for raw in indices or []:
                value = int(raw)
                if value in valid_actor_indices and value not in cleaned:
                    cleaned.append(value)
            previous = tuple(int(v) for v in getattr(self, "selected_indices", []) or [])
            self.selected_indices = cleaned
            self.active_index = cleaned[-1] if cleaned else None
            self._gizmo_delta_display_signature = None
            self._gizmo_pressed_axis = None
            self._gizmo_press_pos = None
            self._hovered_transform_axis = None
            self._highlighted_transform_axis = None
            changed = previous != tuple(cleaned)
            try:
                self.ui_log(f"[SELECTION] set reason={reason} count={len(cleaned)} active={self.active_index} indices={cleaned}")
                self.ui_log(f"[SELECTION_DIAG] set_selection_indices changed={changed} actors={list(self.actors_by_index.keys())} mode={self.transform_mode}")
            except Exception:
                pass
            self.refresh_actor_styles(render=False)
            self._sync_mesh_list_selection()
            self.update_gizmo(render=False)
            if self.active_tool == self.TOOL_MOD_SPLIT:
                if changed:
                    self._reset_split_plane_for_current_selection(render=False, update_size=True)
                else:
                    self._sync_modifier_plane_actor(render=False)
            self._sync_boolean_buttons()
            self._sync_modifier_buttons()
            self.update_inspector()
            self.update_joint_info()
            notify_creator = getattr(self, "notify_active_creator_selection_changed", None)
            if callable(notify_creator):
                notify_creator()
            try:
                self.plotter.render()
            except Exception:
                pass
        except Exception:
            log_exception("set_selection_indices")

    def select_all_parts(self) -> None:
        """Select every visible mesh actor in one pass (Ctrl+A)."""
        try:
            if getattr(self, "active_tool", self.TOOL_NONE) not in {self.TOOL_NONE, self.TOOL_MOD_SPLIT}:
                try:
                    self.statusBar().showMessage("Select all is disabled while this tool is active", 1600)
                except Exception:
                    pass
                return
            indices = sorted(int(i) for i in self.actors_by_index.keys())
            self.set_selection_indices(indices, reason="select all")
        except Exception:
            log_exception("select_all_parts")

    def select_index(self, idx: int, *, toggle: bool = False) -> None:
        if idx not in self.actors_by_index:
            try:
                self.ui_log(f"[SELECTION_DIAG] select_index rejected idx={idx} actors={list(self.actors_by_index.keys())}")
            except Exception:
                pass
            return
        previous_selection = tuple(int(v) for v in self.selected_indices)
        try:
            self.ui_log(f"[SELECTION_DIAG] select_index begin idx={idx} toggle={toggle} previous={list(previous_selection)} active_before={self.active_index} tool={self.active_tool} mode={self.transform_mode}")
        except Exception:
            pass
        if self.active_tool == self.TOOL_JOINT:
            # Joint mode has its own A/B selection workflow. Clicking an already
            # selected board removes it again, even without Shift. This restores
            # the intended "click again to remove" behavior and keeps the
            # selection limited to two boards.
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
            else:
                self.selected_indices.append(idx)
                if len(self.selected_indices) > 2:
                    self.selected_indices = self.selected_indices[-2:]
        elif self._active_tool_allows_scene_multi_selection() and toggle:
            # Shift+click toggles membership in the current selection set.  This
            # must also work while passive multi-selection tools are open, notably
            # VOL, otherwise the tool collapses back to a single piece.
            if idx in self.selected_indices:
                self.selected_indices.remove(idx)
            else:
                self.selected_indices.append(idx)
        else:
            self.selected_indices = [idx]
        # Keep order stable and remove duplicates while preserving the last click order.
        cleaned: list[int] = []
        for raw in self.selected_indices:
            value = int(raw)
            if value in self.actors_by_index and value not in cleaned:
                cleaned.append(value)
        self.selected_indices = cleaned
        selection_changed = tuple(int(v) for v in self.selected_indices) != previous_selection
        self.active_index = idx if idx in self.selected_indices else (self.selected_indices[-1] if self.selected_indices else None)
        self._gizmo_delta_display_signature = None
        self._hovered_transform_axis = None
        self._highlighted_transform_axis = None
        # Keep the chosen transform mode persistent. If there is no active part,
        # update_gizmo() will clear the overlay, but the T/R/S mode stays selected
        # so the next selected part immediately gets the same transform tool.
        self.ui_log(f"[SELECTION] tool={self.active_tool} indices={self.selected_indices} active={self.active_index}")
        try:
            self.ui_log(f"[SELECTION_DIAG] select_index cleaned={self.selected_indices} changed={selection_changed} actors={list(self.actors_by_index.keys())} mode={self.transform_mode}")
        except Exception:
            pass
        self.refresh_actor_styles(render=False)
        self._sync_mesh_list_selection()
        self.update_gizmo(render=False)
        if self.active_tool == self.TOOL_MOD_SPLIT:
            if selection_changed:
                self._reset_split_plane_for_current_selection(render=False, update_size=True)
            else:
                self._sync_modifier_plane_actor(render=False)
        self._sync_boolean_buttons()
        self._sync_modifier_buttons()
        self.plotter.render()
        self.update_inspector()
        self.update_joint_info()
        notify_creator = getattr(self, "notify_active_creator_selection_changed", None)
        if callable(notify_creator):
            notify_creator()

    def clear_selection(self, reason: str = "empty click") -> None:
        try:
            had_selection = bool(self.selected_indices or self.active_index is not None)
            try:
                self.ui_log(f"[SELECTION_DIAG] clear_selection begin reason={reason} selected_before={list(getattr(self, 'selected_indices', []))} active_before={getattr(self, 'active_index', None)} mode={getattr(self, 'transform_mode', None)}")
            except Exception:
                pass
            self.selected_indices = []
            self.active_index = None
            self._gizmo_delta_display_signature = None
            self._gizmo_pressed_axis = None
            self._gizmo_press_pos = None
            self._hovered_transform_axis = None
            self._highlighted_transform_axis = None
            try:
                self.mesh_list.clearSelection()
            except Exception:
                pass
            # Do not reset the transform mode on empty clicks. The user explicitly
            # controls the transform overlay with the N/T/R/S buttons. With no
            # selected part, update_gizmo() simply clears the overlay actors.
            self.update_gizmo(render=False)
            if self.active_tool == self.TOOL_MOD_SPLIT:
                self._reset_split_plane_for_current_selection(render=False, update_size=False)
            self.refresh_actor_styles(render=False)
            self._sync_mesh_list_selection()
            self._sync_boolean_buttons()
            self._sync_modifier_buttons()
            self.update_inspector()
            self.update_joint_info()
            notify_creator = getattr(self, "notify_active_creator_selection_changed", None)
            if callable(notify_creator):
                notify_creator()
            self.plotter.render()
            if had_selection:
                self.ui_log(f"[SELECTION] Cleared by {reason}")
            else:
                self.ui_log(f"[PICKING] Empty click {reason}")
        except Exception:
            log_exception("clear_selection")

    def on_list_clicked(self, item) -> None:
        try:
            idx = int(item.data(Qt.UserRole))
            additive = bool(QApplication.keyboardModifiers() & Qt.ShiftModifier)
            self.select_index(idx, toggle=additive)
        except Exception:
            log_exception("on_list_clicked")

    def update_inspector(self) -> None:
        meshes = self.current_meshes()
        indices = self._selected_transform_indices()
        if not indices:
            self.selection_label.setText("No selection")
            self.bounds_label.setText("Dimensions: -")
            self._set_spin_values_blocked({
                self.pos_x: 0.0, self.pos_y: 0.0, self.pos_z: 0.0,
                self.rot_x: 0.0, self.rot_y: 0.0, self.rot_z: 0.0,
                self.scale_x: 0.0, self.scale_y: 0.0, self.scale_z: 0.0,
            })
            self._sync_light_transform_fields()
            return
        active = self._active_or_first_selected_index(indices)
        if active is None or active >= len(meshes):
            self.selection_label.setText("No selection")
            self.bounds_label.setText("Dimensions: -")
            self._set_spin_values_blocked({
                self.pos_x: 0.0, self.pos_y: 0.0, self.pos_z: 0.0,
                self.rot_x: 0.0, self.rot_y: 0.0, self.rot_z: 0.0,
                self.scale_x: 0.0, self.scale_y: 0.0, self.scale_z: 0.0,
            })
            self._sync_light_transform_fields()
            return
        m = meshes[active]
        local_bounds, c, _local_axes = self._oriented_bounds_for_selection(indices, meshes)
        dims = (local_bounds[1] - local_bounds[0], local_bounds[3] - local_bounds[2], local_bounds[5] - local_bounds[4])
        role = role_from_color_hint_or_ignore(getattr(m, "color", "#B8B8B8"))
        if len(indices) == 1:
            self.selection_label.setText(f"Active: {active:02d} - {m.name}\nRole: {role} | Color: {getattr(m, 'color', '#B8B8B8')}\nSelection: {indices}")
        else:
            self.selection_label.setText(f"Multiple selection: {len(indices)} parts\nActive: {active:02d} - {m.name}\nSelection: {indices}")
        self.bounds_label.setText(
            f"Dimensions: X={dims[0]:.3f}  Y={dims[1]:.3f}  Z={dims[2]:.3f}\n"
            f"Center position: X={c[0]:.3f} Y={c[1]:.3f} Z={c[2]:.3f}"
        )
        # Position and size are group values when several parts are selected.
        # Rotation stays focused on the active part; editing it applies the delta
        # to the whole selection around the group center.
        rx, ry, rz = self._mesh_rotation_euler(m)
        self._set_spin_values_blocked({
            self.pos_x: c[0], self.pos_y: c[1], self.pos_z: c[2],
            self.rot_x: rx, self.rot_y: ry, self.rot_z: rz,
            self.scale_x: max(float(dims[0]), 0.001),
            self.scale_y: max(float(dims[1]), 0.001),
            self.scale_z: max(float(dims[2]), 0.001),
        })
        self._sync_light_transform_fields()

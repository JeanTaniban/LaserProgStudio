# -*- coding: utf-8 -*-
from __future__ import annotations

from ..engraving.roles import role_from_color_hint_or_ignore

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from ..mesh_ops import workmesh_to_polydata
from .display_lod import make_display_lod_mesh
from ..studio_log import log_exception
from .textures import pyvista_texture_for_mesh, apply_texture_to_actor


def _safe_hash_sequence(values: Any) -> int:
    """Return a stable-enough in-process hash for render-cache diffing."""
    try:
        return hash(tuple(values or ()))
    except Exception:
        try:
            normalised = []
            for item in list(values or ()):  # type: ignore[arg-type]
                if isinstance(item, (list, tuple)):
                    normalised.append(tuple(item))
                else:
                    normalised.append(repr(item))
            return hash(tuple(normalised))
        except Exception:
            return hash(repr(values))


def _mesh_render_signature(mesh: Any) -> tuple[Any, ...]:
    """Fingerprint data that affects a PyVista mesh actor.

    The old scene path destroyed every actor after each add/delete/operation.
    Fingerprints let us keep unchanged actors, including after index shifts.
    """
    vertices = getattr(mesh, "vertices", []) or []
    triangles = getattr(mesh, "triangles", []) or []
    uvs = getattr(mesh, "uvs", None) or []
    return (
        str(getattr(mesh, "name", "")),
        str(getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"),
        repr(getattr(mesh, "material", None)),
        repr(getattr(mesh, "engraving", None)),
        repr(getattr(mesh, "texture_projections", None)),
        len(vertices),
        len(triangles),
        len(uvs),
        _safe_hash_sequence(vertices),
        _safe_hash_sequence(triangles),
        _safe_hash_sequence(uvs),
    )




def _point_tuple(value: Any) -> tuple[float, float, float] | None:
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except Exception:
        return None


def _polydata_points_match_mesh(poly: Any, mesh: Any) -> bool:
    """Cheap guard against stale live-edited VTK points.

    Transform drags edit the displayed polydata in-place.  If the render
    signature cache is stale, an undo/redo incremental rebuild may otherwise
    reuse that actor even though the model mesh has moved back.  Sampling avoids
    a full point-by-point scan on large meshes while still catching ordinary
    translate/rotate/scale drifts.
    """
    try:
        vertices = getattr(mesh, "vertices", []) or []
        points = getattr(poly, "points", None)
        if points is None:
            return True
        if len(points) != len(vertices):
            return False
        count = len(vertices)
        if count <= 0:
            return True
        samples = {0, count // 2, count - 1}
        for idx in samples:
            a = _point_tuple(points[idx])
            b = _point_tuple(vertices[idx])
            if a is None or b is None:
                return False
            if max(abs(a[0] - b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) > 1.0e-7:
                return False
        return True
    except Exception:
        return True


def _sync_polydata_points_to_mesh(poly: Any, mesh: Any) -> bool:
    """Force reused actor geometry back to the authoritative WorkMesh."""
    try:
        if _polydata_points_match_mesh(poly, mesh):
            return False
        import numpy as np

        poly.points = np.asarray(getattr(mesh, "vertices", []) or [], dtype=float)
        try:
            poly.modified()
        except Exception:
            try:
                poly.Modified()
            except Exception:
                pass
        return True
    except Exception:
        return False


def sync_mesh_render_signatures(w: Any, indices: list[int] | tuple[int, ...] | set[int] | None = None) -> None:
    """Synchronise render fingerprints after live in-place mesh edits.

    The incremental renderer relies on signatures to decide whether an existing
    actor can be reused.  Gizmo drags mutate mesh vertices and polydata without a
    scene rebuild, so the cache must be refreshed at drag end before undo/redo.
    """
    try:
        meshes = list(w.current_meshes())
        signatures = dict(getattr(w, "_scene_mesh_render_signatures", {}) or {})
        if indices is None:
            target = range(len(meshes))
        else:
            target = [int(i) for i in indices]
        for i in target:
            if 0 <= int(i) < len(meshes):
                signatures[int(i)] = _mesh_render_signature(meshes[int(i)])
            else:
                signatures.pop(int(i), None)
        w._scene_mesh_render_signatures = signatures
    except Exception:
        pass

def _mesh_label_text(w: Any, index: int, mesh: Any) -> str:
    suffix = " [preview]" if w.has_preview() else ""
    is_camera = getattr(w, "_is_render_camera_mesh", lambda _m: False)(mesh)
    role = " [camera]" if is_camera else f" [{role_from_color_hint_or_ignore(getattr(mesh, 'color', '#B8B8B8'))}]"
    return f"{int(index):02d} - {getattr(mesh, 'name', 'part')}{role}{suffix}"


def _refresh_mesh_list(w: Any, meshes: list[Any]) -> None:
    widget = getattr(w, "mesh_list", None)
    if widget is None:
        return
    try:
        labels = tuple(_mesh_label_text(w, i, mesh) for i, mesh in enumerate(meshes))
        if labels == tuple(getattr(w, "_mesh_list_signature", ()) or ()) and widget.count() == len(labels):
            return
        widget.blockSignals(True)
        widget.clear()
        for i, label in enumerate(labels):
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, i)
            widget.addItem(item)
        w._mesh_list_signature = labels
        widget.blockSignals(False)
    except Exception:
        try:
            widget.blockSignals(False)
        except Exception:
            pass
        log_exception("incremental_scene.refresh_mesh_list")


def _next_mesh_actor_name(w: Any) -> str:
    """Return a renderer-unique name for a mesh actor.

    PyVista treats the ``name`` argument of ``add_mesh`` as a replacement key:
    adding a new actor with a name already present in the renderer removes the
    previous actor.  The first incremental renderer used ``mesh_<index>`` names,
    but reused actors after a delete can keep their old renderer name while being
    remapped to a new list index.  A later add at the old index could then erase
    that unrelated reused actor.  Actor names must therefore be immutable, unique
    instance ids, while ``actors_by_index`` remains the source of truth for the
    current model index.
    """
    try:
        value = int(getattr(w, "_scene_mesh_actor_name_counter", 0)) + 1
    except Exception:
        value = 1
    try:
        setattr(w, "_scene_mesh_actor_name_counter", value)
    except Exception:
        pass
    return f"lp_mesh_actor_{value}"


def _add_mesh_actor(w: Any, index: int, mesh: Any) -> tuple[Any | None, Any | None, int, int]:
    display_mesh, lod_info = make_display_lod_mesh(
        mesh,
        threshold=int(getattr(w, "_display_lod_threshold_triangles", 80_000)),
        target=int(getattr(w, "_display_lod_target_triangles", 55_000)),
    )
    poly = workmesh_to_polydata(display_mesh)
    texture = pyvista_texture_for_mesh(w, mesh)
    mesh_kwargs = {"texture": texture} if texture is not None else {"color": getattr(mesh, "color", "#B8B8B8") or "#B8B8B8"}
    actor_name = _next_mesh_actor_name(w)
    kwargs = dict(
        mesh_kwargs,
        show_edges=getattr(w, "show_edges", True),
        edge_color="#222222",
        name=actor_name,
        pickable=True,
        lighting=True,
    )
    try:
        actor = w.plotter.add_mesh(poly, **kwargs, render=False)
    except TypeError:
        actor = w.plotter.add_mesh(poly, **kwargs)
    try:
        setattr(actor, "_laserprog_scene_actor_name", actor_name)
    except Exception:
        pass
    try:
        setattr(actor, "_laserprog_display_lod", lod_info)
    except Exception:
        pass
    try:
        setattr(poly, "_laserprog_display_lod", lod_info)
    except Exception:
        pass
    if bool(getattr(lod_info, "enabled", False)):
        try:
            w.ui_log(
                f"[LOD] Display LOD part={index} tris={lod_info.original_triangles} -> "
                f"{lod_info.displayed_triangles} stride={lod_info.stride}"
            )
        except Exception:
            pass
    if texture is not None:
        apply_texture_to_actor(w, actor, mesh, texture, reason="rebuild_scene")
    return actor, poly, int(getattr(poly, "n_points", 0)), int(getattr(poly, "n_cells", 0))


def _remove_actor(w: Any, actor: Any) -> None:
    if actor is None:
        return
    try:
        w.plotter.remove_actor(actor, render=False)
    except TypeError:
        try:
            w.plotter.remove_actor(actor)
        except Exception:
            pass
    except Exception:
        pass


def _clear_actor_maps(w: Any) -> None:
    w.actors_by_index.clear()
    w.polydata_by_index.clear()
    w.actor_key_by_vtk.clear()
    w.actor_key_by_addr.clear()


def _register_actor_maps(w: Any, actors: dict[int, Any], polydata: dict[int, Any]) -> None:
    _clear_actor_maps(w)
    w.actors_by_index.update(actors)
    w.polydata_by_index.update(polydata)
    for i, actor in actors.items():
        w.actor_key_by_vtk[id(actor)] = int(i)
        try:
            w.actor_key_by_addr[actor.GetAddressAsString("")] = int(i)
        except Exception:
            pass




def _scene_render_signatures(meshes: list[Any]) -> dict[int, tuple[Any, ...]]:
    return {i: _mesh_render_signature(mesh) for i, mesh in enumerate(meshes)}


def _unchanged_actor_scene(w: Any, meshes: list[Any]) -> tuple[int, int, dict[int, tuple[Any, ...]]] | None:
    """Return point/cell totals when a rebuild request has no mesh diff.

    Some controllers call ``rebuild_scene`` as a conservative refresh.  If the
    WorkMesh render signatures and actor maps already match, actor removal/addition
    is pure churn and shows up as global render jank.
    """
    try:
        new_signatures = _scene_render_signatures(meshes)
        old_signatures = dict(getattr(w, "_scene_mesh_render_signatures", {}) or {})
        actors = dict(getattr(w, "actors_by_index", {}) or {})
        polydata = dict(getattr(w, "polydata_by_index", {}) or {})
        if old_signatures != new_signatures:
            return None
        if set(actors.keys()) != set(range(len(meshes))) or set(polydata.keys()) != set(range(len(meshes))):
            return None
        total_points = sum(int(getattr(poly, "n_points", 0)) for poly in polydata.values())
        total_cells = sum(int(getattr(poly, "n_cells", 0)) for poly in polydata.values())
        return total_points, total_cells, new_signatures
    except Exception:
        return None

def _full_rebuild(w: Any, meshes: list[Any]) -> tuple[int, int, str]:
    w._clear_gizmo_actors()
    w._active_pyvista_textures = []
    w.plotter.clear()
    w.material_floor_actor = None
    w._material_floor_signature = None
    w.material_shadow_actors = {}
    w._material_shadow_signature = None
    w._material_shadow_pass_enabled = False
    w._material_key_light = None
    w._material_fill_light = None
    w.floor_grid_actor = None
    try:
        w.laser_area_actor = None
    except Exception:
        pass
    _clear_actor_maps(w)
    total_points = 0
    total_cells = 0
    if bool(getattr(w, "show_floor_grid", False)):
        w._update_floor_grid_actor(render=False)
    else:
        try:
            w._update_laser_area_actor(render=False)
        except Exception:
            pass
    for i, mesh in enumerate(meshes):
        actor, poly, pts, cells = _add_mesh_actor(w, i, mesh)
        if actor is None or poly is None:
            continue
        w.actors_by_index[i] = actor
        w.polydata_by_index[i] = poly
        w.actor_key_by_vtk[id(actor)] = i
        try:
            w.actor_key_by_addr[actor.GetAddressAsString("")] = i
        except Exception:
            pass
        total_points += pts
        total_cells += cells
    w._scene_mesh_render_signatures = {i: _mesh_render_signature(mesh) for i, mesh in enumerate(meshes)}
    w._scene_rebuild_generation = int(getattr(w, "_scene_rebuild_generation", 0)) + 1
    return total_points, total_cells, "full"


def _incremental_rebuild(w: Any, meshes: list[Any]) -> tuple[int, int, str] | None:
    if not bool(getattr(w, "_scene_incremental_rebuild_enabled", True)):
        return None
    old_actors = dict(getattr(w, "actors_by_index", {}) or {})
    old_polydata = dict(getattr(w, "polydata_by_index", {}) or {})
    old_signatures = dict(getattr(w, "_scene_mesh_render_signatures", {}) or {})
    if not old_actors and meshes:
        return None
    new_signatures = {i: _mesh_render_signature(mesh) for i, mesh in enumerate(meshes)}
    signature_to_old: dict[tuple[Any, ...], list[int]] = {}
    for old_i, sig in old_signatures.items():
        if int(old_i) in old_actors:
            signature_to_old.setdefault(sig, []).append(int(old_i))
    for bucket in signature_to_old.values():
        bucket.sort()
    used_old: set[int] = set()
    new_actors: dict[int, Any] = {}
    new_polydata: dict[int, Any] = {}
    total_points = 0
    total_cells = 0
    added = reused = shifted = 0
    for i, mesh in enumerate(meshes):
        sig = new_signatures[i]
        old_i = None
        bucket = signature_to_old.get(sig) or []
        while bucket:
            candidate = int(bucket.pop(0))
            if candidate not in used_old:
                old_i = candidate
                break
        if old_i is not None:
            actor = old_actors.get(old_i)
            poly = old_polydata.get(old_i)
            if actor is not None and poly is not None:
                _sync_polydata_points_to_mesh(poly, mesh)
                new_actors[i] = actor
                new_polydata[i] = poly
                used_old.add(old_i)
                reused += 1
                shifted += int(old_i != i)
                total_points += int(getattr(poly, "n_points", 0))
                total_cells += int(getattr(poly, "n_cells", 0))
                continue
        actor, poly, pts, cells = _add_mesh_actor(w, i, mesh)
        if actor is None or poly is None:
            continue
        new_actors[i] = actor
        new_polydata[i] = poly
        total_points += pts
        total_cells += cells
        added += 1
    removed = 0
    for old_i, actor in old_actors.items():
        if int(old_i) not in used_old:
            _remove_actor(w, actor)
            removed += 1
    _register_actor_maps(w, new_actors, new_polydata)
    w._scene_mesh_render_signatures = new_signatures
    w._scene_rebuild_generation = int(getattr(w, "_scene_rebuild_generation", 0)) + 1
    if bool(getattr(w, "show_floor_grid", False)):
        w._update_floor_grid_actor(render=False)
    elif getattr(w, "floor_grid_actor", None) is not None:
        _remove_actor(w, getattr(w, "floor_grid_actor", None))
        w.floor_grid_actor = None
        try:
            w._update_laser_area_actor(render=False)
        except Exception:
            pass
    else:
        try:
            w._update_laser_area_actor(render=False)
        except Exception:
            pass
    return total_points, total_cells, f"incremental reused={reused} added={added} removed={removed} shifted={shifted}"


def _finish(w: Any, meshes: list[Any], *, keep_camera: bool, cam_position: Any, total_points: int, total_cells: int, mode_label: str) -> None:
    _refresh_mesh_list(w, meshes)
    w.selected_indices = [i for i in w.selected_indices if i in w.actors_by_index]
    allowed_multi = {
        w.TOOL_NONE,
        w.TOOL_JOINT,
        w.TOOL_MOD_SPLIT,
        w.TOOL_MOD_SIMPLIFY,
        w.TOOL_MOD_RELIEF,
        getattr(w, "TOOL_MOD_HOLLOW", "modifier_hollow"),
        getattr(w, "TOOL_TEXTURE_PROJECTION", "texture_projection"),
    }
    if w.active_tool not in allowed_multi and len(w.selected_indices) > 1:
        w.selected_indices = w.selected_indices[-1:]
    w.active_index = w.selected_indices[-1] if w.selected_indices else None
    w._sync_mesh_list_selection()
    if cam_position is not None:
        w.plotter.camera_position = cam_position
    elif not keep_camera:
        w.set_stable_iso_camera(reset=True)
    w.refresh_actor_styles(render=False)
    w.update_gizmo(render=False)
    w._sync_modifier_plane_actor(render=False)
    w._sync_boolean_buttons()
    w._sync_history_buttons()
    w.plotter.render()
    w.update_inspector()
    w.ui_log(f"[3D] Scene OK: actors={len(w.actors_by_index)} points={total_points} cells={total_cells} mode={mode_label}")


def rebuild_scene_optimized(w: Any, *, keep_camera: bool = False) -> None:
    meshes = list(w.current_meshes())
    w.ui_log("[3D] Rebuild PyVista scene - start")
    try:
        try:
            cam_position = w.plotter.camera_position if keep_camera else None
        except Exception:
            cam_position = None
        unchanged = _unchanged_actor_scene(w, meshes) if keep_camera else None
        if unchanged is not None:
            total_points, total_cells, _signatures = unchanged
            _finish(
                w,
                meshes,
                keep_camera=keep_camera,
                cam_position=cam_position,
                total_points=total_points,
                total_cells=total_cells,
                mode_label="unchanged fast-refresh",
            )
            return
        # Gizmos depend on current actor bounds.  Clear them, then recreate once
        # actors are synced.  Mesh actors themselves are diffed/reused below.
        w._clear_gizmo_actors()
        result = _incremental_rebuild(w, meshes) if keep_camera else None
        if result is None:
            result = _full_rebuild(w, meshes)
        total_points, total_cells, mode_label = result
        _finish(
            w,
            meshes,
            keep_camera=keep_camera,
            cam_position=cam_position,
            total_points=total_points,
            total_cells=total_cells,
            mode_label=mode_label,
        )
    except Exception:
        log_exception("rebuild_scene")


__all__ = ["rebuild_scene_optimized", "sync_mesh_render_signatures"]

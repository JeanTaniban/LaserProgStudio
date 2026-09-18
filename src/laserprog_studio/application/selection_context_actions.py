# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable

from laserprog_studio.domain.work_model import WorkMesh, reset_mesh_ids
from laserprog_studio.project import ensure_project_store, mark_project_dirty, sync_window_to_active_scene
from laserprog_studio.services.geometry import bounds_from_vertices_list


@dataclass(slots=True)
class OpenSelectionInSceneResult:
    scene_id: str
    scene_name: str
    mesh_count: int
    center: tuple[float, float, float]


def _selected_indices(owner: Any, indices: Iterable[int] | None = None) -> list[int]:
    if indices is None:
        getter = getattr(owner, "_selected_transform_indices", None)
        if callable(getter):
            try:
                indices = getter()
            except Exception:
                indices = None
    if indices is None:
        indices = getattr(owner, "selected_indices", []) or []
    meshes = list(owner.current_meshes()) if callable(getattr(owner, "current_meshes", None)) else list(getattr(getattr(owner, "mesh_store", None), "meshes", []) or [])
    cleaned: list[int] = []
    for raw in indices or []:
        try:
            idx = int(raw)
        except Exception:
            continue
        if 0 <= idx < len(meshes) and idx not in cleaned:
            cleaned.append(idx)
    return cleaned


def _translate_meshes_to_origin(meshes: list[WorkMesh]) -> tuple[list[WorkMesh], tuple[float, float, float]]:
    vertices: list[tuple[float, float, float]] = []
    for mesh in meshes:
        vertices.extend([(float(x), float(y), float(z)) for x, y, z in getattr(mesh, "vertices", []) or []])
    if not vertices:
        return meshes, (0.0, 0.0, 0.0)
    bounds = bounds_from_vertices_list(vertices)
    center = (
        (float(bounds[0]) + float(bounds[1])) * 0.5,
        (float(bounds[2]) + float(bounds[3])) * 0.5,
        (float(bounds[4]) + float(bounds[5])) * 0.5,
    )
    cx, cy, cz = center
    for mesh in meshes:
        translated: list[tuple[float, float, float]] = []
        for x, y, z in getattr(mesh, "vertices", []) or []:
            translated.append((float(x) - cx, float(y) - cy, float(z) - cz))
        try:
            mesh.vertices = translated
        except Exception:
            pass
    return meshes, center


class SelectionContextActionsController:
    """Actions exposed by the viewport selection context menu.

    The class is UI-neutral on purpose: the Qt menu layer only builds the menu and
    delegates actions here. New context-menu actions should be added here first so
    they can be unit-tested without synthesizing Qt mouse events.
    """

    def __init__(self, owner: Any) -> None:
        self.owner = owner

    @classmethod
    def create(cls, owner: Any) -> "SelectionContextActionsController":
        return cls(owner)

    def selected_indices(self) -> list[int]:
        return _selected_indices(self.owner)

    def can_open_selection_in_new_scene(self) -> bool:
        return bool(self.selected_indices())

    def open_selection_in_new_scene(self, indices: Iterable[int] | None = None) -> OpenSelectionInSceneResult | None:
        owner = self.owner
        source_meshes = list(owner.current_meshes()) if callable(getattr(owner, "current_meshes", None)) else list(getattr(getattr(owner, "mesh_store", None), "meshes", []) or [])
        selected = _selected_indices(owner, indices)
        if not selected:
            return None
        copied: list[WorkMesh] = [copy.deepcopy(source_meshes[int(i)]) for i in selected]
        copied, center = _translate_meshes_to_origin(copied)
        reset_mesh_ids(copied)
        project = ensure_project_store(owner)
        source_scene = getattr(project, "active_scene", None)
        if len(copied) == 1:
            base_name = str(getattr(copied[0], "name", "Selection") or "Selection")
        else:
            base_name = f"{len(copied)} selected parts"
        scene = project.create_scene(
            f"{base_name} isolated",
            meshes=copied,
            make_active=True,
            mark_dirty=True,
            fresh_mesh_ids=False,
        )
        try:
            scene.record_modification(
                "Opened selection in new scene",
                "scene_generated",
                capture_snapshot=True,
                metadata={
                    "source_scene_id": getattr(source_scene, "scene_id", None),
                    "source_scene_name": getattr(source_scene, "name", None),
                    "source_indices": tuple(selected),
                    "center_offset": tuple(center),
                },
            )
        except Exception:
            pass
        sync_window_to_active_scene(owner)
        try:
            owner.selected_indices = list(range(len(copied)))
            owner.active_index = len(copied) - 1 if copied else None
        except Exception:
            pass
        try:
            owner.rebuild_scene(keep_camera=False)
        except TypeError:
            owner.rebuild_scene()
        except Exception:
            pass
        for method_name in ("update_preview_state", "_sync_history_buttons", "sync_scene_tabs", "update_project_title", "update_inspector", "update_joint_info"):
            method = getattr(owner, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    pass
        try:
            mark_project_dirty(owner)
        except Exception:
            pass
        try:
            owner.ui_log(f"[SELECTION_CONTEXT] Opened {len(copied)} selected mesh(es) in new scene '{scene.name}' centered at origin")
        except Exception:
            pass
        return OpenSelectionInSceneResult(scene.scene_id, scene.name, len(copied), center)


__all__ = ["OpenSelectionInSceneResult", "SelectionContextActionsController"]

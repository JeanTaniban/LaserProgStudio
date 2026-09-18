# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from .project_store import ProjectStore


def ensure_project_store(owner: Any) -> ProjectStore:
    project = getattr(owner, "project_store", None)
    if project is None:
        project = ProjectStore.new_empty(scene_name="main")
        owner.project_store = project
    if getattr(owner, "mesh_store", None) is None:
        owner.mesh_store = project.active_model_store
    return project


def sync_window_to_active_scene(owner: Any) -> None:
    project = ensure_project_store(owner)
    owner.mesh_store = project.active_model_store
    try:
        owner.scene_modification_history = project.active_scene.history
    except Exception:
        owner.scene_modification_history = []


def reset_project(owner: Any, *, scene_name: str = "main") -> ProjectStore:
    project = ProjectStore.new_empty(scene_name=scene_name)
    owner.project_store = project
    sync_window_to_active_scene(owner)
    return project


def replace_active_model_store(owner: Any, model_store: Any, *, scene_name: str | None = None, mark_dirty: bool = True) -> None:
    project = ensure_project_store(owner)
    scene = project.active_scene
    scene.model_store = model_store
    if scene_name:
        scene.name = str(scene_name)
    if mark_dirty:
        project.mark_dirty()
    sync_window_to_active_scene(owner)


def mark_project_dirty(owner: Any) -> None:
    import time

    project = ensure_project_store(owner)
    was_dirty = bool(getattr(project, "dirty", False))
    now = time.monotonic()
    project.mark_dirty()
    try:
        owner._last_project_activity_monotonic = now
        if not was_dirty or getattr(owner, "_project_dirty_since_monotonic", None) is None:
            owner._project_dirty_since_monotonic = now
    except Exception:
        pass
    try:
        owner.update_project_title()
    except Exception:
        pass
    try:
        owner.sync_scene_tabs()
    except Exception:
        pass

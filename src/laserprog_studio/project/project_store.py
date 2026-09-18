# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from laserprog_studio.domain.work_model import WorkMesh, reset_mesh_ids

from .ids import make_project_id
from .scene_document import SceneDocument


@dataclass
class ProjectStore:
    """In-memory project document with multiple scenes.

    This is deliberately UI-neutral.  The Qt window can keep using the active
    scene's ``ModelStore`` as ``self.mesh_store`` until all controllers are
    migrated.
    """

    project_id: str = field(default_factory=make_project_id)
    scenes: "OrderedDict[str, SceneDocument]" = field(default_factory=OrderedDict)
    active_scene_id: str | None = None
    project_path: Path | None = None
    dirty: bool = False

    @classmethod
    def new_empty(cls, *, scene_name: str = "main") -> "ProjectStore":
        project = cls()
        project.create_scene(scene_name, make_active=True, mark_dirty=False)
        return project

    @property
    def active_scene(self) -> SceneDocument:
        if self.active_scene_id is None or self.active_scene_id not in self.scenes:
            if not self.scenes:
                self.create_scene("main", make_active=True, mark_dirty=False)
            else:
                self.active_scene_id = next(iter(self.scenes.keys()))
        return self.scenes[str(self.active_scene_id)]

    @property
    def active_model_store(self):
        return self.active_scene.model_store

    def unique_scene_name(self, base: str) -> str:
        """Return a project-unique scene display name."""
        candidate = str(base or "Scene").strip() or "Scene"
        existing = {str(scene.name) for scene in self.scenes.values()}
        if candidate not in existing:
            return candidate
        stem = candidate
        counter = 1
        while True:
            numbered = f"{stem} {counter:02d}"
            if numbered not in existing:
                return numbered
            counter += 1

    def create_scene(
        self,
        name: str,
        *,
        meshes: Iterable[WorkMesh] | None = None,
        source_path: Path | None = None,
        make_active: bool = True,
        mark_dirty: bool = True,
        fresh_mesh_ids: bool = False,
    ) -> SceneDocument:
        scene_name = self.unique_scene_name(str(name or "Scene"))
        if meshes is None:
            scene = SceneDocument(name=scene_name)
        else:
            scene = SceneDocument.from_meshes(scene_name, meshes, source_path=source_path, fresh_mesh_ids=fresh_mesh_ids)
        self.scenes[scene.scene_id] = scene
        if make_active or self.active_scene_id is None:
            self.active_scene_id = scene.scene_id
        if mark_dirty:
            self.mark_dirty(scene.scene_id)
        return scene

    def switch_scene(self, scene_id: str) -> SceneDocument:
        sid = str(scene_id)
        if sid not in self.scenes:
            raise KeyError(f"Unknown scene id: {sid}")
        self.active_scene_id = sid
        return self.scenes[sid]

    def rename_scene(self, scene_id: str, name: str) -> None:
        scene = self.scenes[str(scene_id)]
        new_name = str(name or "").strip()
        if new_name and scene.name != new_name:
            scene.name = new_name
            self.mark_dirty()

    def scene_order(self) -> list[str]:
        """Return scene identifiers in their current display order."""
        return list(self.scenes.keys())

    def move_scene_to_index(self, scene_id: str, index: int) -> None:
        """Move an existing scene to an arbitrary display index.

        The active scene is intentionally left unchanged: this method only
        edits tab order/project metadata.  The requested index is clamped after
        the source scene is removed, so callers can safely pass 0, len(scenes),
        or values computed from a live drag/drop target.
        """
        sid = str(scene_id)
        if sid not in self.scenes:
            raise KeyError(f"Unknown scene id: {sid}")
        old_order = list(self.scenes.keys())
        scene = self.scenes.pop(sid)
        remaining_items = list(self.scenes.items())
        try:
            target_index = int(index)
        except Exception:
            target_index = len(remaining_items)
        target_index = max(0, min(target_index, len(remaining_items)))
        new_order: "OrderedDict[str, SceneDocument]" = OrderedDict()
        inserted = False
        for current_index, (current_id, current_scene) in enumerate(remaining_items):
            if current_index == target_index:
                new_order[sid] = scene
                inserted = True
            new_order[current_id] = current_scene
        if not inserted:
            new_order[sid] = scene
        if list(new_order.keys()) != old_order:
            self.scenes = new_order
            self.dirty = True

    def move_scene_before(self, scene_id: str, before_scene_id: str | None) -> None:
        """Move an existing scene before another scene in display order."""
        sid = str(scene_id)
        before_sid = str(before_scene_id) if before_scene_id else None
        if sid not in self.scenes:
            raise KeyError(f"Unknown scene id: {sid}")
        if before_sid == sid:
            return
        order = list(self.scenes.keys())
        if before_sid is None or before_sid not in self.scenes:
            self.move_scene_to_index(sid, len(order))
            return
        target_index = order.index(before_sid)
        if order.index(sid) < target_index:
            target_index -= 1
        self.move_scene_to_index(sid, target_index)

    def remove_scene(self, scene_id: str) -> SceneDocument:
        sid = str(scene_id)
        if sid not in self.scenes:
            raise KeyError(f"Unknown scene id: {sid}")
        if len(self.scenes) <= 1:
            raise ValueError("Cannot remove the last scene from a project")
        removed = self.scenes.pop(sid)
        if self.active_scene_id == sid:
            self.active_scene_id = next(iter(self.scenes.keys()))
        # Removing a tab changes the project document, not the geometry of the
        # newly active scene; do not mark unrelated scenes as dirty.
        self.dirty = True
        return removed

    def create_scene_from_snapshot(
        self,
        source_scene_id: str,
        snapshot_id: str,
        *,
        name: str | None = None,
        make_active: bool = True,
    ) -> SceneDocument:
        source = self.scenes[str(source_scene_id)]
        snapshot = source.snapshot_meshes(snapshot_id)
        if snapshot is None:
            raise KeyError(f"Unknown snapshot id: {snapshot_id}")
        meshes, source_path = snapshot
        # Restored scenes are intentionally independent copies.  They preserve
        # geometry/materials but receive fresh mesh identities so future copy,
        # paste and scene history operations cannot confuse source/restored parts.
        reset_mesh_ids(meshes)
        scene_name = name or f"{source.name} - restored"
        scene = self.create_scene(scene_name, meshes=meshes, source_path=source_path, make_active=make_active, fresh_mesh_ids=False)
        scene.record_modification(
            f"Restored from scene '{source.name}' history",
            "restore",
            capture_snapshot=True,
            metadata={"source_scene_id": source.scene_id, "source_snapshot_id": snapshot_id},
        )
        return scene

    def create_scene_from_scene(
        self,
        source_scene_id: str,
        *,
        name: str | None = None,
        make_active: bool = True,
        fresh_mesh_ids: bool = True,
    ) -> SceneDocument:
        source = self.scenes[str(source_scene_id)]
        meshes, source_path = source.snapshot()
        scene_name = name or f"{source.name} copy"
        return self.create_scene(
            scene_name,
            meshes=copy.deepcopy(meshes),
            source_path=source_path,
            make_active=make_active,
            fresh_mesh_ids=fresh_mesh_ids,
        )

    def mark_dirty(self, scene_id: str | None = None) -> None:
        self.dirty = True
        sid = str(scene_id or self.active_scene_id or "")
        scene = self.scenes.get(sid) if sid else None
        if scene is not None:
            try:
                scene.dirty = True
            except Exception:
                pass

    def mark_clean(self) -> None:
        self.dirty = False
        for scene in self.scenes.values():
            try:
                scene.dirty = False
            except Exception:
                pass

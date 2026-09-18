# -*- coding: utf-8 -*-
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from laserprog_studio.domain.work_model import ModelStore, WorkMesh, ensure_mesh_ids, reset_mesh_ids

from .history import SceneModificationHistoryEntry, is_semantic_operation
from .ids import make_scene_id, make_snapshot_id

SceneSnapshot = tuple[list[WorkMesh], Path | None]


@dataclass
class SceneDocument:
    """Application-level scene wrapper around the ModelStore.

    The existing application still talks to ``ModelStore``.  This document is the
    migration seam that gives every scene its own store, semantic history and
    restorable snapshots without rewriting every controller at once.
    """

    name: str = "main"
    model_store: ModelStore = field(default_factory=ModelStore)
    scene_id: str = field(default_factory=make_scene_id)
    history: list[SceneModificationHistoryEntry] = field(default_factory=list)
    snapshots: dict[str, SceneSnapshot] = field(default_factory=dict)
    created_at: str | None = None
    modified_at: str | None = None
    history_limit: int = 50
    dirty: bool = False

    def __post_init__(self) -> None:
        self.ensure_mesh_ids()

    @property
    def meshes(self) -> list[WorkMesh]:
        return self.model_store.meshes

    def ensure_mesh_ids(self) -> None:
        ensure_mesh_ids(getattr(self.model_store, "committed_meshes", []) or [])
        preview = getattr(self.model_store, "preview_meshes", None)
        if preview is not None:
            ensure_mesh_ids(preview)

    def snapshot(self) -> SceneSnapshot:
        meshes, source_path = self.model_store.snapshot()
        ensure_mesh_ids(meshes)
        return meshes, source_path

    def store_snapshot(self, snapshot_id: str | None = None) -> str:
        sid = snapshot_id or make_snapshot_id()
        meshes, source_path = self.snapshot()
        self.snapshots[sid] = (copy.deepcopy(meshes), source_path)
        return sid

    def record_modification(
        self,
        description: str,
        operation_type: str,
        *,
        snapshot_id: str | None = None,
        capture_snapshot: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> SceneModificationHistoryEntry | None:
        if not is_semantic_operation(operation_type):
            return None
        sid = snapshot_id
        if capture_snapshot:
            sid = self.store_snapshot(snapshot_id)
        entry = SceneModificationHistoryEntry.create(
            description,
            operation_type,
            snapshot_id=sid,
            metadata=metadata,
        )
        self.history.append(entry)
        self.prune_history()
        return entry

    def prune_history(self) -> None:
        """Keep the visible, restorable history bounded per scene."""
        limit = int(getattr(self, "history_limit", 50) or 0)
        if limit > 0 and len(self.history) > limit:
            self.history = self.history[-limit:]
        referenced = {str(entry.snapshot_id) for entry in self.history if getattr(entry, "snapshot_id", None)}
        for snapshot_id in list(self.snapshots.keys()):
            if str(snapshot_id) not in referenced:
                self.snapshots.pop(snapshot_id, None)

    def snapshot_meshes(self, snapshot_id: str) -> SceneSnapshot | None:
        snapshot = self.snapshots.get(str(snapshot_id))
        if snapshot is None:
            return None
        meshes, source_path = snapshot
        return copy.deepcopy(meshes), source_path

    def clone_as_scene(self, *, name: str, fresh_mesh_ids: bool = False) -> "SceneDocument":
        meshes, source_path = self.snapshot()
        if fresh_mesh_ids:
            reset_mesh_ids(meshes)
        store = ModelStore()
        store.set_meshes(meshes, source_path=source_path)
        cloned = SceneDocument(name=name, model_store=store)
        cloned.history = copy.deepcopy(self.history)
        cloned.snapshots = copy.deepcopy(self.snapshots)
        return cloned

    @classmethod
    def from_meshes(
        cls,
        name: str,
        meshes: Iterable[WorkMesh],
        *,
        source_path: Path | None = None,
        fresh_mesh_ids: bool = False,
    ) -> "SceneDocument":
        scene_meshes = copy.deepcopy(list(meshes))
        if fresh_mesh_ids:
            reset_mesh_ids(scene_meshes)
        else:
            ensure_mesh_ids(scene_meshes)
        store = ModelStore()
        store.set_meshes(scene_meshes, source_path=source_path)
        return cls(name=name, model_store=store)

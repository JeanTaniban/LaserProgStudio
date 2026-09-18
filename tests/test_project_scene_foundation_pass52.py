# -*- coding: utf-8 -*-
from __future__ import annotations

import _path_setup  # noqa: F401

from laserprog_studio.domain.work_model import ModelStore, WorkMesh, ensure_mesh_id
from laserprog_studio.project import AutosavePolicy, ProjectStore, is_semantic_operation


def triangle(name: str = "part") -> WorkMesh:
    return WorkMesh(name, [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])


def test_workmesh_has_stable_id_but_equality_ignores_identity() -> None:
    a = triangle()
    b = triangle()
    assert a.mesh_id
    assert b.mesh_id
    assert a.mesh_id != b.mesh_id
    assert a == b  # geometry/content equality must keep undo comparisons stable.


def test_model_store_assigns_missing_mesh_ids() -> None:
    mesh = triangle()
    mesh.mesh_id = ""
    store = ModelStore()
    store.set_meshes([mesh])
    assert store.meshes[0].mesh_id.startswith("mesh_")
    assert ensure_mesh_id(store.meshes[0]) == store.meshes[0].mesh_id


def test_project_store_starts_with_main_scene_and_active_model_store() -> None:
    project = ProjectStore.new_empty()
    assert project.active_scene.name == "main"
    assert project.active_model_store is project.active_scene.model_store
    assert list(scene.name for scene in project.scenes.values()) == ["main"]


def test_scene_history_records_only_semantic_operations_and_stores_snapshot() -> None:
    project = ProjectStore.new_empty()
    scene = project.active_scene
    scene.model_store.set_meshes([triangle()])
    skipped = scene.record_modification("Move part", "transform")
    assert skipped is None
    entry = scene.record_modification("Boolean subtract applied", "boolean")
    assert entry is not None
    assert entry.snapshot_id in scene.snapshots
    assert len(scene.history) == 1
    assert is_semantic_operation("boolean") is True
    assert is_semantic_operation("translate") is False


def test_restore_history_snapshot_creates_independent_scene_with_fresh_mesh_ids() -> None:
    project = ProjectStore.new_empty()
    source = project.active_scene
    source.model_store.set_meshes([triangle("source")])
    source_id = source.meshes[0].mesh_id
    entry = source.record_modification("Import source", "import")
    assert entry is not None and entry.snapshot_id

    restored = project.create_scene_from_snapshot(source.scene_id, entry.snapshot_id, name="restored")
    assert restored.name == "restored"
    assert project.active_scene is restored
    assert restored.meshes[0].name == "source"
    assert restored.meshes[0].mesh_id != source_id
    assert restored.history[-1].operation_type == "restore"


def test_autosave_policy_has_soft_and_forced_paths() -> None:
    policy = AutosavePolicy(soft_interval_s=120.0, idle_required_s=10.0, forced_interval_s=300.0)
    assert policy.due_kind(dirty=False, now_s=500, last_autosave_s=0, last_activity_s=0) is None
    assert policy.due_kind(dirty=True, now_s=130, last_autosave_s=0, last_activity_s=125) is None
    assert policy.due_kind(dirty=True, now_s=130, last_autosave_s=0, last_activity_s=110) == "soft"
    assert policy.due_kind(dirty=True, now_s=301, last_autosave_s=0, last_activity_s=300) == "forced"
    assert policy.due_kind(dirty=True, now_s=301, last_autosave_s=0, last_activity_s=300, critical_operation_active=True) is None


def test_scene_visible_history_prunes_old_restore_snapshots() -> None:
    from laserprog_studio.project import ProjectStore

    project = ProjectStore.new_empty(scene_name="main")
    scene = project.active_scene
    scene.history_limit = 2
    scene.model_store.set_meshes([triangle("base")])

    first = scene.record_modification("First", "tool_apply", capture_snapshot=True)
    second = scene.record_modification("Second", "tool_apply", capture_snapshot=True)
    third = scene.record_modification("Third", "tool_apply", capture_snapshot=True)

    assert [entry.description for entry in scene.history] == ["Second", "Third"]
    assert first is not None and first.snapshot_id not in scene.snapshots
    assert second is not None and second.snapshot_id in scene.snapshots
    assert third is not None and third.snapshot_id in scene.snapshots

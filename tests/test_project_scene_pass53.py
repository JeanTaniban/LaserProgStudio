# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
from pathlib import Path

import _path_setup  # noqa: F401

try:
    from laserprog_studio.domain.work_model import WorkMesh
except Exception:  # pragma: no cover
    from laserprog_studio.domain.work_model import WorkMesh

from laserprog_studio.io.project_file import load_project, save_project_atomic
from laserprog_studio.project import ProjectStore
from laserprog_studio.project.autosave import AutosavePolicy


def _mesh(name: str = "part") -> WorkMesh:
    return WorkMesh(
        name=name,
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        triangles=[(0, 1, 2)],
    )


def test_restore_history_snapshot_creates_independent_scene() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    scene = project.active_scene
    scene.model_store.set_meshes([_mesh("original")])
    entry = scene.record_modification("Boolean subtract", "boolean", capture_snapshot=True)
    assert entry is not None and entry.snapshot_id

    restored = project.create_scene_from_snapshot(scene.scene_id, entry.snapshot_id, make_active=True)

    assert restored.scene_id != scene.scene_id
    assert restored.name.startswith("main - restored")
    assert project.active_scene_id == restored.scene_id
    assert restored.meshes[0].name == "original"
    assert restored.meshes[0].mesh_id != scene.meshes[0].mesh_id


def test_project_scene_names_are_unique() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    a = project.create_scene("main", meshes=[_mesh("a")])
    b = project.create_scene("main", meshes=[_mesh("b")])
    names = [scene.name for scene in project.scenes.values()]

    assert names == ["main", "main 01", "main 02"]
    assert a.name != b.name


def test_recovery_save_does_not_clear_dirty_or_change_project_path() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    project.active_scene.model_store.set_meshes([_mesh()])
    project.project_path = Path("/tmp/user_project.lpsproj")
    project.mark_dirty()

    with tempfile.TemporaryDirectory() as tmp:
        recovery = Path(tmp) / "user_project.autosave.lpsproj"
        save_project_atomic(project, recovery, mark_clean=False)
        loaded = load_project(recovery)

    assert project.dirty is True
    assert project.project_path == Path("/tmp/user_project.lpsproj")
    assert len(loaded.scenes) == 1
    assert loaded.active_scene.meshes[0].name == "part"


def test_autosave_policy_has_soft_and_forced_modes() -> None:
    policy = AutosavePolicy(soft_interval_s=120.0, idle_required_s=10.0, forced_interval_s=300.0)

    assert policy.due_kind(dirty=True, now_s=121.0, last_autosave_s=0.0, last_activity_s=110.0) == "soft"
    assert policy.due_kind(dirty=True, now_s=301.0, last_autosave_s=0.0, last_activity_s=300.0) == "forced"
    assert policy.due_kind(dirty=True, now_s=301.0, last_autosave_s=0.0, last_activity_s=300.0, critical_operation_active=True) is None
    assert policy.due_kind(dirty=False, now_s=1000.0, last_autosave_s=0.0, last_activity_s=0.0) is None


def test_first_autosave_uses_dirty_since_when_no_previous_autosave(tmp_path, monkeypatch) -> None:
    import time
    from types import SimpleNamespace

    from laserprog_studio.application.project_controller import ProjectController

    project = ProjectStore.new_empty(scene_name="main")
    project.active_scene.model_store.set_meshes([_mesh("autosave")])
    project.project_path = tmp_path / "user_project.lpsproj"
    project.mark_dirty()

    owner = SimpleNamespace(
        project_store=project,
        mesh_store=project.active_model_store,
        autosave_policy=AutosavePolicy(soft_interval_s=120.0, idle_required_s=10.0, forced_interval_s=300.0),
        autosave_in_progress=False,
        autosave_pending=False,
        _last_autosave_monotonic=None,
        _project_dirty_since_monotonic=100.0,
        _last_project_activity_monotonic=100.0,
        TOOL_NONE="none",
        active_tool="none",
        has_preview=lambda: False,
        ui_log=lambda message: None,
    )
    controller = ProjectController(SimpleNamespace(owner=owner))
    monkeypatch.setattr(time, "monotonic", lambda: 221.0)

    assert controller.autosave_tick() is True
    assert owner._last_autosave_monotonic == 221.0
    assert owner.autosave_pending is False
    assert (tmp_path / "user_project.autosave.lpsproj").exists()
    assert project.dirty is True


def test_recovery_fast_save_loads_and_keeps_project_dirty(tmp_path) -> None:
    project = ProjectStore.new_empty(scene_name="main")
    project.active_scene.model_store.set_meshes([_mesh("fast-autosave")])
    project.project_path = tmp_path / "user_project.lpsproj"
    project.mark_dirty()

    recovery = tmp_path / "user_project.autosave.lpsproj"
    save_project_atomic(project, recovery, mark_clean=False, autosave_fast=True)
    loaded = load_project(recovery)

    assert recovery.exists()
    assert project.dirty is True
    assert project.project_path == tmp_path / "user_project.lpsproj"
    assert loaded.active_scene.meshes[0].name == "fast-autosave"


def test_autosave_tick_does_not_start_second_worker_when_in_progress(tmp_path, monkeypatch) -> None:
    import time
    from types import SimpleNamespace

    from laserprog_studio.application.project_controller import ProjectController

    project = ProjectStore.new_empty(scene_name="main")
    project.active_scene.model_store.set_meshes([_mesh("busy")])
    project.project_path = tmp_path / "busy_project.lpsproj"
    project.mark_dirty()

    owner = SimpleNamespace(
        project_store=project,
        mesh_store=project.active_model_store,
        autosave_policy=AutosavePolicy(soft_interval_s=1.0, idle_required_s=0.0, forced_interval_s=2.0),
        autosave_in_progress=True,
        autosave_pending=False,
        _last_autosave_monotonic=0.0,
        _project_dirty_since_monotonic=0.0,
        _last_project_activity_monotonic=0.0,
        TOOL_NONE="none",
        active_tool="none",
        has_preview=lambda: False,
        ui_log=lambda message: None,
    )
    controller = ProjectController(SimpleNamespace(owner=owner))
    monkeypatch.setattr(time, "monotonic", lambda: 3.0)

    assert controller.autosave_tick() is False
    assert owner.autosave_pending is True
    assert not (tmp_path / "busy_project.autosave.lpsproj").exists()

# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import pytest

import _path_setup  # noqa: F401
from laserprog_studio.io import project_file
from laserprog_studio.project import ProjectStore


def _dirty_project(*, project_path: Path | None = None) -> ProjectStore:
    project = ProjectStore.new_empty()
    project.project_path = project_path
    project.mark_dirty()
    return project


def test_atomic_save_failure_preserves_document_state_and_existing_target(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "project.lpsproj"
    target.write_bytes(b"previous-valid-project")
    previous_path = tmp_path / "previous.lpsproj"
    project = _dirty_project(project_path=previous_path)

    def fail_replace(_src, _dst) -> None:
        raise PermissionError("simulated replace failure")

    monkeypatch.setattr(project_file.os, "replace", fail_replace)

    with pytest.raises(PermissionError, match="simulated replace failure"):
        project_file.save_project_atomic(project, target, mark_clean=True)

    assert target.read_bytes() == b"previous-valid-project"
    assert project.project_path == previous_path
    assert project.dirty is True
    assert project.active_scene.dirty is True
    assert not list(tmp_path.glob(f".{target.name}.*.tmp"))


def test_atomic_save_success_marks_clean_only_after_replace(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "project.lpsproj"
    previous_path = tmp_path / "previous.lpsproj"
    project = _dirty_project(project_path=previous_path)
    observed: dict[str, object] = {}
    real_replace = project_file.os.replace

    def inspect_then_replace(src, dst) -> None:
        observed["project_path_during_replace"] = project.project_path
        observed["dirty_during_replace"] = project.dirty
        observed["scene_dirty_during_replace"] = project.active_scene.dirty
        real_replace(src, dst)

    monkeypatch.setattr(project_file.os, "replace", inspect_then_replace)

    result = project_file.save_project_atomic(project, target, mark_clean=True)

    assert result == target
    assert target.exists()
    assert observed == {
        "project_path_during_replace": previous_path,
        "dirty_during_replace": True,
        "scene_dirty_during_replace": True,
    }
    assert project.project_path == target
    assert project.dirty is False
    assert project.active_scene.dirty is False


def test_atomic_recovery_save_never_changes_document_state(tmp_path: Path) -> None:
    target = tmp_path / "recovery.lpsproj"
    previous_path = tmp_path / "manual-project.lpsproj"
    project = _dirty_project(project_path=previous_path)

    project_file.save_project_atomic(project, target, mark_clean=False, autosave_fast=True)

    assert target.exists()
    assert project.project_path == previous_path
    assert project.dirty is True
    assert project.active_scene.dirty is True

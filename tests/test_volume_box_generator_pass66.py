# -*- coding: utf-8 -*-
from __future__ import annotations

import pytest
import _path_setup  # noqa: F401

from laserprog_studio.application.box_live_metrics import make_box_preview_meshes
from laserprog_studio.geometry_ops.cavity_volume import measure_box_generator_selection
from laserprog_studio.io.project_file import load_project, save_project_atomic
from laserprog_studio.project import ProjectStore


def test_pass66_vol_uses_box_generator_metadata_for_selected_box_boards() -> None:
    _boards, meshes, metrics = make_box_preview_meshes(120.0, 80.0, 60.0, 3.0, "front_back_wrap", "top_bottom_wrap", "top_bottom_wrap")

    report = measure_box_generator_selection(meshes, [0, 1, 2, 3, 4, 5])

    assert report is not None
    assert report.mesh_name == "Generated BOX (6 parts)"
    assert report.cavity_count == 1
    assert report.cavity_volume_liters == pytest.approx(metrics.inner_volume_l)
    assert report.outer_volume_liters == pytest.approx(metrics.outer_volume_l)
    assert report.warning is None


def test_pass66_vol_warns_for_partial_box_generator_selection() -> None:
    _boards, meshes, _metrics = make_box_preview_meshes(120.0, 80.0, 60.0, 3.0, "front_back_wrap", "top_bottom_wrap", "top_bottom_wrap")

    report = measure_box_generator_selection(meshes, [0, 1, 2])

    assert report is not None
    assert report.cavity_count == 0
    assert "Select every panel" in str(report.warning)


def test_pass66_project_save_load_preserves_box_generator_metadata(tmp_path) -> None:
    _boards, meshes, metrics = make_box_preview_meshes(120.0, 80.0, 60.0, 3.0, "front_back_wrap", "top_bottom_wrap", "top_bottom_wrap")
    project = ProjectStore.new_empty(scene_name="main")
    project.active_scene.model_store.set_meshes(meshes)
    path = tmp_path / "box_project.lpsproj"

    save_project_atomic(project, path)
    loaded = load_project(path)
    loaded_meshes = loaded.active_scene.model_store.meshes
    report = measure_box_generator_selection(loaded_meshes, [0, 1, 2, 3, 4, 5])

    assert report is not None
    assert report.cavity_volume_liters == pytest.approx(metrics.inner_volume_l)

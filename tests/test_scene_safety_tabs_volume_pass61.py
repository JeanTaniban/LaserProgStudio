# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401
from _scene_tabs_source import read_scene_tabs_source
import pytest

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project import ProjectStore
from laserprog_studio.geometry_ops.cavity_volume import combine_meshes_for_cavity_measurement, measure_cavity_volume
from laserprog_studio.tooling.ids import TOOL_VOLUME_MEASURE
from laserprog_studio.tooling.registry import get_tool_spec


ROOT = Path(__file__).resolve().parents[1]


def _cube_shell(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float):
    vertices = [
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    ]
    triangles = [
        (0, 2, 1), (0, 3, 2),
        (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4),
        (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6),
        (3, 0, 4), (3, 4, 7),
    ]
    return vertices, triangles


def test_project_tracks_scene_dirty_separately_and_save_cleans_all() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    clean_scene_id = project.active_scene.scene_id
    scene = project.create_scene("work", meshes=[WorkMesh("p", [], [])], make_active=True, mark_dirty=True)

    assert project.dirty is True
    assert scene.dirty is True
    assert project.scenes[clean_scene_id].dirty is False

    project.mark_clean()

    assert project.dirty is False
    assert all(not scene.dirty for scene in project.scenes.values())


def test_project_can_reorder_scene_tabs_without_changing_active_scene() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    first = project.active_scene.scene_id
    second = project.create_scene("second", make_active=True).scene_id
    third = project.create_scene("third", make_active=True).scene_id
    project.switch_scene(second)
    project.mark_clean()

    project.move_scene_before(third, first)

    assert list(project.scenes.keys()) == [third, first, second]
    assert project.active_scene_id == second
    assert project.dirty is True


def test_project_can_move_scene_to_any_tab_index() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    first = project.active_scene.scene_id
    second = project.create_scene("second", make_active=True).scene_id
    third = project.create_scene("third", make_active=True).scene_id
    fourth = project.create_scene("fourth", make_active=True).scene_id
    project.switch_scene(third)
    project.mark_clean()

    project.move_scene_to_index(first, 2)
    assert list(project.scenes.keys()) == [second, third, first, fourth]
    assert project.active_scene_id == third

    project.move_scene_to_index(fourth, 0)
    assert list(project.scenes.keys()) == [fourth, second, third, first]

    project.move_scene_to_index(second, 99)
    assert list(project.scenes.keys()) == [fourth, third, first, second]
    assert project.dirty is True


def test_scene_tabs_support_drag_reorder_and_unsaved_close_confirmation_static() -> None:
    source = read_scene_tabs_source(ROOT)

    assert "class DraggableSceneTabFrame" in source
    assert "QDrag" in source
    assert "application/x-laserprog-scene-id" in source
    assert "def move_scene_tab_before" in source
    assert "def move_scene_tab_to_index" in source
    assert "scene_tab_insert_index_for_target" in source
    assert "SceneTabsEndDropZone" in source
    assert "project.move_scene_to_index" in source
    assert "confirm_close_scene" in source


def test_close_event_checks_unsaved_project_static() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "controllers" / "camera.py").read_text(encoding="utf-8")

    assert "confirm_discard_if_dirty(\"Quit\")" in source
    assert "event.ignore()" in source
    assert "Quit cancelled: unsaved project" in source


def test_project_dirty_prompt_offers_save_discard_cancel_static() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "application" / "project_controller.py").read_text(encoding="utf-8")

    assert "QMessageBox.StandardButton.Save" in source
    assert "QMessageBox.StandardButton.Discard" in source
    assert "QMessageBox.StandardButton.Cancel" in source
    assert "def confirm_close_scene" in source
    assert "Delete unsaved scene" in source


def test_volume_tool_accepts_multi_selection_and_measures_combined_shells() -> None:
    spec = get_tool_spec(TOOL_VOLUME_MEASURE)
    assert spec is not None
    assert spec.selection_policy == "multi"

    outer_v, outer_t = _cube_shell(0, 100, 0, 100, 0, 100)
    inner_v, inner_t = _cube_shell(25, 75, 25, 75, 25, 75)
    outer = WorkMesh("outer shell", outer_v, outer_t)
    inner = WorkMesh("inner shell", inner_v, inner_t)

    combined = combine_meshes_for_cavity_measurement([outer, inner])
    report = measure_cavity_volume(combined)

    assert report.closed_shell_count == 2
    assert report.cavity_count == 1
    assert report.cavity_volume_liters == pytest.approx(0.125)


def test_lay_apply_rechecks_default_outline_roles_static() -> None:
    source = (ROOT / "src" / "laserprog_studio" / "application" / "preview_controller.py").read_text(encoding="utf-8")

    assert 'str(operation_type) == "layflat"' in source
    assert "apply_default_outline_to_unassigned(preview_meshes)" in source


def _cube_panel_meshes(size: float = 100.0) -> list[WorkMesh]:
    # Six independent two-triangle panels.  They use duplicate vertices on every
    # shared edge, just like imported/created parts often do before a boolean
    # union.  VOL must weld these coincident edges for multi-selection analysis.
    v, t = _cube_shell(0, size, 0, size, 0, size)
    faces = [
        ("bottom", (0, 1)),
        ("top", (2, 3)),
        ("front", (4, 5)),
        ("right", (6, 7)),
        ("back", (8, 9)),
        ("left", (10, 11)),
    ]
    parts: list[WorkMesh] = []
    for name, tri_ids in faces:
        used: list[int] = []
        for tri_id in tri_ids:
            for idx in t[tri_id]:
                if idx not in used:
                    used.append(idx)
        remap = {idx: local for local, idx in enumerate(used)}
        vertices = [v[idx] for idx in used]
        triangles = [tuple(remap[idx] for idx in t[tri_id]) for tri_id in tri_ids]
        parts.append(WorkMesh(name, vertices, triangles))
    return parts


def test_volume_multi_selection_welds_panels_that_form_one_closed_volume() -> None:
    parts = _cube_panel_meshes(100.0)

    combined = combine_meshes_for_cavity_measurement(parts)
    report = measure_cavity_volume(combined, single_closed_shell_as_cavity=True)

    assert report.shell_count == 1
    assert report.closed_shell_count == 1
    assert report.cavity_count == 1
    assert report.cavity_volume_liters == pytest.approx(1.0)
    assert report.warning is None


def test_volume_tool_keeps_multi_selection_available_while_open_static() -> None:
    scene_source = (ROOT / "src" / "laserprog_studio" / "controllers" / "scene.py").read_text(encoding="utf-8")
    policy_source = (ROOT / "src" / "laserprog_studio" / "controllers" / "tool_selection_policy.py").read_text(encoding="utf-8")
    box_source = (ROOT / "src" / "laserprog_studio" / "controllers" / "selection_box.py").read_text(encoding="utf-8")
    creator_source = (ROOT / "src" / "laserprog_studio" / "tooling" / "cavity_volume_tool.py").read_text(encoding="utf-8")

    assert "def _active_tool_allows_scene_multi_selection" in policy_source
    assert "self._active_tool_allows_scene_multi_selection() and toggle" in scene_source
    assert "allows_multi = bool(self._active_tool_allows_scene_multi_selection())" in box_source
    assert "single_closed_shell_as_cavity" in creator_source
    assert "CavityVolumeCreatorTool" in creator_source

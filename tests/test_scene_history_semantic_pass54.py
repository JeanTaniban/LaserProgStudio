# -*- coding: utf-8 -*-
from __future__ import annotations

import _path_setup  # noqa: F401

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project import ProjectStore, is_semantic_operation


def mesh(name: str = "part") -> WorkMesh:
    return WorkMesh(name, [(0, 0, 0), (1, 0, 0), (0, 1, 0)], [(0, 1, 2)])


def test_scene_visible_history_accepts_scene_edit_operations_but_skips_transforms() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    scene = project.active_scene
    scene.model_store.set_meshes([mesh()])

    assert is_semantic_operation("paste") is True
    assert is_semantic_operation("duplicate") is True
    assert is_semantic_operation("delete") is True
    assert is_semantic_operation("translate") is False
    assert is_semantic_operation("rotate") is False

    assert scene.record_modification("Moved part", "translate") is None
    paste = scene.record_modification("Paste one part", "paste")
    duplicate = scene.record_modification("Duplicate one part", "duplicate")
    delete = scene.record_modification("Delete one part", "delete")

    assert [entry.operation_type for entry in scene.history] == ["paste", "duplicate", "delete"]
    for entry in (paste, duplicate, delete):
        assert entry is not None
        assert entry.snapshot_id in scene.snapshots


def test_restore_from_scene_edit_history_keeps_source_scene_unchanged() -> None:
    project = ProjectStore.new_empty(scene_name="main")
    source = project.active_scene
    source.model_store.set_meshes([mesh("before")])
    entry = source.record_modification("Paste before", "paste")
    assert entry is not None and entry.snapshot_id
    source.model_store.set_meshes([mesh("after")])

    restored = project.create_scene_from_snapshot(source.scene_id, entry.snapshot_id, name="restore check")

    assert source.meshes[0].name == "after"
    assert restored.meshes[0].name == "before"
    assert restored.scene_id != source.scene_id
    assert restored.history[-1].operation_type == "restore"

from types import SimpleNamespace

from laserprog_studio.app_context import AppContext
from laserprog_studio.application import SceneEditController
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState


class _SceneEditDummy(SimpleNamespace):
    TOOL_NONE = "none"

    def __init__(self) -> None:
        super().__init__()
        self.project_store = ProjectStore.new_empty(scene_name="main")
        self.mesh_store = self.project_store.active_model_store
        self.selection_state = SelectionState()
        self.transform_state = TransformState()
        self.tool_state = ToolState(active_tool=self.TOOL_NONE)
        self.preview_state = PreviewState()
        self.ui_layout_state = UiLayoutState()
        self.render_state = RenderState()
        self.clipboard_state = ClipboardState()
        self.scene_renderer = None
        self.active_tool = self.TOOL_NONE
        self.selected_indices = []
        self.active_index = None
        self.logs = []

    def close_active_tool(self, *args, **kwargs) -> None:
        self.active_tool = self.TOOL_NONE

    def rebuild_scene(self, keep_camera: bool = False) -> None:
        self.rebuilt = keep_camera

    def _sync_history_buttons(self) -> None:
        self.synced_history = True

    def sync_scene_tabs(self) -> None:
        self.synced_tabs = True

    def update_project_title(self) -> None:
        self.updated_title = True

    def ui_log(self, message: str) -> None:
        self.logs.append(message)


def test_new_scene_command_adds_scene_in_current_project_instead_of_resetting_project() -> None:
    owner = _SceneEditDummy()
    owner.project_store.active_scene.model_store.set_meshes([mesh("kept")])
    project_id = owner.project_store.project_id

    controller = SceneEditController(AppContext.from_window(owner))
    controller.new_scene()

    assert owner.project_store.project_id == project_id
    assert [scene.name for scene in owner.project_store.scenes.values()] == ["main", "Scene"]
    assert owner.project_store.active_scene.name == "Scene"
    assert owner.mesh_store is owner.project_store.active_scene.model_store
    assert len(next(iter(owner.project_store.scenes.values())).meshes) == 1
    assert owner.project_store.dirty is True

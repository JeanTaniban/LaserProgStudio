# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

import _path_setup  # noqa: F401

from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.app_context import AppContext
from laserprog_studio.application import ClipboardController
from laserprog_studio.project import ProjectStore
from laserprog_studio.services.geometry import bounds_from_vertices_list
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState


def mesh(name: str) -> WorkMesh:
    return WorkMesh(name, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)], [(0, 1, 2)])


class DummyWindow(SimpleNamespace):
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
        self.selected_indices: list[int] = []
        self.active_index: int | None = None
        self.active_tool = self.TOOL_NONE
        self._history_limit = 30
        self.logs: list[str] = []

    def ui_log(self, message: str) -> None:
        self.logs.append(message)

    def has_preview(self) -> bool:
        return False

    def current_meshes(self):
        return self.mesh_store.meshes

    def _selected_transform_indices(self) -> list[int]:
        return list(self.selected_indices)

    def _bounds_from_vertices_list(self, vertices):
        return bounds_from_vertices_list(vertices)

    def _camera_basis(self):
        return (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)

    def push_meshes(self, meshes, reason: str, *, semantic_operation_type: str | None = None) -> None:
        self.mesh_store.set_meshes(meshes, push_undo=True, max_undo=self._history_limit)
        if semantic_operation_type:
            self.project_store.active_scene.record_modification(reason, semantic_operation_type, capture_snapshot=True)
        self.project_store.mark_dirty()


def test_ctrl_c_ctrl_v_can_copy_meshes_between_scenes_with_fresh_ids() -> None:
    owner = DummyWindow()
    source_scene = owner.project_store.active_scene
    source_mesh = mesh("source")
    source_scene.model_store.set_meshes([source_mesh])
    owner.selected_indices = [0]
    owner.active_index = 0

    context = AppContext.from_window(owner)
    controller = ClipboardController(context)
    controller.copy_selected()

    dest_scene = owner.project_store.create_scene("destination", meshes=[], make_active=True)
    owner.mesh_store = dest_scene.model_store
    owner.selected_indices = []
    owner.active_index = None

    controller.paste_selection()

    assert len(source_scene.meshes) == 1
    assert len(dest_scene.meshes) == 1
    assert dest_scene.meshes[0].name == "source_copy"
    assert dest_scene.meshes[0].mesh_id != source_scene.meshes[0].mesh_id
    assert owner.project_store.dirty is True
    assert dest_scene.history[-1].operation_type == "paste"
    assert dest_scene.history[-1].snapshot_id in dest_scene.snapshots
    assert len(context.clipboard.meshes) == 1

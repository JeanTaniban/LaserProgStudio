# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import time

import _path_setup  # noqa: F401

from laserprog_studio.application.selection_context_actions import SelectionContextActionsController
from laserprog_studio.domain.work_model import WorkMesh
from laserprog_studio.project import ProjectStore
from laserprog_studio.state import ClipboardState, PreviewState, RenderState, SelectionState, ToolState, TransformState, UiLayoutState


def cube_mesh(name: str, offset=(0.0, 0.0, 0.0)) -> WorkMesh:
    ox, oy, oz = offset
    verts = [
        (ox + 0.0, oy + 0.0, oz + 0.0),
        (ox + 2.0, oy + 0.0, oz + 0.0),
        (ox + 2.0, oy + 2.0, oz + 0.0),
        (ox + 0.0, oy + 2.0, oz + 0.0),
        (ox + 0.0, oy + 0.0, oz + 2.0),
        (ox + 2.0, oy + 0.0, oz + 2.0),
        (ox + 2.0, oy + 2.0, oz + 2.0),
        (ox + 0.0, oy + 2.0, oz + 2.0),
    ]
    tris = [(0, 1, 2), (0, 2, 3), (4, 6, 5), (4, 7, 6)]
    return WorkMesh(name, verts, tris)


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
        self.selected_indices: list[int] = []
        self.active_index: int | None = None
        self.active_tool = self.TOOL_NONE
        self.logs: list[str] = []
        self.rebuild_calls = 0
        self.tabs_synced = 0

    def current_meshes(self):
        return self.mesh_store.meshes

    def _selected_transform_indices(self) -> list[int]:
        return list(self.selected_indices)

    def rebuild_scene(self, keep_camera: bool = False) -> None:
        self.rebuild_calls += 1

    def sync_scene_tabs(self) -> None:
        self.tabs_synced += 1

    def update_preview_state(self) -> None: pass
    def _sync_history_buttons(self) -> None: pass
    def update_project_title(self) -> None: pass
    def update_inspector(self) -> None: pass
    def update_joint_info(self) -> None: pass
    def ui_log(self, message: str) -> None: self.logs.append(message)


def test_open_selection_in_new_scene_copies_and_centers_selection() -> None:
    owner = DummyWindow()
    owner.mesh_store.set_meshes([cube_mesh("left", (10.0, 0.0, 0.0)), cube_mesh("right", (20.0, 0.0, 0.0))])
    source_ids = [mesh.mesh_id for mesh in owner.mesh_store.meshes]
    owner.selected_indices = [0, 1]
    owner.active_index = 1

    result = SelectionContextActionsController(owner).open_selection_in_new_scene()

    assert result is not None
    assert result.mesh_count == 2
    assert len(owner.project_store.scenes) == 2
    assert owner.project_store.active_scene.name.startswith("2 selected parts isolated")
    assert owner.mesh_store is owner.project_store.active_model_store
    copied = owner.mesh_store.meshes
    assert len(copied) == 2
    assert [mesh.mesh_id for mesh in copied] != source_ids
    all_vertices = [vertex for mesh in copied for vertex in mesh.vertices]
    xs = [v[0] for v in all_vertices]
    ys = [v[1] for v in all_vertices]
    zs = [v[2] for v in all_vertices]
    assert abs((min(xs) + max(xs)) * 0.5) < 1e-9
    assert abs((min(ys) + max(ys)) * 0.5) < 1e-9
    assert abs((min(zs) + max(zs)) * 0.5) < 1e-9
    assert owner.selected_indices == [0, 1]
    assert owner.active_index == 1
    assert owner.project_store.dirty is True


def test_right_click_context_menu_contract_is_short_click_only() -> None:
    source = Path("src/laserprog_studio/controllers/interaction.py").read_text(encoding="utf-8")
    menu_source = Path("src/laserprog_studio/controllers/selection_context_menu.py").read_text(encoding="utf-8")
    assert "_right_selection_context_press(qx, qy)" in source
    assert "_right_selection_context_should_delay_pan(qx, qy)" in source
    assert "_right_selection_context_should_open(qx, qy)" in source
    assert "_show_selection_context_menu(x, y)" in source
    assert "Open in new scene" in menu_source
    assert "_RIGHT_CONTEXT_MAX_MOVE_PX = 5.0" in menu_source
    assert "_RIGHT_CONTEXT_MAX_SECONDS" in menu_source
